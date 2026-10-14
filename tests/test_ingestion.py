import gzip
import json
from pathlib import Path

import pytest

from pramana import Corpus
from pramana.errors import PramanaError
from pramana.ingestion.vishnu import acquire, manifest, parse_legacy_html, parse_text_section


def test_manifest_has_all_books_and_excludes_supplements():
    entries = manifest()
    assert len(entries) == 126
    assert [sum(e["book"] == str(b) for e in entries) for b in range(1, 7)] == [
        22,
        16,
        18,
        24,
        38,
        8,
    ]
    assert not {"vp043.htm", "vp061.htm", "vp100.htm"} & {e["file"] for e in entries}


def test_real_source_separates_notes_and_summary(make_chapter):
    raw = Path("tests/fixtures/wilson-book1-chapter1.txt").read_text()
    chapter = parse_text_section(raw, manifest()[0], make_chapter().source)
    assert "Maitreya" in chapter.text
    assert "Invocation." not in chapter.text
    assert "An address of this kind" not in chapter.text
    assert len(chapter.notes) == 16
    assert chapter.notes[0].id == "1:1"
    assert chapter.notes[0].anchor_offset is not None
    assert [p.label for p in chapter.pages] == ["1", "2", "3", "4", "5", "6"]
    assert all(p.offset <= len(chapter.text) for p in chapter.pages)


def test_repeated_source_note_numbers_keep_distinct_anchors(make_chapter):
    raw = "CHAP. II\n\nSummary.\n\n" + "A long body. " * 10
    raw += (
        "first [*3].\n[p. 514] second [*3].\nFootnotes\n\n^513:3 First note\n\n^514:3 Second note"
    )
    chapter = parse_text_section(raw, manifest()[1], make_chapter().source)
    assert [n.id for n in chapter.notes] == ["513:3", "514:3"]
    assert chapter.notes[0].anchor_offset < chapter.notes[1].anchor_offset


def test_unicode_html_never_folds_source_diacritics(make_chapter):
    html = "<h3>CHAP. I.</h3><p>Summary.</p><p>" + "Viṣṇu and Prakṛti. " * 10
    html += '<a name="page_2">p. 2</a>Text <a href="#fn_1">1</a>.</p>'
    html += '<h3>Footnotes</h3><p><a href="#fr_1">2:1</a>Translator note.</p>'
    chapter = parse_legacy_html(html, manifest()[0], make_chapter().source)
    assert "Viṣṇu" in chapter.text and "Prakṛti" in chapter.text
    assert chapter.notes[0].text == "Translator note."
    assert chapter.pages[0].label == "2"


def test_import_validation_is_atomic_and_reports_line(tmp_path, make_chapter):
    file = tmp_path / "chapters.jsonl"
    file.write_text(make_chapter().model_dump_json() + '\n{"text":"missing provenance"}')
    corpus = Corpus(tmp_path / "store")
    with pytest.raises(PramanaError, match=r":2:"):
        corpus.import_jsonl(file)
    assert corpus.store.status()["chapters"] == 0


def test_missing_and_corrupt_archive_are_actionable(tmp_path):
    with pytest.raises(PramanaError, match="cache missing"):
        acquire(tmp_path, offline=True)
    archive = tmp_path / "wrong.gz"
    archive.write_bytes(b"not gzip")
    with pytest.raises(PramanaError, match="original vp.txt.gz"):
        acquire(tmp_path, archive)


def test_incomplete_archive_never_publishes_jsonl(tmp_path):
    archive = tmp_path / "wrong.gz"
    archive.write_bytes(gzip.compress(b"incomplete"))
    with pytest.raises(PramanaError, match="incomplete"):
        acquire(tmp_path, archive)
    assert not (tmp_path / "corpora/vishnu-purana/chapters.jsonl").exists()


def test_repeat_import_is_idempotent_and_unicode_exact(tmp_path, make_chapter):
    text = "Viṣṇu preserves the universe. ज्ञान 🪷\n\nPrakṛti."
    chapter = make_chapter(text)
    file = tmp_path / "chapters.jsonl"
    file.write_text(chapter.model_dump_json(), encoding="utf-8")
    corpus = Corpus(tmp_path / "store")
    assert corpus.import_jsonl(file) == 1
    assert corpus.import_jsonl(file) == 0
    assert corpus.store.chapter(chapter.id).text == text
    data = json.loads(file.read_text())
    data["pages"] = [{"offset": 10000, "label": "1"}]
    file.write_text(json.dumps(data))
    with pytest.raises(PramanaError, match="page offset"):
        corpus.import_jsonl(file)
