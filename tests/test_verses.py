from fastapi.testclient import TestClient

from pramana import Retriever
from pramana.api import create_app
from pramana.models import Location
from pramana.verses import context

# Verse 7 runs over two paragraphs; the saying is in the second.
CHANDOGYA = (
    "6. 'As the bees make honey,' said the father.\n\n"
    "7. 'Now that which is that subtile essence, in it all that exists has its self:\n\n"
    "It is the True. It is the Self, and thou, O Svetaketu, art it.'\n\n"
    "8. 'Please, Sir, inform me still more,' said the son."
)
SHANKARA = (
    "𑀅 The text says 'It is the Self, and thou, O Svetaketu, art it' (Kh. Up. VI, 8, 7), "
    "teaching identity. As it says, 'That art thou' (Kh. Up. VI, 8, 7). "
    "Elsewhere the teacher repeats: That art thou. "
    "The whole section is relevant (Kh. Up. VI, 8, 1)."
)
RAMANUJA = (
    "The son asks again (Kh. Up. VI, 8, 8). The section as a whole (Kh. Up. VI, 8). "
    "Thou art that, O Svetaketu, means the inner Self."
)


def library(make_chapter, chandogya=CHANDOGYA):
    target = make_chapter(chandogya, book="6", chapter="8")
    target.document_id, target.document = "chandogya-upanishad-sbe01", "Chandogya Upanishad"
    target.location = Location(book="6", chapter="8", sections=["VI, 8"])
    pages = [target]
    for author, text, n in (("Sankaracharya", SHANKARA, "1"), ("Ramanuja", RAMANUJA, "2")):
        c = make_chapter(text, book="1", chapter=n)
        c.document_id, c.document = f"bs-{author.lower()}", f"Brahma Sutra ({author})"
        c.author, c.edition = author, f"Edition {author}"
        c.location = Location(book="1", chapter="1", sections=[n])
        pages.append(c)
    return pages


def client_for(indexed, embedder, tmp_path, pages):
    path = tmp_path / "verses.jsonl"
    path.write_text("\n".join(c.model_dump_json() for c in pages))
    indexed.import_jsonl(path)
    indexed.index(embedder=embedder)
    return TestClient(create_app(retriever=Retriever(indexed, embedder=embedder)))


def test_a_verse_page_lists_its_citations_by_author(indexed, embedder, tmp_path, make_chapter):
    pages = library(make_chapter)
    client = client_for(indexed, embedder, tmp_path, pages)
    target = pages[0]
    start = target.text.index("7. 'Now")
    end = target.text.index("8. 'Please")
    page = client.get(
        "/api/verse", params={"chapter_id": target.id, "start": start, "end": end}
    ).json()
    assert page["text"].startswith("7. 'Now") and page["place"] == "VI, 8"
    (shankara,) = page["citations"]  # Rāmānuja cites verse 8, not this one
    assert shankara["author"] == "Sankaracharya"
    # The second reference's quote is not in this translation: chapter level, listed apart.
    (ref,) = shankara["passages"]
    assert ref["label"] == "Kh. Up. VI, 8, 7" and ref["status"] == "verified"
    # The excerpt marks the reference in code points, after a supplementary character.
    excerpt = ref["context"]
    assert excerpt["text"][excerpt["start"] : excerpt["end"]] == "(Kh. Up. VI, 8, 7)"
    assert excerpt["text"].startswith("𑀅 The text says")
    # References to the section as a whole are listed apart.
    assert {g["author"] for g in page["whole"]} == {"Ramanuja", "Sankaracharya"}

    assert (
        client.get("/api/verse", params={"chapter_id": "nope", "start": 0, "end": 1}).status_code
        == 404
    )
    bad = {"chapter_id": target.id, "start": 5, "end": 2}
    assert client.get("/api/verse", params=bad).status_code == 422


