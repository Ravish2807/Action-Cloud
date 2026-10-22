"""Low-cardinality ActionCloud business metrics for Prometheus scrapes."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from prometheus_client.core import GaugeMetricFamily

log = logging.getLogger(__name__)


class ActionCloudMetricsCollector:
    """Cache DB-derived metrics between scrapes to avoid repeated full scans."""

    cache_seconds = 60.0

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_load = 0.0
        self._snapshot: dict[str, Any] | None = None

    def _metrics(self) -> dict[str, Any] | None:
        with self._lock:
            now = time.monotonic()
            if self._snapshot is not None and now - self._last_load < self.cache_seconds:
                return self._snapshot
            try:
                from .metrics import MetricCalculator

                self._snapshot = MetricCalculator.calculate_run_metrics()
                self._last_load = now
            except Exception:  # noqa: BLE001 - scrape remains available if the DB is down
                log.exception("could not refresh ActionCloud Prometheus business metrics")
            return self._snapshot

    def collect(self):
        snapshot = self._metrics()
        if snapshot is None:
            return

        systems = snapshot.get("systems", {})
        for metric_key, metric_name, help_text in (
            ("success_rate_pct", "actioncloud_task_success_rate_percent", "Task success rate by system."),
            ("avg_latency_ms", "actioncloud_task_latency_milliseconds", "Mean task latency by system."),
            ("avg_tokens_per_task", "actioncloud_tokens_per_task", "Mean tokens used per task by system."),
        ):
            family = GaugeMetricFamily(metric_name, help_text, labels=["system"])
            for system, values in systems.items():
                value = values.get(metric_key)
                if value is not None:
                    family.add_metric([str(system)], float(value))
            yield family

        savings = snapshot.get("comparative_metrics", {}).get("token_savings_pct")
        if savings is not None:
            family = GaugeMetricFamily(
                "actioncloud_token_savings_percent",
                "Token savings of ActionCloud relative to the baseline system.",
            )
            family.add_metric([], float(savings))
            yield family

        tier_family = GaugeMetricFamily(
            "actioncloud_memories_by_tier",
            "Stored memory count by governance tier.",
            labels=["tier"],
        )
        for tier, values in snapshot.get("governance_tier_distribution", {}).items():
            tier_family.add_metric([str(tier)], float(values.get("count", 0)))
        yield tier_family
