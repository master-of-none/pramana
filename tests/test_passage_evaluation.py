import json

import pytest

from pramana import Retriever
from pramana.errors import PramanaError
from pramana.evaluation import evaluate_passages


def gold_for(chapter, quote):
    start = chapter.text.index(quote)
    return {
        "corpus_id": chapter.corpus_id,
        "document_id": chapter.document_id,
        "edition": chapter.edition,
        "language": chapter.language,
        "book": chapter.location.book,
        "chapter": chapter.location.chapter,
        "sections": chapter.location.sections,
        "start": start,
        "end": start + len(quote),
        "quote": quote,
    }


def write(tmp_path, questions, **extra):
    path = tmp_path / "advaita.json"
    path.write_text(json.dumps({"label": "fixture", "questions": questions, **extra}))
    return path


def test_passage_hits_need_the_whole_gold_span(indexed, embedder, tmp_path, make_chapter):
    chapter = next(c for c in indexed.store.chapters() if "preserves" in c.text)
    retriever = Retriever(indexed, embedder=embedder)
    good = {
        "id": "q1",
        "split": "dev",
        "query": "Who preserves the universe?",
        "gold": [gold_for(chapter, "Vishnu preserves the universe.")],
        "review": {"status": "unreviewed"},
    }
    held = {**good, "id": "q2", "split": "heldout"}
    path = write(tmp_path, [good, held], out_of_corpus=[{"id": "o1", "query": "Kubernetes"}])
    report = evaluate_passages(retriever, path)
    assert report["splits"] == {"dev": 1, "heldout": 1}
    assert report["review"] == {"unreviewed": 2}
    lexical = report["strategies"]["lexical"]
    assert lexical["all"]["recall_at_10"] == 1 and lexical["dev"]["questions"] == 1
    assert report["out_of_corpus"][0]["id"] == "o1"
    assert len(report["dataset_sha256"]) == 64

    # A span the passage does not wholly contain is not a hit.
    outside = {**good, "gold": [{**good["gold"][0], "end": len(chapter.text) + 1}]}
    with pytest.raises(PramanaError, match="no longer matches"):
        evaluate_passages(retriever, write(tmp_path, [outside]))


@pytest.mark.parametrize(
    "change",
    [
        {"quote": "Vishnu creates the universe."},
        {"edition": "Another edition"},
        {"start": 3},
    ],
)
def test_changed_or_mismatched_gold_is_rejected(indexed, embedder, tmp_path, change):
    chapter = next(c for c in indexed.store.chapters() if "preserves" in c.text)
    gold = {**gold_for(chapter, "Vishnu preserves the universe."), **change}
    question = {"id": "q", "split": "dev", "query": "Who preserves?", "gold": [gold]}
    with pytest.raises(PramanaError):
        evaluate_passages(Retriever(indexed, embedder=embedder), write(tmp_path, [question]))
    with pytest.raises(PramanaError, match="split"):
        evaluate_passages(
            Retriever(indexed, embedder=embedder),
            write(
                tmp_path, [{**question, "split": "train", "gold": [gold_for(chapter, "Vishnu")]}]
            ),
        )


def test_span_split_across_passages_is_never_a_hit(indexed, embedder, tmp_path, make_chapter):
    words = " ".join(f"word{i}." for i in range(900))
    long = make_chapter("Brahman is the witness. " + words, chapter="7")
    path = tmp_path / "long.jsonl"
    path.write_text(long.model_dump_json())
    indexed.import_jsonl(path)
    indexed.index(embedder=embedder)
    with indexed.store.connect() as db:
        rows = db.execute(
            "SELECT json_extract(data,'$.start'), json_extract(data,'$.end') FROM passages "
            "WHERE chapter_id=? ORDER BY 1",
            (long.id,),
        ).fetchall()
    assert len(rows) > 1
    boundary = rows[0][1]  # First passage ends here; the next begins earlier (overlap).
    quote = long.text[boundary - 12 : boundary + 12]
    gold = {**gold_for(long, quote), "start": boundary - 12, "end": boundary + 12}
    question = {"id": "q", "split": "dev", "query": quote, "gold": [gold]}
    report = evaluate_passages(Retriever(indexed, embedder=embedder), write(tmp_path, [question]))
    contained = any(s <= boundary - 12 and boundary + 12 <= e for s, e in rows)
    assert report["strategies"]["lexical"]["all"]["recall_at_10"] == float(contained)


