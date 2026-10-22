# ActionCloud

ActionCloud is a governed shared-memory service for AI agent fleets. Agents retrieve proven procedures before tasks, store reusable experiences, and report whether reused memories worked. PostgreSQL with pgvector stores the memories; FastAPI and MCP expose them to agents.

## Project status

This beta branch contains the API, MCP server, local Docker Compose stack, simulated evaluation harness, and live Streamlit run dashboard. The evaluation uses simulated agents, not a real-LLM study. AWS EKS deployment work is in [PR #2](https://github.com/Ravish2807/Action-Cloud/pull/2); no AWS resources have been provisioned.

## Local quick start

Prerequisites: Docker Desktop and Python 3.11 or newer. Start services in PowerShell from the repository root:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
Invoke-RestMethod http://localhost:8000/health
```

For the live UI demo, start Streamlit in a second terminal and run the short simulated workload in a third. Follow [dashboard/README.md](dashboard/README.md) for the complete commands and screenshots/metrics views.

## Guides

- [Live dashboard demo](dashboard/README.md)
- [Implementation notes](IMPLEMENTATION.md)
- [External benchmark roadmap](docs/external_benchmarks_roadmap.md)

## Private project files

Never commit `.env`, Terraform state, or `*.tfvars`. The `D14_Report/` and `paper/` folders, plus the root project report and review presentation, are excluded from new commits. Keep local copies under `local-private/`.
