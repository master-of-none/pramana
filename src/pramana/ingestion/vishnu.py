"""Adapter for the archive's Wilson 1840 distribution, not a Sanskrit verse edition."""

import gzip
import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from pramana.errors import PramanaError
from pramana.models import Chapter, Location, Note, PageMark, Source

BASE = "https://archive.sacred-texts.com/hin/vp/"
ARCHIVE_URL = BASE + "vp.txt.gz"
HEADER = "The Vishnu Purana, translated by Horace Hayman Wilson, [1840], at sacred-texts.com"
RIGHTS = "1840 translation: public domain in the US, as stated by the source."
ATTRIBUTION = "H. H. Wilson (1840); digitized by John Bruno Hare, Sacred Texts (2006)."
BOOKS = [
    (35, 57, {43}),
    (58, 74, {61}),
    (75, 92, set()),
    (93, 117, {100}),
    (118, 155, set()),
    (156, 163, set()),
]


def manifest() -> list[dict]:
    entries = []
    for book, (start, end, excluded) in enumerate(BOOKS, 1):
        files = [n for n in range(start, end + 1) if n not in excluded]
        entries.extend(
            {
                "book": str(book),
                "chapter": str(chapter),
                "file": f"vp{n:03}.htm",
                "section": n + 1,
                "url": BASE + f"vp{n:03}.htm",
            }
            for chapter, n in enumerate(files, 1)
        )
    return entries


def _strip_annotations(raw: str, initial_page: str | None = None):
    parts, pages, refs = [], [], {}
    length, cursor = 0, 0
    if initial_page:
        pages.append(PageMark(offset=0, label=initial_page))
    for match in re.finditer(r"\[p\.\s*([^\]]+)\]|\[\*(\d+)\]", raw):
        segment = raw[cursor : match.start()]
        parts.append(segment)
        length += len(segment)
        if match.group(1):
            pages.append(PageMark(offset=length, label=match.group(1).strip()))
        else:
            refs.setdefault(match.group(2), []).append(length)
        cursor = match.end()
    parts.append(raw[cursor:])
    text = "".join(parts)
    leading = len(text) - len(text.lstrip())
    text = text.strip()
    pages = [
        PageMark(offset=max(0, min(len(text), p.offset - leading)), label=p.label) for p in pages
    ]
    refs = {
        key: [max(0, min(len(text), val - leading)) for val in values]
        for key, values in refs.items()
    }
    return text, pages, refs


def parse_text_section(section: str, entry: dict, source: Source) -> Chapter:
    heading = re.search(r"(?m)^CHAP\. ([IVXLCDM]+)\.?\s*$", section)
    if not heading:
        raise PramanaError(f"Missing chapter heading in {entry['file']}; source format changed.")
    before = re.findall(r"\[p\.\s*([^\]]+)\]", section[: heading.start()])
    content = section[heading.end() :].lstrip()
    summary, separator, rest = content.partition("\n\n")
    if not separator:
        raise PramanaError(f"Missing chapter summary/body boundary in {entry['file']}.")
    body, _, footnotes = rest.partition("\nFootnotes\n")
    text, pages, refs = _strip_annotations(body, before[-1] if before else None)
    note_starts = list(re.finditer(r"(?m)^\^(\d+):(\d+)\s+", footnotes))
    notes = []
    for i, m in enumerate(note_starts):
        end = note_starts[i + 1].start() if i + 1 < len(note_starts) else len(footnotes)
        anchors = refs.get(m.group(2), [])
        notes.append(
            Note(
                id=f"{m.group(1)}:{m.group(2)}",
                text=footnotes[m.end() : end].strip(),
                anchor_offset=anchors.pop(0) if anchors else None,
            )
        )
    if len(text) < 80:
        raise PramanaError(f"Suspiciously short translation body in {entry['file']}.")
    return Chapter(
        corpus_id="vishnu-purana",
        document_id="vishnu-purana",
        document="Vishnu Purana",
        edition="Wilson 1840 · Sacred Texts plain-text distribution 2006",
        translator="H. H. Wilson",
        language="en",
        location=Location(book=entry["book"], chapter=entry["chapter"]),
        source=source,
        text=text,
        summary=summary.strip(),
        pages=pages,
        notes=notes,
    )


