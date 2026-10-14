#!/usr/bin/env python3
"""Run a repeatable in-memory poisoning resistance simulation."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from actioncloud.judge import MemoryJudge  # noqa: E402
from actioncloud.schema import MemoryTier  # noqa: E402


def run(poison_rate: float, memories: int, seed: int) -> dict:
    rng = random.Random(seed)
    reached_shared = quarantined = 0
    for _ in range(memories):
        poisoned = rng.random() < poison_rate
        tier, successes = MemoryTier.AGENT, 0
        if poisoned:
            # One initial successful reuse promotes; subsequent failures expose poison.
            tier, successes = MemoryTier.SHARED, 1
            reached_shared += 1
            for n in range(2, 5):
                decision = MemoryJudge.decide(tier, 0.5, n, successes)
                if decision:
                    tier = decision[0]
        else:
            tier = MemoryTier.SHARED
        quarantined += tier is MemoryTier.PRIVATE
    return {"poison_rate": poison_rate, "memories": memories, "reached_shared": reached_shared,
            "quarantined": quarantined,
            "poison_resistance": quarantined / reached_shared if reached_shared else 1.0}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--poison-rate", type=float, default=0.2)
    p.add_argument("--memories", type=int, default=1000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", default="adversarial_report")
    a = p.parse_args()
    if not 0 <= a.poison_rate <= 0.5 or a.memories < 1:
        p.error("poison rate must be in [0, 0.5] and memories must be positive")
    result = run(a.poison_rate, a.memories, a.seed)
    base = Path(a.output)
    base.with_suffix(".json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    base.with_suffix(".md").write_text("# Adversarial memory report\n\n" +
        "\n".join(f"- **{k.replace('_', ' ').title()}:** {v}" for k, v in result.items()) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
