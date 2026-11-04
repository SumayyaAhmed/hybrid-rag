"""Rerank candidates with Voyage's reranker (a hosted cross-encoder), then apply the min-score filter."""

from rag.clients import rerank as voyage_rerank
from rag.retrieve.models import Hit


def rerank(query: str, candidates: list[Hit]) -> list[Hit]:
    """Sets hit.rerank_score (0-1) on every candidate and returns them sorted best first."""
    scores = voyage_rerank(query, [hit.text for hit in candidates])
    for hit, score in zip(candidates, scores):
        hit.rerank_score = score
    return sorted(candidates, key=lambda h: -h.rerank_score)


def apply_min_score(reranked: list[Hit], min_score: float, top_n: int) -> list[Hit]:
    """Drop weak hits. An empty result means "nothing relevant", and generation won't call the LLM."""
    return [h for h in reranked if h.rerank_score >= min_score][:top_n]
