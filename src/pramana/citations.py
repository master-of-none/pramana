"""Printed scripture references ("(Kh. Up. VI, 8, 7)") resolved to passages in the library.

Thibaut's Brahma Sūtra translations print a reference after each quotation. A reference
is resolved only from what is printed: the work's abbreviation and its numbers, mapped
to the matching edition's printed divisions. Nothing is inferred. Bare references
("II, 4, 5") that rely on an earlier one are left as text, and so is any reference whose
division does not exist.

Each resolved reference carries how far it was checked:

- `verified`: the words quoted just before the reference occur, as consecutive word
  pairs, in the target paragraph. That is the numbered verse when it matches, otherwise
  the best-matching paragraph of the cited chapter (the translator's verse numbering can
  differ from the edition's).
- `numbered`: no quotation to check; the paragraph printed with that verse number.
- `chapter`: the cited chapter only (no unique verse paragraph, or the quotation's
  wording did not match: the translations differ).

Offsets are Python code points into the stored chapter text.
"""

import re
import unicodedata
from collections import defaultdict

from pramana.models import Chapter
from pramana.storage import Store

ROMAN = {
    numeral: value
    for value, numeral in enumerate(
        "I II III IV V VI VII VIII IX X XI XII XIII XIV XV XVI XVII XVIII".split(), 1
    )
}
# Abbreviation as printed -> (document ID in this library, division scheme).
# "label": sections printed "VI, 8" with numbered verses; "adhyaya": chapter = first
# number, verse = second; "verse": one chapter, verse = first number; "book": book and
# chapter, no verse numbering (Wilson's prose Purana).
WORKS = (
    (r"Kh\. ?Up", "chandogya-upanishad-sbe01", "label"),
    (r"Bri\. ?Up", "brihadaranyaka-upanishad-sbe15", "label"),
    (r"Mu\. ?Up", "mundaka-upanishad-sbe15", "label"),
    (r"Taitt\. ?Up", "taittiriya-upanishad-sbe15", "label"),
    (r"Ka\. ?Up", "katha-upanishad-sbe15", "label"),
    (r"Sve?t?\. ?Up", "svetasvatara-upanishad-sbe15", "adhyaya"),
    (r"Kau\. ?Up", "kaushitaki-upanishad-sbe01", "adhyaya"),
    (r"Pra?\. ?Up", "prasna-upanishad-sbe15", "adhyaya"),
    (r"Ke\. ?Up", "kena-upanishad-sbe01", "adhyaya"),
    (r"Bha\. ?G[îi]", "bhagavad-gita-sbg", "adhyaya"),
    (r"[ÎI]s[âa]?\. ?Up", "isa-upanishad-sbe01", "verse"),
    (r"Vi\. ?Pu", "vishnu-purana", "book"),
)
NUMBER = r"(?:[IVXLivxl]+|l?\d+)"
REFERENCE = re.compile(
    r"\((?:"
    + "|".join(f"(?P<w{i}>{pattern})" for i, (pattern, _, _) in enumerate(WORKS))
    + rf")\.?\s*(?P<a>{NUMBER})(?:[\.,]\s*(?P<b>{NUMBER}))?(?:[\.,]\s*(?P<c>{NUMBER}))?"
    r"[^()]{0,16}\)"
)
PARAGRAPH = re.compile(r"[^\n]+(?:\n(?!\s*\n)[^\n]+)*")


def _number(text: str | None) -> int | None:
    if not text:
        return None
    text = text.strip().rstrip(".")
    if re.fullmatch(r"l?\d+", text):
        return int(text.replace("l", "1"))  # "l2": a scanned 1
    return ROMAN.get(text.upper().replace("L", "I"))  # "Ill" is a scanned III


