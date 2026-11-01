"""Where Śaṅkara and Rāmānuja part ways: a heuristic map of the Brahma Sūtra.

Each unit is one of Śaṅkara's commentary pages: the sūtras from its first printed sūtra
to the one before his next page in the same pāda. Rāmānuja's pages are matched on the
printed sūtra itself: the same number when the two sūtra lines agree, a number up to
three away when only that line agrees (the recensions divide and number some sūtras
differently), and otherwise the same number, marked unconfirmed. Three signals compare
the two sides, each higher when they differ more:

- `scripture`: the scripture each side cites (resolved printed references, see
  `citations.py`), compared where both sides cite: half verse overlap, half overlap of
  the scripture chapters (Jaccard), as 1 - similarity.
- `wording`: 1 - TF-IDF cosine of the two texts. Both are Thibaut's translations, so a
  low overlap reflects what is discussed, not two translators' styles.
- `dispute`: how often Rāmānuja's text names doctrines distinctive of Śaṅkara's reading
  (nescience, māyā, sublation, a non-differenced Brahman…), per 1,000 words.

Each signal becomes one of five bands: wording by quintile across all units, scripture
by how much is shared, dispute terms by none versus quartiles of those that name them.
The overall band is the rounded mean of the bands measured. This measures wording and
citations, not doctrine: it is a map of where to read, not a judgement of who is right.
"""

import math
import re
from collections import Counter, defaultdict

from pramana.citations import index as citation_index
from pramana.glossary import fold
from pramana.library import category
from pramana.models import Chapter
from pramana.storage import Store

BANDS = ("low", "moderate", "marked", "high", "very high")
SIGNALS = ("scripture", "wording", "dispute")
# Terms in Rāmānuja's text that name doctrines distinctive of Śaṅkara's reading, as
# Thibaut spells them (accents folded). Counted only where they occur as words.
DISPUTE_TERMS = {
    "nescience": r"nescience",
    "avidyā": r"avidya",
    "māyā": r"maya",
    "illusion": r"illusion|illusory|illusive",
    "sublation": r"sublat(?:ion|ed|es|ing|e)",
    "non-differenced Brahman": r"non-?differenced|devoid of all difference",
    "unreal": r"unreal|unreality|falsity",
    "superimposition": r"superimposition|superimposed|adhyasa",
    "pure intelligence": r"(?:mere|pure|non-differenced) intelligence",
}
_TERMS = {
    label: re.compile(rf"\b(?:{pattern})\b", re.IGNORECASE)
    for label, pattern in DISPUTE_TERMS.items()
}
STOP = set(
    """
    the and that this with which from have has had are was were been being for not but
    his her its their they them who whom whose what when where why how all any each
    other such only also than then there these those into upon unto shall should would
    could may might must can will one two three our out own same very more most some
    because therefore thus hence since while being about through after before between
    """.split()
)
WORD = re.compile(r"[a-z]{3,}")
LIMIT = 6
# The printed sūtra that opens a page ("25. And as in the case of light…"), and the
# thresholds for calling two of them the same sūtra (overlap of their words, glosses in
# parentheses removed): checked by reading pairs on 1 November 2026.
SUTRA_LINE = r"(?m)^[ \t]*(?:[A-Za-zâ ]+: )?{n}\.\s+(.*?)(?:\.\s{{2,}}|\.?\n|$)"
SUTRA_STOP = {"the", "and", "account", "that", "for", "with", "not", "its", "but"}
SAME, MOVED, WINDOW = 0.5, 0.75, 3

_cache: dict[tuple, dict] = {}


def _commentaries(chapters: list[Chapter]) -> dict[str, list[Chapter]]:
    """The Brahma Sūtra pages of each commentator, keyed `shankara` / `ramanuja`."""
    sides: dict[str, list[Chapter]] = defaultdict(list)
    for c in chapters:
        if category(c.document) != "Brahma Sūtra":
            continue
        author = fold(c.author or "")
        if "sankara" in author or "shankara" in author:
            sides["shankara"].append(c)
        elif "ramanuja" in author:
            sides["ramanuja"].append(c)
    return sides


