"""
ActionCloud — Live Metrics Dashboard (Streamlit).

Run: streamlit run dashboard/app.py

Pages:
  1. Overview       — total memories, tier donut, KRR gauge
  2. Token Savings  — cumulative token/cost savings chart
  3. Governance     — tier transition history
  4. Role Breakdown — per-role latency / success / reuse
  5. Memory Explorer— searchable memory table
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Path setup: make actioncloud importable when run from the repo root or
# from the dashboard/ directory.
# ---------------------------------------------------------------------------
_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
if str(_repo_root / "src") not in sys.path:
    sys.path.insert(0, str(_repo_root / "src"))

# Load .env before importing actioncloud modules.
from dotenv import load_dotenv  # noqa: E402
load_dotenv(_repo_root / ".env")

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="ActionCloud Dashboard",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Try to import dependencies
# ---------------------------------------------------------------------------
try:
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from dashboard.matrices import (
        build_confidence_matrix,
        build_relevance_outcome_matrix,
        build_tradeoff_matrix,
    )
except ImportError:
    st.error(
        "Missing dependencies. Run: `pip install streamlit plotly pandas psycopg[binary]`"
    )
    st.stop()

try:
    from actioncloud import db
    from actioncloud.metrics import MetricCalculator
    from actioncloud.config import settings
    _DB_AVAILABLE = db.health_check(timeout_s=2)
except Exception as _e:
    _DB_AVAILABLE = False
    _DB_ERROR = str(_e)

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e1e2e, #2a2a3e);
        border-radius: 12px;
        padding: 16px 20px;
        border: 1px solid #3a3a5e;
    }
    .stMetric label { font-size: 13px; color: #a0a0c0; }
    .stMetric [data-testid="metric-value"] { font-size: 28px; font-weight: 700; }
    div[data-testid="stSidebar"] { background: #12121f; }
    h1, h2, h3 { color: #e0e0ff; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("🧠 ActionCloud")
st.sidebar.markdown("**Real-Time Memory Dashboard**")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate",
    [
        "Live LLM Flow",
        "Performance Matrices",
        "📊 Overview",
        "💰 Token Savings",
        "🏛 Governance Flow",
        "👥 Role Breakdown",
        "🔍 Memory Explorer",
    ],
)

run_id_filter = st.sidebar.text_input("Filter by run_id", placeholder="Leave blank for all")
refresh = st.sidebar.button("🔄 Refresh Data")

if not _DB_AVAILABLE:
    st.warning(
        "⚠️ Database not reachable. Start the stack with `make up`, then refresh.\n\n"
        f"DSN: `{settings.dsn.rsplit('@', 1)[-1]}`"
    )
    st.stop()

# ---------------------------------------------------------------------------
# Data loaders (cached for 30s, refreshed on button press)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30, show_spinner=False)
def load_metrics(run_id: str | None):
    return MetricCalculator.calculate_run_metrics(run_id or None)


@st.cache_data(ttl=30, show_spinner=False)
def load_experiences_df(run_id: str | None, limit: int = 500):
    with db.get_conn() as conn, conn.cursor() as cur:
        params = {"run_id": run_id or None, "limit": limit}
        cur.execute(
            """
            SELECT id::text, agent_id, agent_role, task, tier, confidence,
                   success, reuse_count, reuse_success_count,
                   tokens_input + tokens_output AS total_tokens,
                   cost_usd, execution_time_ms, system,
                   created_at, task_key
            FROM experiences
            WHERE (%(run_id)s::text IS NULL OR run_id = %(run_id)s::text)
            ORDER BY created_at DESC
            LIMIT %(limit)s
            """,
            params,
        )
        rows = cur.fetchall()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


@st.cache_data(ttl=30, show_spinner=False)
def load_transitions_df(run_id: str | None, limit: int = 200):
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT tt.experience_id::text, tt.from_tier, tt.to_tier,
                   tt.reason, tt.decided_by, tt.created_at,
                   e.agent_role
            FROM tier_transitions tt
            JOIN experiences e ON e.id = tt.experience_id
            WHERE (%(run_id)s::text IS NULL OR e.run_id = %(run_id)s::text)
            ORDER BY tt.created_at DESC
            LIMIT %(limit)s
            """,
            {"run_id": run_id or None, "limit": limit},
        )
        rows = cur.fetchall()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


