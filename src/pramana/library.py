"""Read-only library catalogue for the Study view: works, divisions and reading order.

Catalogue entries omit chapter text. Categories are display groupings derived from
document titles; they make no claim about a work's tradition or authenticity.
"""

import json
import re

from pramana.discourse import segments
from pramana.glossary import fold
from pramana.models import Chapter
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
