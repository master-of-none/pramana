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


GOLD_KEYS = ("corpus_id", "document_id", "edition", "language", "book", "chapter")


def _resolve_span(chapters, gold: dict):
    """Exactly one chapter, and its text at [start, end) must equal the quote."""
    if any(not gold.get(k) for k in GOLD_KEYS) or not str(gold.get("quote", "")).strip():
        raise PramanaError(
            "Passage gold spans need corpus_id, document_id, edition, language, book, "
            "chapter, sections, start, end and a nonempty quote."
        )
    matches = [
        c
        for c in chapters
        if (c.corpus_id, c.document_id, c.edition, c.language, c.location.book, c.location.chapter)
        == tuple(str(gold[k]) for k in GOLD_KEYS)
        and c.location.sections == gold.get("sections", [])
    ]
    if len(matches) != 1:
        raise PramanaError(
            f"Gold span source for {gold['document_id']} {gold['book']}.{gold['chapter']} is "
            "missing or ambiguous; import the exact annotated edition."
        )
    chapter = matches[0]
    start, end = gold.get("start"), gold.get("end")
    if (
        not isinstance(start, int)
        or not isinstance(end, int)
        or not 0 <= start < end <= len(chapter.text)
        or chapter.text[start:end] != gold["quote"]
    ):
        raise PramanaError(
            f"Gold span in {chapter.document} no longer matches its quote; the stored text "
            "changed or the annotation is wrong."
        )
    return chapter


def evaluate_passages(
    retriever: Retriever, path: Path, limit: int = 10, *, include_opt_in: bool = False
) -> dict:
    """Passage-level benchmark over the whole library; separate from the chapter benchmark.

    A retrieved passage is relevant only if it lies in the gold chapter and contains a
    complete gold span (Python code points), so chunking changes cannot invent evidence.
    `"match": "any"` marks gold spans that are alternatives (a refrain or a verse shared
    by several texts): finding one of them is full recall for that question.
    By default search covers what chat's "All texts" covers (opt-in works excluded);
    `include_opt_in` searches the whole index.
    """
    from pramana.library import default_documents

    within = None if include_opt_in else default_documents(retriever.corpus.store)
    scoped = SearchFilters(document_ids=within) if within is not None else None
    import hashlib

    raw = path.read_bytes()
    dataset = json.loads(raw.decode("utf-8"))
    questions = dataset.get("questions", [])
    if not questions:
        raise PramanaError("Passage benchmark has no questions.")
    chapters = retriever.corpus.store.chapters()
    resolved = []
    for q in questions:
        if q.get("match", "all") not in {"all", "any"}:
            raise PramanaError(f"Question {q.get('id')} has an unknown match mode.")
        if q.get("split") not in {"dev", "heldout"} or not q.get("gold"):
            raise PramanaError(f"Question {q.get('id')} needs a dev/heldout split and gold spans.")
        resolved.append([(_resolve_span(chapters, g), g) for g in q["gold"]])
    review = [q.get("review", {}).get("status", "unreviewed") for q in questions]
    report = {
        "label": dataset.get("label", "Passage-level benchmark"),
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "questions": len(questions),
        "splits": {s: sum(q["split"] == s for q in questions) for s in ("dev", "heldout")},
        "review": {s: review.count(s) for s in sorted(set(review))},
        "scope": (
            "whole index, opt-in works included"
            if include_opt_in or within is None
            else "chat's All texts: opt-in works excluded"
        ),
        "index": retriever.corpus.store.get_meta("index_config"),
        "sources": sorted(
            {(c.id, c.source.checksum) for group in resolved for c, _ in group}, key=str
        ),
        "strategies": {},
        "out_of_corpus": [],
    }
    report["sources"] = [{"chapter_id": i, "source_checksum": s} for i, s in report["sources"]]
    for strategy in ("lexical", "dense", "hybrid"):
        rows = []
        for q, golds in zip(questions, resolved, strict=True):
            hits = retriever.search(q["query"], limit=limit, strategy=strategy, filters=scoped)
            found, first = set(), None
            for rank, hit in enumerate(hits, 1):
                p = hit.passage
                for i, (chapter, gold) in enumerate(golds):
                    if (
                        p.chapter_id == chapter.id
                        and p.start <= gold["start"]
                        and gold["end"] <= p.end
                    ):
                        found.add(i)
                        first = first or rank
            needed = 1 if q.get("match") == "any" else len(golds)
            rows.append(
                {
                    "id": q["id"],
                    "split": q["split"],
                    "recall_at_10": min(1.0, len(found) / needed),
                    "reciprocal_rank": 1 / first if first else 0.0,
                    "top": [
                        f"{h.passage.citation.document} {h.passage.citation.location.book}."
                        f"{h.passage.citation.location.chapter}"
                        for h in hits[:3]
                    ],
                }
            )
        summary = {}
        for split in ("all", "dev", "heldout"):
            part = [r for r in rows if split == "all" or r["split"] == split]
            if part:
                summary[split] = {
                    "recall_at_10": sum(r["recall_at_10"] for r in part) / len(part),
                    "mrr_at_10": sum(r["reciprocal_rank"] for r in part) / len(part),
                    "questions": len(part),
                }
        report["strategies"][strategy] = {
            **summary,
            "failures": [r for r in rows if r["recall_at_10"] < 1],
            "details": rows,
        }
    for q in dataset.get("out_of_corpus", []):
        hits = retriever.search(q["query"], limit=3, strategy="hybrid", filters=scoped)
        report["out_of_corpus"].append(
            {
                "id": q["id"],
                "query": q["query"],
                # Diagnostics only: nearby material is expected; this is not abstention.
                "retrieved": [h.passage.citation.document for h in hits],
            }
        )
    return report
