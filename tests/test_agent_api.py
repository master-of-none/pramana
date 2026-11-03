import json

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from pramana import Corpus
from pramana import agent_excerpts as ex
from pramana.agent_api import AgentAuth, create_agent_app
from pramana.api import create_app
from pramana.cli import app as cli
from pramana.errors import PramanaError
from pramana.models import Location

TOKEN = "k" * 40
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
KATHA = (
    "SECOND VALLI\n\n"
    "1. Death said: 'The good is one thing, the pleasant another; these two, having different "
    "objects, chain a man.'\n\n"
    "2. 'The good and the pleasant approach man: the wise goes round about them and "
    "distinguishes them.'\n\n"
    "3. 'Thou, O Nakiketas, after pondering all pleasures that are or seem delightful, hast "
    "dismissed them all.'"
)
PROSE = (
    "The Self is the witness of all that is seen, free from change and from every limit of the "
    "mind. The student who has understood this lives without fear, and walks the world at "
    "peace with whatever comes to him. A single lamp lights a thousand lamps without loss."
)


def chapter(make_chapter, document_id, text, sections):
    c = make_chapter(text)
    c.document_id, c.document = document_id, document_id.title()
    c.location = Location(book="1", chapter="1", sections=sections)
    return c


def build(tmp_path, make_chapter, chapters):
    path = tmp_path / "in.jsonl"
    path.write_text("\n".join(c.model_dump_json() for c in chapters), encoding="utf-8")
    corpus = Corpus(tmp_path / "library")
    corpus.import_jsonl(path)
    return corpus


@pytest.fixture
def allow():
    return ex.parse_sources(
        {
            "groups": [
                {
                    "rights": "Test rights.",
                    "attribution": "Test attribution.",
                    "documents": [
                        {"id": "katha", "label": "Katha", "kinds": {"verse": "leading-number"}},
                        {"id": "prose", "kinds": {"passage": "windows", "sentence": "windows"}},
                    ],
                }
            ]
        }
    )


@pytest.fixture
def corpus(tmp_path, make_chapter):
    return build(
        tmp_path,
        make_chapter,
        [
            chapter(make_chapter, "katha", KATHA, ["I, 2"]),
            chapter(make_chapter, "prose", PROSE, ["Intro"]),
            chapter(make_chapter, "secret", KATHA, ["Z"]),  # imported, never listed
        ],
    )


@pytest.fixture
def client(corpus, allow):
    return TestClient(
        create_app(corpus.home, agent_auth=AgentAuth({"openclaw": TOKEN}), excerpt_sources=allow)
    )


def test_the_routes_are_off_until_a_token_is_configured(corpus, allow):
    off = TestClient(create_app(corpus.home, agent_auth=AgentAuth(), excerpt_sources=allow))
    response = off.get("/api/excerpts/today", headers=HEADERS)
    assert response.status_code == 404 and "PRAMANA_AGENT_TOKEN" in response.json()["detail"]


def test_a_missing_or_wrong_token_is_refused(client):
    assert client.get("/api/excerpts/today").status_code == 401
    wrong = client.get("/api/excerpts/today", headers={"Authorization": "Bearer nope"})
    assert wrong.status_code == 401 and wrong.headers["www-authenticate"] == "Bearer"
    assert client.get("/api/excerpts/sources").status_code == 401


def test_today_is_stable_and_carries_its_provenance(client):
    first = client.get("/api/excerpts/today?date=2026-11-02", headers=HEADERS).json()
    again = client.get("/api/excerpts/today?date=2026-11-02", headers=HEADERS).json()
    assert first == again and first["date"] == "2026-11-02"
    assert first["rights"] == "Test rights." and first["attribution"] == "Test attribution."
    assert first["boundary"] == ("printed" if first["kind"] == "verse" else "derived")
    assert first["pool"]["size"] == 6 and len(first["pool"]["version"]) == 12
    assert "secret" not in first["document"].lower()
    other = client.get("/api/excerpts/today?date=2026-11-03", headers=HEADERS).json()
    assert other["excerpt_id"] != first["excerpt_id"]
    seeded = client.get("/api/excerpts/today?date=2026-11-02&seed=x", headers=HEADERS).json()
    assert seeded["pool"]["version"] == first["pool"]["version"]


def test_the_listed_documents_only_reach_the_pool(client):
    report = client.get("/api/excerpts/sources", headers=HEADERS).json()
    assert {d["document_id"] for d in report["documents"]} == {"katha", "prose"}
    assert report["excerpts"] == 6
    katha = next(d for d in report["documents"] if d["document_id"] == "katha")
    assert katha["excerpts"] == {"verse": 3} and katha["rights"] == "Test rights."


