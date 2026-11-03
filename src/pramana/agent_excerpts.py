"""Excerpts (verses, passages, sentences) for agents and schedulers.

An excerpt is a slice of a stored chapter. A `verse` is a unit the edition prints a number
for; a `passage` (1-4 whole sentences) or `sentence` is cut from prose by splitting
sentences, so its boundary is derived, not printed, and it never carries a verse number.
Only documents on the reviewed allowlist (`excerpt_sources.json`) can supply excerpts, and a
document with a private local origin is refused outright. Nothing is cleaned: `text` is the
exact `chapter.text[start:end]`, offsets being Python code points.

Selection is stateless: `today` is a pure function of date, timezone and seed.
"""

import hashlib
import importlib.util
import json
import re
import secrets
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pramana.errors import PramanaError
from pramana.models import Chapter
from pramana.storage import Store
from pramana.verses import context as paragraph_context

KINDS = ("verse", "passage", "sentence")
VERSE_PARSERS = ("leading-number", "trailing-ref", "trailing-paren")
REFERENCES = ("section", "chapter", "label")
DEFAULT_CAP = 1000

PARA = re.compile(r"\n[ \t]*\n")
LEAD = re.compile(r"(?m)^[ \t]*['\"]?(\d{1,3})(?:[ \t]?[-–][ \t]?(\d{1,3}))?[ \t]?\.[ \t]+(?=\S)")
TRAIL = re.compile(r"(?m)\b(\d{1,2})\.(\d{1,3})[ \t]*$")
PAREN = re.compile(r"(?m)\((\d{1,3})\)\.?[ \t]*$")
MAX_GAP = 3  # a printed number may skip one or two; the gap is kept, never filled
MARKERS = ("[paragraph continues]",)
ENDS = re.compile(r"[.!?][\"'’”)\]]*$")
LEAD_IN = re.compile(r"(?::|:--|:—)[ \t]*$")
ANAPHORA = re.compile(
    r"^[\"'“‘(]*(?:He|She|It|They|This|That|These|Those|Thus|Therefore|Hence|And|But|Or"
    r"|Nor|For|So|Then|Now|Here|There|His|Her|Their|Its|Such|Moreover|Yet|However|Also|Again"
    r"|Likewise|Accordingly|Because|Since|Whereas|Which|Who|Whom|Whose)\b"
)
SPLIT = re.compile(r"(?<=[.!?])([\"'’”)\]]*)\s+(?=[\"'“‘(]?[A-Z])")
ABBREVIATIONS = {
    "Mr", "Mrs", "Dr", "St", "Vol", "viz", "Cf", "cf", "Ch", "ch", "No", "p", "pp", "vs",
    "etc", "Prof", "Rv", "Up", "Kh", "Bri", "Taitt", "Sk", "Skr",
}  # fmt: skip
CROSS_REFERENCE = re.compile(r"\(see\b|\bcf\.|\bp\. ?\d", re.IGNORECASE)

VERSE_BOUNDS = (40, 1200)
SENTENCE_BOUNDS = (60, 280)
PASSAGE_BOUNDS = (150, 600)
PASSAGE_SENTENCES = 4
NAME_SHARE = 0.25  # more capitalised words than this share is a list of names, not a thought

SOURCES_FILE = Path(__file__).parent / "excerpt_sources.json"


class ExcerptNotFound(KeyError):
    """The ID names nothing in the pool (never imported, not allowlisted, or text changed)."""


@dataclass(frozen=True)
class Entry:
    """One allowlisted document."""

    document_id: str
    label: str
    rights: str
    attribution: str
    kinds: dict[str, str]
    reference: str
    cap: int


@dataclass(frozen=True)
class Unit:
    start: int
    end: int
    body_start: int  # the text without a verse's printed number
    body_end: int
    label: str = ""
    gap_before: bool = False


@dataclass(frozen=True)
class Item:
    id: str
    kind: str
    document_id: str
    chapter_id: str
    start: int
    end: int
    body_start: int
    body_end: int
    label: str

    @property
    def length(self) -> int:
        return self.end - self.start


# --- the allowlist -------------------------------------------------------------------------


