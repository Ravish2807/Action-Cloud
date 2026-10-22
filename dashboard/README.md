# Live dashboard demo

The Streamlit dashboard reads agent run activity from PostgreSQL. **Live LLM Flow** shows tracked tasks moving through retrieval, response, verification, storage, governance, and completion. **Performance Matrices** displays benchmark metrics.

## Start the local stack

Start Docker Desktop, open PowerShell in the repository root, and run:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
docker compose ps
```

If the database has an older volume, apply the activity schema once:

```powershell
docker compose exec postgres psql -U actioncloud -d actioncloud -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/007_llm_run_activity.sql
```

## Run the dashboard

In a second PowerShell terminal:

```powershell
if (!(Test-Path .dashboard-venv)) { py -3.13 -m venv .dashboard-venv }
.\.dashboard-venv\Scripts\python.exe -m pip install -r dashboard\requirements.txt
.\.dashboard-venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

Open [http://localhost:8501](http://localhost:8501).

## Show live tracked runs

In a third terminal, run a short simulated workload:

```powershell
if (!(Test-Path .venv)) { py -3.13 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\run_experiment.py --preset main --seeds 1 --epochs 1 --limit 30 --provider sim --out "$env:TEMP\actioncloud-live-demo"
```

The simulated provider needs no model API key. The benchmark writes run activity into PostgreSQL while it executes and saves its report outside the repository. To call a real model, configure its provider key and use `--provider anthropic`, `--provider gemini`, or `--provider groq`; those calls may incur usage charges.

Stop containers with `docker compose down`. Add `-v` only if you also want to delete the local database volume.
