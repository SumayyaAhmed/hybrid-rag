"""baseline: vector extension + documents, pdf_chunks, products

Spec: specs/00-overview.md (Phase 0 schema). This is the former db/init/001_extensions.sql + 002_schema.sql, unchanged.
A database created before Alembic already has all of this: run `alembic stamp 0001` on it instead of upgrading.

Revision ID: 0001
Revises:
Create Date: 2026-11-04
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("""
    CREATE TABLE documents (
      id          BIGSERIAL PRIMARY KEY,
      filename    TEXT NOT NULL,
      sha256      TEXT NOT NULL UNIQUE,          -- idempotency: same file never ingested twice
      page_count  INT,
      ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """)

    op.execute("""
    CREATE TABLE pdf_chunks (
      id            BIGSERIAL PRIMARY KEY,
      document_id   BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      chunk_index   INT NOT NULL,
      page_start    INT NOT NULL,
      page_end      INT NOT NULL,
      section_title TEXT,
      content       TEXT NOT NULL,
      token_count   INT NOT NULL,
      embedding     vector(1024) NOT NULL,
      tsv tsvector GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(section_title, '')), 'A') ||
            setweight(to_tsvector('english', content), 'B')
          ) STORED,                               -- PG18 defaults to VIRTUAL; STORED is required to index it
      UNIQUE (document_id, chunk_index)
    )
    """)
    op.execute("CREATE INDEX pdf_chunks_embedding_idx ON pdf_chunks USING hnsw (embedding vector_cosine_ops)")
    op.execute("CREATE INDEX pdf_chunks_tsv_idx       ON pdf_chunks USING gin (tsv)")

    op.execute("""
    CREATE TABLE products (
      id           BIGSERIAL PRIMARY KEY,
      sku          TEXT NOT NULL UNIQUE,
      name         TEXT NOT NULL,
      brand        TEXT,
      category     TEXT,
      price        NUMERIC(10,2),
      currency     TEXT NOT NULL DEFAULT 'USD',
      in_stock     BOOLEAN,
      attributes   JSONB NOT NULL DEFAULT '{}',   -- any extra columns (color, size, material…)
      description  TEXT,
      search_text  TEXT NOT NULL,                 -- rendered text used for embedding AND reranking
      content_hash TEXT NOT NULL,                 -- skip re-embedding unchanged rows
      embedding    vector(1024) NOT NULL,
      tsv tsvector GENERATED ALWAYS AS (
            setweight(to_tsvector('simple',  sku), 'A') ||               -- 'simple' = no stemming for codes
            setweight(to_tsvector('english', name), 'A') ||
            setweight(to_tsvector('english', coalesce(brand, '') || ' ' || coalesce(category, '')), 'B') ||
            setweight(to_tsvector('english', coalesce(description, '')), 'C')
          ) STORED,
      updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """)
    op.execute("CREATE INDEX products_embedding_idx ON products USING hnsw (embedding vector_cosine_ops)")
    op.execute("CREATE INDEX products_tsv_idx       ON products USING gin (tsv)")
    op.execute("CREATE INDEX products_category_idx  ON products (category)")
    op.execute("CREATE INDEX products_price_idx     ON products (price)")


def downgrade() -> None:
    op.execute("DROP TABLE products, pdf_chunks, documents")
    op.execute("DROP EXTENSION vector")
