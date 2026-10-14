import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from pramana import Corpus
from pramana.chunking import chunk_chapter
from pramana.errors import PramanaError
from pramana.ingestion import pdf
from pramana.models import Chapter, Source


def tiny_pdf(path: Path, *, text: str | None = None, pages: int = 2):
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(width=200, height=200)
        if text:
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/Font"): DictionaryObject(
                        {NameObject("/F1"): writer._add_object(font)}
                    )
                }
            )
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 10 Tf 10 100 Td ({text}) Tj ET".encode())
            page[NameObject("/Contents")] = writer._add_object(stream)
    writer.write(path)


def test_verified_move_and_conflict_preserves_original(tmp_path):
    source = tmp_path / "source.pdf"
    tiny_pdf(source)
    expected = pdf.checksum(source)
    saved, actual = pdf.preserve_pdf(source, tmp_path / "home")
    assert not source.exists()
    assert actual == expected == pdf.checksum(saved)
    source.write_bytes(b"different input")
    with pytest.raises(PramanaError, match="originals retained"):
        pdf.preserve_pdf(source, tmp_path / "home")
    assert source.read_bytes() == b"different input"
    assert pdf.checksum(saved) == expected


def test_copy_failure_never_removes_input(tmp_path, monkeypatch):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"original")
    monkeypatch.setattr(pdf.shutil, "copyfile", lambda src, dst: dst.write_bytes(b"truncated"))
    with pytest.raises(PramanaError, match="checksum mismatch"):
        pdf.preserve_pdf(source, tmp_path / "home")
    assert source.read_bytes() == b"original"
    assert not (tmp_path / "home/sources/pdfs/source.pdf").exists()


def test_extraction_local_provenance_and_idempotent_import(tmp_path, embedder, monkeypatch):
    home = tmp_path / "home"
    path = home / "sources/pdfs/test.pdf"
    path.parent.mkdir(parents=True)
    tiny_pdf(
        path,
        text=(
            "Knowledge and action are discussed with careful attention to the "
            "nature of self and the way of life."
        ),
    )
    spec = replace(pdf.BOOKS[0], first_page=1)
    output = pdf.extract_pdf(path, home, spec)
    chapter = Chapter.model_validate_json(output.read_text().splitlines()[0])
    assert chapter.source.url is None
    assert chapter.source.local_path == "sources/pdfs/test.pdf"
    assert chapter.author == "Swami Chinmayananda"
    assert chapter.content_type == "mixed"
    assert chapter.pages[0].label == "1"
    corpus = Corpus(home)
    assert corpus.import_jsonl(output) == 2
    from pypdf import PageObject

    def unexpected_extraction(*args, **kwargs):
        raise AssertionError("cached pages should not be extracted again")

    monkeypatch.setattr(PageObject, "extract_text", unexpected_extraction)
    assert pdf.extract_pdf(path, home, spec) == output
    assert corpus.import_jsonl(output) == 0
    passages = chunk_chapter(chapter, embedder.tokenizer)
    assert passages[0].citation.source_local_path == chapter.source.local_path
    assert passages[0].citation.source_url is None
    assert chapter.text[passages[0].start : passages[0].end] == passages[0].text
    other = chapter.model_copy(update={"edition": "Another edition"})
    assert chapter.id != other.id


def test_ocr_cache_coverage_and_configuration(tmp_path, monkeypatch):
    home = tmp_path / "home"
    path = home / "sources/pdfs/scan.pdf"
    path.parent.mkdir(parents=True)
    tiny_pdf(path)
    monkeypatch.setattr(pdf, "ocr_tools", lambda: {"tesseract": "fake", "pdftoppm": "fake"})
    monkeypatch.setattr(
        pdf.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout="tool v1", stderr="")
    )
    calls = []

    def ocr(path, number, tools):
        calls.append(number)
        return {
            "raw": (
                "Ānanda 𑀅 joy knowledge self truth infinite Brahman mind food "
                "breath understanding peace inquiry wisdom life being."
            )
            if number == 1
            else "",
            "ink_fraction": 0.1 if number == 1 else 0,
            "ocr_mean_confidence": 90,
        }

    monkeypatch.setattr(pdf, "ocr_page", ocr)
    spec = replace(pdf.BOOKS[2], first_page=1)
    output = pdf.extract_pdf(path, home, spec)
    report = json.loads((output.parent / "coverage.json").read_text())
    assert report["counts"] == {"extracted": 1, "blank": 1, "questionable": 0}
    assert report["indexed_pages"] == 1
    assert "𑀅" in output.read_text()
    assert sorted(calls) == [1, 2]
    pdf.extract_pdf(path, home, spec)
    assert len(calls) == 2
    monkeypatch.setitem(pdf.PARSER, "version", 999)
    assert pdf.extract_pdf(path, home, spec) != output
    assert len(calls) == 4


