"""answer(query): retrieve -> (nothing found? fixed reply) -> prompt the LLM -> collect cited sources."""

import re

from pydantic import BaseModel

from rag.generate.llm import complete
from rag.generate.prompts import SYSTEM_PROMPT, build_user_message, source_label
from rag.retrieve.models import Hit
from rag.retrieve.pipeline import retrieve

FALLBACK = "I couldn't find that in our catalogue or policies. Could you rephrase or tell me more?"


class Source(BaseModel):
    tag: str      # "S1"
    key: str      # "pdf:123" / "prod:45"
    label: str    # "returns_policy.pdf p.1" / "Trailblaze Running Shoe (SKU 00123)"


class Answer(BaseModel):
    text: str
    sources: list[Source]   # only the ones the LLM actually cited
    used_llm: bool          # False when retrieval returned nothing
    context: str = ""       # exactly what the LLM received (for --show-context)


def cited_tags(text: str) -> set[str]:
    """Finds S1, S2 inside [S1], [S2] and also [S1, S3]."""
    return {tag for bracket in re.findall(r"\[([^\]]+)\]", text) for tag in re.findall(r"S\d+", bracket)}


def answer(query: str) -> Answer:
    return answer_from_hits(query, retrieve(query))


def answer_from_hits(query: str, hits: list[Hit]) -> Answer:
    if not hits:
        # No LLM call -> no hallucination, no cost. This is what RERANK_MIN_SCORE buys us.
        return Answer(text=FALLBACK, sources=[], used_llm=False)

    user_message = build_user_message(query, hits)
    text = complete(SYSTEM_PROMPT, user_message)

    tags = cited_tags(text)
    sources = [
        Source(tag=f"S{i}", key=hit.key, label=source_label(hit))
        for i, hit in enumerate(hits, start=1)
        if f"S{i}" in tags
    ]
    return Answer(text=text, sources=sources, used_llm=True, context=user_message)
