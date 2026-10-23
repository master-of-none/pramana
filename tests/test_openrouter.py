import asyncio
import json

import httpx
import pytest

from pramana import Retriever
from pramana.answering import (
    Answerer,
    AnswerError,
    OllamaProvider,
    OpenRouterProvider,
    provider_from_settings,
)
from pramana.errors import PramanaError
from pramana.models import ChatRequest, Focus

SCHEMA = {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]}


def transport(status=200, content='{"topic": "texts"}', seen=None, finish="stop"):
    def handle(request: httpx.Request):
        if seen is not None:
            seen.append(request)
        body = {"choices": [{"message": {"content": content}, "finish_reason": finish}]}
        return httpx.Response(status, json=body if status == 200 else {"error": "x"})

    return httpx.MockTransport(handle)


def test_requests_ask_for_json_schema_from_free_models_only():
    seen = []
    provider = OpenRouterProvider(key="k", model="org/model:free", transport=transport(seen=seen))
    assert asyncio.run(provider.chat([{"role": "user", "content": "q"}], SCHEMA)) == {
        "topic": "texts"
    }
    body = json.loads(seen[0].content)
    assert str(seen[0].url) == "https://openrouter.ai/api/v1/chat/completions"
    assert seen[0].headers["authorization"] == "Bearer k"
    assert body["model"] == "org/model:free"
    assert body["response_format"]["json_schema"]["schema"] == SCHEMA
    assert body["provider"] == {"require_parameters": True}
    with pytest.raises(PramanaError, match="Only free OpenRouter models"):
        OpenRouterProvider(key="k", model="org/paid-model")


def test_fenced_json_is_accepted_and_failures_are_actionable():
    fenced = OpenRouterProvider(
        key="k", model="m:free", transport=transport(content='```json\n{"topic": "x"}\n```')
    )
    assert asyncio.run(fenced.chat([], SCHEMA)) == {"topic": "x"}
    for status, code, words in (
        (429, 429, "free limit"),
        (401, 503, "API key"),
        (404, 503, "another free model"),
        (500, 503, "HTTP 500"),
    ):
        provider = OpenRouterProvider(key="k", model="m:free", transport=transport(status))
        with pytest.raises(AnswerError, match=words) as caught:
            asyncio.run(provider.chat([], SCHEMA))
        assert caught.value.status_code == code
    unfinished = OpenRouterProvider(key="k", model="m:free", transport=transport(finish="length"))
    with pytest.raises(AnswerError, match="did not finish"):
        asyncio.run(unfinished.chat([], SCHEMA))
    with pytest.raises(AnswerError, match="OPENROUTER_API_KEY") as caught:
        asyncio.run(OpenRouterProvider(key="", model="m:free").chat([], SCHEMA))
    assert caught.value.status_code == 503


def test_provider_is_chosen_explicitly(monkeypatch):
    monkeypatch.delenv("PRAMANA_PROVIDER", raising=False)
    assert isinstance(provider_from_settings(), OllamaProvider)
    monkeypatch.setenv("PRAMANA_PROVIDER", "openrouter")
    monkeypatch.setenv("PRAMANA_CHAT_MODEL", "org/model:free")
    assert isinstance(provider_from_settings(), OpenRouterProvider)
    monkeypatch.setenv("PRAMANA_PROVIDER", "cloud")
    with pytest.raises(PramanaError, match="Unknown PRAMANA_PROVIDER"):
        provider_from_settings()


class Hosted:
    """A hosted provider double: routes everything as on-topic, records answer calls."""

    hosted = True
    model = "m:free"

    def __init__(self):
        self.calls = []

    async def chat(self, messages, schema):
        if "topic" in schema["properties"]:
            return {"topic": "texts"}
        self.calls.append(messages)
        return {"answer": "Vishnu preserves.", "status": "grounded", "evidence_ids": ["E1"]}


def test_private_books_never_reach_a_hosted_model(indexed, embedder, tmp_path, make_chapter):
    private = make_chapter("Vishnu preserves the universe in the private book.", chapter="9")
    private.source = private.source.model_copy(update={"url": None, "local_path": "book.pdf"})
    private.document_id, private.document = "private-book", "Private Book"
    path = tmp_path / "private.jsonl"
    path.write_text(private.model_dump_json())
    indexed.import_jsonl(path)
    indexed.index(embedder=embedder)
    retriever = Retriever(indexed, embedder=embedder)
    provider = Hosted()
    answer = asyncio.run(
        Answerer(retriever, provider=provider).answer(ChatRequest(message="Vishnu preserves"))
    )
    sent = json.dumps(provider.calls)
    assert "private book" not in sent and "Private Book" not in sent
    # Control: a local provider is given the same private passage.
    local = Hosted()
    local.hosted = False
    asyncio.run(Answerer(retriever, provider=local).answer(ChatRequest(message="Vishnu preserves")))
    assert "private book" in json.dumps(local.calls)
    assert all(e.passage.citation.source_local_path is None for e in answer.evidence)
    with pytest.raises(AnswerError, match="private local book") as caught:
        focus = Focus(chapter_id=private.id, start=0, end=10)
        asyncio.run(
            Answerer(retriever, provider=provider).answer(
                ChatRequest(message="Explain", focus=focus)
            )
        )
    assert caught.value.status_code == 403
