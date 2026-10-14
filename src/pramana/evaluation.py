import json
from pathlib import Path

from pramana.errors import PramanaError
from pramana.models import SearchFilters
from pramana.retrieval import Retriever


def evaluate(retriever: Retriever, path: Path) -> dict:
    """Edition-aware chapter benchmark; separate from passage/answer evaluation."""
    questions = json.loads(path.read_text(encoding="utf-8"))["questions"]
    if not questions:
        raise PramanaError("Evaluation file has no questions.")
    chapters = retriever.corpus.store.chapters()
    resolved = []
    for question in questions:
        sources = []
        for gold in question["relevant"]:
            required = ("corpus_id", "document_id", "edition", "language", "book", "chapter")
            if (
                any(not gold.get(key) for key in required)
                or not gold.get("evidence_quote", "").strip()
            ):
                raise PramanaError(
                    "Benchmark evidence needs corpus_id, document_id, edition, "
                    "language, book, chapter and a nonempty evidence_quote."
                )
            matches = [
                c
                for c in chapters
                if (
                    c.corpus_id,
                    c.document_id,
                    c.edition,
                    c.language,
                    c.location.book,
                    c.location.chapter,
                )
                == tuple(str(gold[k]) for k in required)
                and c.location.sections == gold.get("sections", [])
            ]
            if len(matches) != 1 or gold["evidence_quote"] not in matches[0].text:
                raise PramanaError(
                    "Benchmark source is missing, ambiguous or changed; "
                    "import the exact annotated edition."
                )
            sources.append(matches[0])
        if not sources:
            raise PramanaError("Each benchmark question needs at least one evidence record.")
        identities = {(c.corpus_id, c.document_id, c.edition, c.language) for c in sources}
        if len(identities) != 1:
            raise PramanaError("Chapter benchmark questions must target one edition each.")
        resolved.append(sources)
    report = {
        "label": "Initial engineering benchmark · chapter-level relevance",
        "questions": len(questions),
        "strategies": {},
        "index": retriever.corpus.store.get_meta("index_config"),
        "sources": [
            {"chapter_id": c.id, "source_checksum": c.source.checksum}
            for c in {c.id: c for group in resolved for c in group}.values()
        ],
    }
    for strategy in ("lexical", "dense", "hybrid"):
        recall, reciprocal, details = [], [], []
        for question, sources in zip(questions, resolved, strict=True):
            source = sources[0]
            hits = retriever.search(
                question["query"],
                strategy=strategy,
                filters=SearchFilters(
                    corpus_id=source.corpus_id,
                    document_id=source.document_id,
                    edition=source.edition,
                    language=source.language,
                ),
            )
            expected = {c.id for c in sources}
            found = set()
            first = None
            for rank, hit in enumerate(hits, 1):
                if hit.passage.chapter_id in expected:
                    found.add(hit.passage.chapter_id)
                    first = first or rank
            recall.append(len(found) / len(expected))
            reciprocal.append(1 / first if first else 0)
            details.append(
                {
                    "query": question["query"],
                    "recall_at_10": recall[-1],
                    "reciprocal_rank": reciprocal[-1],
                }
            )
        report["strategies"][strategy] = {
            "recall_at_10": sum(recall) / len(recall),
            "mrr_at_10": sum(reciprocal) / len(reciprocal),
            "details": details,
        }
    return report
