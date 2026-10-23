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


def _containing(passages, chapter, gold) -> bool:
    return any(p.start <= gold["start"] and gold["end"] <= p.end for p in passages[chapter.id])


def _ranks(hits, golds) -> list[int | None]:
    """1-based rank of the first hit wholly containing each gold span, or None."""
    ranks: list[int | None] = [None] * len(golds)
    for rank, hit in enumerate(hits, 1):
        p = hit.passage
        for i, (chapter, gold) in enumerate(golds):
            if ranks[i] is None and p.chapter_id == chapter.id:
                if p.start <= gold["start"] and gold["end"] <= p.end:
                    ranks[i] = rank
    return ranks


def _miss(hits, golds) -> str:
    """Where the top hit landed relative to the gold, for failure analysis."""
    if not hits:
        return "nothing retrieved"
    top = hits[0].passage
    if any(top.chapter_id == c.id for c, _ in golds):
        return "right chapter, other passage"
    if any(top.citation.document == c.document for c, _ in golds):
        return "right work, other chapter"
    return "other work"


def _summary(rows: list[dict]) -> dict:
    return {
        "recall_at_10": sum(r["recall_at_10"] for r in rows) / len(rows),
        "mrr_at_10": sum(r["reciprocal_rank"] for r in rows) / len(rows),
        "questions": len(rows),
    }


def _breakdown(rows: list[dict], key: str) -> dict:
    groups: dict[str, list[dict]] = {}
    for r in rows:
        if r.get(key):
            groups.setdefault(r[key], []).append(r)
    return {k: _summary(v) for k, v in sorted(groups.items())}