def _first(c: Chapter) -> int | None:
    s = c.location.sections[0] if c.location.sections else ""
    return int(s) if s.isdigit() else None


def _sutra(c: Chapter, number: int) -> set[str]:
    """Words of the sūtra printed with this number on the page (after any preamble or
    headings, as on the first page of a pāda), without bracketed glosses."""
    m = re.search(SUTRA_LINE.format(n=number), c.text[:20000], re.S)
    if not m:
        return set()
    text = re.sub(r"\([^()]*\)", "", m[1][:400])
    return {w for w in WORD.findall(fold(text)) if w not in SUTRA_STOP}


def _overlap(a: set[str], b: set[str]) -> float:
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def _pairing(first: int, words: set[str], lines: dict[int, set[str]]) -> tuple[str, int]:
    """How Śaṅkara's sūtra `first` is matched in Rāmānuja's pāda, and the number offset.

    The recensions divide and number some sūtras differently. A pair counts as the same
    sūtra when the printed sūtra lines share most of their words; otherwise a strongly
    matching line up to three numbers away is taken (renumbered). Anything else keeps the
    printed number and is marked unconfirmed; nothing is inferred beyond the words.
    """
    same = _overlap(words, lines.get(first, set()))
    if same >= SAME:
        return "same", 0
    near = max(
        (
            (_overlap(words, lines[first + k]), -abs(k), k)
            for k in range(-WINDOW, WINDOW + 1)
            if k and first + k in lines
        ),
        default=(0.0, 0, 0),
    )
    if near[0] >= MOVED and near[0] > same:
        return "renumbered", near[2]
    return "unconfirmed", 0


def _units(sides: dict[str, list[Chapter]]) -> list[dict]:
    """Śaṅkara's pages as sūtra ranges, each with Rāmānuja's pages on the same sūtras."""
    by_pada: dict[tuple, dict[int, list[Chapter]]] = defaultdict(lambda: defaultdict(list))
    rama: dict[tuple, list[tuple[int, Chapter]]] = defaultdict(list)
    lines: dict[tuple, dict[int, set[str]]] = defaultdict(dict)
    for c in sides["shankara"]:
        if (n := _first(c)) is not None:
            by_pada[(c.location.book, c.location.chapter)][n].append(c)
    for c in sides["ramanuja"]:
        if (n := _first(c)) is not None:
            rama[(c.location.book, c.location.chapter)].append((n, c))
            known = lines[(c.location.book, c.location.chapter)]
            if not known.get(n) and (words := _sutra(c, n)):
                known[n] = words
    units = []
    for pada in sorted(by_pada, key=lambda p: tuple(int(x) if x.isdigit() else 0 for x in p)):
        starts = sorted(by_pada[pada])
        for i, first in enumerate(starts):
            last = starts[i + 1] - 1 if i + 1 < len(starts) else None
            pairing, k = _pairing(first, _sutra(by_pada[pada][first][0], first), lines[pada])
            lo, hi = first + k, None if last is None else last + k
            inside = [c for n, c in rama[pada] if lo <= n and (hi is None or n <= hi)]
            before = [n for n, _ in rama[pada] if n < lo]
            exact = bool(inside)
            if not inside and before:
                inside = [c for n, c in rama[pada] if n == max(before)]
            book, chapter = pada
            span = f"{first}" if last is None or last == first else f"{first}–{last}"
            units.append(
                {
                    "book": book,
                    "pada": chapter,
                    "first": first,
                    "last": last,
                    "label": f"{book}.{chapter}.{span}",
                    "shankara": by_pada[pada][first],
                    "ramanuja": inside,
                    "exact": exact,
                    "pairing": pairing if exact else "unconfirmed",
                    "ramanuja_sutra": lo,
                }
            )
    return units


def _words(text: str) -> list[str]:
    return [w for w in WORD.findall(fold(text)) if w not in STOP]


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _ranks(values: list[float | None]) -> list[float | None]:
    """Percentile rank (0..1, ties sharing their midpoint) of each value that exists."""
    present = sorted(v for v in values if v is not None)
    n = len(present)
    out: list[float | None] = []
    for v in values:
        if v is None or not n:
            out.append(None)
            continue
        below = sum(1 for x in present if x < v)
        out.append((below + sum(1 for x in present if x == v) / 2) / n)
    return out


