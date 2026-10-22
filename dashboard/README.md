# Dashboard and live demo

The Streamlit dashboard reads agent run activity from PostgreSQL. It shows the current task stage, tracked runs, completion result, memory write status, and governance tier. The Performance Matrices view displays saved benchmark metrics.

## Start the local services

Start Docker Desktop, open PowerShell in the repository root, then run:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
docker compose ps
```

PostgreSQL, LocalStack (SQS), the API, migration job, and queue worker start as Compose services. The migration runs before the API and worker. Check service output with `docker compose logs -f api worker`.

## Start the dashboard

In a second PowerShell terminal:

```powershell
if (!(Test-Path .dashboard-venv)) { py -3.13 -m venv .dashboard-venv }
.\.dashboard-venv\Scripts\python.exe -m pip install -r dashboard\requirements.txt
.\.dashboard-venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

Open [http://localhost:8501](http://localhost:8501). Keep this terminal open while using the dashboard. Its virtual environment is separate so Streamlit's web dependencies do not conflict with the API environment.

## Produce live activity

In a third terminal, install the benchmark requirements and run the short simulated workload:

```powershell
if (!(Test-Path .venv)) { py -3.13 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\run_experiment.py --preset main --seeds 1 --epochs 1 --limit 30 --provider sim --out "$env:TEMP\actioncloud-live-demo"
```

The simulated provider needs no API key. The dashboard reads the benchmark's run records from the same PostgreSQL database and refreshes during the run. Use **Live LLM Flow** for the stage pipeline and run cards; use **Performance Matrices** to inspect benchmark metrics. The benchmark report is written outside the repository.

To use a real model, configure the provider key in `.env` and select `--provider anthropic`, `--provider gemini`, or `--provider groq`. Real provider calls may incur usage charges. Run `docker compose down` to stop services while retaining database data; `docker compose down -v` also removes the local database volume.

## Local stack versus AWS

This laptop demo exercises the application, database, queue integration, migrations, and dashboard. Docker Compose uses LocalStack and local PostgreSQL; it does not provision or connect to AWS EKS, RDS, or SQS. For the production deployment path and CI workflow, see [infra/README.md](../infra/README.md).
