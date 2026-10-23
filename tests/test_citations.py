from fastapi.testclient import TestClient

from pramana import Retriever
from pramana.api import create_app
from pramana.citations import Library, resolve
from pramana.models import Location

CHANDOGYA = (
    "1. Uddalaka said to his son Svetaketu.\n\n"
    "7. 'That which is that subtle essence, in it all that exists has its self. "
    "It is the True. It is the Self, and thou, O Svetaketu, art it.'\n\n"
    "8. 'Please, Sir, inform me still more,' said the son."
)
COMMENTARY = (
    "𑀅 Scripture says 'thou, O Svetaketu, art it' (Kh. Up. VI, 8, 7). "
    "Compare also (Kh. Up. VI, 8, 8). "
    "And 'the sun is honey' (Kh. Up. VI, 8, 2). "
    "A bare reference (VI, 8, 7) and one to no division (Kh. Up. XX, 1, 1) stay text. "
    "'Uddalaka said to his son Svetaketu' (Kh. Up. VI, 8, 4)."
)


def chapters(make_chapter):
    target = make_chapter(CHANDOGYA, book="6", chapter="8")
    target.document_id, target.document = "chandogya-upanishad-sbe01", "Chandogya Upanishad"
    target.location = Location(book="6", chapter="8", sections=["VI, 8"])
    source = make_chapter(COMMENTARY, book="1", chapter="1")
    source.document_id, source.author = "brahma-sutra-shankara-thibaut", "Sankaracharya"
    source.document, source.location = (
        "Brahma Sutra Bhashya",
        Location(book="1", chapter="1", sections=["4"]),
    )
    return target, source


def test_printed_references_resolve_with_their_checks(make_chapter):
    target, source = chapters(make_chapter)
    refs = resolve(source.text, Library([target, source]))
    by_label = {r["label"]: r for r in refs}
    assert set(by_label) == {
        "Kh. Up. VI, 8, 7",
        "Kh. Up. VI, 8, 8",
        "Kh. Up. VI, 8, 2",
        "Kh. Up. VI, 8, 4",
    }  # the bare and the impossible references are left as text

    quoted = by_label["Kh. Up. VI, 8, 7"]
    assert quoted["status"] == "verified"
    span = target.text[quoted["target"]["start"] : quoted["target"]["end"]]
    assert span.startswith("7. 'That which is that subtle essence")
    # Offsets are Python code points: the supplementary character before counts once.
    assert source.text[quoted["start"] : quoted["end"]] == "(Kh. Up. VI, 8, 7)"

    numbered = by_label["Kh. Up. VI, 8, 8"]  # no quotation: the numbered verse
    assert numbered["status"] == "numbered"
    assert target.text[numbered["target"]["start"] :].startswith("8. 'Please")

    # Quoted words absent from the chapter (another translation's wording): chapter only.
    unmatched = by_label["Kh. Up. VI, 8, 2"]
    assert unmatched["status"] == "chapter" and unmatched["target"]["start"] == 0

    # The quotation decides over a verse number that does not hold it.
    moved = by_label["Kh. Up. VI, 8, 4"]
    assert moved["status"] == "verified"
    assert target.text[moved["target"]["start"] :].startswith("1. Uddalaka")


def test_citation_api_lists_both_directions(indexed, embedder, tmp_path, make_chapter):
    target, source = chapters(make_chapter)
    path = tmp_path / "cite.jsonl"
    path.write_text("\n".join(c.model_dump_json() for c in (target, source)))
    indexed.import_jsonl(path)
    indexed.index(embedder=embedder)
    client = TestClient(create_app(retriever=Retriever(indexed, embedder=embedder)))

    outgoing = client.get(f"/api/citations/{source.id}").json()["outgoing"]
    assert len(outgoing) == 4 and outgoing[0]["target"]["chapter_id"] == target.id
    incoming = client.get(f"/api/citations/{target.id}").json()["incoming"]
    assert {r["author"] for r in incoming} == {"Sankaracharya"} and len(incoming) == 4
    assert client.get("/api/citations/nope").status_code == 404

    summary = client.get("/api/citations").json()
    assert summary["references"] == 4
    assert summary["status"] == {"verified": 2, "numbered": 1, "chapter": 1}
    top = summary["passages"][0]
    assert top["by"] == {"Sankaracharya": 1} and not top["whole_chapter"]
