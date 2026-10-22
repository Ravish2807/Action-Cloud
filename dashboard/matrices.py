"""Plotly figures for the ActionCloud performance matrix page."""

from __future__ import annotations

import re

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


_ARMS = ("baseline", "flat_memory", "actioncloud")
_TIERS = ("private", "agent", "shared", "validated", "organizational")
_BANDS = ("< -25%", "-25 to -10%", "-10 to 0%", "0 to 10%", "10 to 25%", "25 to 50%", "> 50%")
_BIN_EDGES = [-float("inf"), -25, -10, 0, 10, 25, 50, float("inf")]


def _plot_layout(fig: go.Figure, *, height: int = 420) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e0e0ff"),
        margin=dict(l=24, r=24, t=54, b=24),
        height=height,
        coloraxis=dict(colorscale="Tealgrn", colorbar=dict(title="Tasks")),
    )
    fig.update_xaxes(gridcolor="#263247", zerolinecolor="#526174")
    fig.update_yaxes(gridcolor="#263247", zerolinecolor="#526174")
    return fig


def _parse_benchmark_run(run_id: str) -> tuple[str, str, str] | None:
    """Return (experiment, arm, seed) for run ids created by the harness."""
    match = re.match(r"^(.*)-(baseline|flat_memory|actioncloud)-s(\d+)$", str(run_id))
    return match.groups() if match else None


def build_tradeoff_matrix(outcomes: pd.DataFrame) -> go.Figure | None:
    """Bin per-task token and latency reductions against the paired baseline."""
    if outcomes.empty:
        return None

    paired = outcomes.copy()
    parsed = paired["run_id"].map(_parse_benchmark_run)
    paired = paired[parsed.notna()].copy()
    if paired.empty:
        return None
    paired[["experiment", "arm", "seed"]] = pd.DataFrame(
        parsed[parsed.notna()].tolist(), index=paired.index
    )

    pair_keys = ["experiment", "seed", "task_key"]
    figures: dict[str, pd.DataFrame] = {}
    for metric in ("tokens", "latency_ms"):
        pivot = paired.pivot_table(
            index=pair_keys, columns="arm", values=metric, aggfunc="mean"
        )
        if "baseline" not in pivot.columns:
            return None
        for arm in ("flat_memory", "actioncloud"):
            if arm not in pivot.columns:
                figures[arm] = pd.DataFrame()
                continue
            baseline = pivot["baseline"].mask(pivot["baseline"] == 0)
            pivot[f"{arm}_{metric}_reduction"] = (baseline - pivot[arm]) / baseline * 100
        figures[metric] = pivot

    token_pivot = figures["tokens"]
    latency_pivot = figures["latency_ms"]
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Flat memory vs baseline", "ActionCloud vs baseline"),
        horizontal_spacing=0.12,
    )
    for col, arm in enumerate(("flat_memory", "actioncloud"), start=1):
        token_col = f"{arm}_tokens_reduction"
        latency_col = f"{arm}_latency_ms_reduction"
        if token_col not in token_pivot or latency_col not in latency_pivot:
            continue
        points = pd.DataFrame({
            "token_reduction": token_pivot[token_col],
            "latency_reduction": latency_pivot[latency_col],
        }).dropna()
        if points.empty:
            continue
        points["token_band"] = pd.cut(
            points["token_reduction"], _BIN_EDGES, labels=_BANDS, right=False
        )
        points["latency_band"] = pd.cut(
            points["latency_reduction"], _BIN_EDGES, labels=_BANDS, right=False
        )
        matrix = pd.crosstab(points["latency_band"], points["token_band"])
        matrix = matrix.reindex(index=_BANDS, columns=_BANDS, fill_value=0)
        fig.add_trace(
            go.Heatmap(
                z=matrix.to_numpy(),
                x=list(_BANDS),
                y=list(_BANDS),
                coloraxis="coloraxis",
                hovertemplate=(
                    "Token reduction: %{x}<br>Latency reduction: %{y}<br>"
                    "Task families: %{z}<extra></extra>"
                ),
                showscale=(col == 2),
            ),
            row=1,
            col=col,
        )
    fig.update_xaxes(title_text="Token reduction band", tickangle=-28)
    fig.update_yaxes(title_text="Latency reduction band", autorange="reversed")
    fig.update_layout(title="Token savings vs. latency reduction", coloraxis_showscale=True)
    return _plot_layout(fig, height=470)


def build_confidence_matrix(confidence: pd.DataFrame) -> go.Figure | None:
    """Count memories by governance tier and ten equally sized confidence bands."""
    if confidence.empty:
        return None
    band_labels = [f"{i / 10:.1f}-{(i + 1) / 10:.1f}" for i in range(10)]
    data = confidence.copy()
    data["tier"] = data["tier"].astype(str)
    data["confidence_band"] = pd.cut(
        data["confidence"].astype(float),
        bins=[i / 10 for i in range(11)],
        labels=band_labels,
        include_lowest=True,
    )
    matrix = pd.crosstab(data["tier"], data["confidence_band"])
    matrix = matrix.reindex(index=_TIERS, columns=band_labels, fill_value=0)
    fig = go.Figure(go.Heatmap(
        z=matrix.to_numpy(),
        x=band_labels,
        y=[tier.capitalize() for tier in _TIERS],
        colorscale="Tealgrn",
        hovertemplate="Tier: %{y}<br>Confidence: %{x}<br>Memories: %{z}<extra></extra>",
        colorbar=dict(title="Memories"),
    ))
    fig.update_layout(title="Confidence distribution by governance tier")
    fig.update_xaxes(title_text="Confidence band")
    fig.update_yaxes(title_text="Governance tier")
    return _plot_layout(fig, height=390)


def build_relevance_outcome_matrix(outcomes: pd.DataFrame) -> go.Figure | None:
    """Count same-family retrieval presence against the stored task outcome."""
    if outcomes.empty:
        return None
    retrieved_order = ["No same-family memory", "Same-family memory"]
    result_order = ["Failed", "Succeeded"]
    data = outcomes.copy()
    data["retrieval_label"] = data["same_family_retrieved"].map(
        {False: retrieved_order[0], True: retrieved_order[1], 0: retrieved_order[0], 1: retrieved_order[1]}
    )
    data["result_label"] = data["success"].map(
        {False: result_order[0], True: result_order[1], 0: result_order[0], 1: result_order[1]}
    )
    matrix = pd.crosstab(data["retrieval_label"], data["result_label"])
    matrix = matrix.reindex(index=retrieved_order, columns=result_order, fill_value=0)
    fig = go.Figure(go.Heatmap(
        z=matrix.to_numpy(),
        x=result_order,
        y=retrieved_order,
        colorscale="Tealgrn",
        hovertemplate="Retrieval: %{y}<br>Task outcome: %{x}<br>Tasks: %{z}<extra></extra>",
        colorbar=dict(title="Tasks"),
    ))
    fig.update_layout(title="Retrieval relevance vs. task outcome")
    fig.update_xaxes(title_text="Task outcome")
    fig.update_yaxes(title_text="Retrieved same-family memory")
    return _plot_layout(fig, height=310)