def parse_sources(data: dict) -> dict[str, Entry]:
    """Validate and flatten the allowlist; any mistake fails loudly, never silently drops."""
    entries: dict[str, Entry] = {}
    for group in data.get("groups", []):
        for key in ("rights", "attribution"):
            text = group.get(key, "")
            if not text.strip() or re.search(r"Next:|function\(|Previous:", text):
                raise PramanaError(f"Excerpt source group {group.get('name')!r}: bad {key} line.")
        for raw in group["documents"]:
            doc = {"id": raw} if isinstance(raw, str) else raw
            kinds = doc.get("kinds", group.get("kinds", {}))
            reference = doc.get("reference", group.get("reference", "section"))
            if not kinds or set(kinds) - set(KINDS):
                raise PramanaError(f"Excerpt source {doc['id']!r}: kinds must be among {KINDS}.")
            for kind, parser in kinds.items():
                ok = parser in VERSE_PARSERS if kind == "verse" else parser == "windows"
                if not ok:
                    raise PramanaError(f"Excerpt source {doc['id']!r}: bad parser for {kind}.")
            if reference not in REFERENCES:
                raise PramanaError(f"Excerpt source {doc['id']!r}: bad reference style.")
            if doc["id"] in entries:
                raise PramanaError(f"Excerpt source {doc['id']!r} is listed twice.")
            entries[doc["id"]] = Entry(
                document_id=doc["id"],
                label=doc.get("label", ""),
                rights=group["rights"],
                attribution=group["attribution"],
                kinds=dict(kinds),
                reference=reference,
                cap=int(doc.get("cap", group.get("cap", DEFAULT_CAP))),
            )
    return entries


@lru_cache
def load_sources() -> dict[str, Entry]:
    return parse_sources(json.loads(SOURCES_FILE.read_text(encoding="utf-8")))


# --- verse parsers -------------------------------------------------------------------------


def _paragraph_start(text: str, pos: int) -> int:
    start = max((m.end() for m in PARA.finditer(text, 0, pos)), default=0)
    while text[start].isspace():
        start += 1
    return start


def _trim_tail(text: str, start: int, end: int) -> int:
    """Drop trailing paragraphs that are speaker labels, lead-ins or chapter footers."""
    while True:
        cuts = list(PARA.finditer(text, start, end))
        if not cuts:
            return end
        tail = text[cuts[-1].end() : end].strip()
        if not (tail.startswith("The end of") or (len(tail) < 200 and LEAD_IN.search(tail))):
            return end
        end = cuts[-1].start()
        while end > start and text[end - 1].isspace():
            end -= 1


def _extend_back(text: str, start: int) -> int:
    """A page break can split a verse mid-sentence; reach back to where it really starts."""
    while start > 0 and text[start].islower():
        q = start - 1
        while q > 0 and text[q].isspace():
            q -= 1
        before = text[max(0, q - 12) : q + 1]
        if (
            q <= 0
            or ENDS.search(before)
            or TRAIL.search(before)
            or re.search(r"\(\d+\)\.?$", before)
        ):
            break
        start = _paragraph_start(text, q + 1)
    return start


def units_leading(text: str) -> list[Unit]:
    """Printed numbers at line starts, in sequence from 1; a verse runs to the next number."""
    marks, last = [], 0
    for m in LEAD.finditer(text):
        first = int(m[1])
        high = int(m[2]) if m[2] else first
        if high < first or not last < first <= last + MAX_GAP or (not marks and first != 1):
            continue
        marks.append((first, high, m, bool(marks) and first - last > 1))
        last = high
    units = []
    for i, (first, high, m, gap) in enumerate(marks):
        end = marks[i + 1][2].start() if i + 1 < len(marks) else len(text)
        while end > m.start() and text[end - 1].isspace():
            end -= 1
        start = m.start()
        while text[start].isspace():
            start += 1
        end = _trim_tail(text, start, end)
        label = str(first) if high == first else f"{first}–{high}"
        units.append(Unit(start, end, m.end(), end, label, gap))
    return units


def units_trailing_ref(text: str) -> list[Unit]:
    """A paragraph ending in its reference ("2.1"); alone on its line, the paragraph before."""
    units = []
    for m in TRAIL.finditer(text):
        start = _paragraph_start(text, m.start())
        if not text[start : m.start()].strip():
            before = max((p.start() for p in PARA.finditer(text, 0, m.start())), default=0)
            start = _paragraph_start(text, before)
        start = _extend_back(text, start)
        end = m.start() + len(m[0].rstrip())
        units.append(Unit(start, end, start, m.start(), f"{m[1]}.{m[2]}"))
    return units


