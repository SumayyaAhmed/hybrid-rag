"""Voyage AI helpers: embed, rerank, count tokens. One client, created on first use."""

import time
from functools import cache

import voyageai
from voyageai.error import RateLimitError

from rag.config import settings
from rag.errors import UpstreamUnavailable


@cache
def voyage() -> voyageai.Client:
    if not settings.voyage_api_key:
        raise RuntimeError("VOYAGE_API_KEY is empty. Add it to .env (get one at dash.voyageai.com).")
    return voyageai.Client(api_key=settings.voyage_api_key)


def with_retry(call, retries: int = 6):
    """Without a payment method Voyage allows only 3 requests/min, so wait ~20s and try again."""
    for attempt in range(retries):
        try:
            return call()
        except RateLimitError as e:
            if attempt == retries - 1:
                raise UpstreamUnavailable("Voyage rate limit: still hit after retrying; try again in a minute.") from e
            print("Voyage rate limit hit, waiting 20s...")
            time.sleep(20)


@cache
def _tokenizer_client() -> voyageai.Client:
    # count_tokens runs locally (downloads the model's tokenizer once), so it needs no real key.
    return voyageai.Client(api_key=settings.voyage_api_key or "not-needed-for-tokenizing")


def count_tokens(text: str) -> int:
    return _tokenizer_client().count_tokens([text], model=settings.embed_model)


def embed(texts: list[str], input_type: str) -> list[list[float]]:
    """input_type is "document" when storing and "query" when searching."""
    vectors = []
    for i in range(0, len(texts), settings.embed_batch_size):
        batch = texts[i : i + settings.embed_batch_size]
        result = with_retry(lambda: voyage().embed(batch, model=settings.embed_model, input_type=input_type, output_dimension=settings.embed_dim))
        vectors.extend(result.embeddings)
    return vectors


def rerank(query: str, documents: list[str]) -> list[float]:
    """Relevance score (0-1) for each document, in the same order as `documents`."""
    if not documents:
        return []
    result = with_retry(lambda: voyage().rerank(query, documents, model=settings.rerank_model))
    scores = [0.0] * len(documents)
    for r in result.results:  # results come back sorted best-first; r.index points into `documents`
        scores[r.index] = r.relevance_score
    return scores
