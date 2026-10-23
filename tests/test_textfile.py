import hashlib

import pytest

from pramana.errors import PramanaError
from pramana.ingestion import textfile
from pramana.ingestion.textfile import acquire, manifests

TEXT = """Front matter by the translator, presented to the public domain
with his affection.

Running Header

Chapter 1 Self-realization

Janaka said:

How is one to attain liberation? 1.1

Running Header

Ashtavakra said: You are the witness 𑀅. 1.2


Chapter 2 Joy

I am spotless. 2.1
"""


def fixture(**changes):
    return {
        "id": "fix",
        "url": "https://example.org/fix.txt",
        "item_url": "https://example.org/fix",
        "sha256": hashlib.sha256(TEXT.encode()).hexdigest(),
        "document_id": "fix-doc",
        "document": "Fixture Gita",
        "translator": "T. Translator",
        "author": "",
        "edition": "Fixture 1996",
        "content_type": "translation",
        "rights": "Stated in the text: presented to the public domain.",
        "rights_quote": "presented to the public domain\nwith his affection",
        "attribution": "T. Translator",
        "chapter_pattern": r"(?m)^Chapter (\d+) (.+?)\s*$",
        "chapters": 2,
        "verse_pattern": r"(?m)(\d{1,2})\.(\d{1,3})\s*$",
        "verses": 3,
        "strip_lines": ["Running Header"],
        **changes,
    }


def run(tmp_path, monkeypatch, text=TEXT, **changes):
    monkeypatch.setattr(textfile, "manifests", lambda: {"fix": fixture(**changes)})
    saved = tmp_path / "saved.txt"
    saved.write_text(text, encoding="utf-8")
    return acquire(tmp_path / "home", "fix", saved)


def test_chapters_verses_and_cleanup(tmp_path, monkeypatch):
    from pramana.models import Chapter

    out = run(tmp_path, monkeypatch)
    one, two = [Chapter.model_validate_json(x) for x in out.read_text().splitlines()]
    assert one.text.startswith("Chapter 1 Self-realization") and "Front matter" not in one.text
    assert "Running Header" not in one.text and "witness 𑀅. 1.2" in one.text
    assert (one.location.chapter, one.location.sections, two.location.chapter) == (
        "1",
        ["Self-realization"],
        "2",
    )
    assert one.source.checksum == fixture()["sha256"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"sha256": "0" * 64}, "differs from the reviewed edition"),
        ({"rights_quote": "all rights reserved"}, "rights statement is missing"),
        ({"chapters": 3}, "expected chapters"),
        ({"verses": 4}, "numbered verses"),
    ],
)
def test_wrong_or_changed_text_is_rejected(tmp_path, monkeypatch, change, message):
    with pytest.raises(PramanaError, match=message):
        run(tmp_path, monkeypatch, **change)
    assert not (tmp_path / "home" / "corpora" / "fix" / "chapters.jsonl").exists()


def test_committed_manifest_pins_the_edition():
    (m,) = manifests().values()
    assert len(m["sha256"]) == 64 and m["verses"] == 298 and m["chapters"] == 20
    assert m["author"] == ""  # tradition ascribes it to Ashtavakra; no author is claimed
