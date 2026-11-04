"""Phase 2 wired together: 4 searches -> RRF -> rerank -> min-score filter, with fake embed + rerank (spec 02)."""

import pytest
from conftest import FakeEmbed

from rag.retrieve import pipeline, rerank

pytestmark = pytest.mark.db


def fake_rerank(relevant_word: str):
    """Scores 0.9 for texts containing the word, 0.1 otherwise (a stand-in for Voyage's cross-encoder)."""
    return lambda query, documents: [0.9 if relevant_word in d else 0.1 for d in documents]


def test_sku_query_end_to_end(ingested, monkeypatch):
    monkeypatch.setattr(pipeline, "embed", FakeEmbed())
    monkeypatch.setattr(rerank, "voyage_rerank", fake_rerank("00123"))
    trace = pipeline.run("SKU 00123")

    assert set(trace.searches) == {"vec_pdf", "vec_prod", "bm25_pdf", "bm25_prod"}
    assert trace.kept[0].metadata["sku"] == "00123"
    assert trace.kept[0].ranks["bm25_prod"] == 1      # --explain shows where each hit came from
    assert all(h.rerank_score >= 0.5 for h in trace.kept)


def test_out_of_scope_query_keeps_nothing(ingested, monkeypatch):
    monkeypatch.setattr(pipeline, "embed", FakeEmbed())
    monkeypatch.setattr(rerank, "voyage_rerank", fake_rerank("no-text-contains-this"))
    trace = pipeline.run("do you sell lawnmowers?")
    assert trace.reranked                              # candidates were found and scored...
    assert trace.kept == []                            # ...but all were below RERANK_MIN_SCORE
