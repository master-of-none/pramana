import json

import numpy as np
import pytest

from pramana import Retriever, SearchFilters
from pramana.chunking import chunk_chapter
from pramana.errors import PramanaError
from pramana.models import PageMark
from pramana.retrieval import fuse, lexical_query


def test_chunk_offsets_token_limits_coverage_and_stability(make_chapter, embedder):
    chapter = make_chapter("Viṣṇu preserves the world. 🪷\n\n" * 300)
    chapter.pages = [PageMark(offset=0, label="1"), PageMark(offset=1500, label="2")]
    chunks = chunk_chapter(chapter, embedder.tokenizer)
    assert len(chunks) > 2
    assert chunks == chunk_chapter(chapter, embedder.tokenizer)
    covered = set()
    for chunk in chunks:
        assert chunk.text == chapter.text[chunk.start : chunk.end]
        assert chunk.token_count <= 448
        assert "Viṣṇu" in chunk.text
        assert chunk.citation.passage_id == chunk.id
        assert "verse" not in chunk.citation.label.lower()
        covered.update(range(chunk.start, chunk.end))
    assert covered == set(range(len(chapter.text)))
    assert any(c.citation.pages == ["1", "2"] for c in chunks)


def test_huge_sentence_splits_without_losing_text(make_chapter, embedder):
    chapter = make_chapter(" ".join(f"word{i}" for i in range(1600)))
    chunks = chunk_chapter(chapter, embedder.tokenizer)
    assert max(c.token_count for c in chunks) <= 448
    assert chunks[-1].end == len(chapter.text)


@pytest.mark.parametrize("strategy", ["lexical", "dense", "hybrid"])
def test_filtered_search_and_resolvable_citations(indexed, embedder, strategy):
    hits = Retriever(indexed, embedder=embedder).search(
        "Krishna", strategy=strategy, filters=SearchFilters(book="5")
    )
    assert hits
    for hit in hits:
        chapter = indexed.store.chapter(hit.passage.chapter_id)
        assert chapter.location.book == "5"
        assert hit.passage.text == chapter.text[hit.passage.start : hit.passage.end]
        assert indexed.store.passage(hit.passage.id) == hit.passage


def test_plain_queries_cannot_execute_fts_syntax(indexed, embedder):
    query = '"Vishnu" OR text: NOT (Krishna*) ; DROP TABLE chapters; --'
    assert '"OR"' in lexical_query(query)
    Retriever(indexed, embedder=embedder).search(query, strategy="lexical")
    assert indexed.store.status()["chapters"] == 2


def test_diacritic_search_preserves_display(tmp_path, make_chapter, embedder):
    from pramana import Corpus

    chapter = make_chapter("Viṣṇu and Prakṛti are discussed in this Unicode fixture.")
    file = tmp_path / "input.jsonl"
    file.write_text(chapter.model_dump_json())
    corpus = Corpus(tmp_path / "store")
    corpus.import_jsonl(file)
    corpus.index(embedder=embedder)
    hits = Retriever(corpus, embedder=embedder).search("Visnu", strategy="lexical")
    assert "Viṣṇu" in hits[0].passage.text
    assert Retriever(corpus, embedder=embedder).search("Viṣṇu", strategy="lexical") == hits


def test_fusion_combines_ranks_not_incompatible_scores():
    ranking = fuse([["a", "b"], ["b", "c"]])
    assert ranking[0][0] == "b"
    assert ranking[0][1] == pytest.approx(1 / 62 + 1 / 61)


def test_empty_filters_and_invalid_query(indexed, embedder):
    retriever = Retriever(indexed, embedder=embedder)
    assert retriever.search("Vishnu", filters=SearchFilters(book="absent")) == []
    for query in ["", "   ", "***"]:
        with pytest.raises(PramanaError, match="search terms"):
            retriever.search(query)
    with pytest.raises(PramanaError, match="1–50"):
        retriever.search("Vishnu", limit=0)


def test_changed_import_invalidates_index(tmp_path, indexed, make_chapter, embedder):
    file = tmp_path / "updated.jsonl"
    file.write_text(make_chapter("An updated translation.").model_dump_json())
    indexed.import_jsonl(file)
    with pytest.raises(PramanaError, match="stale"):
        Retriever(indexed, embedder=embedder).search("Vishnu")
    indexed.index(embedder=embedder)
    assert indexed.store.status()["indexed"]