def test_formats_return_a_message_ready_to_send(client):
    text = client.get("/api/excerpts/random?kind=verse&format=text", headers=HEADERS)
    assert text.headers["content-type"].startswith("text/plain")
    assert text.text.startswith("“") and "— Katha, I, 2," in text.text
    assert "1. Death" not in text.text and "\n\n" not in text.text.strip()
    markdown = client.get("/api/excerpts/random?kind=verse&format=markdown", headers=HEADERS)
    assert markdown.headers["content-type"].startswith("text/markdown")
    assert markdown.text.startswith("> ") and "**Katha, I, 2," in markdown.text
    assert client.get("/api/excerpts/random?format=xml", headers=HEADERS).status_code == 422


def test_kind_document_and_length_filters(client):
    for _ in range(5):
        assert (
            client.get("/api/excerpts/random?kind=verse", headers=HEADERS).json()["kind"] == "verse"
        )
    only = client.get("/api/excerpts/random?document=prose", headers=HEADERS).json()
    assert only["document"] == "Prose" and only["reference"] == "Prose, Intro"
    assert client.get("/api/excerpts/random?document=secret", headers=HEADERS).status_code == 422
    assert client.get("/api/excerpts/random?kind=poem", headers=HEADERS).status_code == 422
    assert client.get("/api/excerpts/random?min_chars=5000", headers=HEADERS).status_code == 404


def test_random_honours_exclude(client):
    everything = client.get("/api/excerpts/sources", headers=HEADERS).json()["excerpts"]
    seen: list[str] = []
    for _ in range(everything):
        query = "&".join(f"exclude={i}" for i in seen)
        seen.append(
            client.get(f"/api/excerpts/random?{query}", headers=HEADERS).json()["excerpt_id"]
        )
    assert len(set(seen)) == everything  # nothing came twice
    query = "&".join(f"exclude={i}" for i in seen)
    assert client.get(f"/api/excerpts/random?{query}", headers=HEADERS).status_code == 404
    many = "&".join(f"exclude=x{n}" for n in range(101))
    assert client.get(f"/api/excerpts/random?{many}", headers=HEADERS).status_code == 422


def test_an_excerpt_can_be_fetched_again_by_its_id(client):
    one = client.get("/api/excerpts/random?context=true", headers=HEADERS).json()
    again = client.get(f"/api/excerpts/{one['excerpt_id']}?context=true", headers=HEADERS).json()
    assert again["text"] == one["text"] and again["context"]["text"]
    assert client.get("/api/excerpts/nothing:1-2", headers=HEADERS).status_code == 404
    assert client.get("/api/excerpts/ch_missing:1-2", headers=HEADERS).status_code == 404
    # The ID of an excerpt in a document that is not listed does not resolve either.
    assert client.get("/api/excerpts/today?tz=Mars/Base", headers=HEADERS).status_code == 422


def test_requests_are_limited_per_token(corpus, allow):
    now = [0.0]
    auth = AgentAuth({"a": TOKEN, "b": "b" * 40}, limit=2, window=60, clock=lambda: now[0])
    api = TestClient(create_app(corpus.home, agent_auth=auth, excerpt_sources=allow))
    assert [api.get("/api/excerpts/today", headers=HEADERS).status_code for _ in range(2)] == [
        200,
        200,
    ]
    refused = api.get("/api/excerpts/today", headers=HEADERS)
    assert refused.status_code == 429 and int(refused.headers["retry-after"]) >= 1
    other = {"Authorization": "Bearer " + "b" * 40}
    assert api.get("/api/excerpts/today", headers=other).status_code == 200  # its own allowance
    now[0] = 61
    assert api.get("/api/excerpts/today", headers=HEADERS).status_code == 200


def test_an_empty_library_says_what_to_do(tmp_path, allow):
    api = TestClient(
        create_app(tmp_path, agent_auth=AgentAuth({"a": TOKEN}), excerpt_sources=allow)
    )
    response = api.get("/api/excerpts/today", headers=HEADERS)
    assert response.status_code == 409 and "pramana corpus download" in response.json()["detail"]


def test_the_agent_only_app_serves_nothing_else(corpus, allow):
    api = TestClient(create_agent_app(corpus.home, auth=AgentAuth({"a": TOKEN}), sources=allow))
    assert api.get("/api/excerpts/today", headers=HEADERS).status_code == 200
    for path in ("/api/search", "/api/chat", "/api/library", "/api/status", "/api/config", "/"):
        assert api.get(path, headers=HEADERS).status_code in (404, 405), path
    assert api.post("/api/chat", json={"message": "hi"}, headers=HEADERS).status_code == 404
    paths = set(api.get("/openapi.json").json()["paths"])
    assert paths and all(p.startswith("/api/excerpts") for p in paths)


