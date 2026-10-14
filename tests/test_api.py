from fastapi.testclient import TestClient

from pramana import Retriever
from pramana.api import create_app
from pramana.corpus import Corpus


def test_search_context_and_errors(indexed, embedder):
    client = TestClient(create_app(retriever=Retriever(indexed, embedder=embedder)))
    assert client.get("/api/status").json()["indexed"]
    response = client.post("/api/search", json={"query": "Vishnu"})
    assert response.status_code == 200
    passage = response.json()[0]["passage"]
    context = client.get(f"/api/chapters/{passage['chapter_id']}?passage_id={passage['id']}")
    assert context.status_code == 200
    assert context.json()["chapter"]["text"][passage["start"] : passage["end"]] == passage["text"]
    assert client.get("/api/chapters/missing").status_code == 404
    other = next(c for c in indexed.store.chapters() if c.id != passage["chapter_id"])
    assert client.get(f"/api/chapters/{other.id}?passage_id={passage['id']}").status_code == 422
    assert client.post("/api/search", json={"query": "Vishnu", "limit": 100}).status_code == 422
    assert (
        client.post("/api/search", json={"query": "Vishnu", "strategy": "unknown"}).status_code
        == 422
    )


def test_empty_library_returns_setup_instructions(tmp_path):
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/status").json()["chapters"] == 0
    response = client.post("/api/search", json={"query": "Vishnu"})
    assert response.status_code == 409
    assert "pramana index" in response.json()["detail"]
    assert Corpus(tmp_path).store.status()["passages"] == 0
