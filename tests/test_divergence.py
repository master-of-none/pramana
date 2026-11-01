from fastapi.testclient import TestClient

from pramana import Retriever
from pramana.api import create_app
from pramana.citations import Library, resolve
from pramana.divergence import (
    _dispute_bands,
    _ranks,
    _scripture_bands,
    band,
    compute,
    divergence,
    most_different,
)
from pramana.models import Location

CHANDOGYA = (
    "7. 'That which is that subtle essence, in it all that exists has its self. "
    "It is the True. It is the Self, and thou, O Svetaketu, art it.'\n\n"
    "8. 'Please, Sir, inform me still more,' said the son."
)
SHARED = "The Self is to be known through the texts, and Brahman is their purport."


def library(make_chapter):
    def page(author, book, pada, sections, text):
        c = make_chapter(text, book=book, chapter=pada)
        if author == "Sankaracharya":
            c.document_id, c.document = "bs-shankara", "Brahma Sutra Bhashya"
        else:
            c.document_id, c.document = "bs-ramanuja", "Sribhashya (Brahma Sutra commentary)"
        c.author, c.edition = author, f"Edition {author}"
        c.location = Location(book=book, chapter=pada, sections=sections)
        return c

    target = make_chapter(CHANDOGYA, book="6", chapter="8")
    target.document_id, target.document = "chandogya-upanishad-sbe01", "Chandogya Upanishad"
    target.location = Location(book="6", chapter="8", sections=["VI, 8"])
    return [
        target,
        # 1.1.1, after a preamble: different scripture, different wording, and
        # Rāmānuja's text names nescience. The sūtra lines match: the same sūtra.
        page(
            "Sankaracharya",
            "1",
            "1",
            ["1"],
            "FIRST PÂDA.\n\nREVERENCE!\n\n1. Then therefore the enquiry into Brahman.\n\n"
            "'thou, O Svetaketu, art it' (Kh. Up. VI, 8, 7). Superimposition of the "
            "not-Self on the Self is the root of all evil.",
        ),
        page(
            "Ramanuja",
            "1",
            "1",
            ["1"],
            "1. Then therefore the enquiry into Brahman.\n\nThe enquiry into qualified "
            "Brahman (Kh. Up. VI, 8, 8). Nescience cannot belong to Brahman; the theory of "
            "nescience and of a non-differenced Brahman is untenable, and sublation of the "
            "world is impossible.",
        ),
        # A topic page under the same sūtra belongs to the same unit.
        page("Ramanuja", "1", "1", ["1", "The Great Siddhânta"], "The world is real."),
        # 1.1.2: the same text on both sides, citing the same verse; Rāmānuja prints the
        # same sūtra as his 3 (the recensions number it differently).
        page(
            "Sankaracharya",
            "1",
            "1",
            ["2"],
            f"2. Origin of this world from that.\n\n{SHARED} (Kh. Up. VI, 8, 7).",
        ),
        page(
            "Ramanuja", "1", "1", ["2"], "2. An unrelated sūtra about meditation.\n\nOther words."
        ),
        page(
            "Ramanuja",
            "1",
            "1",
            ["3"],
            f"3. Origin of this world from that.\n\n{SHARED} (Kh. Up. VI, 8, 7).",
        ),
        # 1.1.4 (end of the pāda): no sūtra line matches; kept by number, unconfirmed.
        page("Sankaracharya", "1", "1", ["4"], "4. But that, on account of connexion.\n\nText."),
        page("Ramanuja", "1", "1", ["4"], "4. Of the highest Person the eye.\n\nText."),
        # 1.2.1: no page of Rāmānuja's in this pāda at all.
        page("Sankaracharya", "1", "2", ["1"], "1. Everywhere known.\n\nBrahman everywhere."),
        # A pāda heading page without a sūtra number is not a unit.
        page("Ramanuja", "1", "2", ["Second Pâda"], "Second Pâda."),
    ]


def computed(make_chapter):
    pages = library(make_chapter)
    lib = Library(pages)
    outgoing = {c.id: refs for c in pages if (refs := resolve(c.text, lib))}
    return pages, compute(pages, outgoing)


