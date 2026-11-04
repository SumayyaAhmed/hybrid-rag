# Postgres 18 + pgvector (base image) + pg_textsearch (BM25), built from source. See specs/06-bm25-pg-textsearch.md.
FROM pgvector/pgvector:pg18

ARG PG_TEXTSEARCH_VERSION=v1.5.1

# build tools are installed, used and removed in one layer, so they don't stay in the image
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential git ca-certificates postgresql-server-dev-18 \
 && git clone --depth 1 --branch ${PG_TEXTSEARCH_VERSION} https://github.com/timescale/pg_textsearch /tmp/pg_textsearch \
 && make -C /tmp/pg_textsearch \
 && make -C /tmp/pg_textsearch install \
 && rm -rf /tmp/pg_textsearch \
 && apt-get purge -y build-essential git postgresql-server-dev-18 \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*