def test_a_saying_resolves_from_printed_numbers(indexed, embedder, tmp_path, make_chapter):
    pages = library(make_chapter)
    client = client_for(indexed, embedder, tmp_path, pages)
    target = pages[0]
    listed = {s["key"]: s for s in client.get("/api/sayings").json()}
    assert set(listed) == {"tat-tvam-asi", "aham-brahmasmi", "prajnanam-brahma", "ayam-atma-brahma"}
    # Only the Chāndogya is in this library; the others are reported, not guessed.
    assert [k for k, s in listed.items() if s["found"]] == ["tat-tvam-asi"]
    tat = listed["tat-tvam-asi"]
    # The verse runs on past its first paragraph to the next printed number.
    assert tat["verse"]["text"].startswith("7. 'Now") and "art it" in tat["verse"]["text"]
    assert target.text[tat["mark"][0] : tat["mark"][1]] == "thou, O Svetaketu, art it"
    assert tat["cited"] == {"Sankaracharya": 1}
    # Quotations: the bare "That art thou" and Rāmānuja's vocative use; not the quote that
    # sits right before a printed reference to the verse.
    assert tat["quoted"] == {"Sankaracharya": 1, "Ramanuja": 1}
    full = client.get("/api/sayings/tat-tvam-asi").json()
    quotes = [p for g in full["quotations"] for p in g["passages"]]
    words = sorted(
        p["context"]["text"][p["context"]["start"] : p["context"]["end"]] for p in quotes
    )
    assert words == ["That art thou", "Thou art that"]
    assert client.get("/api/sayings/nope").status_code == 404


def test_a_saying_without_its_words_is_not_found(indexed, embedder, tmp_path, make_chapter):
    other = CHANDOGYA.replace("thou, O Svetaketu, art it", "the son was silent")
    client = client_for(indexed, embedder, tmp_path, library(make_chapter, other))
    tat = client.get("/api/sayings/tat-tvam-asi").json()
    assert tat["found"] is False and "verse" not in tat


def test_context_is_cut_at_sentences():
    text = "First sentence here. " * 40 + "The quote (X. 1) follows. And more text. " * 10
    at = text.index("(X. 1)")
    c = context(text, at, at + 6)
    assert c["text"][c["start"] : c["end"]] == "(X. 1)"
    assert c["text"].startswith(("First", "The")) and c["clipped_before"]
    assert len(c["text"]) <= 620


def test_citations_in_the_opposing_view_come_from_printed_cues_only(
    indexed, embedder, tmp_path, make_chapter
):
    pages = library(make_chapter)
    quote = "'It is the Self, and thou, O Svetaketu, art it' (Kh. Up. VI, 8, 7)"
    # A page printed under the pūrvapakṣa title: the opposing view throughout, even where
    # the opponent "replies" to an objection of his own.
    framed = make_chapter(f"To this we reply. The opponent cites {quote}.", book="1", chapter="3")
    framed.document_id, framed.document = "bs-ramanuja", "Brahma Sutra (Ramanuja)"
    framed.author, framed.edition = "Ramanuja", "Edition Ramanuja"
    framed.location = Location(book="1", chapter="1", sections=["1", "The Great Pûrvapaksha"])
    # A cue far before the citation (no reply cue between) is not trusted.
    far = make_chapter(
        "The pûrvapakshin maintains that the Self is the body. "
        + "Filler sentence about something else. " * 60
        + f"Śaṅkara's own view rests on {quote}.",
        book="1",
        chapter="4",
    )
    far.document_id, far.document = "bs-sankaracharya", "Brahma Sutra (Sankaracharya)"
    far.author, far.edition = "Sankaracharya", "Edition Sankaracharya"
    far.location = Location(book="1", chapter="1", sections=["9"])
    client = client_for(indexed, embedder, tmp_path, [*pages, framed, far])
    tat = client.get("/api/sayings/tat-tvam-asi").json()
    roles = {
        (g["author"], p["chapter_id"]): p["role"]
        for g in tat["verse"]["citations"]
        for p in g["passages"]
    }
    assert roles[("Ramanuja", framed.id)] == {"role": "objection", "from": "The Great Pûrvapaksha"}
    assert roles[("Sankaracharya", far.id)] is None
    assert tat["cited_in_objection"] == {"Ramanuja": 1}
