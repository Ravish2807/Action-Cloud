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


def render_stage_flow(stage_counts: dict[str, int]):
    """Render a live pipeline whose animated connector width follows stage load."""
    parts = []
    for index, (key, label, icon) in enumerate(STAGE_VISUALS):
        count = int(stage_counts.get(key, 0))
        active_class = " stage-active" if count else ""
        parts.append(
            f"<div class='flow-stage{active_class}' title='{count} active task(s)'>"
            f"<div class='stage-icon'>{icon}</div>"
            f"<div class='stage-name'>{label}</div>"
            f"<div class='stage-load'>{count} <span>active</span></div>"
            f"</div>"
        )
        if index < len(STAGE_VISUALS) - 1:
            next_key = STAGE_VISUALS[index + 1][0]
            load = max(count, int(stage_counts.get(next_key, 0)))
            thickness = min(18, 3 + load * 2.5)
            parts.append(
                f"<div class='flow-link{' link-live' if load else ''}' "
                f"style='--link-load:{thickness:.1f}px' title='{load} active task(s) in adjacent stage(s)'>"
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
      .stage-icon {{ width:34px; height:34px; margin:0 auto 8px; display:grid; place-items:center;
        border-radius:11px; color:#9baac1; background:#263247; font-size:21px; font-weight:700; }}
      .stage-active .stage-icon {{ color:#05131d; background:linear-gradient(135deg,#63e6d2,#47b8ff);
        box-shadow:0 0 17px #47caff77; }}
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
      @keyframes ac-flow-pulse {{ from {{ transform:translateX(-105%); opacity:.25; }}
        35% {{ opacity:1; }} to {{ transform:translateX(285%); opacity:.25; }} }}
      @media (prefers-reduced-motion: reduce) {{ .flow-link:after {{ animation:none !important; }} }}
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

    df = pd.DataFrame(rows)
    if not df.empty:
        df["updated_at"] = pd.to_datetime(df["updated_at"], utc=True)
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(minutes=15)
    active = (df[(df["status"] == "running") & (df["updated_at"] >= cutoff)]
              if not df.empty else df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active LLM tasks", len(active))
    c2.metric("Models active", active["llm_model"].nunique() if not active.empty else 0)
    c3.metric("Completed runs", int((df["status"] == "completed").sum()) if not df.empty else 0)
    c4.metric("Memories stored", int((df["storage_status"] == "stored").sum()) if not df.empty else 0)
    st.caption("Active means a tracked task reported progress in the last 15 minutes. This panel refreshes every 3 seconds.")

    stage_counts = {key: int((active["stage"] == key).sum()) if not active.empty else 0
                    for key, _, _ in STAGE_VISUALS}
    st.subheader("Live task pipeline")
    render_stage_flow(stage_counts)
    st.caption("Each stage shows its active task count. Connector thickness and motion increase with the load in the stages it joins.")

    if df.empty:
        st.info("No tracked agent runs yet. Start a benchmark or built-in Agent.run_task workload; new runs will appear here.")
        return

    st.subheader("Tracked LLM agents")
    st.caption("The newest active and completed agent tasks appear here and update with the pipeline.")
    display_rows = df.copy()
    display_rows["_active"] = display_rows["status"].eq("running")
    display_rows = display_rows.sort_values(["_active", "started_at"], ascending=[False, False]).head(12)
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

    options = [f"{r['agent_id']} · {str(r['task'])[:85]} · {r['activity_id'][:8]}" for r in rows]
    by_label = {label: row for label, row in zip(options, rows)}
    choice = st.selectbox("Inspect a run", options, key="live_llm_activity_choice")
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

    table_cols = ["started_at", "agent_id", "llm_model", "stage", "status",
                  "outcome_success", "storage_status", "memory_tier", "run_id"]
    st.subheader("Recent tracked runs")
    st.dataframe(df[table_cols].head(30), use_container_width=True, hide_index=True)


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