def evaluate_passages(
    retriever: Retriever, path: Path, limit: int = 10, *, include_opt_in: bool = False
) -> dict:
    """Passage-level benchmark over the whole library; separate from the chapter benchmark.

    A retrieved passage is relevant only if it lies in the gold chapter and contains a
    complete gold span (Python code points), so chunking changes cannot invent evidence.
    `"match": "any"` marks gold spans that are alternatives (a refrain or a verse shared
    by several texts): finding one of them is full recall for that question.
    By default search covers what chat's "All texts" covers (opt-in works excluded);
    `include_opt_in` searches the whole index. A question's own `scope` (a chat scope
    such as "yoga-vasistha") is searched as chat searches it. Follow-ups are scored on
    their reference `standalone` rewrite, and separately on the raw follow-up.
    Out-of-corpus questions (no gold) are diagnostics only: nearby material is expected.
    """
    import hashlib

    from pramana.library import default_documents, scope_documents

    store = retriever.corpus.store
    within = None if include_opt_in else default_documents(store)
    raw = path.read_bytes()
    dataset = json.loads(raw.decode("utf-8"))
    questions = dataset.get("questions", [])
    if not questions:
        raise PramanaError("Passage benchmark has no questions.")
    chapters = store.chapters()
    ooc = [q for q in questions if q.get("type") == "out_of_corpus"]
    questions = [q for q in questions if q.get("type") != "out_of_corpus"]
    resolved = []
    for q in questions:
        if q.get("match", "all") not in {"all", "any"}:
            raise PramanaError(f"Question {q.get('id')} has an unknown match mode.")
        if q.get("split") not in {"dev", "heldout"} or not q.get("gold"):
            raise PramanaError(f"Question {q.get('id')} needs a dev/heldout split and gold spans.")
        resolved.append([(_resolve_span(chapters, g), g) for g in q["gold"]])
    passages: dict[str, list] = {}
    for c in {c.id: c for group in resolved for c, _ in group}.values():
        passages[c.id] = store.passages_for(c.id)
    scopes: dict[str, SearchFilters | None] = {}

    def filters(q: dict) -> SearchFilters | None:
        scope = q.get("scope", "all")
        if scope not in scopes:
            ids = scope_documents(store, scope) if scope != "all" else within
            if scope != "all" and not ids:
                raise PramanaError(f"No imported books are in the {scope} scope.")
            scopes[scope] = SearchFilters(document_ids=ids) if ids is not None else None
        return scopes[scope]

    review = [q.get("review", {}).get("status", "unreviewed") for q in questions + ooc]
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
        "index": store.get_meta("index_config"),
        "sources": sorted(
            {(c.id, c.source.checksum) for group in resolved for c, _ in group}, key=str
        ),
        # Gold spans no single indexed passage contains can never be found: a chunking
        # limit, reported rather than hidden.
        "uncontainable_spans": [
            {"id": q["id"], "quote": g["quote"][:80]}
            for q, group in zip(questions, resolved, strict=True)
            for c, g in group
            if not _containing(passages, c, g)
        ],
        "strategies": {},
        "out_of_corpus": [],
    }
    report["sources"] = [{"chapter_id": i, "source_checksum": s} for i, s in report["sources"]]
    typed = any("type" in q for q in questions)
    for strategy in ("lexical", "dense", "hybrid"):
        rows, raw_followups = [], []
        for q, golds in zip(questions, resolved, strict=True):
            needed = 1 if q.get("match") == "any" else len(golds)
            searches = [("row", q.get("standalone") or q["query"])]
            if q.get("standalone"):
                searches.append(("raw", q["query"]))
            for kind, query in searches:
                # Candidate pools are 50 deep whatever the limit, so the top 10 of this
                # search equal a limit-10 search; deeper ranks explain the misses.
                hits = retriever.search(query, limit=50, strategy=strategy, filters=filters(q))
                ranks = _ranks(hits, golds)
                found = [r for r in ranks if r is not None and r <= limit]
                row = {
                    "id": q["id"],
                    "split": q["split"],
                    "recall_at_10": min(1.0, len(found) / needed),
                    "reciprocal_rank": 1 / min(found) if found else 0.0,
                    "top": [
                        f"{h.passage.citation.document} {h.passage.citation.location.book}."
                        f"{h.passage.citation.location.chapter}"
                        for h in hits[:3]
                    ],
                }
                if typed:
                    row |= {
                        "type": q.get("type"),
                        "text": q.get("text"),
                        "scope": q.get("scope"),
                        "origin": q.get("origin"),
                    }
                if row["recall_at_10"] < 1:
                    seen = [r for r in ranks if r is not None]
                    row["best_rank_at_50"] = min(seen) if seen else None
                    row["miss"] = _miss(hits[:limit], golds)
                if q.get("match") != "any" and len(golds) > 1:
                    row["found"] = [r is not None and r <= limit for r in ranks]
                (rows if kind == "row" else raw_followups).append(row)
        summary = {}
        for split in ("all", "dev", "heldout"):
            part = [r for r in rows if split == "all" or r["split"] == split]
            if part:
                summary[split] = _summary(part)
        failures = [r for r in rows if r["recall_at_10"] < 1]
        result = {**summary, "failures": failures, "details": rows}
        if typed:
            result["by_type"] = _breakdown(rows, "type")
            result["by_text"] = _breakdown(rows, "text")
            # Questions carried over from an earlier dataset version vs newly drafted ones.
            result["by_origin"] = _breakdown(rows, "origin")
            result["failure_kinds"] = {
                k: sum(r["miss"] == k for r in failures)
                for k in sorted({r["miss"] for r in failures})
            }
            result["failure_depth"] = {
                "found_at_11_to_50": sum(r["best_rank_at_50"] is not None for r in failures),
                "not_in_top_50": sum(r["best_rank_at_50"] is None for r in failures),
            }
            pairs = [r["found"] for r in rows if r.get("type") == "comparison" and "found" in r]
            if pairs:
                result["comparison_coverage"] = {
                    "both": sum(all(f) for f in pairs),
                    "one": sum(any(f) and not all(f) for f in pairs),
                    "neither": sum(not any(f) for f in pairs),
                }
            if raw_followups:
                result["followup_raw"] = _summary(raw_followups)
                result["followup_rewritten"] = _summary(
                    [r for r in rows if r.get("type") == "followup"]
                )
        report["strategies"][strategy] = result
    probes = dataset.get("out_of_corpus", []) + ooc
    for q in probes:
        hits = retriever.search(q["query"], limit=3, strategy="hybrid", filters=filters(q))
        report["out_of_corpus"].append(
            {
                "id": q["id"],
                "query": q["query"],
                **({"kind": q["ooc_kind"]} if "ooc_kind" in q else {}),
                # Diagnostics only: nearby material is expected; this is not abstention.
                "retrieved": [h.passage.citation.document for h in hits],
            }
        )
    return report


