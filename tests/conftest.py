"""Test setup. Integration tests (marker `db`) run against a separate `rag_test` database, never the real `rag` one.

Order matters: rag.db opens its connection pool at import time, so DATABASE_URL is pointed at rag_test and
rag_test is created + migrated in pytest_sessionstart, before any test module (and thus rag.db) is imported.
"""

import hashlib
import os

import numpy as np
import psycopg
import pytest

ADMIN_URL = os.environ.get("TEST_ADMIN_DATABASE_URL", "postgresql://rag:rag@localhost:5432/rag")
TEST_DB = "rag_test"
TEST_URL = ADMIN_URL.rsplit("/", 1)[0] + f"/{TEST_DB}"
EMBED_DIM = 1024

os.environ["DATABASE_URL"] = TEST_URL   # env beats .env in pydantic-settings
db_ready = False                        # set in pytest_sessionstart; db tests skip when Postgres isn't running


def recreate_database(name: str) -> None:
    with psycopg.connect(ADMIN_URL, autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
        conn.execute(f"CREATE DATABASE {name}")


def alembic(command: str, revision: str, url: str) -> None:
    from alembic import command as alembic_command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = url
    getattr(alembic_command, command)(cfg, revision)


def pytest_sessionstart(session):
    global db_ready
    if session.config.getoption("markexpr") == "not db":
        return
    try:
        recreate_database(TEST_DB)
    except psycopg.OperationalError:
        return                          # no Postgres: db tests are skipped (see pytest_collection_modifyitems)
    alembic("upgrade", "head", TEST_URL)
    db_ready = True


def pytest_collection_modifyitems(config, items):
    if db_ready:
        return
    skip = pytest.mark.skip(reason="Postgres not reachable: run `make up` first")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)


# --- fakes for the hosted models (CI never calls Voyage or Gemini) ---------------------------------

def fake_embedding(text: str) -> list[float]:
    """Deterministic unit vector per text: same text -> same vector, different texts -> nearly orthogonal."""
    seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")
    v = np.random.default_rng(seed).standard_normal(EMBED_DIM)
    return (v / np.linalg.norm(v)).tolist()


class FakeEmbed:
    """Stands in for rag.clients.embed and counts how many texts it was asked to embed."""

    def __init__(self):
        self.calls = 0

    def __call__(self, texts: list[str], input_type: str) -> list[list[float]]:
        self.calls += 1
        return [fake_embedding(t) for t in texts]


def fake_rerank(relevant_word: str):
    """Stands in for rag.clients.rerank: 0.9 for texts containing the word, 0.1 otherwise (like Voyage's 0-1 scores)."""
    return lambda query, documents: [0.9 if relevant_word in d else 0.1 for d in documents]


def fake_count_tokens(text: str) -> int:
    return len(text.split())            # 1 word = 1 token; avoids downloading Voyage's tokenizer


@pytest.fixture(scope="session")
def ingested():
    """Ingest data/ (4 PDFs + catalogue) into rag_test once, with fake embeddings. Returns the first run's FakeEmbed."""
    from pathlib import Path

    from rag.ingest import pipeline

    fake = FakeEmbed()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(pipeline, "embed", fake)
        mp.setattr(pipeline, "count_tokens", fake_count_tokens)
        lines = pipeline.ingest(Path("data"))
    return fake, lines