def test_any_match_counts_one_of_several_alternatives(indexed, embedder, tmp_path):
    chapters = indexed.store.chapters()
    preserve = next(c for c in chapters if "preserves" in c.text)
    other = next(c for c in chapters if c is not preserve)
    golds = [gold_for(preserve, "Vishnu preserves the universe."), gold_for(other, "Krishna")]
    base = {"id": "q", "split": "dev", "query": "Vishnu preserves", "gold": golds}
    retriever = Retriever(indexed, embedder=embedder)
    for match, expected in (("any", 1.0), ("all", 0.5)):
        report = evaluate_passages(retriever, write(tmp_path, [{**base, "match": match}]))
        row = report["strategies"]["lexical"]["details"][0]
        assert row["recall_at_10"] == expected
    with pytest.raises(PramanaError, match="match mode"):
        evaluate_passages(retriever, write(tmp_path, [{**base, "match": "some"}]))


def test_typed_dataset_reports_breakdowns_followups_and_probes(indexed, embedder, tmp_path):
    chapter = next(c for c in indexed.store.chapters() if "preserves" in c.text)
    gold = [gold_for(chapter, "Vishnu preserves the universe.")]
    base = {"split": "dev", "gold": gold, "text": "Fixture", "scope": "all"}
    questions = [
        {**base, "id": "a1", "type": "fact", "query": "Who preserves the universe?"},
        {**base, "id": "a2", "type": "concept", "query": "cattle mountain shelter"},
        {
            **base,
            "id": "a3",
            "type": "followup",
            "query": "And what does he do?",
            "standalone": "What does Vishnu do to the universe? preserves",
            "history": [{"role": "user", "content": "Who is Vishnu?"}],
        },
        {"id": "o1", "split": "dev", "type": "out_of_corpus", "query": "Kubernetes ingress"},
    ]
    report = evaluate_passages(Retriever(indexed, embedder=embedder), write(tmp_path, questions))
    assert report["questions"] == 3 and report["uncontainable_spans"] == []
    lexical = report["strategies"]["lexical"]
    assert set(lexical["by_type"]) == {"fact", "concept", "followup"}
    assert lexical["by_text"]["Fixture"]["questions"] == 3
    assert lexical["followup_rewritten"]["recall_at_10"] == 1  # the standalone rewrite
    assert "followup_raw" in lexical
    miss = next(r for r in lexical["details"] if r["id"] == "a2")
    assert miss["recall_at_10"] == 0
    kinds = {"right chapter, other passage", "right work, other chapter", "other work"}
    assert miss["miss"] in kinds
    assert sum(lexical["failure_depth"].values()) == len(lexical["failures"])
    assert report["out_of_corpus"][0]["id"] == "o1"


def test_answer_evaluation_scores_status_citations_and_resumes(indexed, embedder, tmp_path):
    import asyncio

    from pramana.evaluation import evaluate_answers
    from pramana.models import ChatResponse, Evidence

    chapter = next(c for c in indexed.store.chapters() if "preserves" in c.text)
    retriever = Retriever(indexed, embedder=embedder)

    class Fake:
        provider = type("P", (), {"model": "fake-model"})()

        def __init__(self):
            self.retriever, self.calls = retriever, 0

        async def answer(self, request):
            self.calls += 1
            if "Kubernetes" in request.message:
                return ChatResponse(
                    answer="Not in the library.",
                    status="insufficient_evidence",
                    retrieval_question=request.message,
                    model="fake-model",
                )
            hit = retriever.search(request.message, strategy="lexical")[0]
            return ChatResponse(
                answer="Vishnu preserves it.",
                status="grounded",
                retrieval_question=request.message,
                model="fake-model",
                evidence=[
                    Evidence(
                        reference="E1",
                        passage=hit.passage,
                        retrieval_relevance=1.0,
                        score_kind="bm25",
                    )
                ],
            )

    gold = [gold_for(chapter, "Vishnu preserves the universe.")]
    questions = [
        {
            "id": "a1",
            "split": "dev",
            "type": "fact",
            "text": "Fixture",
            "expect": "grounded",
            "query": "Who preserves the universe?",
            "gold": gold,
        },
        {
            "id": "o1",
            "split": "heldout",
            "type": "out_of_corpus",
            "text": "Out of corpus",
            "expect": "insufficient_evidence",
            "query": "Kubernetes ingress",
        },
    ]
    path, partial = write(tmp_path, questions), tmp_path / "answers.partial.jsonl"
    fake = Fake()
    report = asyncio.run(evaluate_answers(fake, path, partial=partial))
    assert report["model"] == "fake-model" and fake.calls == 2
    assert report["overall"]["status_accuracy"] == 1 and report["overall"]["gold_cited"] == 1
    assert report["overall"]["refused_when_out_of_corpus"] == 1
    assert report["by_type"]["fact"]["questions"] == 1
    again = asyncio.run(evaluate_answers(fake, path, partial=partial))
    assert fake.calls == 2 and again["overall"] == report["overall"]  # resumed, no new calls