def _fold(text: str) -> str:
    import unicodedata

    return "".join(
        c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c)
    )


# Benchmark thinker keys and the folded author names of their editions.
THINKER_AUTHORS = {"shankara": ("sankara",), "ramanuja": ("ramanuja",)}


def _latency(values: list[float]) -> dict:
    if not values:
        return {}
    ordered = sorted(values)
    pick = lambda q: ordered[min(len(ordered) - 1, int(q * len(ordered)))]  # noqa: E731
    return {"mean": sum(ordered) / len(ordered), "p50": pick(0.5), "p90": pick(0.9)}


def _answer_summary(rows: list[dict]) -> dict:
    answerable = [r for r in rows if r["expect"] == "grounded"]
    refusals = [r for r in rows if r["expect"] == "insufficient_evidence"]
    cited = [r["gold_cited"] for r in answerable if r["gold_cited"] is not None]
    on = [r["evidence_on_thinker"] for r in rows if r.get("evidence_on_thinker") is not None]
    return {
        "questions": len(rows),
        "status_accuracy": sum(r["status_ok"] for r in rows) / len(rows),
        "grounded_when_answerable": (
            sum(r["status"] == "grounded" for r in answerable) / len(answerable)
            if answerable
            else None
        ),
        "refused_when_out_of_corpus": (
            sum(r["status"] == "insufficient_evidence" for r in refusals) / len(refusals)
            if refusals
            else None
        ),
        "gold_cited": sum(cited) / len(cited) if cited else None,
        "evidence_on_thinker": sum(on) / len(on) if on else None,
        "errors": sum(r["status"] == "error" for r in rows),
        "latency_seconds": _latency([r["seconds"] for r in rows]),
    }


async def evaluate_answers(
    answerer,
    path: Path,
    *,
    split: str | None = None,
    limit: int | None = None,
    check: bool = False,
    partial: Path | None = None,
    progress=None,
) -> dict:
    """Answer-level evaluation with the configured model; separate from retrieval scores.

    Per question: whether the status matches the expectation (grounded, or a refusal for
    out-of-corpus questions), whether a cited passage contains a gold span, whether a
    single-thinker question's evidence comes from that thinker's editions, whether a
    comparison returns a view for each expected thinker, and wall-clock latency. None of
    this measures whether an answer's claims are correct; that needs human review.
    `partial` keeps finished questions so an interrupted run resumes.
    """
    import hashlib
    import time

    from pramana.answering import AnswerError
    from pramana.models import ChatRequest

    raw = path.read_bytes()
    dataset_sha = hashlib.sha256(raw).hexdigest()
    questions = json.loads(raw.decode("utf-8")).get("questions", [])
    questions = [q for q in questions if split is None or q.get("split") == split][:limit]
    if not questions:
        raise PramanaError("No questions selected.")
    chapters = answerer.retriever.corpus.store.chapters()
    done: dict[str, dict] = {}
    if partial and partial.exists():
        for line in partial.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("dataset_sha256") == dataset_sha and row.get("check") == check:
                done[row["id"]] = row
    rows = []
    for n, q in enumerate(questions, 1):
        if q["id"] in done:
            rows.append(done[q["id"]])
            continue
        golds = [(_resolve_span(chapters, g), g) for g in q.get("gold", [])]
        expect = q.get("expect", "grounded")
        request = ChatRequest(
            message=q["query"],
            history=q.get("history", []),
            scope=q.get("scope", "all"),
            check=check,
        )
        started = time.perf_counter()
        try:
            response = await answerer.answer(request)
            status, error = response.status, None
        except AnswerError as exc:
            response, status, error = None, "error", str(exc)
        seconds = time.perf_counter() - started
        evidence = [e.passage for e in response.evidence] if response else []
        ranks = [
            any(
                p.chapter_id == c.id and p.start <= g["start"] and g["end"] <= p.end
                for p in evidence
            )
            for c, g in golds
        ]
        gold_cited = None
        if golds and status == "grounded":
            needed = 1 if q.get("match") == "any" else len(golds)
            gold_cited = min(1.0, sum(ranks) / needed)
        elif golds:
            gold_cited = 0.0
        thinkers = q.get("thinkers", [])
        on_thinker = None
        if len(thinkers) == 1 and evidence:
            names = THINKER_AUTHORS.get(thinkers[0], (thinkers[0],))
            on_thinker = sum(
                any(n in _fold(p.citation.author) for n in names) for p in evidence
            ) / len(evidence)
        row = {
            "id": q["id"],
            "split": q["split"],
            "type": q.get("type"),
            "text": q.get("text"),
            "expect": expect,
            "status": status,
            "status_ok": status == expect,
            "gold_cited": gold_cited,
            "evidence_on_thinker": on_thinker,
            "seconds": round(seconds, 2),
            "answer_words": len(response.answer.split()) if response else 0,
            "evidence": len(evidence),
            "retrieval_question": response.retrieval_question if response else None,
            "answer": response.answer if response else error,
            "dataset_sha256": dataset_sha,
            "check": check,
        }
        if len(thinkers) > 1:
            views = [_fold(p.thinker) for p in (response.perspectives if response else [])]
            row["perspectives_for_each_thinker"] = all(
                any(any(n in v for n in THINKER_AUTHORS.get(t, (t,))) for v in views)
                for t in thinkers
            )
        if check and response and response.check:
            row["check_removed"] = response.check.removed
        rows.append(row)
        if partial:
            partial.parent.mkdir(parents=True, exist_ok=True)
            with partial.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        if progress:
            progress(f"{n}/{len(questions)} {q['id']} {status} {seconds:.1f}s")
    comparisons = [r for r in rows if "perspectives_for_each_thinker" in r]
    return {
        "label": "Answer-level evaluation (model-generated answers; not scholarly validation)",
        "dataset_sha256": dataset_sha,
        "model": getattr(answerer.provider, "model", None),
        "check": check,
        "index": answerer.retriever.corpus.store.get_meta("index_config"),
        "overall": _answer_summary(rows),
        "by_split": {
            s: _answer_summary([r for r in rows if r["split"] == s])
            for s in ("dev", "heldout")
            if any(r["split"] == s for r in rows)
        },
        "by_type": {
            t: _answer_summary([r for r in rows if r["type"] == t])
            for t in sorted({r["type"] for r in rows if r["type"]})
        },
        "by_text": {
            t: _answer_summary([r for r in rows if r["text"] == t])
            for t in sorted({r["text"] for r in rows if r["text"]})
        },
        "comparisons_with_each_view": (
            sum(r["perspectives_for_each_thinker"] for r in comparisons) / len(comparisons)
            if comparisons
            else None
        ),
        "details": [{k: v for k, v in r.items() if k not in ("dataset_sha256",)} for r in rows],
    }


