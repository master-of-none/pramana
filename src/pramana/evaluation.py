import json
from pathlib import Path

from pramana.errors import PramanaError
from pramana.models import SearchFilters
from pramana.retrieval import Retriever


def evaluate(retriever: Retriever, path: Path) -> dict:
    """Chapter-level initial engineering benchmark; not scholarly validation."""
    questions = json.loads(path.read_text(encoding="utf-8"))["questions"]
    if not questions:
        raise PramanaError("Evaluation file has no questions.")
    chapters = {
        (c.location.book, c.location.chapter): c
        for c in retriever.corpus.store.chapters()
        if c.corpus_id == "vishnu-purana"
    }
    for question in questions:
        for gold in question["relevant"]:
            source = chapters.get((str(gold["book"]), str(gold["chapter"])))
            if source is None or gold.get("evidence_quote", "") not in source.text:
                raise PramanaError(
                    "Benchmark sources are missing or changed. Import the complete demo edition."
                )
    report = {
        "label": "Initial engineering benchmark · chapter-level relevance",
        "questions": len(questions),
        "strategies": {},
        "index": retriever.corpus.store.get_meta("index_config"),
    }
    for strategy in ("lexical", "dense", "hybrid"):
        recall, reciprocal, details = [], [], []
        for question in questions:
            hits = retriever.search(
                question["query"],
                strategy=strategy,
                filters=SearchFilters(corpus_id="vishnu-purana"),
            )
            expected = {(str(x["book"]), str(x["chapter"])) for x in question["relevant"]}
            found = set()
            first = None
            for rank, hit in enumerate(hits, 1):
                loc = hit.passage.citation.location
                key = (loc.book, loc.chapter)
                if key in expected:
                    found.add(key)
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
