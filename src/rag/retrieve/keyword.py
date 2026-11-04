"""Keyword search with BM25 (pg_textsearch `bm25` index + `<@>` operator). See specs/06-bm25-pg-textsearch.md."""

from psycopg import Connection, sql

# table -> (indexed expression, index name). The expression must match migration 0002 exactly,
# otherwise Postgres can't use the index.
BM25_INDEX = {
    "pdf_chunks": ("coalesce(section_title, '') || ' ' || content", "pdf_chunks_bm25_idx"),
    "products": ("search_text", "products_bm25_idx"),
}


def keyword_search(conn: Connection, table: str, query_text: str, k: int) -> list[tuple[int, float]]:
    """Returns [(id, BM25 score), ...] best first; only rows that contain at least one query word."""
    expr, index = BM25_INDEX[table]
    # <@> returns the BM25 score negated (so ascending ORDER BY = best first); flip it so higher = better.
    query = sql.SQL("""SELECT id, -(({expr}) <@> to_bm25query(%(query)s, {index})) AS score
                       FROM {table}
                       ORDER BY ({expr}) <@> to_bm25query(%(query)s, {index}), id
                       LIMIT %(k)s""").format(
        expr=sql.SQL(expr), index=sql.Literal(index), table=sql.Identifier(table)
    )
    rows = conn.execute(query, {"query": query_text, "k": k}).fetchall()
    return [(id_, score) for id_, score in rows if score > 0]  # the index also returns non-matching rows with score 0
