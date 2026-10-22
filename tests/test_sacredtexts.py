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
    for m in manifests.values():
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