def units_trailing_paren(text: str) -> list[Unit]:
    """A paragraph ending "(37)" or "(37).", numbers in sequence from 1."""
    units, last = [], 0
    for m in PAREN.finditer(text):
        n = int(m[1])
        if not last < n <= last + MAX_GAP or (last == 0 and n != 1):
            continue
        start = _extend_back(text, _paragraph_start(text, m.start()))
        end = m.start() + len(m[0].rstrip())
        units.append(Unit(start, end, start, m.start(), str(n), last > 0 and n - last > 1))
        last = n
    return units


def verse_rejection(text: str, unit: Unit) -> str | None:
    """Why a verse unit is unfit to serve, or None."""
    body = text[unit.start : unit.end]
    if any(marker in body for marker in MARKERS):
        return "marker"
    if body[:1].islower():
        return "lowercase-start"
    if len(body) < VERSE_BOUNDS[0]:
        return "short"
    if len(body) > VERSE_BOUNDS[1]:
        return "long"
    if not ENDS.search(text[unit.start : unit.body_end].rstrip()):
        return "no-terminal"
    return None


def verse_units(text: str, parser: str) -> list[Unit]:
    return {
        "leading-number": units_leading,
        "trailing-ref": units_trailing_ref,
        "trailing-paren": units_trailing_paren,
    }[parser](text)


# --- passages and sentences ----------------------------------------------------------------


def _paragraphs(text: str):
    pos = 0
    for m in [*PARA.finditer(text), None]:
        end = m.start() if m else len(text)
        segment = text[pos:end]
        start = pos + len(segment) - len(segment.lstrip())
        stop = pos + len(segment.rstrip())
        if stop > start:
            yield start, stop
        pos = m.end() if m else len(text)


def _prose_paragraph(paragraph: str) -> bool:
    if len(paragraph) < 40 or any(marker in paragraph for marker in MARKERS):
        return False
    if re.search(r"https?://|Sacred Texts|Next:|Previous:", paragraph):
        return False
    if re.match(r"\s*\d+\s*[.)]\s", paragraph):
        return False  # a numbered paragraph is a verse, not prose
    letters = [c for c in paragraph if c.isalpha()]
    return not letters or sum(c.isupper() for c in letters) / len(letters) <= 0.5


def sentence_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Split a paragraph at sentence ends, leaving abbreviations and initials unsplit."""
    segment = text[start:end]
    spans, pos = [], 0
    for m in SPLIT.finditer(segment):
        word = re.search(r"(\S+)$", segment[pos : m.start()])  # the word ending at the full stop
        token = word.group(1).rstrip(".") if word else ""
        if token in ABBREVIATIONS or re.fullmatch(r"[A-Za-z]", token):
            continue
        spans.append((start + pos, start + m.end(1)))
        pos = m.end()
    spans.append((start + pos, end))
    return spans


def _opens(text: str) -> bool:
    return (text[:1].isupper() or text[:1] in "\"'“‘(") and not any(
        marker in text for marker in MARKERS
    )


def _whole(text: str) -> bool:
    """Begins and ends like a sentence, with quotes and brackets closed."""
    return bool(
        _opens(text)
        and ENDS.search(text)
        and text.count("(") == text.count(")")
        and text.count("[") == text.count("]")
        and text.count('"') % 2 == 0
        and text.count("“") == text.count("”")
    )


def readable(text: str) -> bool:
    """Prose only. Not a list of names (genealogies), and not a scan's small-caps opening."""
    words = re.findall(r"[^\W\d_][\w'’]*", text)
    if not words or (len(words[0]) > 1 and words[0].isupper()):
        return False
    names = sum(1 for w in words[1:] if w[0].isupper() and w != "I")
    return names / len(words) <= NAME_SHARE


def sentence_ok(text: str) -> bool:
    low, high = SENTENCE_BOUNDS
    return (
        low <= len(text) <= high
        and _whole(text)
        and not ANAPHORA.match(text)
        and not CROSS_REFERENCE.search(text)
        and readable(text)
    )


def prose_units(text: str, kinds: set[str]) -> list[tuple[str, Unit]]:
    """Standalone sentences, and passages of whole sentences that never overlap each other."""
    found = []
    for start, end in _paragraphs(text):
        if not _prose_paragraph(text[start:end]):
            continue
        spans = sentence_spans(text, start, end)
        if "sentence" in kinds:
            found += [("sentence", Unit(a, b, a, b)) for a, b in spans if sentence_ok(text[a:b])]
        i = 0
        while "passage" in kinds and i < len(spans):
            a, b = spans[i]
            if ANAPHORA.match(text[a:b]) or not _opens(text[a:b]):
                i += 1
                continue
            j = i
            while b - a < PASSAGE_BOUNDS[0] and j + 1 < len(spans):
                if j - i + 1 >= PASSAGE_SENTENCES:
                    break
                j += 1
                b = spans[j][1]
            window = text[a:b]
            if (
                PASSAGE_BOUNDS[0] <= len(window) <= PASSAGE_BOUNDS[1]
                and _whole(window)
                and readable(window)
            ):
                if not (j == i and sentence_ok(window)):  # that span is already a sentence
                    found.append(("passage", Unit(a, b, a, b)))
                i = j + 1
            else:
                i += 1
    return found


