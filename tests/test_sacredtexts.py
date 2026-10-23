import gzip

import pytest

from pramana.errors import PramanaError
from pramana.ingestion import sacredtexts
from pramana.ingestion.sacredtexts import acquire, books

HEADER = "Fixture Upanishads, tr. by Test, [1900], at sacred-texts.com"
MANIFEST = {
    "id": "fix",
    "archive_url": "https://example.org/fix.txt.gz",
    "title_url": "https://example.org/fix000.htm",
    "header": HEADER,
    "sections": 3,
    "translator": "Test Translator",
    "author": "",
    "edition": "Fixture 1900 · plain text",
    "rights": "Stated by the source: This text is in the public domain.",
    "pages": [
        {
            "file": "fix001.htm",
            "section": 2,
            "url": "https://example.org/fix001.htm",
            "document_id": "katha-upanishad-fix",
            "document": "Katha Upanishad",
            "book": "1",
            "chapter": "1",
            "label": "I, 1",
            "content_type": "translation",
        }
    ],
}
BODY = (
    "\n\n[p. 1]\n\nKATHA-UPANISHAD.\n\n1. Vagasravasa [*1] gave away all. Ātman 𑀅 [***] is"
    " one.\n\n[p. 2]\n\n2. Faith entered [*2] Nakiketas.\n\nFootnotes\n\n^1:1 A name.\n\n"
    "^2:2 Sraddha.\n"
)


def archive(tmp_path, sections=None):
    path = tmp_path / "fix.txt.gz"
    parts = sections or ["preamble", "front matter", BODY]
    path.write_bytes(gzip.compress(f"\r\n{HEADER}\r\n".join(parts).encode()))
    return path


@pytest.fixture
def fixture_manifest(monkeypatch):
    monkeypatch.setattr(sacredtexts, "books", lambda: {"fix": MANIFEST})


def test_committed_manifests_are_complete_and_unique():
    manifests = books()
    assert {"wos", "sbe01", "sbe15", "sbg", "tmu", "brk"} <= set(manifests)
    for m in (m for m in manifests.values() if m.get("format") != "html"):
        assert m["rights"].startswith("Stated by the source: This text is in the public domain")
        keys = [(p["document_id"], p["book"], p["chapter"], p["label"]) for p in m["pages"]]
        assert len(set(keys)) == len(keys)
        assert all(0 < p["section"] < m["sections"] for p in m["pages"])
    assert not any("Hume" in p["label"] for p in manifests["sbe15"]["pages"])


def test_acquire_parses_markers_offsets_and_notes(tmp_path, fixture_manifest):
    from pramana.models import Chapter

    out = acquire(tmp_path / "home", "fix", archive(tmp_path))
    (chapter,) = [Chapter.model_validate_json(line) for line in out.read_text().splitlines()]
    text = chapter.text
    assert text.startswith("KATHA-UPANISHAD.") and "[*" not in text and "[p." not in text
    assert "Ātman 𑀅  is one." in text  # Unmatched symbol marker removed; spacing preserved.
    assert [(p.label, text[p.offset :].lstrip()[:2]) for p in chapter.pages] == [
        ("1", "KA"),
        ("2", "2."),
    ]
    assert [(n.id, n.text) for n in chapter.notes] == [("1:1", "A name."), ("2:2", "Sraddha.")]
    assert text[: chapter.notes[0].anchor_offset].endswith("Vagasravasa ")
    assert chapter.location.sections == ["I, 1"] and chapter.document == "Katha Upanishad"
    assert chapter.source.rights == MANIFEST["rights"]
    again = acquire(tmp_path / "home", "fix", offline=True)
    assert again.read_text() == out.read_text()  # Unchanged archive keeps its timestamp.


