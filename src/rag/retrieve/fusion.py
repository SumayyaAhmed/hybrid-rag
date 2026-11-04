"""Reciprocal Rank Fusion: merge ranked lists using only rank positions, not raw scores."""

from collections import defaultdict


def rrf(ranked_lists: dict[str, list[str]], k: int = 60) -> dict[str, float]:
    """{"vec_pdf": ["pdf:3", "pdf:9"], ...} -> {"pdf:3": 0.032, ...} sorted best first.

    Each list adds 1 / (k + rank) for every key it contains, so a key found by several
    searches collects several contributions. Ties are broken by key for a stable order.
    """
    scores: dict[str, float] = defaultdict(float)
    for keys in ranked_lists.values():
        for rank, key in enumerate(keys, start=1):
            scores[key] += 1.0 / (k + rank)
    return dict(sorted(scores.items(), key=lambda item: (-item[1], item[0])))
