# ActionCloud

ActionCloud is a governed shared-memory service for AI agent fleets. Agents can retrieve proven procedures before work, submit new experiences, and report whether reused memories succeeded. PostgreSQL with pgvector stores the memories; role and confidence rules govern when they can be shared.

## Current deployment status

**AWS demo: decommissioned on 25 October 2026.** There is no live EKS cluster, database, or dashboard URL. The Terraform, Helm, and GitHub deployment configuration remain in this repository for a future deployment. The Terraform state bucket is retained for redeployment and may incur a small storage charge.

GitHub's green **`deployment-validation`** record means the workflow validated the deployment configuration. It does not mean ActionCloud is running in AWS. The real **Deploy ActionCloud to EKS** workflow is manual-only and requires AWS infrastructure to be provisioned first. Applying Terraform and deploying the stack create billable AWS resources.

## Follow the workspace flow

[Open the interactive ActionCloud workspace flowchart](docs/actioncloud-workspace-flow.html) · [View its editable Archify source](docs/actioncloud-workspace-flow.workflow.json)

The flowchart covers the local demo, no-AWS GitHub validation, and the billable AWS deployment path. To use its interactions, download the HTML file from GitHub and open it in a browser; it is self-contained and does not start a service.

## Run the local demo

Prerequisites: Docker Desktop and Python 3.11 or newer. From the repository root:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
```

Then follow [Dashboard and live demo](dashboard/README.md) to start Streamlit and run simulated agent tasks. This local path uses PostgreSQL and LocalStack; it does not provision AWS or use AWS credits.

## Guides

- [Dashboard and live demo](dashboard/README.md)
- [AWS deployment, validation, and teardown](infra/README.md)
- [Implementation notes](IMPLEMENTATION.md)
- [External benchmark roadmap](docs/external_benchmarks_roadmap.md)

## Keep private files out of Git

Never commit `.env`, Terraform state, `*.tfvars`, or plan files. `D14_Report/`, `paper/`, `local-private/`, and the project report and review presentation are excluded from the repository. Keep local copies outside Git.
