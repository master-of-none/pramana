"""Private, page-aware PDF acquisition. No source bytes are shipped in the package."""

import hashlib
import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from pramana.errors import PramanaError
from pramana.models import Chapter, Location, PageMark, Source, digest

PARSER = {"version": 1, "dpi": 200, "ocr_language": "eng", "psm": 3}


@dataclass(frozen=True)
class BookSpec:
    id: str
    filename: str
    title: str
    edition: str
    author: str
    translator: str
    coverage: str
    first_page: int = 1
    ocr: bool = False
    excluded_pages: tuple[int, ...] = ()


BOOKS = (
    BookSpec(
        "holy_geeta_chinmayananda",
        "Holy Geetapdf.pdf",
        "The Holy Geeta",
        "User-supplied English PDF; publication date unverified",
        "Swami Chinmayananda",
        "Swami Chinmayananda",
        "Bhagavad Gita translation and commentary; 1,358 PDF pages",
        2,
    ),
    BookSpec(
        "gita_shankara_sastry",
        "The Bhagavad-Gita, with the Commentary of Sri Sankaracharya.pdf",
        "The Bhagavad-Gita with the Commentary of Sri Sankaracharya",
        "Samata Books, seventh edition, 1977 (first published 1897)",
        "Sankaracharya",
        "Alladi Mahadeva Sastry",
        "Bhagavad Gita translation and commentary; 538 PDF pages",
        17,
    ),
    BookSpec(
        "taittiriya_anandavalli_sastri",
        "Taittiriya-upanishadbook.pdf",
        "The Taittiriya-Upanishad, Book II (Ananda-valli)",
        "G. T. A. Printing Works, Mysore, 1901; Book II, A: Brahmavidya Expounded",
        "Sankaracharya, Suresvaracharya and Sayana (Vidyaranya)",
        "A. Mahadeva Sastri",
        "Book II, Ananda-valli, A: Brahmavidya Expounded only; 324 PDF pages",
        6,
        True,
        (10, 11, 12, 13, 14, 15, 16),
    ),
)


