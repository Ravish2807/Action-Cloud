# ActionCloud

ActionCloud is a governed shared-memory service for AI agent fleets. Agents can retrieve proven procedures before work, store new experiences, and report whether reused memories succeeded. PostgreSQL with pgvector stores memories; the governance layer controls their visibility and confidence.

## Project status

The repository includes a local Docker Compose stack, FastAPI and MCP interfaces, a Streamlit dashboard, a simulated evaluation harness, and production deployment infrastructure for AWS EKS. The cloud infrastructure and deployment workflow are implemented; AWS resources are **not provisioned by this repository**. The published evaluation uses simulated agents, not a real-LLM study.

## Run locally

Prerequisites: Docker Desktop and Python 3.11 or newer. From the repository root:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
```

Then use two more PowerShell terminals to start the dashboard and a short simulated benchmark. The benchmark creates live run records for the dashboard and writes its report under your temporary directory.

```powershell
if (!(Test-Path .dashboard-venv)) { py -3.13 -m venv .dashboard-venv }
.\.dashboard-venv\Scripts\python.exe -m pip install -r dashboard\requirements.txt
.\.dashboard-venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

```powershell
if (!(Test-Path .venv)) { py -3.13 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\run_experiment.py --preset main --seeds 1 --epochs 1 --limit 30 --provider sim --out "$env:TEMP\actioncloud-live-demo"
```

Open [http://localhost:8501](http://localhost:8501), then select **Live LLM Flow** to watch task stages or **Performance Matrices** to view benchmark metrics. The local run uses simulated model responses and needs no model API key. See [dashboard/README.md](dashboard/README.md) for the full walkthrough and [infra/README.md](infra/README.md) for cloud deployment and its local validation steps.

## Project guides

- [Dashboard and live demo](dashboard/README.md)
- [AWS EKS deployment](infra/README.md)
- [Implementation notes](IMPLEMENTATION.md)
- [External benchmark roadmap](docs/external_benchmarks_roadmap.md)

## Security and private project files

Never commit `.env`, Terraform state, or `*.tfvars` files. The `D14_Report/` and `paper/` folders, plus the root project report and review presentation, are excluded from new commits. Their local copies are under `local-private/`.