# --- the pool ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Pool:
    items: tuple[Item, ...]
    by_id: dict[str, Item]
    entries: dict[str, Entry]
    rejected: dict[tuple[str, str], Counter]  # (document, kind) -> reasons
    by_chapter: dict[str, tuple[Item, ...]]  # in reading order, for finding what a passage holds


def excerpt_id(chapter_id: str, start: int, end: int) -> str:
    return f"{chapter_id}:{start}-{end}"


def build_pool(store: Store, entries: dict[str, Entry] | None = None) -> Pool:
    entries = load_sources() if entries is None else entries
    found: list[tuple[Item, str]] = []
    rejected: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for chapter in store.chapters_of(sorted(entries)):
        if chapter.source.local_path is not None:
            raise PramanaError(
                f"Document {chapter.document_id!r} has a private local origin and cannot supply "
                "excerpts. Remove it from excerpt_sources.json."
            )
        entry = entries[chapter.document_id]
        text = chapter.text
        if "verse" in entry.kinds:
            for unit in verse_units(text, entry.kinds["verse"]):
                reason = verse_rejection(text, unit)
                if reason:
                    rejected[(entry.document_id, "verse")][reason] += 1
                else:
                    found.append((_item(chapter, "verse", unit), text[unit.start : unit.end]))
        prose = {kind for kind in entry.kinds if kind != "verse"}
        if prose:
            for kind, unit in prose_units(text, prose):
                found.append((_item(chapter, kind, unit), text[unit.start : unit.end]))
    found.sort(key=lambda pair: pair[0].id)
    unique, seen = [], set()
    for item, words in found:  # the same words twice (a refrain) are served once
        if words not in seen:
            seen.add(words)
            unique.append(item)
    chapters: dict[str, list[Item]] = defaultdict(list)
    for item in sorted(unique, key=lambda i: (i.chapter_id, i.start, i.end)):
        chapters[item.chapter_id].append(item)
    return Pool(
        tuple(unique),
        {i.id: i for i in unique},
        entries,
        dict(rejected),
        {chapter: tuple(items) for chapter, items in chapters.items()},
    )


def _item(chapter: Chapter, kind: str, unit: Unit) -> Item:
    return Item(
        id=excerpt_id(chapter.id, unit.start, unit.end),
        kind=kind,
        document_id=chapter.document_id,
        chapter_id=chapter.id,
        start=unit.start,
        end=unit.end,
        body_start=unit.body_start,
        body_end=unit.body_end,
        label=unit.label,
    )


_pools: dict[str, tuple[tuple, Pool]] = {}


def pool_for(store: Store, entries: dict[str, Entry] | None = None) -> Pool:
    """The pool for the store's current corpus generation; rebuilt only when it changes."""
    entries = load_sources() if entries is None else entries
    stamp = (store.get_meta("generation"), tuple(sorted(entries.items())))
    cached = _pools.get(str(store.path))
    if cached and cached[0] == stamp:
        return cached[1]
    pool = build_pool(store, entries)
    _pools[str(store.path)] = (stamp, pool)
    return pool


# --- selection -----------------------------------------------------------------------------


def _rank(seed: str, item: Item) -> str:
    return hashlib.sha256(f"{seed}:{item.id}".encode()).hexdigest()


def candidates(
    pool: Pool,
    kinds: list[str] | None = None,
    documents: list[str] | None = None,
    min_chars: int = 0,
    max_chars: int = 10**9,
) -> list[Item]:
    for document in documents or []:
        if document not in pool.entries:
            raise ValueError(f"Document {document!r} is not in the excerpt pool.")
    return [
        i
        for i in pool.items
        if (not kinds or i.kind in kinds)
        and (not documents or i.document_id in documents)
        and min_chars <= i.length <= max_chars
    ]


