"""
ActionCloud — ToolBench Adapter.

Converts ToolBench / ToolLLM API tool-use tasks (Qin et al., ICLR 2024)
into ActionCloud TaskSpec objects for benchmarking cross-task tool-call
knowledge reuse.

Dataset: https://huggingface.co/datasets/ToolBench/ToolBench
Paper:   https://arxiv.org/abs/2307.16789

Key idea
--------
ToolBench tasks involve multi-step REST API calls.  Agents frequently fail
on the same API because they re-discover auth headers, parameter order, and
error handling from scratch.  Clustering tasks by shared API suite and
running them sequentially lets ActionCloud store "how to call this API
correctly" as a reusable playbook — the primary hypothesis H1 of the paper.

Quick start
-----------
    # Dry run with the bundled 6-task sample:
    python scripts/adapters/toolbench_importer.py --dry-run

    # Save full task list to JSON:
    python scripts/adapters/toolbench_importer.py --output toolbench_tasks.json

    # Limit to 50 tasks across the top API categories:
    python scripts/adapters/toolbench_importer.py --output tb.json --limit 50
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# API-category → technology tag mapping
# ---------------------------------------------------------------------------

_CATEGORY_TECHNOLOGIES: Dict[str, List[str]] = {
    "Finance":          ["rest-api", "finance", "json", "http"],
    "Weather":          ["rest-api", "weather", "json", "geolocation"],
    "Sports":           ["rest-api", "sports", "json"],
    "Travel":           ["rest-api", "travel", "json", "geolocation"],
    "Social":           ["rest-api", "social-media", "oauth2", "json"],
    "News":             ["rest-api", "news", "json", "nlp"],
    "Food":             ["rest-api", "food", "json"],
    "Shopping":         ["rest-api", "ecommerce", "json", "payments"],
    "Music":            ["rest-api", "music", "oauth2", "json"],
    "Video":            ["rest-api", "video", "oauth2", "json"],
    "Email":            ["rest-api", "email", "smtp", "json"],
    "Maps":             ["rest-api", "maps", "geolocation", "json"],
    "Productivity":     ["rest-api", "productivity", "json"],
    "Health":           ["rest-api", "health", "json"],
    "Education":        ["rest-api", "education", "json"],
}
_DEFAULT_TECHNOLOGIES = ["rest-api", "json", "http"]
_DEFAULT_TOOLS = ["http_get", "http_post", "http_put", "parse_json", "authenticate"]


# ---------------------------------------------------------------------------
# Cluster key helpers
# ---------------------------------------------------------------------------

def _api_cluster_key(tool_name: str, category: str) -> str:
    """
    Stable task_key for a ToolBench tool-use task.

    Format: ``toolbench/<category_slug>/<tool_slug>``

    All tasks that call the same top-level tool family share a task_key,
    enabling KRR measurement across tool invocations.
    """
    cat = category.lower().replace(" ", "_")
    tool = tool_name.lower().replace(" ", "_").replace("-", "_")[:32]
    return f"toolbench/{cat}/{tool}"


def _technologies_for_category(category: str) -> List[str]:
    return list(_CATEGORY_TECHNOLOGIES.get(category, _DEFAULT_TECHNOLOGIES))


# ---------------------------------------------------------------------------
# Core conversion
# ---------------------------------------------------------------------------

def instance_to_task(instance: Dict[str, Any]) -> "AdapterTaskSpec":
    """Convert one ToolBench instance dict → AdapterTaskSpec."""
    from scripts.adapters import AdapterTaskSpec  # noqa: PLC0415

    tool_name: str = instance.get("tool_name", "unknown_api")
    category: str = instance.get("category", "General")
    query: str = instance.get("query", "").strip()
    api_name: str = instance.get("api_name", "")
    required_params: List[str] = instance.get("required_parameters", [])
    optional_params: List[str] = instance.get("optional_parameters", [])

    param_hint = ""
    if required_params:
        param_hint = f"\n\nRequired parameters: {', '.join(str(p) for p in required_params)}"
    if optional_params:
        param_hint += f"\nOptional parameters: {', '.join(str(p) for p in optional_params)}"

    task_description = (
        f"Call the {tool_name} API (category: {category}) to complete the "
        f"following request.\n\n"
        f"**Request:** {query}"
        f"{param_hint}\n\n"
        f"Return the result in JSON format.  Handle authentication, rate limiting, "
        f"and error responses appropriately."
    )

    return AdapterTaskSpec(
        task=task_description,
        task_key=_api_cluster_key(api_name or tool_name, category),
        technologies=_technologies_for_category(category),
        expected_tools=_DEFAULT_TOOLS,
        instance_id=instance.get("instance_id") or f"{tool_name}_{api_name}",
        metadata={
            "tool_name": tool_name,
            "api_name": api_name,
            "category": category,
            "required_parameters": required_params,
            "optional_parameters": optional_params,
        },
    )


# ---------------------------------------------------------------------------
# Adapter class
# ---------------------------------------------------------------------------

class ToolBenchAdapter:
    """
    Loads ToolBench from HuggingFace (or bundled sample) and converts to
    ActionCloud TaskSpecs.

    The ToolBench dataset has 16 464 real-world REST API tasks across 49
    categories.  We cluster by ``(category, api_name)`` so agents that
    repeatedly call the same API family share playbooks.
    """

    DATASET_NAME = "ToolBench/ToolBench"
    SPLIT = "train"

    def load_tasks(self, limit: Optional[int] = None) -> List["AdapterTaskSpec"]:
        raw = self._load_raw(limit)
        tasks = [instance_to_task(inst) for inst in raw]
        log.info(
            "Loaded %d ToolBench tasks across %d API clusters.",
            len(tasks), len({t.task_key for t in tasks}),
        )
        return tasks

    def _load_raw(self, limit: Optional[int]) -> List[Dict[str, Any]]:
        try:
            from datasets import load_dataset  # noqa: PLC0415
            ds = load_dataset(self.DATASET_NAME, split=self.SPLIT, streaming=False)
            instances = [dict(row) for row in ds]
            log.info("Downloaded %d ToolBench instances from HuggingFace.", len(instances))
            return instances[:limit] if limit else instances
        except ImportError:
            log.warning(
                "The 'datasets' package is not installed. "
                "Install it with: pip install datasets\n"
                "Falling back to the bundled 6-instance sample."
            )
            return self._bundled_sample()[:limit or 6]
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to download ToolBench: %s — using bundled sample.", exc)
            return self._bundled_sample()[:limit or 6]

    @staticmethod
    def _bundled_sample() -> List[Dict[str, Any]]:
        """Six representative tasks across three API categories."""
        return [
            {
                "instance_id": "weather_001",
                "tool_name": "Open-Meteo",
                "api_name": "get_current_weather",
                "category": "Weather",
                "query": "Get the current temperature and wind speed in Berlin, Germany.",
                "required_parameters": ["latitude", "longitude", "current_weather"],
                "optional_parameters": ["windspeed_unit", "temperature_unit"],
            },
            {
                "instance_id": "weather_002",
                "tool_name": "Open-Meteo",
                "api_name": "get_forecast",
                "category": "Weather",
                "query": "Fetch a 7-day hourly precipitation forecast for Tokyo.",
                "required_parameters": ["latitude", "longitude", "hourly", "forecast_days"],
                "optional_parameters": ["timezone"],
            },
            {
                "instance_id": "finance_001",
                "tool_name": "Alpha Vantage",
                "api_name": "get_daily_time_series",
                "category": "Finance",
                "query": "Retrieve the last 30 days of daily closing prices for AAPL.",
                "required_parameters": ["function", "symbol", "apikey"],
                "optional_parameters": ["outputsize", "datatype"],
            },
            {
                "instance_id": "finance_002",
                "tool_name": "Alpha Vantage",
                "api_name": "get_forex_rate",
                "category": "Finance",
                "query": "Get the current USD to EUR exchange rate.",
                "required_parameters": ["function", "from_currency", "to_currency", "apikey"],
                "optional_parameters": [],
            },
            {
                "instance_id": "maps_001",
                "tool_name": "OpenStreetMap Nominatim",
                "api_name": "geocode",
                "category": "Maps",
                "query": "Geocode the address '1600 Pennsylvania Ave NW, Washington, DC'.",
                "required_parameters": ["q", "format"],
                "optional_parameters": ["limit", "addressdetails"],
            },
            {
                "instance_id": "maps_002",
                "tool_name": "OpenStreetMap Nominatim",
                "api_name": "reverse_geocode",
                "category": "Maps",
                "query": "Reverse geocode coordinates (48.8584, 2.2945) to get the address.",
                "required_parameters": ["lat", "lon", "format"],
                "optional_parameters": ["zoom"],
            },
        ]

    def to_cluster_sequence(
        self,
        tasks: Optional[List["AdapterTaskSpec"]] = None,
        limit: Optional[int] = None,
    ) -> List["AdapterTaskSpec"]:
        """Interleave tasks across API clusters for maximal KRR opportunity."""
        from scripts.adapters import AdapterBase  # noqa: PLC0415

        class _Tmp(AdapterBase):
            dataset_name = "toolbench"
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
        description="ToolBench → ActionCloud task importer"
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Preview task conversion without saving.")
    p.add_argument("--output", default="toolbench_tasks.json",
                   help="Output JSON file path.")
    p.add_argument("--limit", type=int, default=None,
                   help="Max number of tasks to load.")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _parse_args(argv)
    adapter = ToolBenchAdapter()

    if args.dry_run:
        tasks = adapter.load_tasks(limit=args.limit or 6)
        print(f"\n=== ToolBench — {len(tasks)} tasks (dry run) ===\n")
        for i, t in enumerate(tasks, 1):
            print(f"[{i}] task_key={t.task_key!r}  instance={t.instance_id!r}")
            print(f"     tech={t.technologies}")
            print(f"     task={t.task[:100]!r}...")
            print()
        from collections import Counter  # noqa: PLC0415
        print("Cluster distribution:")
        for key, cnt in Counter(t.task_key for t in tasks).most_common():
            print(f"  {key}: {cnt} tasks")
        return

    adapter.save_json(args.output, limit=args.limit)


if __name__ == "__main__":
    main()
