# ActionCloud

ActionCloud is a governed shared-memory service for AI agent fleets. Agents can retrieve proven procedures before work, submit new experiences, and report whether reused memories succeeded. PostgreSQL with pgvector stores the memories; role and confidence rules govern when they can be shared.

## Current deployment status

**AWS demo: decommissioned on 25 October 2026.** There is no live EKS cluster, database, or dashboard URL. The Terraform, Helm, and GitHub deployment configuration remain in this repository for a future deployment. The Terraform state bucket is retained for redeployment and may incur a small storage charge.

GitHub's green **`deployment-validation`** record means the workflow validated the deployment configuration. It does not mean ActionCloud is running in AWS. The real **Deploy ActionCloud to EKS** workflow is manual-only and requires AWS infrastructure to be provisioned first. Applying Terraform and deploying the stack create billable AWS resources.

## ActionCloud architecture

The moving dots show how memory is read, governed, stored, and surfaced in the dashboard. The drawing is visible here on GitHub and respects reduced-motion settings. Its animation explains the architecture; live agent counts and decisions appear only when the dashboard is connected to a running ActionCloud deployment.

![Animated ActionCloud architecture: agents, MCP and REST API, governed memory retrieval, queue worker, PostgreSQL, dashboard, and local or AWS deployment](docs/actioncloud-architecture.svg)

The diagram is based on the implementation in [`src/actioncloud/service.py`](src/actioncloud/service.py), [`src/actioncloud/pipeline.py`](src/actioncloud/pipeline.py), and [`src/actioncloud/worker.py`](src/actioncloud/worker.py). [xyflow](https://github.com/xyflow/xyflow) is a React/Svelte library for interactive app canvases; GitHub README pages cannot execute that app code, so the architecture is embedded here as an animated SVG. The flow below remains clickable to guide you to the local and AWS instructions.

## Follow the workspace flow

Choose a path below. On GitHub, the diagram is rendered directly in this README; the linked nodes open the relevant setup guides.

```mermaid
flowchart TD
    START([Start here]) --> CHOOSE{What do you want to do?}

    CHOOSE -->|Run and see agents locally| LOCAL_ENV[Prepare .env and local tools]
    LOCAL_ENV --> LOCAL_STACK[Start Docker Compose<br/>PostgreSQL + LocalStack]
    LOCAL_STACK --> LOCAL_SIM[Run the simulated agent workload]
    LOCAL_SIM --> LOCAL_UI[Open Streamlit dashboard<br/>Watch shared memory and run stages]
    LOCAL_UI --> LOCAL_STOP[Stop dashboard and Compose services]

    CHOOSE -->|Check repository changes| PUSH[Push or open a pull request]
    PUSH --> CI[GitHub Actions validates code,<br/>Terraform, and Helm]
    CI --> CI_NOTE[Green validation means checks passed;<br/>it does not deploy or run AWS resources]

    CHOOSE -->|Demonstrate a real AWS deployment| COST[Review AWS costs and deployment guide]
    COST --> APPLY[Manually provision AWS infrastructure<br/>with Terraform]
    APPLY --> DEPLOY[Manually deploy ActionCloud to EKS<br/>with the GitHub workflow / Helm]
    DEPLOY --> AWS_UI[Open the AWS-hosted dashboard<br/>and submit the demo agent workload]
    AWS_UI --> OBSERVE[Observe agents, shared-memory decisions,<br/>and completion in the live UI]
    OBSERVE --> DESTROY[Run the documented teardown<br/>and verify AWS resources are removed]

    LOCAL_STOP --> DONE([Finished])
    CI_NOTE --> DONE
    DESTROY --> DONE

    classDef local fill:#123b35,stroke:#34d399,color:#f0fdf4
    classDef ci fill:#172554,stroke:#60a5fa,color:#eff6ff
    classDef aws fill:#4a2c12,stroke:#fbbf24,color:#fffbeb
    classDef caution fill:#3f1d2e,stroke:#fb7185,color:#fff1f2
    class LOCAL_ENV,LOCAL_STACK,LOCAL_SIM,LOCAL_UI,LOCAL_STOP local
    class PUSH,CI,CI_NOTE ci
    class COST,APPLY,DEPLOY,AWS_UI,OBSERVE,DESTROY aws
    class COST,CI_NOTE caution

    click LOCAL_ENV "dashboard/README.md" "Open local dashboard and demo instructions"
    click LOCAL_UI "dashboard/README.md" "Open local dashboard and demo instructions"
    click COST "infra/README.md" "Review AWS deployment, costs, validation, and teardown"
    click APPLY "infra/README.md" "Review AWS deployment, costs, validation, and teardown"
    click DEPLOY "infra/README.md" "Review AWS deployment, costs, validation, and teardown"
    click DESTROY "infra/README.md" "Review AWS deployment, costs, validation, and teardown"
```

**Recommended path:** use the local route for regular development. The AWS route creates billable resources and is currently decommissioned; follow [the AWS guide](infra/README.md) only when you intend to redeploy and monitor costs.

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
