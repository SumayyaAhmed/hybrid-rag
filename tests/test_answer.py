"""Generation logic around the LLM call (spec 03). The LLM itself is faked: no Gemini calls."""

from helpers import pdf_hit, product_hit

from rag.generate import answer as answer_module
from rag.generate.answer import FALLBACK, answer_from_hits, cited_tags


def test_cited_tags_parses_single_and_grouped_tags():
    text = "Returns take 30 days [S1]. The shoe costs 89.99 USD [S2, S3]. See also [note]."
    assert cited_tags(text) == {"S1", "S2", "S3"}


def test_no_hits_gives_fallback_without_calling_the_llm(monkeypatch):
    def must_not_be_called(*args):
        raise AssertionError("LLM was called although retrieval found nothing")

    monkeypatch.setattr(answer_module, "complete", must_not_be_called)
    result = answer_from_hits("do you sell lawnmowers?", [])
    assert result.text == FALLBACK
    assert result.used_llm is False
    assert result.sources == []


def test_only_cited_sources_are_returned(monkeypatch):
    monkeypatch.setattr(answer_module, "complete", lambda system, user: "It costs 89.99 USD [S2].")
    result = answer_from_hits("how much is the Trailblaze?", [pdf_hit(1), product_hit(7)])
    assert result.used_llm is True
    assert [(s.tag, s.key, s.label) for s in result.sources] == [("S2", "prod:7", "Trailblaze Running Shoe (SKU 00123)")]
    assert "[S1]" in result.context and "[S2]" in result.context   # context = exactly what the LLM received