@st.cache_data(ttl=30, show_spinner=False)
def load_tradeoff_outcomes(run_id: str | None):
    """Load task-family averages for paired benchmark arm comparisons."""
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.run_id, e.system::text AS system, e.task_key,
                   AVG((e.tokens_input + e.tokens_output)::double precision) AS tokens,
                   AVG(e.execution_time_ms::double precision) AS latency_ms
            FROM experiences e
            WHERE e.task_key IS NOT NULL
              AND (%(run_id)s::text IS NULL OR e.run_id = %(run_id)s::text)
            GROUP BY e.run_id, e.system, e.task_key
            """,
            {"run_id": run_id or None},
        )
        rows = cur.fetchall()
    return pd.DataFrame(rows)


@st.cache_data(ttl=30, show_spinner=False)
def load_confidence_rows(run_id: str | None):
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT tier::text AS tier, confidence::double precision AS confidence
            FROM experiences e
            WHERE (%(run_id)s::text IS NULL OR e.run_id = %(run_id)s::text)
            """,
            {"run_id": run_id or None},
        )
        rows = cur.fetchall()
    return pd.DataFrame(rows)


@st.cache_data(ttl=30, show_spinner=False)
def load_relevance_outcomes(run_id: str | None):
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.success,
                   EXISTS (
                       SELECT 1
                       FROM unnest(e.retrieved_experience_ids) AS selected(id)
                       JOIN experiences memory ON memory.id = selected.id
                       WHERE e.task_key IS NOT NULL AND memory.task_key = e.task_key
                   ) AS same_family_retrieved
            FROM experiences e
            WHERE (%(run_id)s::text IS NULL OR e.run_id = %(run_id)s::text)
            """,
            {"run_id": run_id or None},
        )
        rows = cur.fetchall()
    return pd.DataFrame(rows)


STAGES = [
    ("retrieval", "Retrieve memory"),
    ("llm_generation", "LLM response"),
    ("verification", "Verify result"),
    ("memory_storage", "Store memory"),
    ("governance_feedback", "Governance"),
    ("completed", "Complete"),
]

STAGE_VISUALS = [
    ("retrieval", "Retrieve memory", "&#x2315;"),
    ("llm_generation", "LLM response", "&#x2726;"),
    ("verification", "Verify result", "&#x2713;"),
    ("memory_storage", "Store memory", "&#x25A4;"),
    ("governance_feedback", "Governance", "&#x2B21;"),
    ("completed", "Complete", "&#x25CF;"),
]


def load_run_memory_decisions(run_id: str) -> list[dict]:
    """Join run telemetry to persisted retrievals and visibility-blocked candidates."""
    with db.get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.activity_id::text, a.agent_id, a.agent_role, a.stage, a.status,
                   own.id::text AS own_memory_id, own.tier::text AS own_tier,
                   COALESCE((
                       SELECT array_agg(found.id::text)
                       FROM unnest(COALESCE(own.retrieved_experience_ids, ARRAY[]::uuid[])) AS used(id)
                       JOIN experiences found ON found.id = used.id
                   ), ARRAY[]::text[]) AS accepted_memory_ids,
                   COALESCE((
                       SELECT array_agg(candidate.id::text)
                       FROM experiences candidate
                       WHERE own.task_key IS NOT NULL
                         AND candidate.run_id = a.run_id
                         AND candidate.task_key = own.task_key
                         AND candidate.created_at < a.started_at
                         AND candidate.agent_id <> a.agent_id
                         AND (COALESCE((SELECT transition.to_tier::text
                                        FROM tier_transitions transition
                                        WHERE transition.experience_id = candidate.id
                                          AND transition.created_at <= a.started_at
                                        ORDER BY transition.created_at DESC LIMIT 1), candidate.tier::text) = 'private'
                              OR (COALESCE((SELECT transition.to_tier::text
                                            FROM tier_transitions transition
                                            WHERE transition.experience_id = candidate.id
                                              AND transition.created_at <= a.started_at
                                            ORDER BY transition.created_at DESC LIMIT 1), candidate.tier::text) = 'agent'
                                  AND candidate.agent_role::text <> a.agent_role))
                   ), ARRAY[]::text[]) AS blocked_memory_ids,
                   COALESCE((
                       SELECT string_agg(DISTINCT COALESCE((SELECT transition.to_tier::text
                                                           FROM tier_transitions transition
                                                           WHERE transition.experience_id = candidate.id
                                                             AND transition.created_at <= a.started_at
                                                           ORDER BY transition.created_at DESC LIMIT 1), candidate.tier::text), ', ')
                       FROM experiences candidate
                       WHERE own.task_key IS NOT NULL
                         AND candidate.run_id = a.run_id
                         AND candidate.task_key = own.task_key
                         AND candidate.created_at < a.started_at
                         AND candidate.agent_id <> a.agent_id
                         AND (COALESCE((SELECT transition.to_tier::text
                                        FROM tier_transitions transition
                                        WHERE transition.experience_id = candidate.id
                                          AND transition.created_at <= a.started_at
                                        ORDER BY transition.created_at DESC LIMIT 1), candidate.tier::text) = 'private'
                              OR (COALESCE((SELECT transition.to_tier::text
                                            FROM tier_transitions transition
                                            WHERE transition.experience_id = candidate.id
                                              AND transition.created_at <= a.started_at
                                            ORDER BY transition.created_at DESC LIMIT 1), candidate.tier::text) = 'agent'
                                  AND candidate.agent_role::text <> a.agent_role))
                   ), '') AS blocked_memory_tiers
            FROM llm_run_activity a
            LEFT JOIN experiences own ON own.id = a.memory_id
            WHERE a.run_id = %s
            ORDER BY a.started_at
            """,
            (run_id,),
        )
        return cur.fetchall()


