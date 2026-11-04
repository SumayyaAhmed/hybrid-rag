"""retrieve(query): 4 searches (vector + BM25, each on both tables) -> RRF -> rerank -> min-score filter.

`run(query)` returns every intermediate stage (used by `rag search --explain`);
`retrieve(query)` returns just the final hits.
"""

from dataclasses import dataclass

from psycopg import Connection

from rag.clients import embed
from rag.config import settings
from rag.db import pool
from rag.retrieve.fusion import rrf
from rag.retrieve.keyword import keyword_search
from rag.retrieve.models import Hit
from rag.retrieve.rerank import apply_min_score, rerank
from rag.retrieve.vector import vector_search


@dataclass
class Trace:
    searches: dict[str, list[tuple[str, float]]]  # list name -> [(key, raw score)] best first
    fused: dict[str, float]                       # key -> RRF score, best first
    reranked: list[Hit]                           # all candidates with rerank scores
    kept: list[Hit]                               # final result


def fetch_hits(conn: Connection, keys: list[str]) -> dict[str, Hit]:
    """Load full rows for the given keys (one query per table)."""
    pdf_ids = [int(k.split(":")[1]) for k in keys if k.startswith("pdf:")]
    prod_ids = [int(k.split(":")[1]) for k in keys if k.startswith("prod:")]
    hits = {}
    for id_, section, content, filename, p_start, p_end in conn.execute(
        """SELECT c.id, c.section_title, c.content, d.filename, c.page_start, c.page_end
           FROM pdf_chunks c JOIN documents d ON d.id = c.document_id
           WHERE c.id = ANY(%s)""", (pdf_ids,)
    ):
        hits[f"pdf:{id_}"] = Hit(
            key=f"pdf:{id_}", source="pdf", text=f"{section or ''}\n{content}".strip(),
            metadata={"filename": filename, "page_start": p_start, "page_end": p_end, "section": section, "content": content},
        )
    for id_, sku, name, brand, category, price, currency, in_stock, attributes, description, search_text in conn.execute(
        """SELECT id, sku, name, brand, category, price, currency, in_stock, attributes, description, search_text
           FROM products WHERE id = ANY(%s)""", (prod_ids,)
    ):
        hits[f"prod:{id_}"] = Hit(
            key=f"prod:{id_}", source="product", text=search_text,
            metadata={"sku": sku, "name": name, "brand": brand, "category": category, "price": price,
                      "currency": currency, "in_stock": in_stock, "attributes": attributes, "description": description},
        )
    return hits


def run(query: str) -> Trace:
    query_vec = embed([query], input_type="query")[0]
    with pool.connection() as conn:
        searches = {
            "vec_pdf": [(f"pdf:{i}", s) for i, s in vector_search(conn, "pdf_chunks", query_vec, settings.k_vec)],
            "vec_prod": [(f"prod:{i}", s) for i, s in vector_search(conn, "products", query_vec, settings.k_vec)],
            "bm25_pdf": [(f"pdf:{i}", s) for i, s in keyword_search(conn, "pdf_chunks", query, settings.k_bm25)],
            "bm25_prod": [(f"prod:{i}", s) for i, s in keyword_search(conn, "products", query, settings.k_bm25)],
        }
        fused = rrf({name: [key for key, _ in results] for name, results in searches.items()}, k=settings.rrf_k)

        candidate_keys = list(fused)[: settings.rerank_candidates]
        rows = fetch_hits(conn, candidate_keys)

    candidates = []
    for key in candidate_keys:
        hit = rows[key]
        hit.rrf_score = fused[key]
        hit.ranks = {name: rank for name, results in searches.items() for rank, (k, _) in enumerate(results, start=1) if k == key}
        candidates.append(hit)

    reranked = rerank(query, candidates)
    kept = apply_min_score(reranked, settings.rerank_min_score, settings.final_top_n)
    return Trace(searches=searches, fused=fused, reranked=reranked, kept=kept)


def retrieve(query: str) -> list[Hit]:
    return run(query).kept
