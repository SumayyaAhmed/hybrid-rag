"""API endpoints against the rag_test database (spec 10). Voyage and Gemini are faked."""

import pytest
from conftest import FakeEmbed, fake_rerank
from fastapi.testclient import TestClient

from rag.api.main import app
from rag.generate import answer as answer_module
from rag.retrieve import pipeline, rerank

pytestmark = pytest.mark.db

client = TestClient(app)


def test_health(ingested):
    assert client.get("/health").json() == {"status": "ok", "database": "ok", "schema_revision": "0002"}


def test_stats(ingested):
    stats = client.get("/stats").json()
    assert (stats["documents"], stats["products"]) == (4, 15)
    assert stats["pdf_chunks"] > 0


def test_product_by_sku(ingested):
    response = client.get("/products/00123")
    assert response.status_code == 200
    assert response.json()["name"] == "Trailblaze Running Shoe"
    assert client.get("/products/99999").status_code == 404


def test_product_filters(ingested):
    footwear = client.get("/products", params={"category": "footwear"}).json()     # prefix, case-insensitive
    assert footwear and all(p["category"].startswith("Footwear") for p in footwear)
    cheap = client.get("/products", params={"max_price": 50}).json()
    assert cheap and all(float(p["price"]) <= 50 for p in cheap)
    assert len(client.get("/products", params={"limit": 3}).json()) == 3
    assert client.get("/products", params={"limit": 101}).status_code == 422


def test_documents_and_chunks(ingested):
    documents = client.get("/documents").json()
    assert len(documents) == 4
    chunks = client.get(f"/documents/{documents[0]['id']}/chunks").json()
    assert len(chunks) == documents[0]["chunks"]
    assert client.get("/documents/999999/chunks").status_code == 404


def test_search_with_explain(ingested, monkeypatch):
    monkeypatch.setattr(pipeline, "embed", FakeEmbed())
    monkeypatch.setattr(rerank, "voyage_rerank", fake_rerank("00123"))
    body = client.post("/search", json={"query": "SKU 00123", "explain": True}).json()
    assert body["hits"][0]["metadata"]["sku"] == "00123"
    assert set(body["explain"]["searches"]) == {"vec_pdf", "vec_prod", "bm25_pdf", "bm25_prod"}
    assert body["explain"]["fused"] and body["explain"]["reranked"]


def test_ask_end_to_end(ingested, monkeypatch):
    """Real retrieval + prompt building over rag_test; only the three hosted calls are faked."""
    monkeypatch.setattr(pipeline, "embed", FakeEmbed())
    monkeypatch.setattr(rerank, "voyage_rerank", fake_rerank("00123"))
    monkeypatch.setattr(answer_module, "complete", lambda system, user: "The Trailblaze costs 89.99 USD [S1].")
    body = client.post("/ask", json={"query": "How much is SKU 00123?"}).json()
    assert body["used_llm"] is True
    assert body["sources"][0]["label"] == "Trailblaze Running Shoe (SKU 00123)"