def render_stage_flow(stage_counts: dict[str, int], replay_count: int = 0, complete: bool = False):
    """Render flowing live work, then a distinct settled completion state."""
    parts = []
    for index, (key, label, icon) in enumerate(STAGE_VISUALS):
        count = int(stage_counts.get(key, 0))
        active_class = " stage-active" if count else (" stage-complete" if complete else (" stage-done" if replay_count else ""))
        shown_count = count or replay_count
        count_label = "active" if count else ("done" if complete else ("passed" if replay_count else "active"))
        check = "<b class='done-check'>✓</b>" if complete else ""
        parts.append(
            f"<div class='flow-stage{active_class}' title='{shown_count} {count_label} task(s)'>"
            f"<div class='stage-icon'><span>{icon}</span>{check}</div>"
            f"<div class='stage-name'>{label}</div>"
            f"<div class='stage-load'>{shown_count} <span>{count_label}</span></div>"
            f"</div>"
        )
        if index < len(STAGE_VISUALS) - 1:
            next_key = STAGE_VISUALS[index + 1][0]
            load = max(count, int(stage_counts.get(next_key, 0)), replay_count)
            thickness = min(18, 3 + load * 2.5)
            parts.append(
                f"<div class='flow-link{' link-live' if any(stage_counts.values()) else (' link-complete' if complete else (' link-replay' if replay_count else ''))}' "
                f"style='--link-load:{thickness:.1f}px' title='{load} active or replayed task(s) in adjacent stage(s)'>"
                "<span></span></div>"
            )

    html = f"""
    <style>
      .ac-flow-shell {{ overflow-x:auto; border:1px solid #293449; border-radius:18px;
        background:radial-gradient(ellipse at 50% 0%, #192843 0%, #101522 70%);
        padding:22px 18px 18px; }}
      .ac-flow {{ min-width:900px; display:flex; align-items:center; gap:8px; }}
      .flow-stage {{ width:126px; flex:0 0 126px; box-sizing:border-box; text-align:center;
        padding:13px 8px 11px; border:1px solid #344054; border-radius:15px;
        background:linear-gradient(160deg,#1a2232,#121722); color:#aeb8cb;
        transition:transform .35s ease, border-color .35s ease, box-shadow .35s ease; }}
      .flow-stage.stage-active {{ transform:translateY(-3px); border-color:#61d7ff;
        color:#f5fbff; box-shadow:0 0 22px #38bdf855, inset 0 0 22px #38bdf814; }}
      .flow-stage.stage-done {{ border-color:#2f8a78; color:#dcfff7;
        box-shadow:0 0 14px #2dd4bf22, inset 0 0 15px #2dd4bf10; }}
      .flow-stage.stage-complete {{ border-color:#39b98f; color:#eafff5;
        box-shadow:0 0 18px #39b98f33, inset 0 0 16px #39b98f14; }}
      .stage-icon {{ width:34px; height:34px; margin:0 auto 8px; display:grid; place-items:center;
        border-radius:11px; color:#9baac1; background:#263247; font-size:21px; font-weight:700; }}
      .stage-active .stage-icon {{ color:#05131d; background:linear-gradient(135deg,#63e6d2,#47b8ff);
        box-shadow:0 0 17px #47caff77; }}
      .stage-done .stage-icon, .stage-complete .stage-icon {{ color:#05241d; background:linear-gradient(135deg,#6ee7b7,#2dd4bf); }}
      .stage-icon {{ position:relative; }}
      .done-check {{ position:absolute; right:-5px; top:-6px; display:grid; place-items:center;
        width:16px; height:16px; border-radius:50%; color:#06251c; background:#8cffcb;
        border:2px solid #10241e; font-size:10px; line-height:1; }}
      .stage-name {{ font-size:12px; line-height:1.25; font-weight:650; min-height:30px; }}
      .stage-load {{ margin-top:6px; color:#6ee7db; font-size:14px; font-weight:750; }}
      .stage-load span {{ color:#8793a8; font-size:10px; font-weight:500; }}
      .flow-link {{ height:28px; flex:1 1 40px; min-width:32px; position:relative; display:flex;
        align-items:center; }}
      .flow-link:before {{ content:''; width:100%; height:var(--link-load); max-height:18px;
        border-radius:99px; background:linear-gradient(90deg,#334155,#52677f); opacity:.9; }}
      .flow-link.link-live:after {{ content:''; position:absolute; left:0; width:38%;
        height:var(--link-load); max-height:18px; border-radius:99px;
        background:linear-gradient(90deg,#53e7d1,#55aaff); filter:drop-shadow(0 0 5px #43d9ff);
        animation:ac-flow-pulse 1.35s linear infinite; }}
      .flow-link.link-replay:before {{ background:linear-gradient(90deg,#2f8a78,#39b9a5); }}
      .flow-link.link-replay:after {{ content:''; position:absolute; left:0; width:38%; height:var(--link-load);
        max-height:18px; border-radius:99px; background:linear-gradient(90deg,#6ee7b7,#2dd4bf);
        filter:drop-shadow(0 0 5px #2dd4bf99); animation:ac-flow-pulse 2s linear infinite; }}
      .flow-link.link-complete:before {{ background:linear-gradient(90deg,#279d79,#53d6a4);
        animation:ac-complete-glow 2.8s ease-in-out infinite; }}
      @keyframes ac-flow-pulse {{ from {{ transform:translateX(-105%); opacity:.25; }}
        35% {{ opacity:1; }} to {{ transform:translateX(285%); opacity:.25; }} }}
      @keyframes ac-complete-glow {{ 0%,100% {{ opacity:.65; filter:drop-shadow(0 0 1px #39d99b55); }}
        50% {{ opacity:1; filter:drop-shadow(0 0 6px #39d99b99); }} }}
      @media (prefers-reduced-motion: reduce) {{ .flow-link:after, .flow-link.link-complete:before {{ animation:none !important; }} }}
    </style>
    <div class="ac-flow-shell"><div class="ac-flow">{''.join(parts)}</div></div>
    """
    st.html(html)


