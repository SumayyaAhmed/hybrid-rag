from typing import Literal

from pydantic import BaseModel


class Hit(BaseModel):
    key: str                          # "pdf:123" or "prod:45" — one id space across both tables
    source: Literal["pdf", "product"]
    text: str                         # pdf section + content, or product search_text
    metadata: dict                    # filename/pages/section, or sku/price/in_stock…
    ranks: dict = {}                  # {"vec_pdf": 3, "bm25_pdf": 1, …} for --explain
    rrf_score: float = 0.0
    rerank_score: float | None = None
