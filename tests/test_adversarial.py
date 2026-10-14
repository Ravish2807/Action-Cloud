"""Governance behavior under deliberately poisoned reuse outcomes."""
from actioncloud.judge import MemoryJudge
from actioncloud.schema import MemoryTier


def test_poisoned_shared_memory_is_quarantined_after_three_failures():
    tier = MemoryTier.SHARED
    for count in range(1, 4):
        result = MemoryJudge.decide(tier, 0.6, count, 0)
        if result:
            tier = result[0]
    assert tier is MemoryTier.PRIVATE


def test_quarantine_is_terminal_for_automatic_promotion():
    assert MemoryJudge.decide(MemoryTier.PRIVATE, 0.3, 10, 10) is None


def test_confidence_filter_excludes_untrusted_candidate():
    from actioncloud.builder import CompactContextBuilder
    from actioncloud.policy import MemorySelectionPolicy
    candidate = {"id": "00000000-0000-0000-0000-000000000001", "task": "task",
                 "solution": "bad", "success": True, "tier": "shared", "confidence": 0.2,
                 "relevance": 0.9}
    context, ids, count, final_count = CompactContextBuilder.build_context(
        [candidate], MemorySelectionPolicy(min_confidence=0.5))
    assert not context and not ids and count == 1 and final_count == 0