@st.fragment(run_every="3s")
def render_live_llm_flow(selected_run: str | None):
    """Refresh telemetry without rerunning the other dashboard sections."""
    try:
        rows = db.get_llm_activity(run_id=selected_run, limit=100)
    except Exception as exc:  # migration may not yet be applied on existing volumes
        st.error("Live run tracking is not installed in this database yet.")
        st.code("make migrate  # or apply sql/007_llm_run_activity.sql")
        st.caption(str(exc))
        return

    if not rows:
        st.info("No tracked agent runs yet. Start the cloud live demo; its newest run will appear here automatically.")
        return

    # Follow the most recently started run by default. Persisted widget state
    # previously kept the dashboard pinned to an older demo run.
    focused_run = selected_run or rows[0]["run_id"]
    focused_rows = [row for row in rows if row["run_id"] == focused_run]
    df = pd.DataFrame(focused_rows)
    if not df.empty:
        df["updated_at"] = pd.to_datetime(df["updated_at"], utc=True)
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(minutes=15)
    active = (df[(df["status"] == "running") & (df["updated_at"] >= cutoff)]
              if not df.empty else df)
    planned = 25 if focused_run.startswith("cloud-live25-") else len(df)
    completed_count = int((df["status"] == "completed").sum())
    stored_count = int((df["storage_status"] == "stored").sum())
    execution_complete = len(df) >= planned and completed_count >= planned and stored_count >= planned
    failed_count = int((df["status"] == "failed").sum())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Agents planned / tracked", f"{planned} / {len(df)}")
    c2.metric("Active now", len(active))
    c3.metric("Tasks completed", f"{completed_count} / {planned}")
    c4.metric("Memories stored", f"{stored_count} / {planned}")
    st.markdown(f"**Following run:** `{focused_run}`")
    if execution_complete:
        st.success(f"COMPLETED — {planned}/{planned} agents finished and {stored_count}/{planned} memories are stored in ActionCloud.")
    elif failed_count:
        st.error(f"ATTENTION — {failed_count} agent task(s) failed; {completed_count}/{planned} completed so far.")
    elif completed_count >= planned:
        st.warning(f"STORING MEMORIES — all {planned} agent tasks finished; {stored_count}/{planned} writes have reached PostgreSQL.")
    else:
        st.info(f"RUNNING — {len(active)} active; {completed_count}/{planned} tasks complete; {stored_count}/{planned} memories stored.")
    st.caption("Live counts refresh every 3 seconds. Active flow moves in cyan; completed flow settles to green with check marks.")

    stage_counts = {key: int((active["stage"] == key).sum()) if not active.empty else 0
                    for key, _, _ in STAGE_VISUALS}
    st.subheader("Live task pipeline")
    replay_count = completed_count if active.empty and not execution_complete else 0
    render_stage_flow(stage_counts, replay_count=planned if execution_complete else replay_count,
                      complete=execution_complete)

    memory_rows = load_run_memory_decisions(focused_run)
    decisions = {row["activity_id"]: row for row in memory_rows}

    st.subheader("Tracked LLM agents")
    st.caption("The newest active and completed agent tasks appear here and update with the pipeline.")
    display_rows = df.copy()
    display_rows["_active"] = display_rows["status"].eq("running")
    display_rows = display_rows.sort_values(["_active", "started_at"], ascending=[False, False]).head(25)
    for start in range(0, len(display_rows), 3):
        agent_cols = st.columns(3)
        for col, (_, item) in zip(agent_cols, display_rows.iloc[start:start + 3].iterrows()):
            with col:
                with st.container(border=True):
                    status_color = "green" if item["status"] == "completed" else ("red" if item["status"] == "failed" else "blue")
                    st.badge(str(item["status"]).replace("_", " ").title(), color=status_color)
                    st.markdown(f"**{item['agent_id']}** · {item['agent_role']}")
                    st.caption(str(item["task"])[:130])
                    st.markdown(f"Stage: **{item['stage']}** · Model: `{item['llm_model']}`")
                    st.caption(f"Storage: {item.get('storage_status') or 'pending'} · Tier: {item.get('memory_tier') or 'pending'}")

    st.subheader("Shared memory handoff")
    st.caption("Green indicates an actually retrieved memory ID. Red indicates a same-task memory that the stored tier and role rules make invisible.")
    accepted_agents = sum(bool((decisions.get(item["activity_id"], {}).get("accepted_memory_ids") or []))
                          for _, item in df.iterrows())
    blocked_agents = sum(bool((decisions.get(item["activity_id"], {}).get("blocked_memory_ids") or []))
                         for _, item in df.iterrows())
    handoff_a, handoff_b = st.columns(2)
    handoff_a.metric("Agents that retrieved memory", f"{accepted_agents} / {len(df)}")
    handoff_b.metric("Agents blocked by tier / role", f"{blocked_agents} / {len(df)}")
    for _, item in df.sort_values("started_at").iterrows():
        decision = decisions.get(item["activity_id"], {})
        accepted = decision.get("accepted_memory_ids") or []
        blocked = decision.get("blocked_memory_ids") or []
        if accepted:
            ids = ", ".join(f"`{str(mid)[:8]}`" for mid in accepted)
            st.success(f"{item['agent_id']} ({item['agent_role']}) accepted {len(accepted)} memory item(s): {ids}")
        elif blocked:
            tiers_text = decision.get("blocked_memory_tiers") or "restricted tier"
            st.error(f"{item['agent_id']} ({item['agent_role']}) was denied {len(blocked)} same-task memory item(s) by {tiers_text} visibility policy.")
        elif item.get("status") == "running":
            st.info(f"{item['agent_id']} is running; its memory decision will appear after retrieval and persistence.")
        else:
            st.caption(f"{item['agent_id']} ({item['agent_role']}): no same-task memory was selected or blocked for this run.")

    options = [f"{r['agent_id']} · {str(r['task'])[:85]} · {r['activity_id'][:8]}" for r in focused_rows]
    by_label = {label: row for label, row in zip(options, focused_rows)}
    choice = st.selectbox("Inspect an agent in this run", options, key=f"live_llm_activity_choice_{focused_run}")
    record = by_label[choice]
    current_stage = record["stage"]
    current_idx = next((i for i, (key, _) in enumerate(STAGES) if key == current_stage), -1)

    if record["status"] == "failed":
        st.error(f"Run failed during {current_stage}: {record.get('error_text') or 'No error detail recorded'}")
    if current_idx >= 0:
        cols = st.columns(len(STAGES))
        for i, (_, label) in enumerate(STAGES):
            if record["status"] == "failed" and i == current_idx:
                state, color = "FAILED", "#ef4444"
            elif i < current_idx or record["status"] == "completed":
                state, color = "DONE", "#22c55e"
            elif i == current_idx:
                state, color = "IN PROGRESS", "#38bdf8"
            else:
                state, color = "WAITING", "#64748b"
            cols[i].markdown(
                f"<div style='border:1px solid {color};border-radius:10px;padding:12px;"
                f"min-height:75px;background:#171b2b;color:#e8ecff'>"
                f"<div style='font-size:11px;color:{color};font-weight:700'>{state}</div>"
                f"<div style='font-size:13px;margin-top:7px'>{label}</div></div>",
                unsafe_allow_html=True,
            )

    info1, info2, info3 = st.columns(3)
    info1.write(f"**Agent:** `{record['agent_id']}` · {record['agent_role']}")
    info2.write(f"**Model:** `{record['llm_model']}`")
    info3.write(f"**Run:** `{record['run_id']}`")
    storage = record.get("storage_status") or "pending"
    tier = record.get("memory_tier") or "awaiting governance"
    memory_id = record.get("memory_id") or "not assigned"
    st.markdown(f"**Memory write:** `{storage}`　 **Governance tier:** `{tier}`　 **Memory ID:** `{memory_id}`")
    if record.get("outcome_success") is not None:
        st.markdown(f"**Task result:** {'SUCCESS' if record['outcome_success'] else 'FAILED'}")
    with st.expander("Task and completion output", expanded=True):
        st.write(record["task"])
        if record.get("result_text"):
            st.code(record["result_text"], language=None)

    table_cols = ["started_at", "agent_id", "agent_role", "llm_model", "stage", "status",
                  "outcome_success", "storage_status", "memory_tier", "run_id"]
    st.subheader("Agents in the focused run")
    st.dataframe(df[table_cols], width="stretch", hide_index=True)

    earlier = [row for row in rows if row["run_id"] != focused_run]
    if earlier:
        with st.expander("Earlier runs"):
            st.dataframe(pd.DataFrame(earlier)[table_cols].head(30), width="stretch", hide_index=True)


