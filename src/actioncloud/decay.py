"""
ActionCloud — Memory Decay Scheduler.

Provides two independent decay mechanisms:

1. **TTL-based expiry** (``MEMORY_TTL_DAYS``):
   Any memory with ``expires_at < now()`` is quarantined to PRIVATE tier
   and marked as superseded.  The memory is NOT deleted — its audit trail
   is preserved and its author can still read it.

2. **Usage-frequency decay** (``MEMORY_DECAY_DAYS``):
   Any memory above AGENT that has not been reused in ``MEMORY_DECAY_DAYS``
   days is demoted ONE tier (ORGANIZATIONAL → VALIDATED → SHARED → AGENT).
   This prevents stale institutional knowledge from polluting retrieval
   without evidence of continued usefulness.

Both mechanisms write ``tier_transitions`` records (``decided_by='decay_scheduler'``)
so the governance audit trail is complete.

Usage
-----
    # One-shot manual pass (safe to run at any time):
    python -m actioncloud.decay

    # Import and call from a cron job or the API:
    from actioncloud.decay import run_decay_pass
    result = run_decay_pass()
    print(result)

    # From the REST API (POST /admin/decay):
    curl -X POST http://localhost:8000/admin/decay \\
         -H "X-API-Key: $ACTIONCLOUD_ADMIN_KEY"
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from .config import settings
from . import db

log = logging.getLogger(__name__)


def run_decay_pass(
    ttl_days: int | None = None,
    decay_days: int | None = None,
) -> Dict[str, Any]:
    """
    Execute one decay pass: TTL pruning followed by usage-frequency demotion.

    Parameters
    ----------
    ttl_days:
        Override for ``MEMORY_TTL_DAYS``. ``0`` disables TTL pruning.
        Defaults to ``settings.memory_ttl_days``.
    decay_days:
        Override for ``MEMORY_DECAY_DAYS``. ``0`` disables usage-frequency
        decay.  Defaults to ``settings.memory_decay_days``.

    Returns
    -------
    dict with keys:
        pruned_count   int  — memories quarantined by TTL expiry.
        demoted_count  int  — memories demoted by usage-frequency decay.
        ran_at         str  — ISO-8601 UTC timestamp of the pass.
        ttl_days       int  — effective TTL setting used.
        decay_days     int  — effective decay setting used.
    """
    effective_ttl = settings.memory_ttl_days if ttl_days is None else ttl_days
    effective_decay = settings.memory_decay_days if decay_days is None else decay_days

    pruned = 0
    demoted = 0

    if effective_ttl > 0:
        log.info("Memory decay: pruning memories expired after %d day(s).", effective_ttl)
        pruned = db.prune_expired_memories()
        log.info("Memory decay: pruned %d expired memories.", pruned)
    else:
        log.debug("Memory decay: TTL pruning disabled (MEMORY_TTL_DAYS=0).")

    if effective_decay > 0:
        log.info(
            "Memory decay: demoting memories not reused in %d day(s).", effective_decay
        )
        demoted = db.demote_stale_memories(effective_decay)
        log.info("Memory decay: demoted %d stale memories.", demoted)
    else:
        log.debug("Memory decay: usage-frequency decay disabled (MEMORY_DECAY_DAYS=0).")

    result = {
        "pruned_count": pruned,
        "demoted_count": demoted,
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "ttl_days": effective_ttl,
        "decay_days": effective_decay,
    }
    log.info("Memory decay pass complete: %s", result)
    return result


def _main() -> None:
    """CLI entry point: run a decay pass and print the result."""
    import json  # noqa: PLC0415
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    db.require_database()
    result = run_decay_pass()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    _main()
