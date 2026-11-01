"""Verse pages and the great sayings (mahāvākyas), for the Study view.

A verse page sets one scripture verse beside every passage that cites it with a printed
reference (from the citation index, `citations.py`), grouped by author, each with the
words around the reference. The four great sayings are curated entry points
(`sayings.json`): each names a printed section and verse number, is resolved in the
stored text at runtime, and counts only if its check words occur there. Nothing is
located by guessing. Quotations of a saying's wording without a printed reference are
listed separately and never merged with references.

Offsets are Python code points into the stored chapter text.
"""

import json
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from pramana.citations import _verse
from pramana.citations import index as citation_index
from pramana.glossary import fold
from pramana.library import role_spans
from pramana.models import Chapter
from pramana.storage import Store

CONTEXT_BEFORE, CONTEXT_AFTER = 420, 160
NEAR = 300  # at most this far before a printed reference, within one sentence: its quote
_cache: dict[tuple, dict] = {}


@lru_cache
def curated() -> list[dict]:
    return json.loads((Path(__file__).parent / "sayings.json").read_text(encoding="utf-8"))


def _place(chapter: Chapter) -> str:
    return ", ".join(chapter.location.sections) or (
        f"{chapter.location.book}.{chapter.location.chapter}"
    )


def context(text: str, start: int, end: int) -> dict:
    """The words around a span, widened to sentence boundaries, with the span's position."""
    lo = max(0, start - CONTEXT_BEFORE)
    hi = min(len(text), end + CONTEXT_AFTER)
    if lo > 0:
        cut = max(text.rfind(". ", lo, start - 1), text.rfind("\n", lo, start - 1))
        lo = cut + 1 if cut >= 0 else lo
    if hi < len(text):
        stop = min(
            (i for i in (text.find(". ", end, hi), text.find("\n", end, hi)) if i >= 0), default=-1
        )
        hi = stop + 1 if stop >= 0 else hi
    excerpt = text[lo:hi]
    lead = len(excerpt) - len(excerpt.lstrip())
    return {
        "text": excerpt.strip(),
        "start": start - lo - lead,
        "end": end - lo - lead,
        "clipped_before": lo > 0,
        "clipped_after": hi < len(text),
    }


def _verse_extent(chapter: Chapter, number: int) -> tuple[int, int] | None:
    """A numbered verse from its paragraph to the next printed number (a verse may run
    over several paragraphs, as Bṛhadāraṇyaka II, 5, 19 does), or the chapter's end."""
    first = _verse(chapter, number)
    if not first:
        return None
    following = list(re.finditer(rf"(?m)^[ \t]*'?{number + 1}\.\s", chapter.text))
    end = following[0].start() if len(following) == 1 and following[0].start() > first[0] else None
    return first[0], (end if end is not None else len(chapter.text))


TITLE_ROLE = re.compile(r"(?P<objection>purvapaksh?a)|(?P<reply>siddhanta)")
# A cued segment runs until the next cue, which can be pages away when a reply carries
# no printed cue; only a citation this close after the cue that opens it is labelled.
CUE_REACH = 1200


def _role(chapter: Chapter, at: int, spans: dict[str, list[dict]]) -> dict | None:
    """Whether a citation stands in an objection or a reply, from printed cues only.

    A page whose printed title names the pūrvapakṣa ("The Small Pûrvapaksha") is the
    opposing view throughout, replies to objections within it included, so the title
    decides; otherwise a cued segment of the text does, near its cue only. A
    commentator citing a text while setting out the opposing view does not endorse it.
    """
    title = " ".join(chapter.location.sections[1:])
    if m := TITLE_ROLE.search(fold(title)):
        return {"role": "objection" if m["objection"] else "reply", "from": title}
    if chapter.id not in spans:
        spans[chapter.id] = role_spans(chapter.text)
    for span in spans[chapter.id]:
        if span["start"] <= at < min(span["end"], span["start"] + CUE_REACH):
            return {"role": span["role"], "from": "cue"}
    return None


def _entry(ref: dict, chapters: dict[str, Chapter], spans: dict[str, list[dict]]) -> dict:
    source = chapters[ref["chapter_id"]]
    return {
        "role": _role(source, ref["start"], spans),
        "author": ref["author"],
        "document": ref["document"],
        "chapter_id": ref["chapter_id"],
        "place": ref["place"],
        "label": ref["label"],
        "status": ref["status"],
        "start": ref["start"],
        "end": ref["end"],
        "context": context(source.text, ref["start"], ref["end"]),
    }


