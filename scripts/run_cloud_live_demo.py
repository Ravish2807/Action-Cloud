"""Run a short, SQS-backed multi-agent demo inside the EKS API pod.

PowerShell invocation from the repository root:

    Get-Content scripts/run_cloud_live_demo.py -Raw |
      kubectl exec -i deployment/actioncloud-actioncloud-api -n actioncloud `
        --container api -- python -

This uses the simulated model provider (no external LLM calls) while agents
use the deployed REST API and AWS SQS/RDS memory pipeline.
"""

from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from uuid import UUID

import httpx

from actioncloud import db
from actioncloud.agents import TaskSpec, build_agent
from actioncloud.benchmark import load_tasks
from actioncloud.benchmark.simulator import SimulatedAgentLLM
from actioncloud.benchmark.verifier import TaskVerifier
from actioncloud.client import ActionCloudClient
from actioncloud.config import settings
from actioncloud.schema import AgentRole


API_URL = os.environ.get("ACTIONCLOUD_API_URL", "http://127.0.0.1:8000")
DISPLAY_PACING_SECONDS = float(os.environ.get("DEMO_STAGE_SECONDS", "4"))
if not settings.admin_key:
    raise RuntimeError("The ActionCloud admin key was not loaded from Secrets Manager")

run_id = f"cloud-live25-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
tasks = load_tasks()
coding_tasks = [item for item in tasks if item["role"] == "coding" and item.get("task_key")]
with db.get_conn() as conn, conn.cursor() as cur:
    cur.execute(
        "SELECT task_key, count(*) AS uses FROM experiences "
        "WHERE agent_id LIKE 'cloud-demo-writer-%' GROUP BY task_key"
    )
    task_uses = {row["task_key"]: row["uses"] for row in cur.fetchall()}
if not coding_tasks:
    raise RuntimeError("The benchmark task catalog has no coding tasks for the cloud demo")
# Each demo gets a fresh run_id and scopes retrieval to that run. Reusing a
# task key is safe and makes the demo repeatable after the small task pool has
# already been exercised.
task = min(coding_tasks, key=lambda item: (task_uses.get(item["task_key"], 0), item["task_key"]))
role = AgentRole(task["role"])
task_spec = TaskSpec(
    task=task["task"],
    task_key=task["task_key"],
    technologies=task.get("technologies", []),
    expected_tools=task.get("expected_tools", []),
)


class DemoPacedLLM:
    """Keep generation visible long enough for the dashboard's 3s refresh."""

    def __init__(self, seed: int) -> None:
        self.model = "sim-agent-v1"
        self._simulator = SimulatedAgentLLM(seed=seed)

    def set_instance(self, instance_id: str) -> None:
        self._simulator.set_instance(instance_id)

    def complete(self, prompt: str, system: str | None = None):
        # This wall-clock pause is only for the live presentation. The simulator
        # response's model latency/cost values remain its deterministic values.
        time.sleep(DISPLAY_PACING_SECONDS)
        return self._simulator.complete(prompt, system)

suffix = run_id.rsplit("-", 1)[-1].lower()
identities = {"writer": f"cloud-demo-writer-{suffix}"}
agent_roles = {"writer": role}
blocked_labels = []
accepted_labels = []
for blocked_role in AgentRole:
    if blocked_role == role:
        continue
    label = f"blocked-{blocked_role.value}"
    identities[label] = f"cloud-demo-{label}-{suffix}"
    agent_roles[label] = blocked_role
    blocked_labels.append(label)
for number in range(1, 14):
    label = f"coding-{number:02d}"
    identities[label] = f"cloud-demo-{label}-{suffix}"
    agent_roles[label] = role
    accepted_labels.append(label)

with httpx.Client(
    base_url=API_URL,
    timeout=15,
    headers={"X-API-Key": settings.admin_key},
) as admin:
    api_keys: dict[str, str] = {}
    for label, agent_id in identities.items():
        agent_role = agent_roles[label]
        response = admin.post(
            "/agents",
            json={"agent_id": agent_id, "agent_role": agent_role.value, "rotate": True},
        )
        response.raise_for_status()
        api_keys[label] = response.json()["api_key"]


def make_agent(label: str):
    agent_id = identities[label]
    agent_role = agent_roles[label]
    client = ActionCloudClient(
        agent_id=agent_id,
        agent_role=agent_role,
        base_url=API_URL,
        timeout=30,
        api_key=api_keys[label],
    )
    return build_agent(
        role=agent_role,
        agent_id=agent_id,
        client=client,
        run_id=run_id,
        use_memory=True,
        scope_run_id=run_id,
        llm=DemoPacedLLM(seed=42),
        report_reuse=True,
        feedback_rate=1.0,
    )


def run_one(label: str, instance_id: str) -> dict[str, object]:
    agent = make_agent(label)
    try:
        outcome = agent.run_task(
            TaskSpec(
                task=task_spec.task,
                task_key=task_spec.task_key,
                technologies=task_spec.technologies,
                expected_tools=task_spec.expected_tools,
                instance_id=instance_id,
            )
        )
        return {
            "agent_id": identities[label],
            "experience_id": str(outcome.experience_id) if outcome.experience_id else None,
            "retrieved_ids": [str(item) for item in outcome.retrieved_ids],
            "success": outcome.success,
            "tokens": outcome.total_tokens,
        }
    finally:
        agent.client.close()


