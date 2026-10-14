#!/usr/bin/env python3
"""Evaluate task-key similarity thresholds and save a JSON/Markdown report."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from actioncloud.benchmark import load_tasks  # noqa: E402
from actioncloud.embeddings import cosine, experience_embedding_text, get_embedding_provider  # noqa: E402


def main() -> None:
    tasks = list(load_tasks())
    provider = get_embedding_provider()
    vectors = [provider.embed(experience_embedding_text(t["task"], t["technologies"])) for t in tasks]
    same: list[float] = []
    diff: list[float] = []
    for i in range(len(tasks)):
        for j in range(i + 1, len(tasks)):
            (same if tasks[i]["task_key"] == tasks[j]["task_key"] else diff).append(
                cosine(vectors[i], vectors[j])
            )
    rows = []
    for n in range(1, 10):
        threshold = n / 10
        tp = sum(s >= threshold for s in same)
        fp = sum(s >= threshold for s in diff)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / len(same) if same else 0.0
        rows.append({"threshold": threshold, "precision": precision, "recall": recall,
                     "false_positive_rate": fp / len(diff) if diff else 0.0})
    best = max(rows, key=lambda row: 2 * row["precision"] * row["recall"] /
               (row["precision"] + row["recall"]) if row["precision"] + row["recall"] else 0)
    report = {"provider": provider.name, "task_count": len(tasks), "same_pairs": len(same),
              "different_pairs": len(diff), "recommended_threshold": best["threshold"], "points": rows}
    (ROOT / "embedding_calibration.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    md = [f"# Embedding calibration: {provider.name}", "",
          f"Recommended threshold: **{best['threshold']:.1f}** (best F1)", "",
          "| Threshold | Precision | Recall | False positive rate |", "|---:|---:|---:|---:|"]
    md.extend(f"| {r['threshold']:.1f} | {r['precision']:.2%} | {r['recall']:.2%} | {r['false_positive_rate']:.2%} |" for r in rows)
    (ROOT / "embedding_calibration.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"provider={provider.name} recommended_threshold={best['threshold']:.1f}")


if __name__ == "__main__":
    main()
