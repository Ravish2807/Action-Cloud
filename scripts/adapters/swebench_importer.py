"""
ActionCloud — SWE-bench Lite Adapter.

Converts SWE-bench Lite instances (300 real GitHub issues, ICLR 2024) into
ActionCloud TaskSpec objects for benchmarking cross-task knowledge reuse.

Dataset: https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite

Quick start
-----------
    # Dry run (no DB writes) — just preview conversions:
    python scripts/adapters/swebench_importer.py --dry-run --limit 10

    # Full import into a tasks JSON for the harness:
    python scripts/adapters/swebench_importer.py --output swebench_tasks.json

    # Run the ActionCloud benchmark against SWE-bench tasks:
    python scripts/adapters/swebench_importer.py --run --provider mock

Environment
-----------
    HF_DATASETS_CACHE   Optional HuggingFace cache directory.
    LLM_PROVIDER        LLM backend for live runs (mock/gemini/groq/anthropic).
    ACTIONCLOUD_*       Standard ActionCloud env vars for DB + auth.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Repository → technology tag mapping
# ---------------------------------------------------------------------------

_REPO_TECHNOLOGIES: Dict[str, List[str]] = {
    "django/django":            ["python", "django", "orm", "http"],
    "scikit-learn/scikit-learn":["python", "scikit-learn", "ml", "numpy"],
    "sympy/sympy":              ["python", "sympy", "math", "symbolic"],
    "matplotlib/matplotlib":    ["python", "matplotlib", "visualization"],
    "pytest-dev/pytest":        ["python", "pytest", "testing"],
    "astropy/astropy":          ["python", "astropy", "science", "numpy"],
    "sphinx-doc/sphinx":        ["python", "sphinx", "documentation"],
    "flask/flask":              ["python", "flask", "http", "web"],
    "pallets/jinja":            ["python", "jinja2", "templates"],
    "sqlalchemy/sqlalchemy":    ["python", "sqlalchemy", "orm", "database"],
    "requests/requests":        ["python", "requests", "http", "networking"],
    "pydata/xarray":            ["python", "xarray", "data-analysis", "numpy"],
}

_DEFAULT_TOOLS = ["code_search", "file_edit", "bash", "git"]


# ---------------------------------------------------------------------------
# Cluster key helpers
# ---------------------------------------------------------------------------

def _repo_cluster_key(instance_id: str, issue_repo: str) -> str:
    """
    Stable task_key for a SWE-bench instance.

    Format: ``swebench/<repo_slug>`` so all issues from the same repository
    share a cluster key, enabling KRR measurement across bugs in the same
    codebase.

    Example: ``"swebench/django__django"``
    """
    slug = issue_repo.replace("/", "__").lower()
    return f"swebench/{slug}"


def _technologies_for_repo(repo: str) -> List[str]:
    return list(_REPO_TECHNOLOGIES.get(repo, ["python"]))


# ---------------------------------------------------------------------------
# Core conversion
# ---------------------------------------------------------------------------

def instance_to_task(instance: Dict[str, Any]) -> "AdapterTaskSpec":
    """Convert one SWE-bench instance dict → AdapterTaskSpec."""
    from scripts.adapters import AdapterTaskSpec  # noqa: PLC0415

    instance_id: str = instance.get("instance_id", "")
    repo: str = instance.get("repo", "")
    issue_title: str = (instance.get("problem_statement") or "")[:120].strip()
    issue_body: str = (instance.get("problem_statement") or "").strip()

    task_description = (
        f"Fix the following issue in the {repo} repository.\n\n"
        f"**Issue:** {issue_title}\n\n"
        f"{issue_body[:800]}"
    )

    return AdapterTaskSpec(
        task=task_description,
        task_key=_repo_cluster_key(instance_id, repo),
        technologies=_technologies_for_repo(repo),
        expected_tools=_DEFAULT_TOOLS,
        instance_id=instance_id,
        metadata={
            "repo": repo,
            "base_commit": instance.get("base_commit", ""),
            "test_patch": instance.get("test_patch", ""),
            "patch": instance.get("patch", ""),
            "version": instance.get("version", ""),
        },
    )


# ---------------------------------------------------------------------------
# Adapter class
# ---------------------------------------------------------------------------

class SWEBenchAdapter:
    """
    Loads SWE-bench Lite from HuggingFace and converts to ActionCloud TaskSpecs.

    Falls back to a bundled minimal JSON sample if the ``datasets`` package is
    not installed — useful for CI and dry-run demos without a network.
    """

    DATASET_NAME = "princeton-nlp/SWE-bench_Lite"
    SPLIT = "test"

    def load_tasks(self, limit: Optional[int] = None) -> List["AdapterTaskSpec"]:
        """Download SWE-bench Lite and return converted tasks."""
        raw = self._load_raw(limit)
        tasks = [instance_to_task(inst) for inst in raw]
        log.info("Loaded %d SWE-bench Lite tasks across %d repository clusters.",
                 len(tasks), len({t.task_key for t in tasks}))
        return tasks

    def _load_raw(self, limit: Optional[int]) -> List[Dict[str, Any]]:
        try:
            from datasets import load_dataset  # noqa: PLC0415
            ds = load_dataset(self.DATASET_NAME, split=self.SPLIT)
            instances = [dict(row) for row in ds]
            log.info("Downloaded %d instances from HuggingFace.", len(instances))
            return instances[:limit] if limit else instances
        except ImportError:
            log.warning(
                "The 'datasets' package is not installed. "
                "Install it with: pip install datasets\n"
                "Falling back to the bundled 5-instance sample."
            )
            return self._bundled_sample()[:limit or 5]
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to download SWE-bench: %s — using bundled sample.", exc)
            return self._bundled_sample()[:limit or 5]

    @staticmethod
    def _bundled_sample() -> List[Dict[str, Any]]:
        """Five representative instances for offline demos and CI."""
        return [
            {
                "instance_id": "django__django-13710",
                "repo": "django/django",
                "problem_statement": (
                    "Queryset.order_by() crashes when the ordering references "
                    "a field through a join that uses a subquery annotation."
                ),
                "base_commit": "abc123",
                "test_patch": "",
                "patch": "",
                "version": "4.0",
            },
            {
                "instance_id": "django__django-14411",
                "repo": "django/django",
                "problem_statement": (
                    "ModelAdmin.get_form() does not respect the 'fields' attribute "
                    "when the form has a GenericRelation field."
                ),
                "base_commit": "def456",
                "test_patch": "",
                "patch": "",
                "version": "4.0",
            },
            {
                "instance_id": "scikit-learn__scikit-learn-14894",
                "repo": "scikit-learn/scikit-learn",
                "problem_statement": (
                    "OneHotEncoder raises a confusing TypeError when input data "
                    "contains NaN values in sparse matrices."
                ),
                "base_commit": "ghi789",
                "test_patch": "",
                "patch": "",
                "version": "0.24",
            },
            {
                "instance_id": "sympy__sympy-20590",
                "repo": "sympy/sympy",
                "problem_statement": (
                    "Symbol('x').is_real returns None instead of True when the "
                    "symbol is declared with assumptions real=True."
                ),
                "base_commit": "jkl012",
                "test_patch": "",
                "patch": "",
                "version": "1.9",
            },
            {
                "instance_id": "pytest-dev__pytest-8365",
                "repo": "pytest-dev/pytest",
                "problem_statement": (
                    "pytest --collect-only crashes with RecursionError when a "
                    "conftest.py imports a module that imports conftest.py."
                ),
                "base_commit": "mno345",
                "test_patch": "",
                "patch": "",
                "version": "7.0",
            },
        ]

    def to_cluster_sequence(
        self,
        tasks: Optional[List["AdapterTaskSpec"]] = None,
        limit: Optional[int] = None,
    ) -> List["AdapterTaskSpec"]:
        """Interleave tasks across repository clusters (promotes cross-repo KRR)."""
        from scripts.adapters import AdapterBase  # noqa: PLC0415

        class _Tmp(AdapterBase):
            dataset_name = "swebench"
            def load_tasks(self, limit=None): return tasks or []

        return _Tmp().to_cluster_sequence(tasks=tasks or self.load_tasks(), limit=limit)

    def save_json(self, output_path: str | Path, limit: Optional[int] = None) -> None:
        """Save converted tasks to JSON for harness consumption."""
        tasks = self.load_tasks(limit=limit)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                [
                    {
                        "task": t.task,
                        "task_key": t.task_key,
                        "technologies": t.technologies,
                        "expected_tools": t.expected_tools,
                        "instance_id": t.instance_id,
                        "metadata": t.metadata,
                    }
                    for t in tasks
                ],
                f,
                indent=2,
            )
        print(f"Saved {len(tasks)} tasks to {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="SWE-bench Lite → ActionCloud task importer"
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print converted tasks without saving or running the benchmark.",
    )
    p.add_argument(
        "--output",
        default="swebench_tasks.json",
        help="Output JSON file path (default: swebench_tasks.json).",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of tasks to load (default: all 300).",
    )
    p.add_argument(
        "--run",
        action="store_true",
        help="Run the ActionCloud benchmark harness against the loaded tasks.",
    )
    p.add_argument(
        "--provider",
        default="mock",
        choices=["mock", "simulated", "gemini", "groq", "anthropic"],
        help="LLM provider for --run (default: mock).",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _parse_args(argv)
    adapter = SWEBenchAdapter()

    if args.dry_run:
        tasks = adapter.load_tasks(limit=args.limit or 5)
        print(f"\n=== SWE-bench Lite — {len(tasks)} tasks (dry run) ===\n")
        for i, t in enumerate(tasks, 1):
            print(f"[{i}] task_key={t.task_key!r}  instance={t.instance_id!r}")
            print(f"     tech={t.technologies}")
            print(f"     task={t.task[:100]!r}...")
            print()
        print("Cluster distribution:")
        from collections import Counter  # noqa: PLC0415
        for key, cnt in Counter(t.task_key for t in tasks).most_common():
            print(f"  {key}: {cnt} tasks")
        return

    if args.run:
        import os  # noqa: PLC0415
        os.environ.setdefault("LLM_PROVIDER", args.provider)
        try:
            from actioncloud.benchmark.harness import (  # noqa: PLC0415
                ArmConfig, Workload, run_experiment,
            )
        except ImportError:
            sys.exit(
                "Could not import actioncloud. "
                "Run from the project root with: "
                "python -m scripts.adapters.swebench_importer --run"
            )
        tasks = adapter.to_cluster_sequence(limit=args.limit or 30)
        print(f"Running benchmark on {len(tasks)} SWE-bench tasks…")
        results = run_experiment(
            arms=[ArmConfig.BASELINE, ArmConfig.ACTIONCLOUD],
            seeds=[42],
            workload=Workload(epochs=1),
            provider=args.provider,
        )
        print(json.dumps(results.get("summary", results), indent=2))
        return

    adapter.save_json(args.output, limit=args.limit)


if __name__ == "__main__":
    main()
