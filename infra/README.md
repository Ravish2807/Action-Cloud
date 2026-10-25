# AWS EKS deployment

ActionCloud includes Terraform for AWS infrastructure, a Helm chart for the API and worker, and a GitHub Actions deployment workflow. The default architecture uses EKS, private Multi-AZ RDS PostgreSQL with pgvector, encrypted SQS and a dead-letter queue, ECR, Secrets Manager, IAM roles for service accounts, an Application Load Balancer, autoscaling, and Prometheus/Grafana monitoring.

**Status:** the infrastructure and deployment workflow are in the repository, but no AWS environment is provisioned automatically. Terraform creates billable resources; review its plan and regional pricing before applying it.

## What the cloud deployment adds

- Terraform provisions the VPC, EKS cluster and worker nodes, RDS, SQS/DLQ, ECR, secrets, and least-privilege IAM roles.
- Helm runs database migrations and deploys the API and queue worker with health checks, resource settings, disruption protection, and rolling upgrades.
- The API uses a CPU horizontal pod autoscaler; Cluster Autoscaler can add worker nodes when pods cannot be scheduled.
- GitHub Actions builds an immutable image, deploys it to EKS, and supports Helm rollback when a release fails.
- AWS credentials are obtained through GitHub OIDC; the workflow does not require long-lived AWS access keys in GitHub.
- Optional Route 53 and ACM settings expose the API through HTTPS. Prometheus and Grafana remain internal by default.

## Test the feature on a laptop

You can exercise the application and its AWS-compatible queue path locally without AWS credentials:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://localhost:8000/health
```

Compose starts PostgreSQL with pgvector, LocalStack's SQS emulator, the API, the migration job, and the worker. Inspect their logs with:

```powershell
docker compose logs -f api worker
```

Run the end-to-end API workflow from another PowerShell terminal after creating the Python environment and installing the project requirements:

```powershell
if (!(Test-Path .venv)) { py -3.13 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\verify_e2e.py
```

This validates the laptop stack, not EKS provisioning or AWS IAM. To see tracked benchmark tasks in the UI, follow [the dashboard live demo](../dashboard/README.md).

## Show the Streamlit dashboard from AWS

The dashboard is a separate Streamlit workload. After the API/worker release and AWS Load Balancer Controller are running, build and push its image, then enable the dashboard and restricted public ingress:

```powershell
$ecr = terraform -chdir=infra/terraform output -raw ecr_repository_url
$currentIp = (Invoke-RestMethod https://checkip.amazonaws.com).Trim()
$dashboardTag = "dashboard-demo-$(Get-Date -Format yyyyMMddHHmmss)"

docker build -f dashboard/Dockerfile -t "$ecr`:$dashboardTag" .
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ($ecr -replace '/.*$','')
docker push "$ecr`:$dashboardTag"

helm upgrade actioncloud helm/actioncloud --namespace actioncloud --reuse-values `
  --set dashboard.enabled=true `
  --set "dashboard.image.repository=$ecr" `
  --set "dashboard.image.tag=$dashboardTag" `
  --set dashboard.public.enabled=true `
  --set "dashboard.public.allowedCidrs[0]=$currentIp/32" `
  --wait --timeout 10m

kubectl get ingress actioncloud-actioncloud-dashboard -n actioncloud
```

Open the Ingress `ADDRESS` in a browser using `http://`. AWS provides a public load-balancer DNS name, not a permanent single IP. The CIDR setting limits browser access to the machine's current public IP; refresh it if that IP changes. The internet-facing load balancer has an hourly charge. Disable the dashboard ingress or destroy the AWS stack after the demonstration to stop those charges. For a public audience beyond your own IP, add HTTPS and user authentication first.

## Provision a real AWS environment

Prerequisites: an AWS account and credentials with authority to create the listed resources, Terraform 1.9+, AWS CLI, Helm 3, kubectl, and a GitHub repository with Actions enabled.

1. Create a dedicated encrypted and versioned S3 bucket for Terraform state. Copy `terraform/backend.tf.example` to `terraform/backend.tf`, set the bucket, state key, and region, and keep the file private. State contains generated credentials.
2. Copy `terraform/terraform.tfvars.example` to `terraform/terraform.tfvars`. Set `github_repository` and a restricted `cluster_public_access_cidrs` value. Add Route 53 and hostname settings only if you want a public API endpoint.
3. Initialize and inspect Terraform from `infra/terraform`:

   ```powershell
   terraform init
   terraform fmt -check
   terraform validate
   terraform plan
   ```

4. Review every resource and its cost before applying. Applying provisions billable resources such as the EKS control plane, NAT gateways, worker nodes, and Multi-AZ RDS. Destroying the stack also deletes resources and may affect stored data.
5. After provisioning, add the Terraform output values required by `.github/workflows/deploy.yml` as repository variables. Create a protected `production` GitHub Environment and configure its OIDC deployment role. For the default private EKS API endpoint, use a controlled self-hosted GitHub runner inside the VPC and set `DEPLOY_RUNNER=actioncloud-aws`.
6. Merge the deployment workflow to `main`, or manually dispatch it from GitHub Actions. It builds and pushes the commit image to ECR, installs the cluster add-ons, deploys the Helm release, waits for readiness, and updates the optional Route 53 record.

The exact Terraform variables and workflow environment variables are documented in `terraform/terraform.tfvars.example`, `terraform/outputs.tf`, and `.github/workflows/deploy.yml`. Keep the GitHub deployment environment protected and retrieve application secrets only through an authorized operator role.
