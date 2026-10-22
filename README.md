# ActionCloud

ActionCloud is a governed shared-memory service for AI agent fleets. Agents retrieve proven procedures before a task, store reusable experiences, and report whether reused memories succeeded. PostgreSQL with pgvector stores memories; governance controls their confidence and visibility.

## Status

This branch contains the live-run dashboard improvements and benchmark tracking flow. The benchmark can use a simulated provider for a local demo. Results presented by the simulator are not a real-LLM evaluation.

## Quick start

Prerequisites: Docker Desktop and Python 3.11 or newer. Start the local services from the repository root:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
```

Follow [dashboard/README.md](dashboard/README.md) to launch the UI and run a short workload that fills the live flow. The cloud deployment feature and its AWS setup are documented on the deployment branch.

## Guides

- [Live dashboard demo](dashboard/README.md)
- [Implementation notes](IMPLEMENTATION.md)
- [External benchmark roadmap](docs/external_benchmarks_roadmap.md)

## Private project files

Never commit `.env`, Terraform state, or `*.tfvars`. The `D14_Report/` and `paper/` folders, plus the root project report and review presentation, are excluded from new commits. Local copies belong under `local-private/`.
