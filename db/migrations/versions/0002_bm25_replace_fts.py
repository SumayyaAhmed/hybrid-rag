"""bm25 replace fts: pg_textsearch BM25 indexes instead of tsvector + GIN

Spec: specs/06-bm25-pg-textsearch.md
Needs the db/Dockerfile image (pg_textsearch installed + shared_preload_libraries=pg_textsearch).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-04
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_textsearch")

    # built-in FTS out (dropping the column also drops its GIN index)
    op.execute("ALTER TABLE pdf_chunks DROP COLUMN tsv")
    op.execute("ALTER TABLE products   DROP COLUMN tsv")

    # BM25 in. Queries must repeat the exact indexed expression (see retrieve/keyword.py).
    op.execute("""
    CREATE INDEX pdf_chunks_bm25_idx ON pdf_chunks
      USING bm25 ((coalesce(section_title, '') || ' ' || content)) WITH (text_config = 'english')
    """)
    op.execute("""
    CREATE INDEX products_bm25_idx ON products
      USING bm25 (search_text) WITH (text_config = 'english')
    """)


def downgrade() -> None:
    op.execute("DROP INDEX pdf_chunks_bm25_idx")
    op.execute("DROP INDEX products_bm25_idx")

    # same definitions as 0001; generated columns are recomputed from existing rows, so no re-ingest
    op.execute("""
    ALTER TABLE pdf_chunks ADD COLUMN tsv tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(section_title, '')), 'A') ||
        setweight(to_tsvector('english', content), 'B')
      ) STORED
    """)
    op.execute("CREATE INDEX pdf_chunks_tsv_idx ON pdf_chunks USING gin (tsv)")
    op.execute("""
    ALTER TABLE products ADD COLUMN tsv tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('simple',  sku), 'A') ||
        setweight(to_tsvector('english', name), 'A') ||
        setweight(to_tsvector('english', coalesce(brand, '') || ' ' || coalesce(category, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(description, '')), 'C')
      ) STORED
    """)
    op.execute("CREATE INDEX products_tsv_idx ON products USING gin (tsv)")
    # the extension stays installed: dropping it is harmless to skip, and other objects may use it
