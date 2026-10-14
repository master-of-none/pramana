import os
from pathlib import Path

import pytest

from pramana import Corpus, Retriever
from pramana.embeddings import LocalEmbedder


@pytest.mark.model
def test_actual_model_offline_index_search_and_context(tmp_path, make_chapter):
    home = Path(os.environ.get("PRAMANA_HOME", ".pramana"))
    embedder = LocalEmbedder(home)
    corpus = Corpus(tmp_path)
    file = tmp_path / "chapter.jsonl"
    chapter = make_chapter("Krishna shelters the cowherds beneath Mount Govardhana.")
    file.write_text(chapter.model_dump_json())
    corpus.import_jsonl(file)
    assert corpus.index(embedder=embedder) == 1
    hit = Retriever(corpus, embedder=embedder).search("Who protected the cattle from rain?")[0]
    assert "Krishna" in hit.passage.text
    assert hit.score_kind == "rrf"


@pytest.mark.model
def test_complete_demo_manifest_and_all_citation_offsets():
    from pramana.ingestion.vishnu import manifest

    home = Path(os.environ.get("PRAMANA_HOME", ".pramana"))
    corpus = Corpus(home)
    all_chapters = {c.id: c for c in corpus.store.chapters()}
    chapters = {k: c for k, c in all_chapters.items() if c.corpus_id == "vishnu-purana"}
    expected = {(e["book"], e["chapter"]) for e in manifest()}
    assert {(c.location.book, c.location.chapter) for c in chapters.values()} == expected
    assert corpus.store.status()["indexed"]
    with corpus.store.connect() as db:
        rows = db.execute("SELECT data FROM passages").fetchall()
    from pramana.models import Passage

    passages = [Passage.model_validate_json(row[0]) for row in rows]
    assert passages
    for passage in passages:
        chapter = all_chapters[passage.chapter_id]
        assert passage.text == chapter.text[passage.start : passage.end]
        assert passage.token_count <= 448
        assert passage.citation.source_url == (
            str(chapter.source.url) if chapter.source.url else None
        )
        assert passage.citation.source_local_path == chapter.source.local_path
        assert passage.citation.author == chapter.author
        assert passage.citation.content_type == chapter.content_type