def _capped(pool: Pool, items: list[Item], seed: str) -> list[Item]:
    by_document: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        by_document[item.document_id].append(item)
    kept = []
    for document, group in by_document.items():
        group.sort(key=lambda i: _rank(seed, i))
        kept += group[: pool.entries[document].cap]
    return sorted(kept, key=lambda i: _rank(seed, i))


def pool_version(items: list[Item]) -> str:
    return hashlib.sha256("\n".join(sorted(i.id for i in items)).encode()).hexdigest()[:12]


def today(pool: Pool, items: list[Item], *, day: date, seed: str = "") -> tuple[Item, dict]:
    """Same excerpt for every caller on a date; none repeats until the whole pool has run."""
    if not items:
        raise PramanaError("No excerpts match those filters.")
    ranked = _capped(pool, items, seed)
    chosen = ranked[(day - date(1970, 1, 1)).days % len(ranked)]
    return chosen, {"size": len(ranked), "version": pool_version(ranked)}


def pick_random(pool: Pool, items: list[Item], exclude: set[str]) -> tuple[Item, dict]:
    """Uniform within a document; a document past its cap is down-weighted, not cut off."""
    items = [i for i in items if i.id not in exclude]
    if not items:
        raise PramanaError("No excerpts match those filters.")
    sizes = Counter(i.document_id for i in items)
    weights = [min(1.0, pool.entries[i.document_id].cap / sizes[i.document_id]) for i in items]
    chosen = secrets.SystemRandom().choices(items, weights)[0]
    return chosen, {"size": len(items), "version": pool_version(items)}


class NoMatch(PramanaError):
    """A topic that finds no excerpt in the pool."""


def _similarity(retriever, strategy: str, topic: str, texts: list[str]) -> list[float]:
    """How near each text is to the topic, for ordering only (never returned or shown)."""
    from pramana.retrieval import fold_word

    if strategy == "lexical":
        words = set(re.findall(r"\w+", fold_word(topic)))
        return [float(len(words & set(re.findall(r"\w+", fold_word(t))))) for t in texts]
    import numpy as np

    vectors = np.asarray(retriever.embedder.documents(texts), dtype=np.float32)
    query = np.asarray(retriever.embedder.query(topic), dtype=np.float32)
    return [float(x) for x in vectors @ (query / np.linalg.norm(query))]


def ranked(
    pool: Pool,
    store: Store,
    retriever,
    topic: str,
    items: list[Item],
    exclude: set[str] | None = None,
    *,
    strategy: str = "hybrid",
    hits: int = 12,
) -> list[Item]:
    """Excerpts for a topic, nearest first: search the allowlisted documents with the existing
    retriever, take the excerpts that lie wholly inside the top hits' passages, and order those
    against the topic. A search result, not a claim that the text supports anything about it."""
    from pramana.models import SearchFilters

    if (
        strategy == "hybrid"
        and getattr(retriever, "_embedder", None) is None
        and importlib.util.find_spec("sentence_transformers") is None
    ):
        raise PramanaError(
            "Hybrid topic search needs sentence-transformers, which this install leaves out. "
            "Use strategy=lexical, or install the full environment."
        )
    allowed = {i.id: i for i in items if i.id not in (exclude or set())}
    if not allowed:
        raise NoMatch("Every matching excerpt is excluded.")
    documents = sorted({i.document_id for i in allowed.values()})
    found: list[Item] = []
    for hit in retriever.search(
        topic, limit=hits, strategy=strategy, filters=SearchFilters(document_ids=documents)
    ):
        p = hit.passage
        found += [
            i
            for i in pool.by_chapter.get(p.chapter_id, ())
            if i.id in allowed and p.start <= i.start and i.end <= p.end
        ]
    found = list(dict.fromkeys(found))
    if not found:
        raise NoMatch("No excerpt in the pool is about that topic.")
    chapters: dict[str, str] = {}
    texts = []
    for item in found:
        if item.chapter_id not in chapters:
            chapters[item.chapter_id] = store.chapter(item.chapter_id).text
        texts.append(chapters[item.chapter_id][item.start : item.end])
    scores = _similarity(retriever, strategy, topic, texts)
    order = sorted(range(len(found)), key=lambda n: (-scores[n], n))
    return [found[n] for n in order]


def about(
    pool: Pool,
    store: Store,
    retriever,
    topic: str,
    items: list[Item],
    exclude: set[str] | None = None,
    *,
    strategy: str = "hybrid",
    hits: int = 12,
    best: int = 5,
) -> tuple[Item, dict]:
    """One excerpt about a topic: chosen at random among the `best` nearest."""
    nearest = ranked(pool, store, retriever, topic, items, exclude, strategy=strategy, hits=hits)
    return secrets.choice(nearest[:best]), {
        "size": len(nearest),
        "version": pool_version(nearest),
    }


