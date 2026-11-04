"""The min-score filter is what makes "no answer" possible (spec 02, section 2E)."""

from helpers import pdf_hit

from rag.retrieve.rerank import apply_min_score


def test_hits_below_min_score_are_dropped():
    hits = [pdf_hit(1, score=0.9), pdf_hit(2, score=0.49), pdf_hit(3, score=0.5)]
    assert [h.key for h in apply_min_score(hits, min_score=0.5, top_n=6)] == ["pdf:1", "pdf:3"]


def test_capped_at_top_n_and_order_kept():
    hits = [pdf_hit(i, score=1 - i / 10) for i in range(1, 6)]   # already sorted best first, like rerank() returns
    assert [h.key for h in apply_min_score(hits, min_score=0.0, top_n=3)] == ["pdf:1", "pdf:2", "pdf:3"]


def test_all_weak_hits_give_empty_result():
    hits = [pdf_hit(1, score=0.45), pdf_hit(2, score=0.1)]
    assert apply_min_score(hits, min_score=0.5, top_n=6) == []
