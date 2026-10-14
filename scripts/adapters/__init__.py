"""
ActionCloud — External Benchmark Adapter Base.

All dataset adapters (SWE-bench, ToolBench, etc.) implement AdapterBase so
the harness can consume them with a uniform interface:

    tasks = SWEBenchAdapter().load_tasks()          # list[TaskSpec]
    clusters = SWEBenchAdapter().to_cluster_sequence(tasks)  # grouped by task_key

Usage
-----
    from scripts.adapters.swebench_importer import SWEBenchAdapter
    from scripts.adapters.toolbench_importer import ToolBenchAdapter
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AdapterTaskSpec:
    """
    Universal task representation produced by any adapter.

    Compatible with `agents.base.TaskSpec` — can be converted via `.to_task_spec()`.
    """

    task: str
    task_key: str                          # Cluster identifier (e.g. repo/issue group)
    technologies: List[str] = field(default_factory=list)
    expected_tools: List[str] = field(default_factory=list)
    instance_id: Optional[str] = None     # Original dataset identifier
    metadata: Dict[str, Any] = field(default_factory=dict)  # Raw dataset fields

    def to_task_spec(self):
        """Convert to the harness-native TaskSpec."""
        # Import here to avoid circular deps when running standalone.
        from actioncloud.agents.base import TaskSpec  # noqa: PLC0415
        return TaskSpec(
            task=self.task,
            task_key=self.task_key,
            technologies=self.technologies,
            expected_tools=self.expected_tools,
            instance_id=self.instance_id,
        )


class AdapterBase(ABC):
    """
    Base class for all external dataset adapters.

    Subclasses must implement `load_tasks()`.  The `to_cluster_sequence()`
    default groups tasks by `task_key` and interleaves them so that tasks from
    the same cluster are spread across the sequence rather than batched — this
    maximises the opportunity for cross-task memory reuse within a run.
    """

    dataset_name: str = "unknown"

    @abstractmethod
    def load_tasks(self, limit: Optional[int] = None) -> List[AdapterTaskSpec]:
        """Load and return a flat list of AdapterTaskSpec instances."""

    def to_cluster_sequence(
        self,
        tasks: Optional[List[AdapterTaskSpec]] = None,
        limit: Optional[int] = None,
    ) -> List[AdapterTaskSpec]:
        """
        Interleaved sequence: tasks from the same cluster are spread out.

        Example with clusters A(3 tasks), B(2 tasks):
            Naïve: [A1, A2, A3, B1, B2]
            Interleaved: [A1, B1, A2, B2, A3]

        This interleaving is what triggers cross-task KRR measurement — Agent N
        sees a memory from A's first task when solving A's second task.
        """
        if tasks is None:
            tasks = self.load_tasks(limit=limit)

        # Group by task_key, preserving insertion order.
        buckets: Dict[str, List[AdapterTaskSpec]] = {}
        for t in tasks:
            buckets.setdefault(t.task_key, []).append(t)

        # Round-robin interleave.
        result: List[AdapterTaskSpec] = []
        active = list(buckets.values())
        while active:
            next_active = []
            for bucket in active:
                result.append(bucket.pop(0))
                if bucket:
                    next_active.append(bucket)
            active = next_active

        return result[:limit] if limit else result