def test_changed_structure_keeps_last_output(tmp_path, fixture_manifest):
    home = tmp_path / "home"
    out = acquire(home, "fix", archive(tmp_path))
    before = out.read_text()
    with pytest.raises(PramanaError, match="expected 3"):
        acquire(home, "fix", archive(tmp_path, ["preamble", BODY]))
    assert out.read_text() == before
    with pytest.raises(PramanaError, match="Unknown Sacred Texts book"):
        acquire(home, "missing")


HTML = """<HTML><HEAD><META name="description" content="Fixture Book, at sacred-texts.com">
</HEAD><BODY><CENTER><A HREF="index.htm">Index</A></CENTER><HR></p>
<p><A NAME="page_7"><FONT SIZE=1 COLOR=GREEN>p. 7</FONT></A></p> <h1>The Crest</h1>
<p>I BOW before Govinda, who is supreme bliss. 𑀅 Ātman.</p>
<p><A NAME="page_"><FONT SIZE=1 COLOR=GREEN>p. </FONT></A></p>
<p>For beings a human birth is hard to win.</p>
<p><HR><CENTER><A HREF="next.htm">Next: Two</A></CENTER><nav><p>Sacred Texts</p></nav>
</BODY></HTML>"""


def test_html_books_cache_pages_and_skip_unnumbered_anchors(tmp_path, monkeypatch):
    from pramana.models import Chapter

    manifest = {
        "id": "fixhtml",
        "format": "html",
        "identify": "Fixture Book, at sacred-texts.com",
        "title_url": "https://example.org/fix00.htm",
        "translator": "Test Translator",
        "author": "Sankaracharya",
        "edition": "Fixture 1946 · HTML",
        "rights": "Stated by the source: This text is in the public domain in the US.",
        "pages": [
            {
                "file": "fix05.htm",
                "url": "https://example.org/fix05.htm",
                "document_id": "crest-fix",
                "document": "The Crest",
                "book": "1",
                "chapter": "1",
                "label": "First Steps",
                "content_type": "translation",
            },
            {
                "file": "fix06.htm",
                "url": "https://example.org/fix06.htm",
                "document_id": "essay-fix",
                "document": "An Essay",
                "book": "1",
                "chapter": "1",
                "label": "Essay",
                "content_type": "commentary",
                "author": "Charles Johnston",
            },
        ],
    }
    monkeypatch.setattr(sacredtexts, "books", lambda: {"fixhtml": manifest})
    saved = tmp_path / "saved"
    saved.mkdir()
    for page in manifest["pages"]:
        (saved / page["file"]).write_text(HTML, encoding="utf-8")
    out = acquire(tmp_path / "home", "fixhtml", saved)
    crest, essay = [Chapter.model_validate_json(x) for x in out.read_text().splitlines()]
    assert crest.text.startswith("The Crest\n\nI BOW") and "𑀅 Ātman." in crest.text
    assert "Next:" not in crest.text and [p.label for p in crest.pages] == ["7"]
    assert (crest.author, essay.author, essay.content_type) == (
        "Sankaracharya",
        "Charles Johnston",
        "commentary",
    )
    # Offline rebuild from the cache; a foreign page is rejected without publishing.
    assert acquire(tmp_path / "home", "fixhtml", offline=True).read_text() == out.read_text()
    cached = tmp_path / "home" / "corpora" / "sacred-texts-fixhtml" / "html" / "fix06.htm"
    cached.write_text("<html><p>Just a moment...</p></html>")
    with pytest.raises(PramanaError, match="not a page of this edition"):
        acquire(tmp_path / "home", "fixhtml", offline=True)
    assert out.read_text().count("\n") == 2


def test_committed_html_manifest_attributes_essays_to_johnston():
    cjw = books()["cjw"]
    authors = {p["document"]: p["author"] for p in cjw["pages"]}
    assert authors["The Teachings of Sankara"] == "Charles Johnston"
    assert authors["The Crest-Jewel of Wisdom (Vivekachudamani)"] == "Sankaracharya"
    assert cjw["rights"].startswith("Stated by the source: This text is in the public domain")