print(json.dumps({
    "event": "starting cloud agent demo",
    "provider": "sim",
    "display_pacing_seconds": DISPLAY_PACING_SECONDS,
    "task": task_spec.task,
    "task_key": task_spec.task_key,
    "run_id": run_id,
    "agents_total": len(identities),
    "writer": identities["writer"],
    "cross_role_readers": len(blocked_labels),
    "same_role_readers": len(accepted_labels),
    "agents": list(identities.values()),
    "write_path": "ActionCloud REST API -> Amazon SQS -> worker -> Amazon RDS",
    "memory_policy_demo": "11 distinct cross-role readers are checked before reuse feedback can promote the memory; 13 same-role coding readers can retrieve the writer's AGENT-tier memory",
}), flush=True)

# Pick a deterministic simulation seed that produces a strictly verified
# writer result. That lets the real governance pipeline publish its memory at
# AGENT tier so the role boundary can be demonstrated without fabricated UI.
verifier = TaskVerifier()
writer_instance = None
probe = SimulatedAgentLLM(seed=42)
for attempt in range(100):
    candidate = f"{run_id}-writer-{attempt}"
    probe.set_instance(candidate)
    response = probe.complete(f"## Your task\n{task_spec.task}")
    if verifier.verify(task_spec.task_key, response.text).strict:
        writer_instance = candidate
        break
if writer_instance is None:
    raise RuntimeError("Could not find a strictly verified deterministic writer seed")

writer = run_one("writer", writer_instance)
writer_id = writer["experience_id"]
if not writer_id:
    raise RuntimeError("Writer did not return an experience ID")

record = None
deadline = time.monotonic() + 60
while time.monotonic() < deadline:
    record = db.get_experience(UUID(writer_id))
    if record:
        break
    time.sleep(0.5)
if not record:
    raise RuntimeError("The queue worker did not persist the writer's experience within 60 seconds")
if record.get("tier") != "agent":
    raise RuntimeError(f"Writer memory expected AGENT tier for role-policy demo, got {record.get('tier')!r}")

print(json.dumps({
    "event": "writer memory stored",
    "agent_id": writer["agent_id"],
    "experience_id": writer_id,
    "tier": record.get("tier"),
    "success": writer["success"],
}), flush=True)

def run_cohort(labels: list[str]) -> list[dict[str, object]]:
    with ThreadPoolExecutor(max_workers=len(labels)) as pool:
        futures = {
            pool.submit(run_one, label, f"{run_id}-{label}"): label
            for label in labels
        }
        results = []
        for future in as_completed(futures):
            result = future.result()
            result["reused_writer_memory"] = writer_id in result["retrieved_ids"]
            results.append(result)
        return results


# Run the cross-role cohort first while the writer's memory is still at AGENT
# tier. Successful coding reuses can promote it to SHARED, so the allowed
# cohort follows only after the visibility-denial demonstration is recorded.
blocked_readers = run_cohort(blocked_labels)
if any(result["retrieved_ids"] for result in blocked_readers):
    raise RuntimeError("A cross-role reader unexpectedly received a memory from this run's AGENT-tier writer")

accepted_readers = run_cohort(accepted_labels)
if not all(result["reused_writer_memory"] for result in accepted_readers):
    raise RuntimeError("At least one same-role coding reader did not retrieve the writer's memory")

readers = blocked_readers + accepted_readers
expected_agents = len(identities)
deadline = time.monotonic() + 180
activities = []
stored_experience_count = 0
while time.monotonic() < deadline:
    activities = db.get_llm_activity(run_id=run_id, limit=100)
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM experiences WHERE run_id = %s", (run_id,))
        stored_experience_count = cur.fetchone()["n"]
    all_tasks_done = len(activities) == expected_agents and all(
        item.get("status") == "completed" for item in activities
    )
    all_memories_stored = len(activities) == expected_agents and all(
        item.get("storage_status") == "stored" for item in activities
    )
    if stored_experience_count == expected_agents and all_tasks_done and all_memories_stored:
        break
    time.sleep(1)

print(json.dumps({
    "event": "cloud demo complete",
    "provider": "sim",
    "run_id": run_id,
    "agents_total": expected_agents,
    "tasks_completed": len(activities),
    "memories_persisted": stored_experience_count,
    "memories_stored": sum(item.get("storage_status") == "stored" for item in activities),
    "writer_memory_id": writer_id,
    "writer_tier": record.get("tier"),
    "accepted_readers": sum(result["reused_writer_memory"] for result in accepted_readers),
    "blocked_readers": sum(not result["reused_writer_memory"] for result in blocked_readers),
    "readers": readers,
    "expected_policy_decisions": {
        "coding_readers": f"{len(accepted_labels)} same-role readers accepted writer memory under AGENT visibility",
        "cross_role_readers": f"{len(blocked_labels)} distinct other-role readers were blocked before reuse could promote it",
    },
    "all_experiences_persisted": stored_experience_count == expected_agents,
    "activities": [
        {
            "agent_id": item.get("agent_id"),
            "stage": item.get("stage"),
            "status": item.get("status"),
            "storage_status": item.get("storage_status"),
            "memory_tier": item.get("memory_tier"),
            "outcome_success": item.get("outcome_success"),
        }
        for item in activities
    ],
}), flush=True)