def _group(entries: list[dict]) -> list[dict]:
    by: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        by[e["author"]].append(e)
    return [
        {"author": author, "passages": sorted(items, key=lambda e: (e["document"], e["place"]))}
        for author, items in sorted(by.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    ]


def _data(store: Store) -> dict:
    key = (str(store.path), store.get_meta("generation"))
    if key not in _cache:
        _cache.clear()
        _cache[key] = {
            "chapters": {c.id: c for c in store.chapters()},
            "sayings": {},
            "roles": {},
        }
    return _cache[key]


def verse(store: Store, chapter_id: str, start: int, end: int) -> dict:
    """One verse and every printed reference to it, grouped by citing author."""
    data = _data(store)
    chapters = data["chapters"]
    target = chapters.get(chapter_id)
    if target is None:
        raise KeyError(chapter_id)
    if not 0 <= start < end <= len(target.text):
        raise ValueError("The span is outside the chapter.")
    incoming = citation_index(store)["incoming"].get(chapter_id, [])
    whole = (0, len(target.text))
    exact, chapter_level = [], []
    for ref in incoming:
        span = (ref["target_start"], ref["target_end"])
        if span == whole:
            chapter_level.append(_entry(ref, chapters, data["roles"]))
        elif span[0] < end and start < span[1]:
            exact.append(_entry(ref, chapters, data["roles"]))
    return {
        "chapter_id": chapter_id,
        "document": target.document,
        "place": _place(target),
        "edition": target.edition,
        "translator": target.translator,
        "start": start,
        "end": end,
        "text": target.text[start:end],
        "citations": _group(exact),
        "whole": _group(chapter_level),
    }


def _resolve(entry: dict, chapters: dict[str, Chapter]) -> dict | None:
    t = entry["target"]
    found = [
        c
        for c in chapters.values()
        if c.document_id == t["document_id"]
        and c.location.sections
        and c.location.sections[0] == t["section"]
    ]
    if len(found) != 1:
        return None
    chapter = found[0]
    span = _verse_extent(chapter, t["verse"])
    if not span:
        return None
    words = chapter.text[span[0] : span[1]]
    for check in entry["check"]:
        at = words.lower().find(check.lower())
        if at >= 0:
            return {
                "chapter": chapter,
                "start": span[0],
                "end": span[1],
                "mark": [span[0] + at, span[0] + at + len(check)],
            }
    return None


def _quotations(entry: dict, found: dict, store: Store, chapters: dict[str, Chapter]) -> list:
    """Places that use the saying's wording without a printed reference to its verse."""
    outgoing = citation_index(store)["outgoing"]
    target = found["chapter"]
    # The wording as a whole saying: it must end there (punctuation, a line end, or a
    # vocative, as in "that art thou, O Svetaketu"), so "thou art that which is…" is not it.
    pattern = re.compile(
        r"\b(?:"
        + "|".join(r"\s+".join(map(re.escape, p.split())) for p in entry["phrases"])
        + r")(?=\s*(?:[.,;:!?'\"’”)\]]|$|O\b))",
        re.IGNORECASE | re.MULTILINE,
    )
    hits = []
    for c in chapters.values():
        if c.document_id == target.document_id:
            continue
        refs = [
            r["start"]
            for r in outgoing.get(c.id, [])
            if r["target"]["chapter_id"] == target.id
            and r["target"]["start"] < found["end"]
            and found["start"] < r["target"]["end"]
        ]
        for m in pattern.finditer(c.text):
            if any(_attached(c.text, m.end(), r) for r in refs):
                continue  # the quote of a printed reference, already listed
            hits.append(
                {
                    "author": c.author or c.translator,
                    "document": c.document,
                    "chapter_id": c.id,
                    "place": _place(c),
                    "start": m.start(),
                    "end": m.end(),
                    "context": context(c.text, m.start(), m.end()),
                }
            )
    return hits


def _attached(text: str, end: int, ref: int) -> bool:
    """Whether words ending at `end` are the quotation of the reference at `ref`: shortly
    before it, with no sentence break between."""
    if not end <= ref <= end + NEAR:
        return False
    return not re.search(r"[.!?]['’\"”]?\s+[A-Z]", text[end:ref])


def _counts(groups: list[dict]) -> dict[str, int]:
    return {g["author"]: len(g["passages"]) for g in groups}


def _objections(groups: list[dict]) -> dict[str, int]:
    """Per author, how many of those citations stand in a cued objection."""
    out = {}
    for g in groups:
        n = sum(1 for p in g["passages"] if (p.get("role") or {}).get("role") == "objection")
        if n:
            out[g["author"]] = n
    return out


def saying(store: Store, key: str) -> dict:
    """A great saying: its verse page, plus quotations of its wording."""
    data = _data(store)
    if key in data["sayings"]:
        return data["sayings"][key]
    entry = next((e for e in curated() if e["key"] == key), None)
    if entry is None:
        raise KeyError(key)
    head = {k: entry[k] for k in ("key", "saying", "devanagari", "english", "note")}
    head["number"] = entry["target"]["verse"]
    found = _resolve(entry, data["chapters"])
    if not found:
        result = {**head, "found": False}
    else:
        page = verse(store, found["chapter"].id, found["start"], found["end"])
        quotations = _group(_quotations(entry, found, store, data["chapters"]))
        result = {
            **head,
            "found": True,
            "mark": found["mark"],
            "verse": page,
            "quotations": quotations,
            "cited": _counts(page["citations"]),
            "cited_in_objection": _objections(page["citations"]),
            "quoted": _counts(quotations),
        }
    data["sayings"][key] = result
    return result


def sayings(store: Store) -> list[dict]:
    """Every curated saying, as a summary (no citing passages)."""
    out = []
    for entry in curated():
        full = saying(store, entry["key"])
        summary = {k: v for k, v in full.items() if k not in ("verse", "quotations")}
        if full["found"]:
            v = full["verse"]
            summary["verse"] = {
                k: v[k] for k in ("chapter_id", "document", "place", "start", "end", "text")
            }
        out.append(summary)
    return out