def test_tokens_are_checked_and_parsed():
    with pytest.raises(PramanaError, match="shorter than 32"):
        AgentAuth({"default": "short"})
    auth = AgentAuth.from_env(
        {
            "PRAMANA_AGENT_TOKEN": TOKEN,
            "PRAMANA_AGENT_TOKENS": f"claude:{'c' * 40}, gemini:{'g' * 40}",
        }
    )
    assert set(auth.tokens) == {"default", "claude", "gemini"} and auth.enabled
    assert auth.who(f"Bearer {'c' * 40}") == "claude"
    assert not AgentAuth.from_env({}).enabled
    with pytest.raises(PramanaError, match="name:token"):
        AgentAuth.from_env({"PRAMANA_AGENT_TOKENS": "just-a-token"})


def test_the_command_line_prints_the_same_excerpts(monkeypatch, tmp_path, make_chapter):
    katha = chapter(make_chapter, "katha-upanishad-sbe15", KATHA, ["I, 2"])
    corpus = build(tmp_path, make_chapter, [katha])  # a document on the committed allowlist
    monkeypatch.setenv("PRAMANA_HOME", str(corpus.home))
    runner = CliRunner()
    today = runner.invoke(cli, ["excerpt", "today", "--date", "2026-11-02"])
    assert today.exit_code == 0, today.output
    assert today.output.startswith("“") and "Kaṭha Upaniṣad, I, 2," in today.output
    as_json = runner.invoke(cli, ["excerpt", "random", "--kind", "verse", "--format", "json"])
    assert json.loads(as_json.stdout)["kind"] == "verse"
    sources = json.loads(runner.invoke(cli, ["excerpt", "sources"]).stdout)
    assert next(d for d in sources if d["document_id"] == "katha-upanishad-sbe15")["excerpts"] == {
        "verse": 3
    }
    assert runner.invoke(cli, ["excerpt", "today", "--tz", "Mars/Base"]).exit_code == 1
    token = runner.invoke(cli, ["agent", "token"]).stdout.strip()
    assert len(token) >= 32
    monkeypatch.delenv("PRAMANA_AGENT_TOKEN", raising=False)
    refused = runner.invoke(cli, ["serve", "--agent-only"])
    assert refused.exit_code == 1 and "pramana agent token" in refused.output


@pytest.fixture
def topical(corpus, allow, embedder):
    from pramana import Retriever

    corpus.index(embedder=embedder)
    auth = AgentAuth({"openclaw": TOKEN})
    retriever = Retriever(corpus, embedder=embedder)
    return TestClient(create_app(retriever=retriever, agent_auth=auth, excerpt_sources=allow))


def test_a_topic_returns_an_excerpt_without_a_score(topical):
    found = topical.get("/api/excerpts/random?topic=the+pleasant+and+the+good", headers=HEADERS)
    data = found.json()
    assert found.status_code == 200 and data["topic"] == "the pleasant and the good"
    assert data["retrieval"] == "hybrid" and data["rights"] == "Test rights."
    assert data["document"] != "Secret"
    assert not [k for k in data if "score" in k or "relevan" in k or "confiden" in k]
    kinds = topical.get("/api/excerpts/random?topic=lamp&kind=verse", headers=HEADERS).json()
    assert kinds["kind"] == "verse"
    text = topical.get("/api/excerpts/random?topic=lamp&format=text", headers=HEADERS)
    assert text.status_code == 200 and text.text.startswith("“")


def test_a_topic_is_checked_and_can_find_nothing(topical):
    for query in ("topic=!!", "topic=x", "topic=" + "a" * 201, "topic=lamp&strategy=dense"):
        assert topical.get(f"/api/excerpts/random?{query}", headers=HEADERS).status_code == 422
    nothing = topical.get("/api/excerpts/random?topic=zanzibar&strategy=lexical", headers=HEADERS)
    assert nothing.status_code == 404 and "about that topic" in nothing.json()["detail"]
    everything = client_ids(topical)
    query = "&".join(f"exclude={i}" for i in everything)
    gone = topical.get(f"/api/excerpts/random?topic=lamp&{query}", headers=HEADERS)
    assert gone.status_code == 404


def client_ids(api):
    """Every excerpt ID, deterministically: one full cycle of the daily rotation."""
    return {
        api.get(f"/api/excerpts/today?date=2026-01-{day:02d}", headers=HEADERS).json()["excerpt_id"]
        for day in range(1, 7)
    }


