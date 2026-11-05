"""/ask: the same as one turn of the chat loop (app.py)."""

from fastapi import APIRouter

from rag.api.schemas import AskRequest, AskResponse
from rag.generate.answer import answer

router = APIRouter(tags=["chat"])


@router.post("/ask")
def ask(body: AskRequest) -> AskResponse:
    """Answer a shopper question with cited sources. Nothing relevant found -> fallback text, `used_llm: false` (still 200)."""
    result = answer(body.query)
    return AskResponse(
        answer=result.text,
        sources=result.sources,
        used_llm=result.used_llm,
        context=result.context if body.show_context else None,
    )
