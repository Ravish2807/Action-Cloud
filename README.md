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

Choose a route below. Each route reads left to right; click its setup or deployment nodes for the relevant guide.

```mermaid
flowchart LR
    START([Start]) --> CHOOSE{Choose a route}

    CHOOSE -->|Local demo| LOCAL_ENV
    subgraph LOCAL["1 · Run locally · recommended"]
        direction LR
        LOCAL_ENV[Prepare .env] --> LOCAL_STACK[Start Docker Compose<br/>PostgreSQL + LocalStack]
        LOCAL_STACK --> LOCAL_SIM[Run simulated<br/>agent workload]
        LOCAL_SIM --> LOCAL_UI[Watch stages and memory<br/>in Streamlit]
        LOCAL_UI --> LOCAL_STOP[Stop dashboard<br/>and Compose]
    end

    CHOOSE -->|GitHub checks| PUSH
    subgraph CI_PATH["2 · Validate changes · no AWS resources"]
        direction LR
        PUSH[Push or open<br/>a pull request] --> CI[GitHub Actions checks<br/>code, Terraform, Helm]
        CI --> CI_NOTE[Green means validation passed;<br/>it does not deploy AWS]
    end

    CHOOSE -->|AWS deployment| COST
    subgraph AWS_PATH["3 · Live AWS demo · billable"]
        direction LR
        COST[Review AWS costs<br/>and deployment guide] --> APPLY[Provision infrastructure<br/>with Terraform]
        APPLY --> DEPLOY[Deploy API and worker<br/>to EKS with Helm]
        DEPLOY --> AWS_UI[Open hosted dashboard<br/>and run agent workload]
        AWS_UI --> OBSERVE[Observe shared-memory<br/>decisions and completion]
        OBSERVE --> DESTROY[Tear down and verify<br/>AWS resources removed]
    end

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