def band(rank: float | None) -> str | None:
    return None if rank is None else BANDS[min(len(BANDS) - 1, int(rank * len(BANDS)))]


def _wording_bands(values: list[float | None], reference: list[bool]) -> list[int | None]:
    """A continuous signal: quintiles of its rank among the confirmed pairs, so pairs of
    possibly different sūtras do not stretch the scale."""
    pool = sorted(v for v, ok in zip(values, reference, strict=True) if ok and v is not None)
    if not pool:
        return [None for _ in values]

    def rank(v: float) -> float:
        below = sum(1 for x in pool if x < v)
        return (below + sum(1 for x in pool if x == v) / 2) / len(pool)

    return [None if v is None else BANDS.index(band(rank(v))) for v in values]


def _scripture_bands(values: list[float | None]) -> list[int | None]:
    """Fixed meanings: the same scripture (low) to nothing in common (very high).

    Most stretches that cite on both sides share no scripture at all, so ranks would tie
    most of them; bands say how much is shared instead.
    """

    def one(v: float) -> int:
        if v <= 0:
            return 0
        if v >= 1:
            return 4
        return 1 if v <= 0.5 else 2 if v < 0.85 else 3

    return [None if v is None else one(v) for v in values]


def _dispute_bands(values: list[float | None]) -> list[int | None]:
    """None of the terms is low; stretches that name them are split into quartiles."""
    named = _ranks([v if v else None for v in values])
    return [
        None if v is None else 0 if not v else 1 + min(3, int(r * 4))
        for v, r in zip(values, named, strict=True)
    ]


def _cited(chapters: list[Chapter], outgoing: dict) -> dict[tuple, dict]:
    """Scripture targets cited on these pages: a verse span, or a whole chapter."""
    found: dict[tuple, dict] = {}
    for c in chapters:
        for ref in outgoing.get(c.id, []):
            t = ref["target"]
            key = (
                (t["chapter_id"],)
                if ref["status"] == "chapter"
                else (t["chapter_id"], t["start"], t["end"])
            )
            found.setdefault(
                key,
                {
                    "label": ref["label"],
                    "chapter_id": t["chapter_id"],
                    "start": t["start"],
                    "end": t["end"],
                },
            )
    return found


