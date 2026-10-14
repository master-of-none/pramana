import json

import pytest

from pramana import Retriever
from pramana.errors import PramanaError
from pramana.evaluation import evaluate


def test_evaluation_rejects_missing_provenance_and_empty_evidence(indexed, embedder, tmp_path):
    path = tmp_path / "questions.json"
    for gold in (
        {"book": "1", "chapter": "1", "evidence_quote": "Vishnu"},
        {
            "corpus_id": "fixture",
            "document_id": "fixture",
            "edition": "Fixture edition",
            "language": "en",
            "book": "1",
            "chapter": "1",
            "evidence_quote": "",
        },
    ):
        path.write_text(
            json.dumps({"questions": [{"query": "Who preserves?", "relevant": [gold]}]})
        )
        with pytest.raises(PramanaError, match="Benchmark evidence needs"):
            evaluate(Retriever(indexed, embedder=embedder), path)


def test_evaluation_never_crosses_editions(indexed, embedder, tmp_path, make_chapter):
    second = make_chapter("A contradictory source with the same labels.")
    second.edition = "Different edition"
    source = tmp_path / "second.jsonl"
    source.write_text(second.model_dump_json())
    indexed.import_jsonl(source)
    indexed.index(embedder=embedder)
    gold = {
        "corpus_id": "fixture",
        "document_id": "fixture",
        "edition": "Fixture edition",
        "language": "en",
        "book": "1",
        "chapter": "1",
        "evidence_quote": "Vishnu preserves",
    }
    path = tmp_path / "questions.json"
    question = {"query": "Who preserves the universe?", "relevant": [gold]}
    path.write_text(json.dumps({"questions": [question]}))
    report = evaluate(Retriever(indexed, embedder=embedder), path)
    assert report["strategies"]["hybrid"]["recall_at_10"] == 1
    gold["edition"] = "Different edition"
    path.write_text(json.dumps({"questions": [question]}))
    with pytest.raises(PramanaError, match="missing, ambiguous or changed"):
        evaluate(Retriever(indexed, embedder=embedder), path)
