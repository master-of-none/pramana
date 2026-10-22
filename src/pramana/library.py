"""Read-only library catalogue for the Study view: works, divisions and reading order.

Catalogue entries omit chapter text. Categories are display groupings derived from
document titles; they make no claim about a work's tradition or authenticity.
"""

import json
import re

from pramana.discourse import segments
from pramana.glossary import fold
from pramana.models import Chapter, Passage
from pramana.storage import Store

CATEGORIES = (
    ("Brahma Sūtra", r"brahma[ -]?sutra|sribhashya"),
    ("Upaniṣads", r"[uo]panish|aranyaka"),  # "Brahmopanishad": sandhi joins the vowel.
    ("Bhagavad Gītā", r"\bgita\b|\bgeeta\b|bhagavad"),
    ("Purāṇas", r"purana"),
)
OTHER = "Prakaraṇas and expositions"


def category(document: str) -> str:
    folded = fold(document)
    return next((name for name, pattern in CATEGORIES if re.search(pattern, folded)), OTHER)


def _part(value: str):
    # Numbers sort numerically; printed labels (e.g. a pāda heading page) sort first.
    return (1, int(value), "") if value.isdigit() else (0, 0, value)


def order(location: dict) -> tuple:
    return (
        _part(location["book"]),
        _part(location["chapter"]),
        tuple(_part(s) for s in location.get("sections", [])),
    )


def catalogue(store: Store) -> list[dict]:
    """Every document with its divisions in reading order, without chapter text."""
    with store.connect() as db:
        rows = db.execute(
            "SELECT id, json_extract(data,'$.document_id') AS document_id, "
            "json_extract(data,'$.document') AS document, "
            "COALESCE(json_extract(data,'$.author'),'') AS author, translator, edition, "
            "COALESCE(json_extract(data,'$.content_type'),'translation') AS content_type, "
            "json_extract(data,'$.location') AS location, "
            "json_extract(data,'$.source.url') AS url, "
            "json_extract(data,'$.source.local_path') AS local_path, "
            "json_extract(data,'$.source.rights') AS rights, "
            "json_extract(data,'$.source.attribution') AS attribution FROM chapters"
        ).fetchall()
    documents: dict[tuple, dict] = {}
    for row in rows:
        key = (row["document_id"], row["edition"])
        doc = documents.setdefault(
            key,
            {
                "document_id": row["document_id"],
                "document": row["document"],
                "category": category(row["document"]),
                "author": row["author"],
                "translator": row["translator"],
                "edition": row["edition"],
                "rights": row["rights"],
                "attribution": row["attribution"],
                "local": row["url"] is None,
                "content_types": set(),
                "chapters": [],
            },
        )
        doc["content_types"].add(row["content_type"])
        doc["chapters"].append({"id": row["id"], "location": json.loads(row["location"])})
    result = []
    for doc in documents.values():
        doc["content_types"] = sorted(doc["content_types"])
        doc["chapters"].sort(key=lambda c: order(c["location"]))
        result.append(doc)
    names = [name for name, _ in CATEGORIES] + [OTHER]
    return sorted(result, key=lambda d: (names.index(d["category"]), d["document"], d["edition"]))


# Chat scopes: display groupings or a named commentator, resolved to document IDs.
SCOPES = {
    "upanishads": ("Upaniṣads", lambda d: d["category"] == "Upaniṣads"),
    "gita": ("Bhagavad Gītā", lambda d: d["category"] == "Bhagavad Gītā"),
    "shankara": ("Śaṅkara", lambda d: "sankara" in fold(d["author"])),
    "ramanuja": ("Rāmānuja", lambda d: "ramanuja" in fold(d["author"])),
}


def scope_documents(store: Store, scope: str) -> list[str]:
    _, matches = SCOPES[scope]
    return list(dict.fromkeys(d["document_id"] for d in catalogue(store) if matches(d)))


def scopes(store: Store) -> list[dict]:
    """Scopes that contain at least one imported document."""
    docs = catalogue(store)
    found = []
    for key, (label, matches) in SCOPES.items():
        ids = {d["document_id"] for d in docs if matches(d)}
        if ids:
            found.append({"scope": key, "label": label, "documents": len(ids)})
    return found


def neighbours(store: Store, chapter: Chapter) -> dict:
    """Previous and next chapter IDs within the same document and edition."""
    for doc in catalogue(store):
        if (doc["document_id"], doc["edition"]) == (chapter.document_id, chapter.edition):
            ids = [c["id"] for c in doc["chapters"]]
            i = ids.index(chapter.id)
            return {
                "previous": ids[i - 1] if i else None,
                "next": ids[i + 1] if i + 1 < len(ids) else None,
            }
    return {"previous": None, "next": None}


