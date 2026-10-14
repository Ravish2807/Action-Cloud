from __future__ import annotations

from dataclasses import dataclass, field
import os
from .schema import MemoryTier


@dataclass
class MemorySelectionPolicy:
    """
    Configurable memory selection policy governing retrieval, filtering,
    redundancy elimination, and context token budgeting.
    """

    candidate_k: int = 10
    max_context_memories: int = 1
    # Calibrated on the 136-task benchmark with the hashing embedder
    # (query = task + technologies): 0.30 keeps ~91 % of same-family matches
    # while ~1 % of different-family pairs clear it. Re-calibrate with
    # scripts/calibrate_threshold.py if you switch embedding provider.
    similarity_threshold: float = 0.30
    redundancy_threshold: float = 0.85
    context_token_budget: int = 1000
    # Ranking bonus per unit of Memory-Judge confidence (0..1).
    trust_weight: float = 0.10
    # Memories whose outcome record has pushed confidence below this are not
    # injected. New successful memories start at 0.6; one failed outcome
    # report -> 0.40 (excluded); one success -> 0.73; 1 success + 1 failure
    # -> 0.55 (kept).
    min_confidence: float = 0.45
    # 0 = exact scoring of every visible row; N > 0 = HNSW pre-selects N
    # nearest neighbours first (use for stores beyond a few thousand rows).
    ann_candidates: int = 0
    min_tier: MemoryTier = MemoryTier.PRIVATE

    # Confidence calibration: memories above the boost threshold get a ranking
    # bonus; memories below the penalty threshold are down-ranked but still
    # returned (unless they are also below min_confidence, in which case they
    # are filtered out entirely).
    confidence_boost_threshold: float = 0.80   # High-confidence memories are preferred
    confidence_penalty_below: float = 0.50     # Low-confidence memories are down-ranked

    # When True, the context builder annotates each memory with its confidence
    # score so the agent can make an informed decision about trust level.
    annotate_confidence: bool = True

    @classmethod
    def from_env(cls) -> MemorySelectionPolicy:
        return cls(
            candidate_k=int(os.environ.get("MEMORY_CANDIDATE_K", "10")),
            max_context_memories=int(os.environ.get("MEMORY_MAX_CONTEXT_MEMORIES", "1")),
            similarity_threshold=float(os.environ.get("MEMORY_SIMILARITY_THRESHOLD", "0.30")),
            redundancy_threshold=float(os.environ.get("MEMORY_REDUNDANCY_THRESHOLD", "0.85")),
            context_token_budget=int(os.environ.get("MEMORY_CONTEXT_TOKEN_BUDGET", "1000")),
            trust_weight=float(os.environ.get("MEMORY_TRUST_WEIGHT", "0.10")),
            min_confidence=float(os.environ.get("MEMORY_MIN_CONFIDENCE", "0.45")),
            ann_candidates=int(os.environ.get("MEMORY_ANN_CANDIDATES", "0")),
            min_tier=MemoryTier(os.environ.get("MEMORY_MIN_TIER", "private")),
            confidence_boost_threshold=float(
                os.environ.get("MEMORY_CONFIDENCE_BOOST", "0.80")
            ),
            confidence_penalty_below=float(
                os.environ.get("MEMORY_CONFIDENCE_PENALTY", "0.50")
            ),
            annotate_confidence=os.environ.get(
                "MEMORY_ANNOTATE_CONFIDENCE", "true"
            ).strip().lower() in {"1", "true", "yes"},
        )