def test_interrupted_ocr_preserves_published_records(tmp_path, monkeypatch):
    home = tmp_path / "home"
    path = home / "sources/pdfs/scan.pdf"
    path.parent.mkdir(parents=True)
    tiny_pdf(path)
    monkeypatch.setattr(pdf, "ocr_tools", lambda: {"tesseract": "fake"})
    monkeypatch.setattr(
        pdf.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout="tool v1", stderr="")
    )
    text = (
        "The nature of knowledge and truth is considered carefully with "
        "commentary about understanding the self and finding peace."
    )
    monkeypatch.setattr(pdf, "ocr_page", lambda *args: {"raw": text})
    spec = replace(pdf.BOOKS[2], first_page=1)
    output = pdf.extract_pdf(path, home, spec)
    original = output.read_bytes()
    (output.parent / "pages/0002.json").unlink()

    def fail(*args):
        raise PramanaError("interrupted acquisition")

    monkeypatch.setattr(pdf, "ocr_page", fail)
    with pytest.raises(PramanaError, match="interrupted"):
        pdf.extract_pdf(path, home, spec)
    assert output.read_bytes() == original
    assert (output.parent / "pages/0001.json").exists()


def test_source_origins_and_cleaning(make_chapter):
    original = make_chapter().source.model_dump()
    assert Source.model_validate(original).url is not None
    for patch in (
        {"url": None},
        {"local_path": "sources/a.pdf"},
        {"url": None, "local_path": "../a.pdf"},
        {"url": None, "local_path": "/tmp/a.pdf"},
    ):
        with pytest.raises(ValidationError):
            Source.model_validate({**original, **patch})
    raw = "Holy Geeta by Swami Chinmayananda\n13\nĀnanda 𑀅 and joy.\nA second line."
    assert pdf.clean_text(raw, pdf.BOOKS[0]) == "Ānanda 𑀅 and joy. A second line."
    assert pdf.page_quality("", {"ink_fraction": 0.1})[0] == "questionable"
    assert pdf.page_quality("noise 123???", {})[0] == "questionable"


def test_missing_ocr_setup_is_actionable(monkeypatch):
    monkeypatch.setattr(pdf.shutil, "which", lambda name: None)
    with pytest.raises(PramanaError, match="brew install poppler tesseract"):
        pdf.ocr_tools()


def test_replacement_removes_omitted_pages_only_in_its_edition(tmp_path, make_chapter, embedder):
    corpus = Corpus(tmp_path / "library")
    first = make_chapter("Action prepares the mind for understanding.")
    second = make_chapter("A contents page which should be omitted.", chapter="2")
    other = first.model_copy(update={"edition": "Independent edition"})
    path = tmp_path / "import.jsonl"
    path.write_text("\n".join(c.model_dump_json() for c in [first, second, other]))
    corpus.import_jsonl(path)
    corpus.index(embedder=embedder)
    path.write_text(first.model_dump_json())
    assert corpus.import_jsonl(path, replace_document=True) == 1
    assert {c.id for c in corpus.store.chapters()} == {first.id, other.id}
    assert corpus.store.status()["state"] == "stale"
    assert corpus.import_jsonl(path, replace_document=True) == 0
    with corpus.store.connect() as db:
        assert not db.execute("SELECT * FROM passages WHERE chapter_id=?", (second.id,)).fetchall()
        assert db.execute("SELECT COUNT(*) FROM passages_fts").fetchone()[0] == 2


def test_bad_pdf_fails_with_setup_message(tmp_path):
    home = tmp_path / "home"
    path = home / "sources/pdfs/bad.pdf"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"%PDF-1.7\ninterrupted file")
    with pytest.raises(PramanaError, match="Cannot read PDF"):
        pdf.extract_pdf(path, home, pdf.BOOKS[0])
