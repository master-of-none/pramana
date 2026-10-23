import json
import shutil
import sys
from pathlib import Path

import pytest

from pramana.errors import PramanaError
from pramana.ingestion import pdf
from pramana.ingestion.pdf import BookSpec, clean_markdown, extract_pdf

pytestmark = pytest.mark.skipif(not shutil.which("pdftoppm"), reason="needs poppler")

FAKE = """#!{python}
import sys, pathlib
images, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
log = pathlib.Path({log!r})
log.write_text(log.read_text() + "run\\n" if log.exists() else "run\\n")
for image in sorted(images.glob("*.png")):
    page = int(image.stem[4:])
    (out / image.stem).mkdir(parents=True, exist_ok=True)
    (out / image.stem / (image.stem + ".md")).write_text(
        "# VIVEKACHUDAMANI\\n\\nसंन्यस्य सर्वकर्माणि भवबन्धविमुक्तये ।\\n\\n"
        f"{{page}}. Let the **wise** man give up *all* works, being free of bondage, "
        "and practise the realisation of the Atman with steady and earnest effort.\\n\\n"
        "![figure](img.png)\\n", encoding="utf-8")
"""


@pytest.fixture
def scan(tmp_path, monkeypatch):
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(4):
        writer.add_blank_page(width=300, height=400)
    home = tmp_path / "home"
    target = home / "sources" / "pdfs" / "scan.pdf"
    target.parent.mkdir(parents=True)
    with target.open("wb") as handle:
        writer.write(handle)
    log = tmp_path / "calls.log"
    fake = tmp_path / "bin" / "chandra"
    fake.parent.mkdir()
    fake.write_text(FAKE.format(python=sys.executable, log=str(log)))
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake.parent}:{Path(shutil.which('pdftoppm')).parent}")
    monkeypatch.setitem(pdf.CHANDRA, "batch", 2)
    return home, target, log


def spec(**changes):
    base = dict(
        id="scan-fixture",
        filename="scan.pdf",
        title="Fixture Scan",
        edition="Fixture 1921",
        author="Sankaracharya",
        translator="T. Translator",
        coverage="Fixture pages 2-3",
        first_page=2,
        ocr=True,
        ocr_engine="chandra",
        origin_url="https://example.org/scan",
        rights="Stated by the source: public domain.",
        attribution="T. Translator",
        corpus_id="scan-fixture",
        last_page=3,
    )
    return BookSpec(**{**base, **changes})


def test_chandra_pages_are_cleaned_bounded_and_cached(scan):
    from pramana.models import Chapter

    home, target, log = scan
    out = extract_pdf(target, home, spec())
    records = [Chapter.model_validate_json(x) for x in out.read_text().splitlines()]
    assert [r.location.chapter for r in records] == ["pdf-page-0002", "pdf-page-0003"]
    text = records[0].text
    assert "संन्यस्य" in text and "2. Let the wise man give up all works" in text
    assert "#" not in text and "**" not in text and "img.png" not in text
    assert records[0].source.url.unicode_string() == "https://example.org/scan"
    assert records[0].corpus_id == "scan-fixture" and records[0].source.local_path is None
    assert log.read_text().count("run") == 1  # pages 2-3 in one batch; 1 and 4 skipped
    extract_pdf(target, home, spec())
    assert log.read_text().count("run") == 1  # resumed entirely from the page cache
    report = json.loads((out.parent / "coverage.json").read_text())
    assert report["configuration"]["tools"]["engine"] == "chandra"


def test_devanagari_lines_can_be_left_out(scan):
    from pramana.models import Chapter

    home, target, _ = scan
    out = extract_pdf(target, home, spec(keep_devanagari=False))
    first = Chapter.model_validate_json(out.read_text().splitlines()[0])
    assert "संन्यस्य" not in first.text and "Let the wise man" in first.text


def test_markdown_cleanup_and_missing_tool(scan, monkeypatch):
    assert (
        clean_markdown("## Title\n**bold** and _ital_ text ![x](y)") == "Title\nbold and ital text "
    )
    home, target, _ = scan
    monkeypatch.setenv("PATH", str(Path(shutil.which("pdftoppm")).parent))
    with pytest.raises(PramanaError, match="uv tool install"):
        extract_pdf(target, home, spec(id="other"))


def test_public_scan_must_match_its_pin(tmp_path, monkeypatch):
    home = tmp_path / "home"
    wrong = tmp_path / "wrong.pdf"
    wrong.write_bytes(b"%PDF-1.4 not the reviewed scan")
    with pytest.raises(PramanaError, match="differs from the reviewed scan"):
        pdf.acquire_public(home, "vivekachudamani", wrong)


def test_verse_runs_math_and_marginalia(scan, monkeypatch):
    from pramana.ingestion.pdf import clean_text

    monkeypatch.setitem(pdf.MARGINALIA, "scan-fixture", ("v<sub>2</sub> {",))
    raw = (
        "v<sub>2</sub> { [ Note ends. ] सर्वदा स्थापनं बुद्धेः ।\n\n"
        "न, तत्समाधानमित्युक्तं न तु चित्तस्य बाधनम् ॥२६॥ 26. Not the mere thought.\n\n"
        "an impulse of मोह or blind attachment; briefly, $X + \\text{mind}$ . Vedanta."
    )
    text = clean_text(raw, spec(keep_devanagari=False))
    assert text == (
        "[ Note ends. ]\n\n26. Not the mere thought.\n\n"
        "an impulse of मोह or blind attachment; briefly, X + mind. Vedanta."
    )


def test_newer_cleanup_recomputes_cached_text_without_ocr(scan):
    from pramana.models import Chapter

    home, target, log = scan
    out = extract_pdf(target, home, spec())
    page = next(out.parent.glob("pages/0002.json"))
    data = json.loads(page.read_text())
    stale = {**data, "text": "stale text", "cleanup": 1}
    page.write_text(json.dumps(stale))
    out = extract_pdf(target, home, spec())
    first = Chapter.model_validate_json(out.read_text().splitlines()[0])
    assert "stale" not in first.text and "Let the wise man" in first.text
    assert json.loads(page.read_text())["cleanup"] == pdf.CHANDRA_CLEANUP
    assert log.read_text().count("run") == 1  # raw OCR reused; Chandra not run again