def test_config_mismatch_requires_explicit_rebuild(indexed, embedder):
    embedder.identity = {"model": "changed", "revision": "2"}
    with pytest.raises(PramanaError, match="--rebuild"):
        indexed.index(embedder=embedder)
    with pytest.raises(PramanaError, match="--rebuild"):
        Retriever(indexed, embedder=embedder).search("Vishnu")
    assert indexed.index(embedder=embedder, rebuild=True) > 0


def test_failed_embedding_retains_last_good_index(indexed, embedder):
    before = indexed.store.status()
    embedder.documents = lambda texts: np.zeros((len(texts), 128), dtype=np.float32)
    with pytest.raises(PramanaError, match="zero vectors"):
        indexed.index(embedder=embedder, rebuild=True)
    assert indexed.store.status() == before


def test_repeat_index_noop(indexed, embedder):
    assert indexed.index(embedder=embedder) == 0


def test_incompatible_chunking_rejected_for_lexical_search(indexed, embedder):
    config = indexed.store.get_meta("index_config")
    config["chunking"]["max_tokens"] = 10
    with indexed.store.connect() as db:
        db.execute("UPDATE meta SET value=? WHERE key='index_config'", (json.dumps(config),))
    with pytest.raises(PramanaError, match="incompatible"):
        Retriever(indexed, embedder=embedder).search("Vishnu", strategy="lexical")


def test_commentary_filters_before_ranking(indexed, embedder, make_chapter, tmp_path):
    chapter = make_chapter("Action and knowledge are explained in this commentary.", chapter="3")
    chapter.document_id = "commentary"
    chapter.author = "A commentator"
    chapter.content_type = "mixed"
    path = tmp_path / "commentary.jsonl"
    path.write_text(chapter.model_dump_json())
    indexed.import_jsonl(path)
    indexed.index(embedder=embedder)
    engine = Retriever(indexed, embedder=embedder)
    for strategy in ("lexical", "dense", "hybrid"):
        hits = engine.search(
            "action knowledge",
            strategy=strategy,
            filters=SearchFilters(
                document_id="commentary", author="A commentator", content_type="mixed"
            ),
        )
        assert hits and all(h.passage.chapter_id == chapter.id for h in hits)
        assert not engine.search(
            "action",
            strategy=strategy,
            filters=SearchFilters(document_id="commentary", author="Someone else"),
        )


def test_translation_filter_handles_legacy_chapter_json(indexed, embedder):
    with indexed.store.connect() as db:
        for row in db.execute("SELECT id, data FROM chapters").fetchall():
            data = json.loads(row["data"])
            data.pop("content_type", None)
            data.pop("author", None)
            db.execute("UPDATE chapters SET data=? WHERE id=?", (json.dumps(data), row["id"]))
    hits = Retriever(indexed, embedder=embedder).search(
        "Vishnu preserves", filters=SearchFilters(content_type="translation")
    )
    assert hits and hits[0].passage.citation.content_type == "translation"


def test_glossary_expands_sanskrit_and_english_lexically():
    from pramana.glossary import expansions, terms

    assert "superimposition" in expansions("What is adhyāsa?")
    assert "adhyasa" in expansions("Explain SUPERIMPOSITION")
    assert "liberation" in expansions("माया और मोक्ष")
    assert expansions("brahmanical rituals") == []
    assert '"superimposition"' in lexical_query("adhyasa", expand=True)
    assert "superimposition" not in lexical_query("adhyasa")
    assert len({t.term for t in terms()}) == len(terms())


def test_glossary_endpoint(indexed, embedder):
    from fastapi.testclient import TestClient

    from pramana.api import create_app

    client = TestClient(create_app(retriever=Retriever(indexed, embedder=embedder)))
    entries = client.get("/api/glossary").json()
    assert {"term": "adhyāsa", "devanagari": "अध्यास"}.items() <= next(
        e for e in entries if e["term"] == "adhyāsa"
    ).items()