if refresh:
    st.cache_data.clear()

rid = run_id_filter.strip() or None
metrics = load_metrics(rid)
systems = metrics.get("systems", {})
tiers = metrics.get("governance_tier_distribution", {})
comp = metrics.get("comparative_metrics", {})

ac = systems.get("actioncloud", {})
bl = systems.get("baseline", {})

# ---------------------------------------------------------------------------
if page == "Live LLM Flow":
    st.title("LLM Run Monitor")
    st.caption("Follow tracked agent tasks from memory retrieval through their final memory tier.")
    render_live_llm_flow(rid)


if page == "Performance Matrices":
    st.title("ActionCloud performance matrices")
    st.caption("Explore benchmark trade-offs, memory confidence, and retrieval outcomes. Matrix queries are cached for 30 seconds; click Refresh Data to force an update.")

    tradeoff_data = load_tradeoff_outcomes(rid)
    confidence_data = load_confidence_rows(rid)
    relevance_data = load_relevance_outcomes(rid)

    st.subheader("Token savings vs. latency")
    tradeoff_fig = build_tradeoff_matrix(tradeoff_data)
    if tradeoff_fig is None:
        if tradeoff_data.empty:
            st.info("No benchmark outcomes yet. Run the main benchmark to populate this matrix.")
        else:
            st.info("This comparison needs matching baseline and memory-arm runs. Clear the run_id filter to compare complete benchmark arms.")
    else:
        st.plotly_chart(
            tradeoff_fig,
            width="stretch",
            alt="Task-family counts grouped by token and latency reduction bands for flat memory and ActionCloud versus baseline.",
        )
    st.caption("Each cell counts paired task families in the selected token and latency reduction bands. Positive reductions mean fewer tokens or lower latency than baseline.")

    left, right = st.columns(2)
    with left:
        st.subheader("Confidence by governance tier")
        confidence_fig = build_confidence_matrix(confidence_data)
        if confidence_fig is None:
            st.info("No memory confidence data yet.")
        else:
            st.plotly_chart(
                confidence_fig,
                width="stretch",
                alt="Memory counts by governance tier and confidence score band.",
            )
    with right:
        st.subheader("Retrieval relevance and outcome")
        relevance_fig = build_relevance_outcome_matrix(relevance_data)
        if relevance_fig is None:
            st.info("No retrieval outcome data yet.")
        else:
            st.plotly_chart(
                relevance_fig,
                width="stretch",
                alt="Task counts grouped by same-family memory retrieval and task success or failure.",
            )
        st.caption("This compares whether a same-family memory was retrieved with the task result. It is not a candidate-level confusion matrix.")