def test_units_pair_the_same_printed_sutra(make_chapter):
    pages, data = computed(make_chapter)
    assert data["available"]
    by_label = {u["label"]: u for u in data["units"]}
    assert list(by_label) == ["1.1.1", "1.1.2–3", "1.1.4", "1.2.1"]
    ids = {(c.author, tuple(c.location.sections)): c.id for c in pages if c.author}
    first = by_label["1.1.1"]
    # The sūtra line is found after the preamble; the topic page belongs to the unit.
    assert first["pairing"] == "same" and first["exact"]
    assert first["ramanuja"] == [
        ids[("Ramanuja", ("1",))],
        ids[("Ramanuja", ("1", "The Great Siddhânta"))],
    ]
    # Śaṅkara's 2 is Rāmānuja's 3 by its printed words; his 2 is a different sūtra.
    moved = by_label["1.1.2–3"]
    assert moved["pairing"] == "renumbered" and moved["ramanuja_sutra"] == 3
    # Śaṅkara's 2-3 shifted by one: Rāmānuja's 3-4.
    assert moved["ramanuja"] == [ids[("Ramanuja", ("3",))], ids[("Ramanuja", ("4",))]]
    # No matching sūtra line: kept by number and marked unconfirmed.
    assert by_label["1.1.4"]["pairing"] == "unconfirmed"
    assert by_label["1.1.4"]["ramanuja"] == [ids[("Ramanuja", ("4",))]]
    # Nothing at all in that pāda: empty and unconfirmed.
    lone = by_label["1.2.1"]
    assert lone["ramanuja"] == [] and lone["pairing"] == "unconfirmed"


def test_signals_explain_where_the_commentaries_differ(make_chapter):
    _, data = computed(make_chapter)
    by_label = {u["label"]: u for u in data["units"]}
    first, same = by_label["1.1.1"], by_label["1.1.2–3"]
    # Scripture: each side cites a different verse; the same verse is shared.
    assert first["shared"] == 0
    assert [r["label"] for r in first["only_shankara"]] == ["Kh. Up. VI, 8, 7"]
    assert [r["label"] for r in first["only_ramanuja"]] == ["Kh. Up. VI, 8, 8"]
    assert first["bands"]["scripture"] == "moderate"  # same chapter, different verses
    assert same["shared"] == 1 and same["bands"]["scripture"] == "low"
    # Dispute terms are found in Rāmānuja's text only, with counts.
    assert first["terms"] == {"nescience": 2, "non-differenced Brahman": 1, "sublation": 1}
    assert same["terms"] == {} and same["bands"]["dispute"] == "low"
    order = list(data["bands"])
    for signal in ("overall", "wording", "dispute"):
        assert order.index(first["bands"][signal]) > order.index(same["bands"][signal]), signal
    # A unit without Rāmānuja's text has no wording or dispute signal.
    assert by_label["1.2.1"]["bands"]["wording"] is None
    assert by_label["1.2.1"]["bands"]["dispute"] is None
    # Confirmed pairs only in the lists, most different first; no numeric scores.
    assert [u["label"] for u in most_different(data)] == ["1.1.1", "1.1.2–3"]
    assert most_different(data, least=True)[0]["label"] == "1.1.2–3"
    assert all(isinstance(v, str | None) for u in data["units"] for v in u["bands"].values())


def test_bands():
    assert _ranks([3.0, None, 1.0, 1.0, 2.0]) == [0.875, None, 0.25, 0.25, 0.625]
    assert [band(r) for r in (0.0, 0.2, 0.5, 0.99, 1.0, None)] == [
        "low",
        "moderate",
        "marked",
        "very high",
        "very high",
        None,
    ]
    # Scripture by meaning: the same, partly shared, nothing in common.
    assert _scripture_bands([0.0, 0.3, 0.7, 0.9, 1.0, None]) == [0, 1, 2, 3, 4, None]
    # Dispute: no terms is low; units that name them are split into quartiles.
    assert _dispute_bands([0.0, 1.0, 2.0, 3.0, 4.0, None]) == [0, 1, 2, 3, 4, None]


def test_one_kind_of_evidence_alone_is_not_very_high(make_chapter):
    pages = library(make_chapter)
    data = compute(pages, {})  # no scripture resolved; no dispute terms counted below
    for unit in data["units"]:
        measured = [
            b for s, b in unit["bands"].items() if s != "overall" and b not in (None, "low")
        ]
        if len(measured) <= 1:
            assert unit["bands"]["overall"] != "very high", unit["label"]


def test_one_commentary_alone_is_reported_not_mapped(make_chapter):
    pages = [c for c in library(make_chapter) if c.author != "Ramanuja"]
    data = compute(pages, {})
    assert not data["available"] and "Rāmānuja" in data["reason"] and data["units"] == []


def test_divergence_api_and_cache(indexed, embedder, tmp_path, make_chapter):
    client = TestClient(create_app(retriever=Retriever(indexed, embedder=embedder)))
    assert client.get("/api/divergence").json()["available"] is False
    path = tmp_path / "bs.jsonl"
    path.write_text("\n".join(c.model_dump_json() for c in library(make_chapter)))
    indexed.import_jsonl(path)  # a new generation: the cached map is rebuilt
    data = client.get("/api/divergence").json()
    assert data["available"] and len(data["units"]) == 4
    assert data["documents"]["ramanuja"]["document_id"] == "bs-ramanuja"
    assert data["units"][data["ranking"][0]]["label"] == "1.1.1"
    assert divergence(indexed.store) is divergence(indexed.store)