def test_a_topic_needs_a_built_index_and_says_so(corpus, allow, embedder):
    from pramana import Retriever

    api = TestClient(
        create_app(
            retriever=Retriever(corpus, embedder=embedder),
            agent_auth=AgentAuth({"a": TOKEN}),
            excerpt_sources=allow,
        )
    )
    assert api.get("/api/excerpts/random", headers=HEADERS).status_code == 200  # no index needed
    response = api.get("/api/excerpts/random?topic=lamp", headers=HEADERS)
    assert response.status_code == 409 and "pramana index" in response.json()["detail"]


def test_the_agent_only_app_searches_by_topic_too(corpus, allow, embedder):
    from pramana import Retriever

    corpus.index(embedder=embedder)
    api = TestClient(
        create_agent_app(
            auth=AgentAuth({"a": TOKEN}),
            sources=allow,
            retriever=Retriever(corpus, embedder=embedder),
        )
    )
    assert api.get("/api/excerpts/random?topic=lamp", headers=HEADERS).status_code == 200
    assert api.get("/api/search", headers=HEADERS).status_code == 404


def test_the_command_line_takes_a_topic(monkeypatch, tmp_path, make_chapter, embedder):
    monkeypatch.setenv("PRAMANA_HOME", str(tmp_path / "library"))
    katha = chapter(make_chapter, "katha-upanishad-sbe15", KATHA, ["I, 2"])
    corpus = build(tmp_path, make_chapter, [katha])
    corpus.index(embedder=embedder)
    monkeypatch.setattr("pramana.retrieval.Retriever.embedder", property(lambda self: embedder))
    result = CliRunner().invoke(cli, ["excerpt", "random", "--topic", "wise pleasant"])
    assert result.exit_code == 0, result.output
    assert "Kaṭha Upaniṣad" in result.output
    lexical = CliRunner().invoke(
        cli, ["excerpt", "random", "--topic", "zanzibar", "--strategy", "lexical"]
    )
    assert lexical.exit_code == 1 and "about that topic" in lexical.output


def test_the_excerpts_download_group_is_exactly_what_the_allowlist_needs():
    from pathlib import Path

    import pramana
    from pramana.cli import EXCERPTS, SACRED_TEXTS, SOURCES, TEXT_FILES

    def document_ids(node):
        if isinstance(node, dict):
            yield from ([node["document_id"]] if "document_id" in node else [])
            for value in node.values():
                yield from document_ids(value)
        elif isinstance(node, list):
            for value in node:
                yield from document_ids(value)

    root = Path(pramana.__file__).parent / "ingestion"
    manifests = {}
    for path in [*root.glob("sacredtexts/*.json"), *root.glob("textfiles/*.json")]:
        data = json.loads(path.read_text(encoding="utf-8"))
        manifests[data["id"]] = set(document_ids(data))
    provides = {}
    for name in EXCERPTS:
        assert name in SOURCES
        manifest = SACRED_TEXTS.get(name) or TEXT_FILES.get(name)
        provides[name] = manifests[manifest] if manifest else {"vishnu-purana"}
    needed = set(ex.load_sources())
    assert needed <= set().union(*provides.values())  # nothing the pool needs is missing
    assert all(ids & needed for ids in provides.values())  # and nothing is downloaded for nothing
    assert not {"brahma-sutra", "sribhashya", "yoga-vasistha"} & set(EXCERPTS)


def test_the_download_command_knows_the_excerpts_group(monkeypatch):
    fetched = []
    monkeypatch.setattr("pramana.cli.acquire_source", lambda name, *a: fetched.append(name) or name)
    result = CliRunner().invoke(cli, ["corpus", "download", "--source", "excerpts"])
    assert result.exit_code == 0 and len(fetched) == 9 and "vishnu-purana" in fetched
    assert "brahma-sutra" not in fetched
    again = CliRunner().invoke(
        cli, ["corpus", "download", "--source", "excerpts", "--archive", "x.gz"]
    )
    assert again.exit_code == 1 and "--archive applies to one source" in again.output
    bogus = CliRunner().invoke(cli, ["corpus", "download", "--source", "nothing"])
    assert bogus.exit_code == 1 and "excerpts" in bogus.output


