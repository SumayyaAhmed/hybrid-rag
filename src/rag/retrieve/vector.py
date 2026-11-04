"""Semantic search with pgvector: nearest embeddings by cosine distance."""

import numpy as np
from psycopg import Connection, sql

TABLES = {"pdf_chunks", "products"}


def vector_search(conn: Connection, table: str, query_vec: list[float], k: int) -> list[tuple[int, float]]:
    """Returns [(id, cosine similarity), ...] best first."""
    assert table in TABLES
    # `<=>` is cosine distance; it matches the HNSW index (vector_cosine_ops), so the index is used.
    query = sql.SQL("""SELECT id, 1 - (embedding <=> %(q)s) AS similarity
                       FROM {table}
                       ORDER BY embedding <=> %(q)s
                       LIMIT %(k)s""").format(table=sql.Identifier(table))
    return conn.execute(query, {"q": np.array(query_vec), "k": k}).fetchall()
