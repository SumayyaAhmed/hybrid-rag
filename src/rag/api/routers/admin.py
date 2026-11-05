"""/ingest. No auth yet (spec 10, non-goals): only expose the API on localhost."""

from pathlib import Path

from fastapi import APIRouter

from rag.api.schemas import IngestRequest, IngestResponse
from rag.ingest.pipeline import ingest

router = APIRouter(tags=["admin"])

DATA_DIR = Path("data")


@router.post("/ingest")
def run_ingest(body: IngestRequest) -> IngestResponse:
    """Load new/changed PDFs and catalogue rows from data/. Unchanged files are skipped. Calls Voyage, so it can be slow."""
    return IngestResponse(lines=ingest(DATA_DIR, body.only))