# Page: Overview
# ---------------------------------------------------------------------------
if page == "📊 Overview":
    st.title("📊 ActionCloud — System Overview")

    total_memories = sum(v.get("count", 0) for v in tiers.values())
    krr = ac.get("effective_reuse_rate_pct", 0)
    ri = ac.get("redundancy_index", 0)
    token_save = comp.get("token_savings_pct", 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Memories", f"{total_memories:,}")
    c2.metric("Effective Reuse Rate", f"{krr:.1f}%")
    c3.metric("Redundancy Index", f"{ri:.3f}", delta=f"{1-ri:.1%} eliminated", delta_color="inverse")
    c4.metric("Token Savings vs Baseline", f"{token_save:.1f}%", delta_color="normal")

    st.markdown("---")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Memory Tier Distribution")
        if tiers:
            tier_names = list(tiers.keys())
            tier_counts = [tiers[t].get("count", 0) for t in tier_names]
            tier_colors = {
                "private": "#ef4444", "agent": "#f97316",
                "shared": "#eab308", "validated": "#22c55e",
                "organizational": "#6366f1",
            }
            colors = [tier_colors.get(t, "#94a3b8") for t in tier_names]
            fig = go.Figure(go.Pie(
                labels=[t.capitalize() for t in tier_names],
                values=tier_counts,
                hole=0.55,
                marker=dict(colors=colors),
                textinfo="label+percent",
            ))
            fig.update_layout(
                showlegend=False,
                margin=dict(l=0, r=0, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e0e0ff"),
                height=300,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No tier data yet. Run the benchmark first.")

    with col2:
        st.subheader("Arm Comparison")
        if ac and bl:
            metrics_to_compare = {
                "Success Rate (%)": ("success_rate_pct", False),
                "Avg Tokens/Task": ("avg_tokens_per_task", True),
                "Avg Latency (ms)": ("avg_latency_ms", True),
                "Total Cost ($)": ("total_cost_usd", True),
            }
            rows_data = []
            for label, (key, lower_is_better) in metrics_to_compare.items():
                rows_data.append({
                    "Metric": label,
                    "Baseline": bl.get(key, 0),
                    "ActionCloud": ac.get(key, 0),
                })
            df_cmp = pd.DataFrame(rows_data)
            fig2 = px.bar(
                df_cmp.melt(id_vars="Metric", var_name="System", value_name="Value"),
                x="Metric", y="Value", color="System", barmode="group",
                color_discrete_map={"Baseline": "#94a3b8", "ActionCloud": "#6366f1"},
            )
            fig2.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e0e0ff"),
                legend=dict(bgcolor="rgba(0,0,0,0)"),
                margin=dict(l=0, r=0, t=10, b=10),
                height=300,
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Need both baseline and actioncloud arm data.")

# ---------------------------------------------------------------------------
# Page: Token Savings
# ---------------------------------------------------------------------------
elif page == "💰 Token Savings":
    st.title("💰 Cumulative Token & Cost Savings")
    df = load_experiences_df(rid)
    if df.empty:
        st.info("No experience data yet.")
    else:
        df["created_at"] = pd.to_datetime(df["created_at"])
        df = df.sort_values("created_at")

        bl_df = df[df["system"] == "baseline"].copy()
        ac_df = df[df["system"] == "actioncloud"].copy()

        if not bl_df.empty and not ac_df.empty:
            bl_df["cumulative_tokens"] = bl_df["total_tokens"].cumsum()
            ac_df["cumulative_tokens"] = ac_df["total_tokens"].cumsum()
            bl_df["cumulative_cost"] = bl_df["cost_usd"].cumsum()
            ac_df["cumulative_cost"] = ac_df["cost_usd"].cumsum()

            fig = make_subplots(rows=1, cols=2, subplot_titles=("Cumulative Tokens", "Cumulative Cost ($)"))
            fig.add_trace(go.Scatter(x=bl_df["created_at"], y=bl_df["cumulative_tokens"],
                                     name="Baseline", line=dict(color="#94a3b8")), row=1, col=1)
            fig.add_trace(go.Scatter(x=ac_df["created_at"], y=ac_df["cumulative_tokens"],
                                     name="ActionCloud", line=dict(color="#6366f1")), row=1, col=1)
            fig.add_trace(go.Scatter(x=bl_df["created_at"], y=bl_df["cumulative_cost"],
                                     name="Baseline", showlegend=False, line=dict(color="#94a3b8")), row=1, col=2)
            fig.add_trace(go.Scatter(x=ac_df["created_at"], y=ac_df["cumulative_cost"],
                                     name="ActionCloud", showlegend=False, line=dict(color="#6366f1")), row=1, col=2)
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e0e0ff"), height=400,
                legend=dict(bgcolor="rgba(0,0,0,0)"),
            )
            st.plotly_chart(fig, use_container_width=True)

            saved_tokens = bl_df["total_tokens"].sum() - ac_df["total_tokens"].sum()
            saved_cost = bl_df["cost_usd"].sum() - ac_df["cost_usd"].sum()
            c1, c2 = st.columns(2)
            c1.metric("Total Tokens Saved", f"{int(saved_tokens):,}", delta_color="normal")
            c2.metric("Total Cost Saved", f"${saved_cost:.4f}", delta_color="normal")
        else:
            st.info("Need both arms. Run the benchmark with both BASELINE and ACTIONCLOUD.")

# ---------------------------------------------------------------------------
# Page: Governance Flow
# ---------------------------------------------------------------------------
elif page == "🏛 Governance Flow":
    st.title("🏛 Memory Governance — Tier Transitions")
    df_t = load_transitions_df(rid)
    if df_t.empty:
        st.info("No tier transitions recorded yet.")
    else:
        # Sankey diagram
        tier_order = ["private", "agent", "shared", "validated", "organizational"]
        node_labels = [t.capitalize() for t in tier_order]
        node_idx = {t: i for i, t in enumerate(tier_order)}

        sources, targets, values = [], [], []
        counts: dict = {}
        for _, row in df_t.iterrows():
            f = str(row.get("from_tier") or "private")
            t_to = str(row.get("to_tier") or "private")
            if f in node_idx and t_to in node_idx:
                key = (node_idx[f], node_idx[t_to])
                counts[key] = counts.get(key, 0) + 1

        for (s, t), v in counts.items():
            sources.append(s)
            targets.append(t)
            values.append(v)

        if sources:
            fig_s = go.Figure(go.Sankey(
                node=dict(label=node_labels,
                          color=["#ef4444","#f97316","#eab308","#22c55e","#6366f1"]),
                link=dict(source=sources, target=targets, value=values,
                          color="rgba(99,102,241,0.3)"),
            ))
            fig_s.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e0e0ff"), height=400,
            )
            st.plotly_chart(fig_s, use_container_width=True)

        st.subheader("Recent Transitions")
        st.dataframe(df_t[["from_tier", "to_tier", "reason", "decided_by", "agent_role", "created_at"]]
                     .head(50), use_container_width=True)

# ---------------------------------------------------------------------------
# Page: Role Breakdown
# ---------------------------------------------------------------------------
elif page == "👥 Role Breakdown":
    st.title("👥 Per-Role Performance Breakdown")
    df = load_experiences_df(rid)
    if df.empty:
        st.info("No data yet.")
    else:
        ac_df = df[df["system"] == "actioncloud"] if "system" in df.columns else df
        if ac_df.empty:
            st.info("No ActionCloud arm data.")
        else:
            grp = ac_df.groupby("agent_role").agg(
                tasks=("id", "count"),
                success_rate=("success", "mean"),
                avg_tokens=("total_tokens", "mean"),
                avg_latency_ms=("execution_time_ms", "mean"),
                avg_reuse=("reuse_count", "mean"),
            ).reset_index()
            grp["success_rate"] = (grp["success_rate"] * 100).round(1)
            grp.columns = ["Role","Tasks","Success %","Avg Tokens","Avg Latency(ms)","Avg Reuses"]

            fig = px.bar(grp, x="Role", y="Success %",
                         color="Success %", color_continuous_scale="Viridis",
                         title="Success Rate by Agent Role")
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                               plot_bgcolor="rgba(0,0,0,0)",
                               font=dict(color="#e0e0ff"), height=350)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(grp, use_container_width=True)

# ---------------------------------------------------------------------------
# Page: Memory Explorer
# ---------------------------------------------------------------------------
elif page == "🔍 Memory Explorer":
    st.title("🔍 Memory Explorer")
    df = load_experiences_df(rid, limit=200)
    if df.empty:
        st.info("No memories stored yet.")
    else:
        search = st.text_input("🔎 Search task text")
        tier_filter = st.multiselect("Filter by tier",
                                     ["private","agent","shared","validated","organizational"],
                                     default=["shared","validated","organizational"])
        if search:
            df = df[df["task"].str.contains(search, case=False, na=False)]
        if tier_filter:
            df = df[df["tier"].isin(tier_filter)]

        display_cols = ["agent_role","tier","confidence","success","total_tokens",
                        "reuse_count","task","created_at"]
        display_cols = [c for c in display_cols if c in df.columns]
        st.dataframe(df[display_cols].head(100), use_container_width=True)
        st.caption(f"Showing {min(len(df), 100)} of {len(df)} matching memories.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.caption(f"ActionCloud v0.5.0 • {datetime.utcnow().strftime('%H:%M UTC')}")
