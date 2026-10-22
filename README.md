# ActionCloud

**Governed experience memory for AI agent fleets.**

ActionCloud lets AI agents learn from each other's work. Agents record what they did; before starting a new task, an agent receives the single most relevant *proven* procedure from the fleet as a compact, token-budgeted prompt block. A governance layer tracks whether reused memories actually worked, so good procedures spread and flawed ones are held back.

![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-4169E1?logo=postgresql&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-stdio%20server-6E56CF)
![Status](https://img.shields.io/badge/status-beta-orange)

---

## Contents

- [Why ActionCloud](#why-actioncloud)
- [How it works](#how-it-works)
- [Quickstart](#quickstart)
- [Live dashboard](#live-dashboard)
- [Connecting agents](#connecting-agents)
- [API reference](#api-reference)
- [Governance model](#governance-model)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Evaluation](#evaluation)
- [Development](#development)
- [Security](#security)
- [Limitations and roadmap](#limitations-and-roadmap)

---

## Why ActionCloud

Agent fleets repeat work. Ten agents hit the same Docker, database or CI problem and each re-derives the fix from scratch, paying for the same reasoning tokens every time. Naively sharing everything makes it worse: prompts bloat, and one agent's subtly wrong answer propagates to every other agent.

ActionCloud is built around three decisions:

- **Density over volume.** Inject one relevant, compact procedure rather than a pile of loosely related history. In our evaluation, injecting one memory beats injecting five.
- **Trust is earned.** New memories start with narrow visibility and are promoted only when *other* agents report that reusing them worked.
- **Evidence is authenticated.** Outcome reports come from key-authenticated agents and count only for memories that agent was actually given, so governance can't be gamed.

## Features

- **Hybrid retrieval.** pgvector cosine similarity plus Postgres full-text ranking, with a calibrated relevance threshold. When nothing clears the threshold, nothing is injected.
- **Compact context builder.** Relevance filtering, trust-aware ranking, near-duplicate removal and a hard token budget. Output is a structured procedure: prerequisites, steps and pitfalls.
- **Memory Judge.** A five-tier trust ladder, a confidence estimate updated on every outcome report, and automatic quarantine of failing memories. Every tier change is audited.
- **Authenticated agents.** Per-agent API keys (stored hashed). Identity and role come from the key, never from the request.
- **Two interfaces, one service.** A REST API (FastAPI) and an MCP stdio server for Claude Desktop, Cursor and other MCP clients.
- **Queue or in-request writes.** Amazon SQS with an idempotent worker for production, or synchronous writes for single-node setups. Both run the same ingest pipeline.
- **Built-in evaluation harness.** 136 tasks across 12 agent roles, ground-truth verification, and ablations. It runs offline in a simulated environment, or against a real LLM.
- **Live run dashboard.** Streamlit shows agent activity across memory retrieval, LLM response, verification, storage, governance, and completion, with a live stage pipeline and tracked run details.

---

## How it works

```mermaid
graph LR
    A[Agent] -->|1 get context| API
    API --> R[Hybrid search<br/>visibility + trust filters]
    R --> B[Context builder<br/>threshold · rank · dedupe · budget]
    B -->|2 compact procedure| A
    A -->|3 store experience| P[Ingest pipeline<br/>tier · extract · embed]
    A -->|4 report outcome| J[Memory Judge]
    P --> DB[(Postgres + pgvector)]
    J -->|confidence · promote · quarantine| DB
    R --- DB
```

1. **Retrieve.** Before a task, the agent asks for context. ActionCloud searches the memories this agent is allowed to see, drops anything below the relevance threshold or the confidence floor, removes duplicates, and returns at most `k` procedures within the token budget.
2. **Act.** The agent prepends the block to its prompt and does the task.
3. **Store.** The agent records what it did. The pipeline assigns an initial tier, extracts a reusable step list, embeds the task, and writes everything in one idempotent transaction.
4. **Report.** The agent reports whether the injected memory worked. The Memory Judge updates confidence and, when thresholds are met, promotes or quarantines the memory.

---

## Quickstart

**Prerequisites:** Docker Desktop and Python 3.11+.

```bash
git clone https://github.com/nagashiva23/action-cloud.git && cd action-cloud
make setup          # virtualenv + dependencies; creates .env from .env.example
make up             # Postgres 16 + pgvector and LocalStack (SQS)
make test           # 106 tests
```

### Live dashboard

The dashboard reads run activity from PostgreSQL. Keep the database running, start the dashboard in one terminal, then launch a benchmark in another. The dashboard refreshes every three seconds and shows active tasks by stage, recent agent runs, task results, memory write status, and governance tier.

#### Windows PowerShell

Use Python 3.13 (or another supported Python 3.11+) and Docker Desktop. Run the following from the repository root.

**Terminal 1 — start the local services and apply the activity schema:**

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d
docker compose exec postgres psql -U actioncloud -d actioncloud -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/007_llm_run_activity.sql
```

Wait until Postgres is healthy before applying the schema. The schema file is applied automatically when Postgres initializes a new data volume. The explicit command above is safe to repeat and applies it to an existing volume too.

**Terminal 2 — install and start the dashboard:**

```powershell
if (!(Test-Path .dashboard-venv)) { py -3.13 -m venv .dashboard-venv }
.\.dashboard-venv\Scripts\python.exe -m pip install -r dashboard\requirements.txt
.\.dashboard-venv\Scripts\python.exe -m streamlit run dashboard\app.py
```

Open [http://localhost:8501](http://localhost:8501) and select **Live LLM Flow**. The dashboard uses its own virtual environment to keep Streamlit's web dependencies separate from the API environment.

**Terminal 3 — set up the benchmark environment and run a live demo:**

```powershell
if (!(Test-Path .venv)) { py -3.13 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\run_experiment.py --preset main --seeds 1 --epochs 1 --limit 30 --provider sim --out "$env:TEMP\actioncloud-live-demo"
```

The `sim` provider runs simulated LLM responses and needs no model API key. The dashboard tracks the benchmark's baseline, flat-memory, and ActionCloud agent tasks as they run. The command saves its report outside the repository. This in-process benchmark needs PostgreSQL; the REST API and queue worker do not need to be running.

For real model calls, configure the matching provider key in `.env` and pass `--provider anthropic`, `--provider gemini`, or `--provider groq`. Real providers may incur usage charges.

#### macOS and Linux

After `make setup` and `make up`, run `make migrate` if you already have a database volume from an earlier checkout. Install the dashboard dependencies in a separate environment and start it:

```bash
python3 -m venv .dashboard-venv
./.dashboard-venv/bin/python -m pip install -r dashboard/requirements.txt
./.dashboard-venv/bin/python -m streamlit run dashboard/app.py
```

In another terminal, run the demo benchmark (use `--out /tmp/actioncloud-live-demo` to keep its report outside the repository):

```bash
./.venv/bin/python scripts/run_experiment.py --preset main --seeds 1 --epochs 1 --limit 30 --provider sim --out /tmp/actioncloud-live-demo
```

The `--limit 30` setting keeps the demo short. Increase it to 100 or remove it to run more tasks. Completed runs remain available in the dashboard after the active task count returns to zero.

To run the API or worker for other workflows, use `make api` and `make worker` in separate terminals. They are not required for this benchmark demo.

**Run the API** (in-request writes, so no worker is needed):

```bash
export ACTIONCLOUD_ADMIN_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
SYNC_WRITE=true make api
```

**Register two agents.** Each key is printed once; store it.

```bash
make agent ID=deployer-1 ROLE=deployment      # -> ac_...   (call it $KEY_A)
make agent ID=deployer-2 ROLE=deployment      # -> ac_...   (call it $KEY_B)
```

**Agent 1 records an experience:**

```bash
curl -s -X POST localhost:8000/experiences \
  -H "X-API-Key: $KEY_A" -H "Content-Type: application/json" -d '{
    "task": "Fix PostgreSQL container failing with pgvector extension missing",
    "action": "1. Switch the image to pgvector/pgvector:pg16\n2. Recreate the volume with docker compose down -v\n3. Run CREATE EXTENSION IF NOT EXISTS vector",
    "solution": "1. Switch the image to pgvector/pgvector:pg16\n2. Recreate the volume with docker compose down -v\n3. Run CREATE EXTENSION IF NOT EXISTS vector",
    "result": "Postgres starts with the vector extension",
    "success": true,
    "technologies": ["docker", "postgres", "pgvector"],
    "run_id": "quickstart", "system": "actioncloud"
  }'
# {"id":"a03b25f9-…","queued":false,"message":"processed synchronously"}
```

**Agent 2 hits a similar problem and asks for context:**

```bash
curl -s -X POST localhost:8000/context \
  -H "X-API-Key: $KEY_B" -H "Content-Type: application/json" \
  -d '{"query": "pgvector extension missing in my Postgres docker container",
       "technologies": ["docker", "postgres", "pgvector"]}'
```

The `context` field of the response, which is ready to prepend to a prompt:

```text
## Relevant prior experience from other agents

### 1. [WORKED] [AGENT] Fix PostgreSQL container failing with pgvector extension missing
- Prerequisites: docker, postgres, pgvector
- Procedure:
  1. Switch the image to pgvector/pgvector:pg16
  2. Recreate the volume with docker compose down -v
  3. Run CREATE EXTENSION IF NOT EXISTS vector
Use the above if it applies. If it does not, solve the task directly and ignore it.
```

The full response also carries `"injected_experience_ids"`, `"final_count": 1` and `"context_tokens": 106`.

**Agent 2 reports that it worked**, which promotes the memory fleet-wide:

```bash
curl -s -X POST localhost:8000/experiences/<id>/reuse \
  -H "X-API-Key: $KEY_B" -H "Content-Type: application/json" -d '{"success": true}'
# {"counted":true,"tier":"shared","confidence":0.7333,"transition":"shared",
#  "reason":"Promoted to shared: successful reuse by another agent", …}
```

---

## Connecting agents

### MCP (Claude Desktop, Cursor, and other MCP clients)

```json
{
  "mcpServers": {
    "actioncloud": {
      "command": "/path/to/action-cloud/.venv/bin/python",
      "args": ["-m", "actioncloud.mcp_server"],
      "env": {
        "PYTHONPATH": "/path/to/action-cloud/src",
        "DATABASE_URL": "postgresql://actioncloud:actioncloud@localhost:5433/actioncloud",
        "SYNC_WRITE": "true",
        "ACTIONCLOUD_API_KEY": "ac_…"
      }
    }
  }
}
```

The server acts as the agent that owns `ACTIONCLOUD_API_KEY`. The typical tool loop is `get_memory_context` → do the task → `reuse_memory` for each returned id → `remember_experience`.

### Python

```python
from actioncloud.client import ActionCloudClient
from actioncloud.schema import AgentRole, SystemCondition

with ActionCloudClient(agent_id="deployer-2", agent_role=AgentRole.DEPLOYMENT,
                       api_key="ac_…") as ac:
    ctx = ac.context("pgvector extension missing in Postgres container",
                     technologies=["docker", "postgres", "pgvector"])
    prompt = f"{ctx['context']}\n\n## Your task\n…"          # send to your LLM

    ok = True                                                # did the task actually work?
    for exp_id in ctx["injected_experience_ids"]:
        ac.report_reuse(exp_id, success=ok)

    ac.store(task="Fix pgvector extension missing", action="1. …\n2. …",
             result="Postgres up with vector", success=ok,
             run_id="prod", system=SystemCondition.ACTIONCLOUD,
             technologies=["docker", "postgres", "pgvector"])
```

Retrieval failures degrade gracefully: if ActionCloud is unreachable, `context()` returns an empty block and the agent carries on without memory.

---

## API reference

### REST

Every endpoint except `/health` requires an agent key, sent as `X-API-Key: ac_…` or `Authorization: Bearer ac_…`. The caller's `agent_id` and role come from the key and may be omitted from request bodies; naming a different agent returns `403`. Interactive docs are at `/docs` while the API is running.

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/health` | GET | Database and queue status (unauthenticated) |
| `/context` | POST | Compact, governed context block for a task. Records which memories were injected. |
| `/experiences` | POST | Store an experience. Returns `202` when queued. |
| `/experiences/{id}/reuse` | POST | Report `{success}` for a memory you were given. Counted once per injection. |
| `/experiences/{id}` | GET | Full record, if visible to the caller (otherwise `404`) |
| `/search` | GET | Governed hybrid search (`q`, `technologies`, `limit`, `min_tier`, `scope_run_id`) |
| `/metrics` | GET | Aggregate metrics over stored experiences |
| `/metrics/prometheus` | GET | Prometheus scrape endpoint (internal production credential required) |
| `/agents` | POST | **Admin:** register `{agent_id, agent_role}`; returns the API key once |
| `/agents/{id}` | DELETE | **Admin:** revoke an agent's key |

### MCP tools

| Tool | Key arguments | Purpose |
| :--- | :--- | :--- |
| `get_memory_context` | `task`, `technologies`, `k_inject`, `token_budget` | Compact memory block plus the ids to report on |
| `search_memory` | `query`, `limit`, `min_tier` | Governed hybrid search |
| `remember_experience` | `task`, `action_taken`, `result`, `success`, `solution`, `technologies` | Store an experience (numbered steps extract best) |
| `reuse_memory` | `experience_id`, `success` | Report whether an injected memory worked |
| `get_memory_metrics` | `run_id` | Aggregate metrics |

Legacy names are still accepted: tools `search_fleet_memory`, `store_experience`, `report_memory_reuse`, `get_fleet_metrics`; arguments `query`, `role`, `max_memories`, `action`. Errors come back as `isError` results without internal details.

---

## Governance model

### Trust tiers

| Tier | Visible to | How a memory gets here |
| :--- | :--- | :--- |
| `PRIVATE` | Its author only | Self-assessed failure, or quarantined |
| `AGENT` | Author + agents of the same role | Self-assessed success (entry point) |
| `SHARED` | All agents | ≥ 1 counted successful reuse by another agent |
| `VALIDATED` | All agents | ≥ 3 counted reuses at ≥ 80 % success |
| `ORGANIZATIONAL` | All agents | ≥ 10 counted reuses at ≥ 90 % success |

Knowledge spreads within a role first, and across roles only after it has proven itself.

### Outcome reports

- **Counted only against real injections.** A report counts only if `/context` actually gave that memory to the reporting agent, and each injection earns at most one counted report.
- **No self-promotion.** An author's positive report on its own memory is ignored. A negative one ("my solution failed CI") counts, once.
- **Confidence tracks evidence.** Confidence is updated on every counted report as `(successes + 1.2) / (reports + 2)`, a Beta-prior mean centred on 0.6. Memories below `MEMORY_MIN_CONFIDENCE` (0.45) are not injected, so one failed reuse is enough to stop a new memory spreading.
- **Quarantine.** At ≥ 3 reports with < 40 % success, a memory is demoted to `PRIVATE`.
- **Audit.** Every tier change is written to `tier_transitions`, every report to `reuse_events`, and every injection to `injections`.

### Author reputation (optional)

With `MEMORY_AUTHOR_PRIOR=true`, a new memory's confidence starts from its author's reputation: the same Beta posterior, computed over all counted reports on that author's earlier memories. An author whose memories keep failing starts new ones below the injection floor.

It is off by default, because in our evaluation it has a trade-off:
- **Under attack it helps a little.** With colluding adversarial agents it lowers flawed injections by 2–4 points.
- **When everyone is honest it costs about 3 points of success.** Honest authors with an unlucky start get held back.

---

## Configuration

All settings are environment variables; see [`.env.example`](.env.example).

| Variable | Default | Description |
| :--- | :--- | :--- |
| **Database** | | |
| `DATABASE_URL` | — | Full connection URL; overrides the `DB_*` fields |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | `localhost` / `5433`¹ / `actioncloud` / `actioncloud` / `actioncloud` | Postgres connection |
| **Auth** | | |
| `AUTH_REQUIRED` | `true` | Require agent API keys on the REST API |
| `ACTIONCLOUD_ADMIN_KEY` | — | Enables `POST`/`DELETE /agents` |
| `ACTIONCLOUD_API_KEY` | — | Identity used by the MCP server and the Python client |
| **Writes** | | |
| `SYNC_WRITE` | `false` | Process writes in-request instead of through SQS |
| `QUEUE_NAME` / `AWS_REGION` | `actioncloud-experiences` / `us-east-1` | SQS queue |
| `AWS_ENDPOINT_URL` | — | Set for LocalStack; leave unset on AWS |
| `WORKER_MAX_RECEIVES` | `5` | Deliveries before the worker drops a failing message |
| **Retrieval** | | |
| `EMBEDDING_PROVIDER` | `hashing` | `hashing` (offline, lexical), `gemini` or `openai` |
| `EMBEDDING_DIM` | `1536` | Vector size; fixed by the schema |
| `MEMORY_MAX_CONTEXT_MEMORIES` | `1` | Memories injected per task (`k`) |
| `MEMORY_SIMILARITY_THRESHOLD` | `0.30` | Minimum relevance to inject; re-run `make calibrate` after changing embedder |
| `MEMORY_MIN_CONFIDENCE` | `0.45` | Confidence floor for injection |
| `MEMORY_CONTEXT_TOKEN_BUDGET` | `1000` | Hard cap on context size |
| `MEMORY_CANDIDATE_K` / `MEMORY_REDUNDANCY_THRESHOLD` / `MEMORY_TRUST_WEIGHT` | `10` / `0.85` / `0.10` | Candidate pool, duplicate cutoff, trust ranking bonus |
| `MEMORY_ANN_CANDIDATES` | `0` | `0` = exact scoring of every visible memory; `N` = HNSW pre-selects `N` nearest neighbours first. Use about `200` beyond a few thousand memories. Run-scoped queries, and queries whose neighbours are all invisible to the caller, fall back to exact scoring |
| `MEMORY_AUTHOR_PRIOR` | `false` | Start a new memory's confidence from its author's track record (see *Author reputation*) |
| **Models** | | |
| `LLM_PROVIDER` | `mock` | Extraction and benchmark agents: `sim`, `mock`, `anthropic`, `gemini`, `groq` |
| `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `GROQ_API_KEY` / `OPENAI_API_KEY` | — | Provider credentials |

¹ `5433` in `.env.example` and `docker-compose.yml`, which avoids clashing with a locally installed Postgres. `docker-compose.yml` publishes on `DB_PORT`, so changing it in `.env` moves both.

---

## Deployment

The local stack runs the API and queue worker in containers alongside PostgreSQL and LocalStack. For production, this repository includes an EKS deployment chart, Terraform infrastructure, and GitHub Actions workflows:

| Local | AWS |
| :--- | :--- |
| `pgvector/pgvector:pg16` container | Amazon RDS for PostgreSQL 16 with the `vector` extension |
| LocalStack SQS | Amazon SQS with server-side encryption and a dead-letter queue |
| `api` and `worker` Compose services | EKS API and worker Deployments, with CPU-based API autoscaling |

The local container stack starts with `docker compose up --build -d`. The Helm release runs the SQL migration Job before deploying the API and worker. Production uses an RDS-managed master credential only for migrations; API and worker pods receive a separate, least-privilege database user from Secrets Manager through IRSA. `/health` reports dependency readiness and `/health/live` is the process liveness probe. `/metrics/prometheus` is protected by a bearer token in production; the existing authenticated JSON `/metrics` route remains available to API clients.

### Provision the AWS environment

Terraform under [`infra/terraform`](infra/terraform) creates a two-AZ VPC, EKS cluster and managed node group, private Multi-AZ RDS PostgreSQL, encrypted SQS queue and DLQ, ECR, Secrets Manager credentials, IRSA roles for the application, migrations, AWS Load Balancer Controller and Cluster Autoscaler, CloudWatch logs, and optional ACM/Route 53 setup. Cluster Autoscaler can grow the managed node group from two to six workers; the API HPA scales API pods by CPU within its configured range.

The default configuration creates billable AWS resources, including an EKS control plane, two NAT gateways, two on-demand nodes, and Multi-AZ RDS. Review the plan and AWS pricing for your region before applying. This repository does not apply Terraform or create AWS resources for you.

1. Install Terraform 1.13+, AWS CLI, Helm 3, and kubectl. Configure AWS credentials for the account and region where you want the stack.
2. Create a dedicated, encrypted, versioned S3 bucket for Terraform state. Copy `infra/terraform/backend.tf.example` to `infra/terraform/backend.tf` and fill in that bucket. The state contains generated credentials; keep it private and out of git.
3. Create `infra/terraform/terraform.tfvars` (do not commit it). Set `github_repository = "OWNER/REPOSITORY"`. For a public API, also set `api_hostname` and `route53_zone_id` for an existing Route 53 zone. Set `cluster_public_access_cidrs` to the trusted egress CIDR used for cluster administration. The default allows only loopback, so the EKS API is not publicly reachable until you set an explicit CIDR. GitHub-hosted runner IPs change; use a self-hosted runner in the VPC or a controlled deployment network for a restricted EKS endpoint.
4. From `infra/terraform`, run `terraform init`, `terraform fmt -check`, `terraform validate`, and `terraform plan`. Inspect the resource list and costs before choosing to run `terraform apply`.
5. After apply, copy these Terraform outputs into GitHub repository variables: `aws_region` → `AWS_REGION`, `cluster_name` → `EKS_CLUSTER_NAME`, `ecr_repository_url` → `ECR_REPOSITORY`, `database_endpoint` → `DATABASE_ENDPOINT`, `queue_name` → `QUEUE_NAME`, `application_secret_arn` → `APPLICATION_SECRET_ARN`, `database_secret_arn` → `DATABASE_MASTER_SECRET_ARN`, `runtime_role_arn` → `RUNTIME_ROLE_ARN`, `migration_role_arn` → `MIGRATION_ROLE_ARN`, `load_balancer_controller_role_arn` → `LOAD_BALANCER_ROLE_ARN`, `cluster_autoscaler_role_arn` → `CLUSTER_AUTOSCALER_ROLE_ARN`, `github_deploy_role_arn` → `AWS_DEPLOY_ROLE_ARN`, `api_certificate_arn` → `ACM_CERTIFICATE_ARN`, and `route53_zone_id` → `ROUTE53_ZONE_ID`. Set `API_HOSTNAME` to the same hostname used in Terraform, or leave the hostname and certificate variables empty to omit public ingress.
6. Create a GitHub Environment named `production`, add required reviewers, and allow only the intended deployment branch. The deploy role trusts the `production` environment through GitHub OIDC; no static AWS access keys are stored in GitHub.
7. Create a self-hosted GitHub Actions runner inside the VPC, label it `actioncloud-aws`, and set the GitHub repository variable `DEPLOY_RUNNER=actioncloud-aws`. This lets the protected workflow reach the private EKS API without opening it to changing GitHub-hosted runner IPs. Open a pull request to run CI. After merging to `main`, the workflow builds an immutable image, installs the AWS Load Balancer Controller, Cluster Autoscaler, metrics-server and Prometheus/Grafana, then applies the Helm release. The API and worker use max-surge rolling updates; Helm waits for readiness and automatically rolls back a failed application upgrade. The workflow points the optional Route 53 record at the ALB after the API becomes healthy.

The API hostname and certificate are optional. Grafana and Prometheus stay internal; connect with `kubectl port-forward` when you need to view them. Prometheus collects service metrics and evaluates the included alerts; configure an Alertmanager receiver to deliver notifications. The API HPA scales pods by CPU, and Cluster Autoscaler scales worker nodes when pods cannot be scheduled. These defaults are starting points; tune replica counts, thresholds, and instance sizes against measured workload and cost. The project does not claim a specific availability SLA or compliance certification; configure those requirements for your account and organization.

After deployment, retrieve the generated administrator key from the application secret using an authorized operator role, then use it to register agents through `POST /agents`. Keep this key in a secure secret store. See [`.env.example`](.env.example) for the local configuration and [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) for deployment details.

---

## Evaluation

The harness runs 136 tasks in 45 task families across all 12 roles, for 3 epochs (408 tasks per configuration) and 5 seeds.
- **Grading:** every task has a ground-truth procedure, and the same verifier grades every configuration.
- **Isolation:** each configuration has its own run scope, so none can read another's memories.

| Configuration | Success | Flawed memories injected | Tokens / task | Cost / success |
| :--- | ---: | ---: | ---: | ---: |
| No memory | 65.0 % | — | 928 | $0.0198 |
| Shared memory, no governance | 75.4 % | 27.7 % | 608 | $0.0089 |
| **ActionCloud** | **86.8 %** | **4.4 %** | **591** | **$0.0075** |

**Ablations:**
- **Injecting 1 memory beats 5.** At k=5, retrieval precision falls from 95 % to 57 % with no gain in success.
- **The relevance threshold helps.** Always injecting the top hit costs 2.5 points of success.
- **Governance depends on observable outcomes.** With 30 / 70 / 100 % of outcomes observed, flawed injections are 12.3 / 4.4 / 0.0 %.

Full tables are in [`results/RESULTS.md`](results/RESULTS.md).

> **Read this before quoting the numbers.** These results come from a **simulated agent environment** (`LLM_PROVIDER=sim`), not a real LLM. How much a correct memory helps an agent is a stated *assumption* of the simulator (`benchmark/simulator.py`), not a finding. What the simulation does measure is everything ActionCloud controls: whether the right memory is retrieved, what the context costs in tokens, and how often flawed memories get through. To test with a real model, run the same harness with `LLM_PROVIDER=anthropic|gemini|groq`; the verifier and metrics are unchanged.

**Reproduce:**

```bash
make experiment     # all presets, 5 seeds -> results/   (~10 min, needs only Postgres)
make fleet          # 12-role fleet, one agent per task
make calibrate      # retrieval threshold calibration
```

---

## Development

For how the project was built phase by phase, and why it looks the way it does, see [IMPLEMENTATION.md](IMPLEMENTATION.md).

```bash
make test       # 106 tests; database tests skip cleanly if Postgres is down
make verify     # end-to-end check against a running API (make api)
make mcp        # run the MCP server on stdio
make migrate    # apply sql/002+ to an existing database
```

```
src/actioncloud/
  api.py           REST API and authentication
  mcp_server.py    MCP stdio server
  service.py       MemoryService: shared by REST, MCP and the in-process client
  pipeline.py      Ingest: initial tier → extraction → embedding → one transaction
  builder.py       Context builder: threshold, trust ranking, dedupe, token budget
  judge.py         Memory Judge: tiers, confidence, quarantine (pure functions)
  db.py            SQL, visibility rules, atomic reuse accounting
  auth.py          Agent registry and API keys (also a CLI)
  embeddings.py    hashing / Gemini / OpenAI embedders
  worker.py        SQS consumer
  benchmark/       Tasks, ground-truth procedures, verifier, simulator, harness
sql/               Schema and migrations
scripts/           Experiments, calibration, end-to-end checks
dashboard/         Streamlit metrics dashboard and live LLM run monitor
tests/             Unit, integration, API-attack and evaluation tests
results/           The evaluation run cited above
```

---

## Security

- **API keys:** 256-bit random tokens. Only their SHA-256 hash is stored. Keys are compared by hash lookup; the admin key uses a constant-time comparison.
- **Identity:** always taken from the key. `tests/test_auth.py` exercises each attack this prevents: impersonation, reading another agent's private memories, self-promotion through a second identity, and report flooding.
- **Hidden records:** an agent asking for a memory it cannot see gets `404`, not `403`, so the response doesn't confirm the memory exists.
- **SQL:** every query is parameterised.
- **MCP boundary:** the MCP stdio server holds database credentials itself. It binds one identity for honest clients; the REST API is the security boundary.

## Limitations and roadmap

- **Real-LLM evaluation:** the headline results are simulated. The harness supports real providers; rate limiting and resumable runs are next.
- **Semantic embeddings:** the default embedder is lexical. The Gemini and OpenAI providers are implemented but not yet evaluated.
- **Cross-role transfer:** it is lightly exercised, because the benchmark's task families are mostly role-specific.
- **Scale:** exact scoring (the default) grows linearly with the number of visible memories, to about 240 ms at 5,000. Beyond a few thousand memories, set `MEMORY_ANN_CANDIDATES` so the HNSW index pre-selects candidates.
- **Collusion:** governance limits but does not stop large colluding groups. In simulation, about 30 % adversarial agents bring ActionCloud down to no-memory performance.
- **Keys:** there is no rate limiting or key expiry; a leaked key works until it is revoked.
- **Packaging:** the API/worker Docker image, CI checks, and EKS deployment scaffolding are included. The repository still has no license file.
- **External benchmark datasets:** the current 136-task suite is built-in. A future roadmap target is adapting standard external agent benchmarks (e.g. SWE-bench for GitHub issues, ToolBench for tool trajectories) to benchmark cross-agent memory reuse across clustered open-source repositories.

