"""API unit tests (spec 10): no database, no API keys. The RAG functions behind the endpoints are faked.

TestClient is used without `with`, so the app's lifespan (DB check at startup) doesn't run here.
"""

from fastapi.testclient import TestClient

from rag.api.main import app
from rag.api.routers import chat
from rag.errors import UpstreamUnavailable
from rag.generate import answer as answer_module
from rag.generate.answer import FALLBACK, Answer, Source

client = TestClient(app)


def fake_answer(query: str) -> Answer:
    return Answer(text="You have 30 days [S1].", sources=[Source(tag="S1", key="pdf:1", label="returns_policy.pdf p.1")],
                  used_llm=True, context="<sources>…</sources>")


def test_ask_returns_answer_and_sources(monkeypatch):
    monkeypatch.setattr(chat, "answer", fake_answer)
    response = client.post("/ask", json={"query": "what is the return window?"})
    assert response.status_code == 200
    assert response.json() == {
        "answer": "You have 30 days [S1].",
        "sources": [{"tag": "S1", "key": "pdf:1", "label": "returns_policy.pdf p.1"}],
        "used_llm": True,
        "context": None,                       # only included when show_context is true
    }


def test_ask_show_context(monkeypatch):
    monkeypatch.setattr(chat, "answer", fake_answer)
    response = client.post("/ask", json={"query": "return window?", "show_context": True})
    assert response.json()["context"] == "<sources>…</sources>"


def test_ask_nothing_relevant_is_200_with_fallback(monkeypatch):
    monkeypatch.setattr(answer_module, "retrieve", lambda query: [])   # real answer(), retrieval finds nothing
    response = client.post("/ask", json={"query": "do you sell lawnmowers?"})
    assert response.status_code == 200
    assert response.json()["answer"] == FALLBACK
    assert response.json()["used_llm"] is False


def test_empty_or_missing_query_is_422():
    assert client.post("/ask", json={"query": "   "}).status_code == 422    # whitespace is stripped first
    assert client.post("/ask", json={}).status_code == 422
    assert client.post("/search", json={"query": "x" * 1001}).status_code == 422


def test_upstream_unavailable_is_503(monkeypatch):
    def quota_used_up(query):
        raise UpstreamUnavailable("Gemini daily free-tier quota is used up")

    monkeypatch.setattr(chat, "answer", quota_used_up)
    response = client.post("/ask", json={"query": "return window?"})
    assert response.status_code == 503
    assert response.json() == {"detail": "Gemini daily free-tier quota is used up"}
    assert response.headers["retry-after"] == "60"


def test_docs_and_openapi():
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/ask", "/search", "/products", "/products/{sku}", "/documents", "/documents/{document_id}/chunks",
            "/ingest", "/health", "/stats"} <= set(paths)
