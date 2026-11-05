"""Request and response models. FastAPI uses them to validate input (bad body -> 422), filter output and build /docs."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from rag.generate.answer import Source
from rag.retrieve.models import Hit

# stripped first, so "   " counts as empty and is rejected
Query = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


# --- system ----------------------------------------------------------------------
class Health(BaseModel):
    status: Literal["ok"]
    database: Literal["ok"]
    schema_revision: str | None      # Alembic revision the DB is on, e.g. "0002"


class Stats(BaseModel):
    documents: int
    pdf_chunks: int
    products: int


# --- chat --------------------------------------------------------------------------
class AskRequest(BaseModel):
    query: Query
    show_context: bool = False       # include exactly what the LLM received


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]            # only the sources the answer actually cites
    used_llm: bool                   # False = nothing relevant found, fallback text returned
    context: str | None = None


# --- retrieval ---------------------------------------------------------------------
class SearchRequest(BaseModel):
    query: Query
    explain: bool = False            # include every stage, like `rag search --explain`


class RankedKey(BaseModel):
    key: str                         # "pdf:12" / "prod:3"
    score: float


class Explain(BaseModel):
    searches: dict[str, list[RankedKey]]   # vec_pdf, vec_prod, bm25_pdf, bm25_prod: raw scores, best first
    fused: list[RankedKey]                 # RRF scores, best first
    reranked: list[Hit]                    # every candidate with its rerank score (kept or not)


class SearchResponse(BaseModel):
    hits: list[Hit]                  # the final kept hits (what /ask would send to the LLM)
    explain: Explain | None = None


# --- catalogue -------------------------------------------------------------------------
class Product(BaseModel):
    sku: str
    name: str
    brand: str | None
    category: str | None
    price: Decimal | None
    currency: str
    in_stock: bool | None
    attributes: dict
    description: str | None


class Document(BaseModel):
    id: int
    filename: str
    page_count: int | None
    chunks: int
    ingested_at: datetime


class Chunk(BaseModel):
    id: int
    chunk_index: int
    page_start: int
    page_end: int
    section_title: str | None
    content: str
    token_count: int


# --- admin -----------------------------------------------------------------------------
class IngestRequest(BaseModel):
    only: Literal["pdf", "catalogue"] | None = None


class IngestResponse(BaseModel):
    lines: list[str]                 # one summary line per file, same as `rag ingest`