def search(
    pool: Pool,
    store: Store,
    retriever,
    topic: str,
    items: list[Item],
    exclude: set[str] | None = None,
    *,
    strategy: str = "hybrid",
    limit: int = 5,
) -> list[Item]:
    """The `limit` excerpts nearest a topic, best first. Deterministic: the same query gives the
    same list. No score is returned."""
    return ranked(
        pool,
        store,
        retriever,
        topic,
        items,
        exclude,
        strategy=strategy,
        hits=max(12, limit * 3),
    )[:limit]


def day_in(tz: str, on: date | None = None, now: datetime | None = None) -> date:
    """ "Today" in an IANA timezone, or the date given; ValueError for an unknown zone."""
    try:
        zone = ZoneInfo(tz)
    except (KeyError, ValueError, OSError) as exc:
        raise ValueError(f"Unknown timezone {tz!r}.") from exc
    return on or (now or datetime.now(UTC)).astimezone(zone).date()


# --- rendering -----------------------------------------------------------------------------


def reference(entry: Entry, chapter: Chapter, item: Item) -> str:
    label = entry.label or chapter.document
    where = chapter.location
    if item.kind == "verse":
        if entry.reference == "section" and where.sections:
            return f"{label}, {where.sections[0]}, {item.label}"
        if entry.reference == "label":
            return f"{label} {item.label}"
        return f"{label} {where.chapter}.{item.label}"
    place = ", ".join(where.sections) or f"Book {where.book}, chapter {where.chapter}"
    return f"{label}, {place}"


def render(store: Store, pool: Pool, item: Item, *, with_context: bool = False) -> tuple[dict, str]:
    """The JSON response, and the excerpt's words for a message (a verse's printed number
    left out, whitespace collapsed)."""
    chapter = store.chapter(item.chapter_id)
    entry = pool.entries[item.document_id]
    text = chapter.text[item.start : item.end]
    data = {
        "excerpt_id": item.id,
        "kind": item.kind,
        "boundary": "printed" if item.kind == "verse" else "derived",
        "text": text,
        "reference": reference(entry, chapter, item),
        "document": chapter.document,
        "edition": chapter.edition,
        "translator": chapter.translator,
        "content_type": chapter.content_type,
        "language": chapter.language,
        "source_url": str(chapter.source.url) if chapter.source.url else None,
        "rights": entry.rights,
        "attribution": entry.attribution,
        "notes": [
            {"id": n.id, "text": n.text}
            for n in chapter.notes
            if n.anchor_offset is not None and item.start <= n.anchor_offset < item.end
        ],
    }
    if with_context:
        data["context"] = paragraph_context(chapter.text, item.start, item.end)
    return data, collapse(chapter.text[item.body_start : item.body_end])


def collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def message(data: dict, body: str, fmt: str) -> str:
    """A ready-to-send message; `fmt` is "text" or "markdown"."""
    if fmt == "markdown":
        link = f" ([source]({data['source_url']}))" if data["source_url"] else ""
        return f"> {body}\n\n— **{data['reference']}** · {data['attribution']}{link}\n"
    return f"“{body}”\n— {data['reference']} · {data['attribution']}\n"


def list_message(rendered: list[tuple[dict, str]], fmt: str) -> str:
    """A numbered, ready-to-send list; `fmt` is "text" or "markdown"."""
    blocks = []
    for number, (data, body) in enumerate(rendered, 1):
        if fmt == "markdown":
            blocks.append(f"{number}. > {body}\n   — **{data['reference']}**")
        else:
            blocks.append(f"{number}. “{body}”\n   — {data['reference']} · {data['attribution']}")
    return "\n\n".join(blocks) + "\n"


def report(pool: Pool) -> list[dict]:
    """Per document: excerpts by kind and rejected verse units by reason, plus rights lines."""
    counts: dict[str, Counter] = defaultdict(Counter)
    for item in pool.items:
        counts[item.document_id][item.kind] += 1
    rows = []
    for document, entry in sorted(pool.entries.items()):
        rows.append(
            {
                "document_id": document,
                "label": entry.label,
                "excerpts": dict(counts[document]),
                "rejected_verse_units": dict(pool.rejected.get((document, "verse"), {})),
                "cap": entry.cap,
                "rights": entry.rights,
                "attribution": entry.attribution,
            }
        )
    return rows
