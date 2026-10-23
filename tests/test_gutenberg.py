import hashlib

import pytest

from pramana.errors import PramanaError
from pramana.ingestion import gutenberg
from pramana.ingestion.gutenberg import acquire, manifests, parse_volume, roman

VOL1 = """<html><body><h2>Transcriber's Notes</h2><p>Front matter.</p>
<h2>CONTENTS OF THE FIRST VOLUME.</h2>
<table><tr><td><a href="#c1">CHAPTER I.</a></td><td>Introduction 1</td></tr></table>
<h2>THE YOGA PHILOSOPHY.</h2><p>The translator's essay.</p>
<div class="chapter"><h2>BOOK I. ON APATHY<br/>CHAPTER I.<br/>INTRODUCTION.</h2>
<p><span class="dropcap">O</span>m, salutation to Reality.</p>
<p>2. He is the knower 𑀅 of all<a id="FNanchor_1" href="#Footnote_1">[1]</a>.</p>
<p>3. You must not <span class="pagenum">[Pg 816]</span> give up your duties [4].</p>
<p>[817]</p><p>4. Next page begins here.</p></div>
<div class="chapter"><h2>CHAPTER II.</h2><p>Second chapter text.</p></div>
<h2>BOOK II.</h2>
<div class="chapter"><h2>CHAPTER I.</h2><p>Book two begins.</p></div>
<h2>FOOTNOTES:</h2>
<div class="footnote"><p><a id="Footnote_1" href="#FNanchor_1">[1]</a> A note on knowing.</p></div>
</body></html>"""
VOL2 = """<html><body><h2>CONTENTS</h2>
<h2>CHAPTER II.</h2><p>Book two continues.</p>
<h2>CHAPTER II.</h2><p>A misprinted repeat of the number.</p></body></html>"""


def manifest(**changes):
    def vol(ebook, html, books):
        return {
            "ebook": ebook,
            "label": f"Vol. {ebook}",
            "url": f"https://example.org/{ebook}.html",
            "page_url": f"https://example.org/{ebook}",
            "sha256": hashlib.sha256(html.encode()).hexdigest(),
            "books": books,
        }

    return {
        "id": "fix-yv",
        "document_id": "fix-yv",
        "document": "Yoga Vasishtha Fixture",
        "translator": "T. Translator",
        "author": "",
        "edition": "Fixture",
        "content_type": "translation",
        "rights": "Stated by the source: free use in the US.",
        "attribution": "T. Translator",
        "volumes": [
            vol(
                1,
                VOL1,
                [
                    {"book": "1", "printed": "I", "chapters": 2},
                    {"book": "2", "printed": "II", "chapters": 1},
                ],
            ),
            vol(2, VOL2, [{"book": "2", "printed": "II", "chapters": 2}]),
        ],
        **changes,
    }


def run(tmp_path, monkeypatch, m=None, vol2=VOL2):
    monkeypatch.setattr(gutenberg, "manifests", lambda: {"fix-yv": m or manifest()})
    saved = tmp_path / "saved"
    saved.mkdir(exist_ok=True)
    (saved / "pg1.html").write_text(VOL1, encoding="utf-8")
    (saved / "pg2.html").write_text(vol2, encoding="utf-8")
    return acquire(tmp_path / "home", "fix-yv", saved)


def test_volumes_parse_by_heading_and_continue_books(tmp_path, monkeypatch):
    from pramana.models import Chapter

    out = run(tmp_path, monkeypatch)
    records = [Chapter.model_validate_json(x) for x in out.read_text().splitlines()]
    places = [(r.location.book, r.location.chapter, r.location.sections[0]) for r in records]
    assert places == [
        ("1", "1", "BOOK I. ON APATHY CHAPTER I. INTRODUCTION."),
        ("1", "2", "CHAPTER II."),
        ("2", "1", "CHAPTER I."),
        ("2", "2", "CHAPTER II."),  # continues across the volume boundary
        ("2", "3", "CHAPTER II."),  # printed misprint kept; position stays unique
    ]
    first = records[0]
    assert "Om, salutation" in first.text and "𑀅" in first.text
    assert "essay" not in first.text and "Front matter" not in first.text
    (note,) = first.notes
    assert note.text == "A note on knowing." and first.text[: note.anchor_offset].endswith("of all")
    assert "A note on knowing" not in records[2].text  # footnotes never enter chapter text
    # Printed page numbers become page marks; small unlinked footnote markers stay.
    assert "You must not give up your duties [4]." in first.text and "Pg" not in first.text
    assert "[817]" not in first.text
    marks = {p.label: first.text[p.offset :].lstrip()[:9] for p in first.pages}
    assert marks == {"816": "give up y", "817": "4. Next p"}
    assert records[0].source.url.unicode_string() == "https://example.org/1"


def test_changed_files_or_structure_are_rejected(tmp_path, monkeypatch):
    with pytest.raises(PramanaError, match="differs from the reviewed edition"):
        run(tmp_path, monkeypatch, vol2=VOL2 + "<p>edited</p>")
    m = manifest()
    m["volumes"][0]["books"][0]["chapters"] = 3
    with pytest.raises(PramanaError, match="expected chapters per book"):
        run(tmp_path, monkeypatch, m)
    assert not (tmp_path / "home" / "corpora" / "fix-yv" / "chapters.jsonl").exists()


def test_roman_numerals_and_committed_manifest():
    assert [roman(x) for x in ("I", "IV", "XLIX", "CXIV", "LXXXXI")] == [1, 4, 49, 114, 91]
    (m,) = manifests().values()
    assert len(m["volumes"]) == 7 and all(len(v["sha256"]) == 64 for v in m["volumes"])
    totals = {}
    for v in m["volumes"]:
        for b in v["books"]:
            totals[b["book"]] = totals.get(b["book"], 0) + b["chapters"]
    assert totals == {"1": 33, "2": 20, "3": 122, "4": 62, "5": 92, "6.1": 128, "6.2": 216}


def test_unlisted_book_heading_keeps_the_current_book():
    # Counts are then checked against the manifest, which catches a wrong book map.
    volume = {"ebook": 9, "books": [{"book": "1", "printed": "I"}]}
    assert [(c["book"], c["position"]) for c in parse_volume(VOL1, volume)] == [
        ("1", 1),
        ("1", 2),
        ("1", 3),
    ]