def parse_legacy_html(html: str, entry: dict, source: Source) -> Chapter:
    """Parse legacy HTML without folding accents; reuse the marker-aware text parser."""
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find(
        lambda tag: (
            tag.name in {"h2", "h3"}
            and re.fullmatch(r"CHAP\.\s*[IVXLCDM]+\.", tag.get_text(strip=True))
        )
    )
    if not heading:
        raise PramanaError("Expected a legacy Sacred Texts chapter HTML file.")
    out = [heading.get_text(), ""]
    # Include only paragraphs following the chapter heading; navigation is never ingested.
    for element in heading.find_all_next(["p", "h3"]):
        if element.name == "h3":
            if "Footnotes" in element.get_text():
                out.extend(["Footnotes", ""])
            else:
                break
        else:
            for anchor in element.find_all("a"):
                name = str(anchor.get("name", ""))
                href = str(anchor.get("href", ""))
                if name.startswith("page_"):
                    anchor.replace_with(f"[p. {name[5:]}]")
                elif href.startswith("#fn_"):
                    anchor.replace_with(f"[*{anchor.get_text(strip=True)}]")
                elif href.startswith("#fr_"):
                    anchor.replace_with("^" + anchor.get_text(strip=True) + " ")
            out.extend([element.get_text(), ""])
    chapter = parse_text_section("\n".join(out), entry, source)
    return chapter.model_copy(update={"edition": "Wilson 1840 · Sacred Texts Unicode HTML 2006"})


def acquire(home: Path, archive: Path | None = None, *, offline: bool = False) -> Path:
    root = home / "corpora" / "vishnu-purana"
    root.mkdir(parents=True, exist_ok=True)
    target = root / "vp.txt.gz"
    if archive:
        if archive.resolve() != target.resolve():
            shutil.copyfile(archive, target)
    elif not target.exists():
        if offline:
            raise PramanaError("Corpus cache missing. Supply --archive /path/to/vp.txt.gz.")
        try:
            response = httpx.get(
                ARCHIVE_URL,
                follow_redirects=True,
                timeout=60,
                headers={"User-Agent": "Pramana/0.1 (explicit corpus download)"},
            )
            response.raise_for_status()
            # A challenge/error page must never poison the cache.
            gzip.decompress(response.content)
            target.write_bytes(response.content)
        except (httpx.HTTPError, OSError, EOFError) as exc:
            raise PramanaError(
                f"Source download failed ({type(exc).__name__}). Open {BASE} in a browser, "
                "download ‘Text [Zipped]’, then run: "
                "pramana corpus download --archive /path/to/vp.txt.gz"
            ) from exc
    raw = target.read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    receipt = root / "receipt.json"
    if receipt.exists() and json.loads(receipt.read_text())["checksum"] == checksum:
        retrieved = json.loads(receipt.read_text())["retrieved_at"]
    else:
        retrieved = datetime.now(UTC).isoformat()
    try:
        decoded = gzip.decompress(raw).decode("utf-8").replace("\r\n", "\n")
    except (OSError, EOFError, UnicodeDecodeError) as exc:
        raise PramanaError(
            "Not a UTF-8 Sacred Texts gzip archive; supply the original vp.txt.gz."
        ) from exc
    sections = decoded.split(HEADER)
    records = []
    for entry in manifest():
        if entry["section"] >= len(sections):
            raise PramanaError("Archive is incomplete; expected all 126 chapters across six books.")
        source = Source(
            url=entry["url"],
            retrieved_at=retrieved,
            checksum=checksum,
            rights=RIGHTS,
            attribution=ATTRIBUTION,
        )
        records.append(parse_text_section(sections[entry["section"]], entry, source))
    # Publish normalized records only after the complete manifest validates.
    output = root / "chapters.jsonl"
    temporary = output.with_suffix(".tmp")
    temporary.write_text("\n".join(c.model_dump_json() for c in records) + "\n", encoding="utf-8")
    temporary.replace(output)
    receipt.write_text(
        json.dumps(
            {
                "archive_url": ARCHIVE_URL,
                "retrieved_at": retrieved,
                "checksum": checksum,
                "rights": RIGHTS,
                "attribution": ATTRIBUTION,
                "chapters": manifest(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return output