def checksum(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def preserve_pdf(path: Path, home: Path) -> tuple[Path, str]:
    """Copy, verify and atomically publish before removing the input, even across volumes."""
    sha = checksum(path)
    destination = home / "sources" / "pdfs" / path.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if path.resolve() == destination.resolve():
        return destination, sha
    if destination.exists():
        if checksum(destination) != sha:
            raise PramanaError(
                f"Different PDF already exists at {destination}; originals retained."
            )
    else:
        temporary = destination.with_suffix(".pdf.partial")
        try:
            shutil.copyfile(path, temporary)
            if checksum(temporary) != sha:
                raise PramanaError("PDF copy checksum mismatch; original retained.")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    if checksum(destination) != sha:
        raise PramanaError("PDF destination checksum mismatch; original retained.")
    path.unlink()
    return destination, sha


def ocr_tools() -> dict[str, str]:
    tools = {name: shutil.which(name) for name in ("pdftoppm", "tesseract")}
    missing = [name for name, value in tools.items() if not value]
    if missing:
        raise PramanaError(
            f"Local OCR requires {', '.join(missing)}. macOS: brew install poppler tesseract; "
            "Debian/Ubuntu: apt install poppler-utils tesseract-ocr tesseract-ocr-eng. "
            "Then repeat pramana corpus import-books. No model or tool is downloaded implicitly."
        )
    return tools


def ocr_page(path: Path, number: int, tools: dict[str, str]) -> dict:
    with TemporaryDirectory(prefix="pramana-ocr-") as directory:
        base = Path(directory) / "page"
        try:
            subprocess.run(
                [
                    tools["pdftoppm"],
                    "-f",
                    str(number),
                    "-l",
                    str(number),
                    "-singlefile",
                    "-r",
                    str(PARSER["dpi"]),
                    "-gray",
                    str(path),
                    str(base),
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
            raster = base.with_suffix(".pgm").read_bytes()
            header = re.match(rb"P5\s+(\d+)\s+(\d+)\s+255\s", raster)
            if not header:
                raise PramanaError("Poppler returned an unsupported grayscale raster.")
            pixels = raster[header.end() :]
            ink = pixels.translate(bytes(1 if n < 180 else 0 for n in range(256))).count(1)
            ink /= max(len(pixels), 1)
            subprocess.run(
                [
                    tools["tesseract"],
                    str(base.with_suffix(".pgm")),
                    str(base),
                    "-l",
                    PARSER["ocr_language"],
                    "--psm",
                    str(PARSER["psm"]),
                    "txt",
                    "tsv",
                ],
                check=True,
                capture_output=True,
                timeout=120,
                env={**os.environ, "OMP_THREAD_LIMIT": "1"},
            )
        except (subprocess.SubprocessError, OSError) as exc:
            raise PramanaError(
                f"OCR failed on PDF page {number}; repeat to resume cached pages."
            ) from exc
        confidences = []
        for line in base.with_suffix(".tsv").read_text().splitlines()[1:]:
            fields = line.split("\t")
            if len(fields) >= 12 and fields[11].strip() and float(fields[10]) >= 0:
                confidences.append(float(fields[10]))
        return {
            "raw": base.with_suffix(".txt").read_text(encoding="utf-8"),
            "ocr_mean_confidence": sum(confidences) / len(confidences) if confidences else 0,
            "ink_fraction": ink,
        }


def clean_text(raw: str, spec: BookSpec) -> str:
    """Canonical extraction; raw text is retained separately. No speculative OCR word repair."""
    lines = raw.replace("\x00", "").replace("\u00ad", "").splitlines()
    cleaned = []
    for i, line in enumerate(lines):
        line = line.strip()
        if re.fullmatch(r"Holy Geeta by Swami Chinmayananda", line, re.I):
            continue
        if (i < 6 or i >= len(lines) - 4) and re.fullmatch(r"\d+", line):
            continue
        # Margin headings in the noisy Shankara text are retained in raw extraction.
        if (
            spec.id == "gita_shankara_sastry"
            and i < 2
            and re.search(r"(?:YOGA|ARJUNA|BHAGAVAD|DISCOURSE).*\d+\s*$", line)
        ):
            continue
        cleaned.append(line)
    text = "\n".join(cleaned)
    text = re.sub(r"(?<=[a-z])-\n(?=[a-z])", "", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def page_quality(text: str, details: dict) -> tuple[str, list[str]]:
    words = re.findall(r"[A-Za-z]{2,}", text)
    reasons = []
    if not text:
        if details.get("ink_fraction", 0) > 0.004:
            return "questionable", ["Visible ink but no recognized text"]
        return "blank", []
    if len(words) < 15:
        reasons.append("Little recognized English text")
    if details.get("ocr_mean_confidence", 100) < 65:
        reasons.append("Low OCR word confidence (not factual confidence)")
    letters = sum(c.isalpha() for c in text)
    if letters / max(len(text), 1) < 0.55:
        reasons.append("High non-letter content; inspect Sanskrit/OCR artifacts")
    return ("questionable" if reasons else "extracted"), reasons


def extract_pdf(
    path: Path,
    home: Path,
    spec: BookSpec,
    *,
    workers: int = 2,
    progress: Callable[[str], None] | None = None,
) -> Path:
    """Resume extraction by checksum/configuration; publish records only after all pages succeed."""
    home = home.resolve()
    path = path.resolve()
    if not path.is_relative_to(home):
        raise PramanaError("Move the original into PRAMANA_HOME/sources/pdfs before extraction.")
    sha = checksum(path)
    tools = ocr_tools() if spec.ocr else {}
    tool_versions = {}
    if tools:
        for name, executable in tools.items():
            result = subprocess.run(
                [executable, "--version" if name == "tesseract" else "-v"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            tool_versions[name] = (result.stdout + result.stderr).splitlines()[0]
    import pypdf

    config = {**PARSER, "pypdf": pypdf.__version__, "tools": tool_versions, "book": asdict(spec)}
    cache = home / "extractions" / (sha + "-" + digest(json.dumps(config, sort_keys=True))[:16])
    cache.mkdir(parents=True, exist_ok=True)
    receipt_path = cache / "receipt.json"
    acquisition = home / "sources" / "acquisitions" / (sha + ".json")
    if not acquisition.exists():
        previous = [
            json.loads(p.read_text())["acquired_at"]
            for p in (home / "extractions").glob(sha + "-*/receipt.json")
        ]
        atomic_json(
            acquisition,
            {"acquired_at": min(previous) if previous else datetime.now(UTC).isoformat()},
        )
    if not receipt_path.exists():
        atomic_json(receipt_path, json.loads(acquisition.read_text()))
    acquired_at = json.loads(receipt_path.read_text())["acquired_at"]
    try:
        reader = PdfReader(path)
        count = len(reader.pages)
    except (PdfReadError, OSError, ValueError) as exc:
        raise PramanaError(
            "Cannot read PDF; verify the original is complete and unencrypted, "
            "then repeat import-books. Existing records were retained."
        ) from exc
    # PDF parsing stays sequential; only independent raster/OCR jobs run concurrently.
    extracted = {}
    if not spec.ocr:
        for index, page in enumerate(reader.pages):
            if not (cache / "pages" / f"{index + 1:04d}.json").exists():
                extracted[index] = page.extract_text() or ""

    def process(index):
        page_file = cache / "pages" / f"{index + 1:04d}.json"
        if page_file.exists():
            data = json.loads(page_file.read_text(encoding="utf-8"))
            if (
                data.get("page") != index + 1
                or not isinstance(data.get("raw"), str)
                or not isinstance(data.get("text"), str)
                or data.get("quality") not in {"blank", "extracted", "questionable"}
                or not isinstance(data.get("indexed"), bool)
            ):
                raise PramanaError(
                    f"Invalid extraction cache {page_file}; remove this page and retry."
                )
            return data
        details = ocr_page(path, index + 1, tools) if spec.ocr else {"raw": extracted[index]}
        text = clean_text(details["raw"], spec)
        quality, reasons = page_quality(text, details)
        data = {
            **details,
            "page": index + 1,
            "text": text,
            "quality": quality,
            "reasons": reasons,
            "indexed": index + 1 >= spec.first_page
            and index + 1 not in spec.excluded_pages
            and len(re.findall(r"[A-Za-z]{2,}", text)) >= 15,
        }
        atomic_json(page_file, data)
        return data

    pages = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 4))) as pool:
        for page in pool.map(process, range(count)):
            pages.append(page)
            if progress and (len(pages) % 20 == 0 or len(pages) == count):
                progress(f"{spec.id}: extracted {len(pages)}/{count} pages")
    if checksum(path) != sha:
        raise PramanaError(
            "PDF changed during extraction; repeat with a stable original. "
            "Previous records were retained."
        )
    source = Source(
        local_path=path.relative_to(home).as_posix(),
        checksum=sha,
        retrieved_at=acquired_at,
        rights="User-supplied private edition; redistribution permission unestablished. "
        "Keep original and derived text out of public distribution.",
        attribution=f"{spec.author}; English: {spec.translator}. {spec.edition}",
    )
    records = [
        Chapter(
            corpus_id="local_books",
            document_id=spec.id,
            document=spec.title,
            edition=spec.edition,
            author=spec.author,
            translator=spec.translator,
            language="en",
            content_type="mixed",
            source=source,
            location=Location(
                book=spec.coverage,
                chapter=f"pdf-page-{p['page']:04d}",
                sections=["Physical PDF page; textual chapter/verse not assigned"],
            ),
            pages=[PageMark(offset=0, label=str(p["page"]))],
            text=p["text"],
        )
        for p in pages
        if p["indexed"]
    ]
    if not records:
        raise PramanaError("No usable English pages extracted; inspect coverage and OCR setup.")
    report = {
        "document_id": spec.id,
        "source_checksum": sha,
        "source": source.model_dump(mode="json"),
        "coverage": spec.coverage,
        "configuration": config,
        "total_pages": count,
        "indexed_pages": len(records),
        "counts": {
            q: sum(p["quality"] == q for p in pages) for q in ("extracted", "blank", "questionable")
        },
        "limitations": [
            "Physical PDF pages, not verified printed page/chapter/verse references.",
            "Translations and commentary are inseparable and indexed as mixed.",
            "OCR quality flags are heuristics; English text needs editorial review.",
            "Canonical text is cleaned; offsets address it, raw extraction is retained.",
        ],
        "pages": [{k: v for k, v in p.items() if k not in {"text", "raw"}} for p in pages],
    }
    atomic_json(cache / "coverage.json", report)
    output = cache / "records.jsonl"
    temporary = output.with_suffix(".jsonl.tmp")
    temporary.write_text("\n".join(c.model_dump_json() for c in records) + "\n", encoding="utf-8")
    temporary.replace(output)
    atomic_json(
        home / "sources" / f"{spec.id}.json",
        {
            "pdf": source.local_path,
            "checksum": sha,
            "records": output.relative_to(home).as_posix(),
            "coverage_report": (cache / "coverage.json").relative_to(home).as_posix(),
        },
    )
    return output


def import_books(home: Path, source_directory: Path, progress=print) -> list[dict]:
    from pramana.corpus import Corpus

    home = home.resolve()
    # Check prerequisites before relocating any input.
    ocr_tools()
    results = []
    corpus = Corpus(home)
    for spec in BOOKS:
        original = source_directory / spec.filename
        saved = home / "sources" / "pdfs" / spec.filename
        if original.exists():
            saved, _ = preserve_pdf(original, home)
        elif not saved.exists():
            raise PramanaError(f"Missing {original}; place the PDF there and repeat import-books.")
        output = extract_pdf(saved, home, spec, progress=progress)
        changed = corpus.import_jsonl(output, replace_document=True)
        results.append(
            {
                "document_id": spec.id,
                "changed_pages": changed,
                "coverage_report": str(output.parent / "coverage.json"),
            }
        )
    return results