def test_hybrid_topic_says_so_when_the_install_has_no_embedding_library(corpus, allow, monkeypatch):
    from pramana import Retriever

    monkeypatch.setattr("importlib.util.find_spec", lambda name, *a: None)
    api = TestClient(
        create_app(
            retriever=Retriever(corpus),  # no embedder injected, as on a torch-free server
            agent_auth=AgentAuth({"a": TOKEN}),
            excerpt_sources=allow,
        )
    )
    response = api.get("/api/excerpts/random?topic=lamp", headers=HEADERS)
    assert response.status_code == 409 and "strategy=lexical" in response.json()["detail"]
    assert api.get("/api/excerpts/random", headers=HEADERS).status_code == 200


def test_search_lists_excerpts_best_first_with_no_score(topical):
    url = "/api/excerpts/search?q=the+pleasant+and+the+good&limit=3"
    found = topical.get(url, headers=HEADERS)
    data = found.json()
    assert found.status_code == 200 and data["query"] == "the pleasant and the good"
    assert data["retrieval"] == "hybrid" and data["count"] == len(data["results"]) <= 3
    assert data["results"][0]["rights"] == "Test rights."
    assert data["results"][0]["document"] != "Secret"
    assert topical.get(url, headers=HEADERS).json() == data  # the same list every time
    text = " ".join(map(str, data)) + str([sorted(r) for r in data["results"]])
    assert not [w for w in ("score", "relevan", "confiden") if w in text]
    ids = [r["excerpt_id"] for r in data["results"]]
    assert len(set(ids)) == len(ids)
    skipped = topical.get(url + f"&exclude={ids[0]}", headers=HEADERS).json()
    assert ids[0] not in [r["excerpt_id"] for r in skipped["results"]]
    verses = topical.get("/api/excerpts/search?q=lamp+good&kind=verse", headers=HEADERS).json()
    assert {r["kind"] for r in verses["results"]} == {"verse"}


def test_search_formats_validation_and_boundaries(topical):
    text = topical.get("/api/excerpts/search?q=the+good&limit=2&format=text", headers=HEADERS)
    assert text.headers["content-type"].startswith("text/plain")
    blocks = text.text.strip().split("\n\n")
    assert 1 <= len(blocks) <= 2
    assert [b[:4] for b in blocks] == ["1. “", "2. “"][: len(blocks)]
    assert all("\n   — " in b for b in blocks)
    markdown = topical.get("/api/excerpts/search?q=the+good&format=markdown", headers=HEADERS)
    assert markdown.headers["content-type"].startswith("text/markdown")
    for query in ("q=x", "q=!!", "q=lamp&limit=0", "q=lamp&limit=11", "q=lamp&strategy=dense"):
        assert topical.get(f"/api/excerpts/search?{query}", headers=HEADERS).status_code == 422
    assert topical.get("/api/excerpts/search", headers=HEADERS).status_code == 422
    nothing = topical.get("/api/excerpts/search?q=zanzibar&strategy=lexical", headers=HEADERS)
    assert nothing.status_code == 404 and "about that topic" in nothing.json()["detail"]
    assert topical.get("/api/excerpts/search?q=lamp").status_code == 401


def test_search_is_not_mistaken_for_an_excerpt_id_and_needs_an_index(corpus, allow, embedder):
    from pramana import Retriever

    api = TestClient(
        create_app(
            retriever=Retriever(corpus, embedder=embedder),
            agent_auth=AgentAuth({"a": TOKEN}),
            excerpt_sources=allow,
        )
    )
    unbuilt = api.get("/api/excerpts/search?q=lamp", headers=HEADERS)
    assert unbuilt.status_code == 409 and "pramana index" in unbuilt.json()["detail"]
    assert api.get("/api/excerpts/search/extra", headers=HEADERS).status_code == 404


def test_the_command_line_searches_too(monkeypatch, tmp_path, make_chapter, embedder):
    monkeypatch.setenv("PRAMANA_HOME", str(tmp_path / "library"))
    katha = chapter(make_chapter, "katha-upanishad-sbe15", KATHA, ["I, 2"])
    corpus = build(tmp_path, make_chapter, [katha])
    corpus.index(embedder=embedder)
    monkeypatch.setattr("pramana.retrieval.Retriever.embedder", property(lambda self: embedder))
    result = CliRunner().invoke(cli, ["excerpt", "search", "wise pleasant", "--limit", "2"])
    assert result.exit_code == 0, result.output
    assert result.output.startswith("1. “") and "Kaṭha Upaniṣad" in result.output
    as_json = CliRunner().invoke(
        cli, ["excerpt", "search", "pleasant", "--format", "json", "--limit", "3"]
    )
    assert 1 <= len(json.loads(as_json.stdout)) <= 3
    lexical = CliRunner().invoke(cli, ["excerpt", "search", "zanzibar", "--strategy", "lexical"])
    assert lexical.exit_code == 1 and "about that topic" in lexical.output