async def evaluate_routing(answerer, path: Path) -> dict:
    """The routing step alone: one short model call per question, no retrieval.

    Out-of-corpus questions should route as unrelated, others as texts. The routing
    prompt was chosen by comparing variants on this dataset, so these numbers are tuned,
    not held out. Near-domain
    questions (other traditions, works not in the library) may route either way; a
    "texts" route still leaves the evidence-based refusal to the answer step.
    """
    import hashlib

    raw = path.read_bytes()
    questions = json.loads(raw.decode("utf-8")).get("questions", [])
    rows = []
    for q in questions:
        # Routing sees the standalone question, as chat does after rewriting a follow-up.
        text = q.get("standalone") or q["query"]
        route = await answerer.route(text)
        rows.append(
            {
                "id": q["id"],
                "type": q.get("type"),
                "kind": q.get("ooc_kind"),
                "query": text,
                "route": route,
            }
        )
    answerable = [r for r in rows if r["type"] != "out_of_corpus"]
    probes = [r for r in rows if r["type"] == "out_of_corpus"]
    kinds = sorted({r["kind"] for r in probes if r["kind"]})
    return {
        "label": "Routing step (texts or unrelated) before retrieval",
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "model": getattr(answerer.provider, "model", None),
        "answerable_routed_to_texts": sum(r["route"] == "texts" for r in answerable),
        "answerable": len(answerable),
        "out_of_corpus_routed_unrelated": {
            k: [
                sum(r["route"] == "unrelated" for r in probes if r["kind"] == k),
                sum(r["kind"] == k for r in probes),
            ]
            for k in kinds
        },
        "wrongly_declined": [r for r in answerable if r["route"] == "unrelated"],
        "details": rows,
    }