def _words(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", text.lower())
    return re.findall(r"\w+", "".join(c for c in folded if not unicodedata.combining(c)))


def _pairs(text: str) -> set[tuple[str, str]]:
    words = _words(text)
    return set(zip(words, words[1:], strict=False))


def _quotation(text: str, position: int) -> str | None:
    """The quoted words that end just before a reference, if any."""
    before = text[max(0, position - 600) : position].rstrip()
    if not before or before[-1] not in "'’\"”":
        return None
    body = before[:-1]
    opening = max(body.rfind(" '"), body.rfind("\n'"), body.rfind("‘"), body.rfind('"'))
    return body[opening + 1 :].strip(" '‘") if opening >= 0 else None


class Library:
    """Target chapters of the referenced works, indexed by printed division."""

    def __init__(self, chapters: list[Chapter]):
        self.labels: dict[tuple, Chapter] = {}
        self.numbers: dict[tuple, Chapter] = defaultdict(lambda: None)
        self.single: dict[str, Chapter] = {}
        self.books: dict[tuple, Chapter] = {}
        targets = {doc for _, doc, _ in WORKS}
        counts: dict[str, int] = defaultdict(int)
        for chapter in chapters:
            doc = chapter.document_id
            if doc not in targets:
                continue
            counts[doc] += 1
            location = chapter.location
            first = location.sections[0] if location.sections else ""
            if m := re.fullmatch(r"([IVXL]+), (\d+)", first):
                self.labels[(doc, ROMAN.get(m[1]), int(m[2]))] = chapter
            if location.chapter.isdigit():
                self.numbers[(doc, int(location.chapter))] = chapter
            if location.book.isdigit() and location.chapter.isdigit():
                self.books[(doc, int(location.book), int(location.chapter))] = chapter
            self.single[doc] = chapter
        self.single = {doc: c for doc, c in self.single.items() if counts[doc] == 1}

    def chapter(self, doc: str, scheme: str, a, b, c):
        """(chapter, printed verse number or None), or (None, None) if unresolved."""
        if doc.startswith("katha") and a == 2 and b and b <= 3:
            b += 3  # Thibaut prints adhyāya II, vallī 1-3; this edition numbers vallīs 4-6.
        if scheme == "label":
            return self.labels.get((doc, a, b)), c
        if scheme == "adhyaya":
            return self.numbers.get((doc, a)), b
        if scheme == "verse":
            return self.single.get(doc), a
        return self.books.get((doc, a, b)), None


def _paragraphs(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in PARAGRAPH.finditer(text)]


def _verse(chapter: Chapter, number: int | None) -> tuple[int, int] | None:
    if number is None:
        return None
    found = list(re.finditer(rf"(?m)^[ \t]*'?{number}\.\s", chapter.text))
    if len(found) != 1:
        return None
    start = found[0].start() + len(found[0][0]) - len(found[0][0].lstrip())
    return next(((s, e) for s, e in _paragraphs(chapter.text) if s <= start < e), None)


def resolve(text: str, library: Library) -> list[dict]:
    """Every printed reference in `text` that names a work in the library."""
    found = []
    for m in REFERENCE.finditer(text):
        index = int(next(k for k, v in m.groupdict().items() if k.startswith("w") and v)[1:])
        _, doc, scheme = WORKS[index]
        a, b, c = (_number(m[g]) for g in "abc")
        chapter, number = library.chapter(doc, scheme, a, b, c)
        if chapter is None or a is None:
            continue
        verse = _verse(chapter, number)
        quote = _quotation(text, m.start())
        target, status = (0, len(chapter.text)), "chapter"
        pairs = _pairs(quote) if quote else set()
        if len(pairs) >= 2:

            def score(span, chapter=chapter, pairs=pairs):
                hit = len(pairs & _pairs(chapter.text[span[0] : span[1]]))
                return hit / len(pairs), hit

            if verse and score(verse)[0] >= 0.3 and score(verse)[1] >= 2:
                target, status = verse, "verified"
            else:
                best = max(_paragraphs(chapter.text), key=score, default=None)
                if best and score(best)[0] >= 0.4 and score(best)[1] >= 2:
                    target, status = best, "verified"
        elif verse:
            target, status = verse, "numbered"
        found.append(
            {
                "start": m.start(),
                "end": m.end(),
                "label": m[0][1:-1],
                "status": status,
                "quote": quote if status == "verified" else None,
                "target": {
                    "chapter_id": chapter.id,
                    "document": chapter.document,
                    "place": ", ".join(chapter.location.sections)
                    or f"{chapter.location.book}.{chapter.location.chapter}",
                    "start": target[0],
                    "end": target[1],
                },
            }
        )
    return found


_cache: dict[tuple, dict] = {}


def index(store: Store) -> dict:
    """References from every chapter, and the reverse map from target chapters.

    Rebuilt when the library's generation changes; reading it costs one pass over the
    stored text.
    """
    key = (str(store.path), store.get_meta("generation"))
    if key in _cache:
        return _cache[key]
    chapters = store.chapters()
    library = Library(chapters)
    outgoing, incoming = {}, defaultdict(list)
    for chapter in chapters:
        refs = resolve(chapter.text, library)
        if refs:
            outgoing[chapter.id] = refs
        for ref in refs:
            incoming[ref["target"]["chapter_id"]].append(
                {
                    "chapter_id": chapter.id,
                    "document": chapter.document,
                    "author": chapter.author or chapter.translator,
                    "place": ", ".join(chapter.location.sections)
                    or f"{chapter.location.book}.{chapter.location.chapter}",
                    "start": ref["start"],
                    "end": ref["end"],
                    "label": ref["label"],
                    "status": ref["status"],
                    "quote": ref["quote"],
                    "target_start": ref["target"]["start"],
                    "target_end": ref["target"]["end"],
                }
            )
    _cache.clear()
    _cache[key] = {"outgoing": outgoing, "incoming": dict(incoming)}
    return _cache[key]


def for_chapter(store: Store, chapter_id: str) -> dict:
    data = index(store)
    return {
        "outgoing": data["outgoing"].get(chapter_id, []),
        "incoming": data["incoming"].get(chapter_id, []),
    }


def summary(store: Store, limit: int = 40) -> dict:
    """The most-cited passages, with counts per citing author, and resolution totals."""
    data = index(store)
    statuses: dict[str, int] = defaultdict(int)
    for refs in data["outgoing"].values():
        for ref in refs:
            statuses[ref["status"]] += 1
    chapters = {c.id: c for c in store.chapters()}
    passages: dict[tuple, dict] = {}
    for chapter_id, refs in data["incoming"].items():
        target = chapters[chapter_id]
        for ref in refs:
            # Chapter-level references are counted against the chapter as a whole.
            span = (ref["target_start"], ref["target_end"])
            entry = passages.setdefault(
                (chapter_id, span),
                {
                    "chapter_id": chapter_id,
                    "document": target.document,
                    "place": ", ".join(target.location.sections)
                    or f"{target.location.book}.{target.location.chapter}",
                    "start": span[0],
                    "end": span[1],
                    "whole_chapter": span == (0, len(target.text)),
                    "opening": target.text[span[0] : span[0] + 160].strip(),
                    "by": defaultdict(int),
                    "total": 0,
                },
            )
            entry["by"][ref["author"]] += 1
            entry["total"] += 1
    top = sorted(
        (p for p in passages.values() if not p["whole_chapter"]),
        key=lambda p: (-p["total"], p["document"], p["start"]),
    )[:limit]
    for entry in top:
        entry["by"] = dict(sorted(entry["by"].items(), key=lambda x: -x[1]))
        # The verse number printed at the start of the passage, if any.
        verse = re.match(r"\s*'?(\d+)\s?\.", entry["opening"])
        entry["verse"] = int(verse[1]) if verse else None
    return {
        "references": sum(statuses.values()),
        "status": dict(statuses),
        "passages": top,
    }