def role_spans(text: str) -> list[dict]:
    """Code-point spans of explicitly cued objection/reply segments in a chapter."""
    spans, cursor = [], 0
    for part in segments(text):
        end = cursor + len(part["text"])
        if part["role"] != "unmarked":
            spans.append({"role": part["role"], "start": cursor, "end": end})
        cursor = end
    return spans


def parallel(store: Store, book: str, chapter: str, sutra: str) -> list[dict]:
    """Each Brahma Sūtra commentary's pages for one sūtra, matched on printed location.

    A commentary page may begin at an earlier sūtra and continue through this one; the
    nearest preceding page is then returned with `exact: false`.
    """
    result = []
    for doc in catalogue(store):
        if doc["category"] != "Brahma Sūtra" or not sutra.isdigit():
            continue
        pada = [
            c
            for c in doc["chapters"]
            if c["location"]["book"] == book and c["location"]["chapter"] == chapter
        ]

        def first(c):
            s = c["location"].get("sections", [])
            return int(s[0]) if s and s[0].isdigit() else None

        exact = [c for c in pada if first(c) == int(sutra)]
        before = [first(c) for c in pada if first(c) is not None and first(c) < int(sutra)]
        pages = exact or [c for c in pada if before and first(c) == max(before)]
        if pages:
            result.append(
                {
                    "document_id": doc["document_id"],
                    "document": doc["document"],
                    "author": doc["author"],
                    "edition": doc["edition"],
                    "exact": bool(exact),
                    "chapters": [p["id"] for p in pages],
                }
            )
    return result


def slug(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", fold(term)).strip("-")


def _names(item) -> list[str]:
    return [n for n in (item.term, *item.aliases, *item.english) if n]


CONCEPT_GROUPS = (
    ("shankara", "Śaṅkara"),
    ("ramanuja", "Rāmānuja"),
    ("upanishads", "Upaniṣads"),
    ("gita", "Bhagavad Gītā"),
    ("other", "Other works"),
)


def mentions(item, text: str) -> bool:
    folded = fold(text)
    return any(
        re.search(r"(?<![\w-])" + re.escape(fold(n)) + r"(?![\w-])", folded) for n in _names(item)
    )


def concept(store: Store, key: str, limit: int = 4) -> dict | None:
    """A glossary concept with its strongest lexical passages per group of texts.

    Matches are phrase matches on the concept's names (IAST, ASCII and English), so
    "tat tvam asi" never matches a stray "tat". FTS splits hyphens and drops
    diacritics, so candidates are re-checked for a standalone, unhyphenated mention:
    "anna-maya" (made of food) is not "māyā". Ranking is BM25 within each group; it
    shows where a concept is discussed, not what each author concludes about it.
    """
    from pramana.glossary import terms

    items = {slug(t.term): t for t in terms()}
    item = items.get(key)
    if item is None:
        return None
    docs = catalogue(store)
    claimed: set[str] = set()
    groups = []
    phrase = " OR ".join('"' + re.sub(r'"', "", fold(n)) + '"' for n in _names(item))
    with store.connect() as db:
        indexed = db.execute("SELECT COUNT(*) FROM passages").fetchone()[0] > 0
        for group, label in CONCEPT_GROUPS:
            if group == "other":
                ids = [d["document_id"] for d in docs if d["document_id"] not in claimed]
            else:
                ids = [d["document_id"] for d in docs if SCOPES[group][1](d)]
            claimed.update(ids)
            if not ids or not indexed:
                continue
            rows = db.execute(
                "SELECT p.data FROM passages_fts JOIN passages p ON p.id=passages_fts.id "
                "JOIN chapters c ON c.id=p.chapter_id WHERE passages_fts MATCH ? "
                f"AND json_extract(c.data,'$.document_id') IN ({','.join('?' * len(ids))}) "
                "ORDER BY bm25(passages_fts), p.id LIMIT ?",
                [phrase, *ids, limit * 8],
            ).fetchall()
            passages = [
                p
                for p in (Passage.model_validate_json(r[0]) for r in rows)
                if mentions(item, p.text)
            ][:limit]
            if passages:
                groups.append({"group": group, "label": label, "passages": passages})
    found = [p.text for g in groups for p in g["passages"]]
    counts = {t.term: sum(mentions(t, text) for text in found) for t in terms() if t is not item}
    related = [
        {"slug": slug(t.term), "term": t.term, "passages": counts[t.term]}
        for t in sorted(terms(), key=lambda t: -counts.get(t.term, 0))
        if t is not item and counts[t.term] >= 2
    ][:8]
    return {
        "slug": key,
        **item.model_dump(),
        "indexed": indexed,
        "groups": groups,
        "related": related,
    }


def concepts() -> list[dict]:
    from pramana.glossary import terms

    return [{"slug": slug(t.term), **t.model_dump()} for t in terms()]
