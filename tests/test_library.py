from fastapi.testclient import TestClient

from pramana import Retriever
from pramana.api import create_app
from pramana.library import category, order, role_spans
from pramana.models import Location


def commentary(make_chapter, author, doc, book, pada, sections, text):
    chapter = make_chapter(text, book=book, chapter=pada)
    chapter.location = Location(book=book, chapter=pada, sections=sections)
    chapter.author, chapter.document_id = author, doc
    chapter.document = f"Brahma Sutra commentary by {author}"
    chapter.edition = f"Edition {author}"
    return chapter


def client_with(indexed, embedder, tmp_path, chapters):
    path = tmp_path / "bs.jsonl"
    path.write_text("\n".join(c.model_dump_json() for c in chapters))
    indexed.import_jsonl(path)
    indexed.index(embedder=embedder)
    return TestClient(create_app(retriever=Retriever(indexed, embedder=embedder)))


def test_library_parallel_and_roles(indexed, embedder, tmp_path, make_chapter):
    s1 = commentary(
        make_chapter, "Sankaracharya", "bs-s", "1", "1", ["1"], "1. Then the enquiry. 𑀅"
    )
    s4 = commentary(make_chapter, "Sankaracharya", "bs-s", "1", "1", ["4"], "4. But that, harmony.")
    r_head = commentary(make_chapter, "Ramanuja", "bs-r", "1", "1", ["First Pâda"], "FIRST PÂDA.")
    r1 = commentary(make_chapter, "Ramanuja", "bs-r", "1", "1", ["1"], "1. Then the enquiry.")
    r1t = commentary(
        make_chapter,
        "Ramanuja",
        "bs-r",
        "1",
        "1",
        ["1", "The Great Pûrvapaksha"],
        "THE GREAT PÛRVAPAKSHA.\n\nDifference is unreal.\n\nTHE GREAT SIDDHÂNTA.\n\nNot so.",
    )
    client = client_with(indexed, embedder, tmp_path, [s4, r1t, s1, r1, r_head])

    library = client.get("/api/library").json()
    bs = [d for d in library if d["category"] == "Brahma Sūtra"]
    assert [d["author"] for d in bs] == ["Ramanuja", "Sankaracharya"]
    ramanuja = bs[0]
    assert [c["id"] for c in ramanuja["chapters"]] == [r_head.id, r1.id, r1t.id]
    assert "text" not in ramanuja["chapters"][0] and ramanuja["rights"] == "Test fixture"
    assert library[0]["category"] == "Brahma Sūtra"  # Categories in their display order.

    exact = client.get("/api/parallel", params={"book": "1", "chapter": "1", "sutra": "1"}).json()
    assert {(p["author"], tuple(p["chapters"]), p["exact"]) for p in exact} == {
        ("Ramanuja", (r1.id, r1t.id), True),
        ("Sankaracharya", (s1.id,), True),
    }
    # Sūtra 2 has no page of its own: the page that begins at sūtra 1 continues it.
    later = client.get("/api/parallel", params={"book": "1", "chapter": "1", "sutra": "2"}).json()
    assert {(p["author"], p["exact"]) for p in later} == {
        ("Ramanuja", False),
        ("Sankaracharya", False),
    }
    assert (
        client.get("/api/parallel", params={"book": "2", "chapter": "1", "sutra": "1"}).json() == []
    )

    context = client.get(f"/api/chapters/{r1t.id}").json()
    assert [r["role"] for r in context["roles"]] == ["objection", "reply"]
    text = context["chapter"]["text"]
    assert text[context["roles"][1]["start"] :].startswith("THE GREAT SIDDHÂNTA.")
    assert (context["previous"], context["next"]) == (r1.id, None)
    assert client.get(f"/api/chapters/{s1.id}").json()["previous"] is None


def test_ordering_and_categories():
    assert category("Katha Upanishad") == "Upaniṣads"
    assert category("Brahmopanishaḍ") == category("Mukṭikopanishaḍ") == "Upaniṣads"
    assert category("Sribhashya (Brahma Sutra commentary)") == "Brahma Sūtra"
    assert category("The Holy Geeta") == "Bhagavad Gītā"
    assert category("Bhagavad Gita") == "Bhagavad Gītā"
    assert category("Ashtavakra Gita (The Heart of Awareness)") == "Prakaraṇas and expositions"
    assert category("Knowledge of Self") == "Prakaraṇas and expositions"
    keys = [
        {"book": "1", "chapter": c, "sections": s}
        for c, s in [("10", []), ("2", []), ("2", ["Intro"])]
    ]
    assert sorted(keys, key=order) == [keys[1], keys[2], keys[0]]
    assert role_spans("Plain prose only.") == []


def test_concept_pages_group_passages_and_skip_compounds(indexed, embedder, tmp_path, make_chapter):
    s = commentary(
        make_chapter,
        "Sankaracharya",
        "bs-s",
        "1",
        "1",
        ["1"],
        "Superimposition (adhyâsa) of the not-Self on the Self is avidyā.",
    )
    r = commentary(
        make_chapter, "Ramanuja", "bs-r", "1", "1", ["1"], "Mâyâ here does not mean falsehood."
    )
    u = make_chapter("The sheath anna-maya is made of food.", chapter="5")
    u.document_id, u.document = "taittiriya-x", "Taittiriya Upanishad"
    client = client_with(indexed, embedder, tmp_path, [s, r, u])
    page = client.get("/api/concepts/adhyasa").json()
    assert page["term"] == "adhyāsa" and page["indexed"]
    assert [(g["label"], [p["chapter_id"] for p in g["passages"]]) for g in page["groups"]] == [
        ("Śaṅkara", [s.id])
    ]
    maya = client.get("/api/concepts/maya").json()
    assert [g["label"] for g in maya["groups"]] == ["Rāmānuja"]  # anna-maya is not māyā
    assert client.get("/api/concepts/nothing").status_code == 404
    listed = {c["slug"]: c["term"] for c in client.get("/api/concepts").json()}
    assert listed["tat-tvam-asi"] == "tat tvam asi" and listed["saksin"] == "sākṣin"


def test_reading_paths_resolve_or_mark_missing(indexed, embedder, tmp_path, make_chapter):
    gita = make_chapter("The Self is never born.", book="1", chapter="2")
    gita.document_id, gita.document = "bhagavad-gita-sbg", "Bhagavad Gita"
    client = client_with(indexed, embedder, tmp_path, [gita])
    found = {p["slug"]: p for p in client.get("/api/paths").json()}
    steps = found["first-steps"]["steps"]
    gita_step = next(s for s in steps if s["document"] == "Bhagavad Gita")
    assert gita_step["available"] and gita_step["chapter_id"] == gita.id
    assert not any(s["available"] for s in steps if s is not gita_step)
    assert all(
        s["kind"] == "sutra" and not s["available"] for s in found["two-commentaries"]["steps"]
    )
