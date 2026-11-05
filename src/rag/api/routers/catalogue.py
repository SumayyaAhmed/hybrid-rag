"""Plain database browsing (no AI): products and ingested documents."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from psycopg.rows import dict_row

from rag.api.dependencies import DbConn
from rag.api.schemas import Chunk, Document, Product

router = APIRouter(tags=["catalogue"])

PRODUCT_COLUMNS = "sku, name, brand, category, price, currency, in_stock, attributes, description"


@router.get("/products")
def list_products(
    conn: DbConn,
    category: str | None = None,
    in_stock: bool | None = None,
    max_price: Annotated[Decimal | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Product]:
    """`category` matches from the start: "Footwear" also returns "Footwear > Running"."""
    where, params = [], {"limit": limit, "offset": offset}
    if category is not None:
        where.append("category ILIKE %(category)s")
        params["category"] = category + "%"
    if in_stock is not None:
        where.append("in_stock = %(in_stock)s")
        params["in_stock"] = in_stock
    if max_price is not None:
        where.append("price <= %(max_price)s")
        params["max_price"] = max_price
    # only fixed SQL fragments are joined in; every user value goes through %(...)s parameters
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            f"SELECT {PRODUCT_COLUMNS} FROM products {where_sql} ORDER BY sku LIMIT %(limit)s OFFSET %(offset)s", params
        ).fetchall()
    return [Product(**row) for row in rows]


@router.get("/products/{sku}")
def get_product(sku: str, conn: DbConn) -> Product:
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute(f"SELECT {PRODUCT_COLUMNS} FROM products WHERE sku = %s", (sku,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"no product with SKU {sku}")
    return Product(**row)


@router.get("/documents")
def list_documents(conn: DbConn) -> list[Document]:
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """SELECT d.id, d.filename, d.page_count, d.ingested_at, count(c.id) AS chunks
               FROM documents d LEFT JOIN pdf_chunks c ON c.document_id = d.id
               GROUP BY d.id ORDER BY d.filename"""
        ).fetchall()
    return [Document(**row) for row in rows]


@router.get("/documents/{document_id}/chunks")
def list_chunks(document_id: int, conn: DbConn) -> list[Chunk]:
    if conn.execute("SELECT 1 FROM documents WHERE id = %s", (document_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail=f"no document with id {document_id}")
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """SELECT id, chunk_index, page_start, page_end, section_title, content, token_count
               FROM pdf_chunks WHERE document_id = %s ORDER BY chunk_index""",
            (document_id,),
        ).fetchall()
    return [Chunk(**row) for row in rows]