def compute(chapters: list[Chapter], outgoing: dict) -> dict:
    sides = _commentaries(chapters)
    if not sides["shankara"] or not sides["ramanuja"]:
        missing = [
            name
            for name, key in (("Śaṅkara", "shankara"), ("Rāmānuja", "ramanuja"))
            if not sides[key]
        ]
        return {
            "available": False,
            "reason": f"Import both Brahma Sūtra commentaries first (missing: "
            f"{', '.join(missing)}): `pramana corpus download --source brahma-sutra` and "
            "`--source sribhashya`.",
            "units": [],
        }
    units = _units(sides)

    # Wording: TF-IDF over every unit's text on both sides.
    texts = [
        (
            Counter(_words("\n".join(c.text for c in u["shankara"]))),
            Counter(_words("\n".join(c.text for c in u["ramanuja"]))),
        )
        for u in units
    ]
    df: Counter = Counter()
    for pair in texts:
        for counts in pair:
            df.update(counts.keys())
    docs = 2 * len(texts)

    def weights(counts: Counter) -> dict[str, float]:
        return {
            w: (1 + math.log(n)) * math.log((1 + docs) / (1 + df[w])) for w, n in counts.items()
        }

    raw: dict[str, list[float | None]] = {s: [] for s in SIGNALS}
    details = []
    for u, (left, right) in zip(units, texts, strict=True):
        a, b = _cited(u["shankara"], outgoing), _cited(u["ramanuja"], outgoing)
        if a and b:
            # Half for verses in common, half for the same scripture chapters.
            verses = len(a.keys() & b.keys()) / len(a.keys() | b.keys())
            ca, cb = {k[0] for k in a}, {k[0] for k in b}
            raw["scripture"].append(1 - (verses + len(ca & cb) / len(ca | cb)) / 2)
        else:
            raw["scripture"].append(None)  # compared only where both sides cite
        raw["wording"].append(
            1 - _cosine(weights(left), weights(right)) if left and right else None
        )
        words = sum(right.values())
        rama_text = "\n".join(c.text for c in u["ramanuja"])
        terms = {
            label: n for label, pattern in _TERMS.items() if (n := len(pattern.findall(rama_text)))
        }
        raw["dispute"].append(1000 * sum(terms.values()) / words if words else None)
        details.append(
            {
                "shared": len(a.keys() & b.keys()),
                "only_shankara": [a[k] for k in a.keys() - b.keys()][:LIMIT],
                "only_ramanuja": [b[k] for k in b.keys() - a.keys()][:LIMIT],
                "terms": dict(sorted(terms.items(), key=lambda x: -x[1])),
            }
        )
    levels = {
        "scripture": _scripture_bands(raw["scripture"]),
        "wording": _wording_bands(raw["wording"], [u["pairing"] != "unconfirmed" for u in units]),
        "dispute": _dispute_bands(raw["dispute"]),
    }
    # Overall: the average of the bands measured; wording breaks ties in the ranking. No
    # dispute term is not evidence of agreement, so it counts only where terms occur.
    # One kind of evidence alone reaches "high" at most; "very high" needs two that agree.
    overall: list[float | None] = []
    strong: list[int] = []
    for i in range(len(units)):
        present = [
            b
            for s in SIGNALS
            if (b := levels[s][i]) is not None and not (s == "dispute" and b == 0)
        ]
        mean = sum(present) / len(present) if present else None
        overall.append(None if mean is None else min(mean, 3.0) if len(present) == 1 else mean)
        strong.append(sum(1 for b in present if b >= 3))
    wording_rank = _ranks(raw["wording"])
    documents = {
        key: {
            "document_id": sides[key][0].document_id,
            "document": sides[key][0].document,
            "edition": sides[key][0].edition,
        }
        for key in ("shankara", "ramanuja")
    }
    return {
        "available": True,
        "documents": documents,
        "bands": list(BANDS),
        "units": [
            {
                **{
                    k: u[k]
                    for k in (
                        "book",
                        "pada",
                        "first",
                        "last",
                        "label",
                        "exact",
                        "pairing",
                        "ramanuja_sutra",
                    )
                },
                "shankara": [c.id for c in u["shankara"]],
                "ramanuja": [c.id for c in u["ramanuja"]],
                "bands": {
                    "overall": None if overall[i] is None else BANDS[int(overall[i] + 0.5)],
                    **{s: None if levels[s][i] is None else BANDS[levels[s][i]] for s in SIGNALS},
                },
                **details[i],
            }
            for i, u in enumerate(units)
        ],
        # Unit indices from most to least different overall (an order, not a score).
        "ranking": sorted(
            range(len(units)),
            key=lambda i: (
                units[i]["pairing"] == "unconfirmed",  # confirmed pairs first
                -(int(overall[i] + 0.5) if overall[i] is not None else -1),  # the band
                -strong[i],  # then how many strong signals agree
                -(overall[i] if overall[i] is not None else -1.0),
                -(wording_rank[i] or 0.0),
                i,
            ),
        ),
    }


def divergence(store: Store) -> dict:
    """The map for the library, rebuilt when its generation changes."""
    key = (str(store.path), store.get_meta("generation"))
    if key not in _cache:
        _cache.clear()
        _cache[key] = compute(store.chapters(), citation_index(store)["outgoing"])
    return _cache[key]


def most_different(data: dict, limit: int = 12, *, least: bool = False) -> list[dict]:
    """Confirmed pairs only (the same sūtra on both sides), most or least different."""
    order = [i for i in data.get("ranking", []) if data["units"][i]["pairing"] != "unconfirmed"]
    return [data["units"][i] for i in (order[::-1] if least else order)[:limit]]
