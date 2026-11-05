"""/search: retrieval only (no LLM), the same as `rag search [--explain]`."""

from fastapi import APIRouter

from rag.api.schemas import Explain, RankedKey, SearchRequest, SearchResponse
from rag.retrieve.pipeline import run

router = APIRouter(tags=["retrieval"])


@router.post("/search")
def search(body: SearchRequest) -> SearchResponse:
    """The hits that /ask would send to the LLM. With `explain: true`, every stage: 4 searches -> RRF -> rerank."""
    trace = run(body.query)
    explain = None
    if body.explain:
        explain = Explain(
            searches={name: [RankedKey(key=k, score=s) for k, s in results] for name, results in trace.searches.items()},
            fused=[RankedKey(key=k, score=s) for k, s in trace.fused.items()],
            reranked=trace.reranked,
        )
    return SearchResponse(hits=trace.kept, explain=explain)
