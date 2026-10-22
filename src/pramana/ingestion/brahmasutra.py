"""Adapter for Thibaut's Brahma Sutra Bhashya (SBE 34, 38) as distributed by Sacred Texts.

One chapter record per Sacred Texts page. Pages are keyed by adhyaya, pada and the
first sutra number printed on the page; that printed number must match the manifest.
"""

import hashlib
import json
import re
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from pramana.errors import PramanaError
from pramana.models import Chapter, Location, Note, PageMark, Source

INDEXES = {
    "SBE 34": "https://archive.sacred-texts.com/hin/sbe34/",
    "SBE 38": "https://archive.sacred-texts.com/hin/sbe38/",
}
EDITION = "Thibaut, SBE 34 (scan of 1904 printing) and 38 (1896) · Sacred Texts HTML"
RIGHTS = (
    "Stated by the source: public domain worldwide; the files may be used for any "
    "non-commercial purpose provided this notice of attribution is left intact."
)
ATTRIBUTION = (
    "Sankaracharya, commentary; English: George Thibaut, Sacred Books of the East 34 and 38, "
    "Clarendon Press. Scanned by Srinivasan Sriram (sripedia.org initiative); OCRed and "
    "proofed at Distributed Proofing (Juliet Sutherland, project manager); formatting and "
    "proofing at sacred-texts.com by J. B. Hare."
)
BLOCKS = ["p", "h1", "h2", "h3"]
HEADER = re.compile(r"tr\. by George Thibaut \[(1890|1896)\]")


def manifest() -> list[dict]:
    path = Path(__file__).with_name("brahmasutra-manifest.json")
    return json.loads(path.read_text(encoding="utf-8"))


def parse_page(html: str, entry: dict, source: Source) -> Chapter:
    """Body text after the edition header; page anchors and own footnotes are retained."""
    soup = BeautifulSoup(html, "html.parser")
    header = soup.find(lambda tag: tag.name == "p" and HEADER.search(tag.get_text()))
    if header is None:
        raise PramanaError(f"{entry['file']} is not a Thibaut SBE page; source format changed.")
    parts, pages, refs, length = [], [], {}, 0
    footnotes = None
    for element in header.find_all_next(BLOCKS):
        if element.name == "h3" and element.get_text(strip=True) == "Footnotes":
            footnotes = element
            break
        if element.find_parent("nav") or element.find_parent("center"):
            break
        page = next(
            (
                a
                for a in element.find_all("a", attrs={"name": re.compile(r"^page_")})
                if a.find_parent(BLOCKS) is element
            ),
            None,
        )
        if page is not None:
            # A page begins with the next paragraph, after its separator.
            pages.append((length + 2 if parts else 0, page["name"][5:]))
            continue
        for anchor in element.find_all("a", href=re.compile(r"^#fn_")):
            if anchor.find_parent(BLOCKS) is not element:
                continue
            # The marker offset is recorded; the marker itself is not canonical text.
            anchor.replace_with(f"\x00{anchor['href'][4:]}\x00")
        # Unclosed <p> tags nest; take only text whose nearest block is this element.
        own = "".join(
            str(t) for t in element.find_all(string=True) if t.find_parent(BLOCKS) is element
        )
        raw = re.sub(r"\s*(\x00[^\x00]+\x00)", r"\1", re.sub(r"\s+", " ", own)).strip()
        if raw.startswith("Next:"):
            break
        if not raw:
            continue
        if parts:
            parts.append("\n\n")
            length += 2
        for i, piece in enumerate(raw.split("\x00")):
            if i % 2:
                refs[piece] = length
            else:
                parts.append(piece)
                length += len(piece)
    text = "".join(parts)
    if len(text) < 80:
        raise PramanaError(f"Suspiciously short commentary body in {entry['file']}.")
    first = re.search(r"(?m)(?:^|\n\n)(\d+)\. ", text)
    if not first or first.group(1) != entry["sutra"]:
        raise PramanaError(
            f"{entry['file']} does not begin sutra {entry['sutra']}; source structure changed."
        )
    notes = []
    anchors = footnotes.find_all_next("a", attrs={"name": re.compile(r"^fn_")}) if footnotes else []
    for i, target in enumerate(anchors):
        key = target["name"][3:]
        link = target.find_next("a", href=True)
        # Footnotes for an earlier page are repeated here; keep only this page's own.
        if key not in refs or link is None:
            continue
        stop = anchors[i + 1] if i + 1 < len(anchors) else None
        # A note may continue outside its <P> (e.g. a quoted verse block).
        words = []
        for node in link.next_elements:
            if node is stop or getattr(node, "name", None) in {"center", "nav", "hr"}:
                break
            if isinstance(node, str) and node.find_parent("a") is not link:
                words.append(str(node))
        content = re.sub(r"\s+", " ", "".join(words)).strip()
        if content:
            notes.append(Note(id=link.get_text(strip=True), text=content, anchor_offset=refs[key]))
    return Chapter(
        corpus_id="brahma-sutra-thibaut",
        document_id="brahma-sutra-shankara-thibaut",
        document="Brahma Sutra Bhashya",
        edition=EDITION,
        translator="George Thibaut",
        author="Sankaracharya",
        content_type="mixed",
        language="en",
        location=Location(book=entry["adhyaya"], chapter=entry["pada"], sections=[entry["sutra"]]),
        source=source,
        text=text,
        pages=[PageMark(offset=min(offset, len(text)), label=label) for offset, label in pages],
        notes=notes,
    )


def _fetch(client: httpx.Client, url: str) -> bytes:
    response = client.get(url)
    response.raise_for_status()
    # A challenge or error page must never enter the cache.
    if not HEADER.search(response.text):
        raise PramanaError(f"{url} did not return a Thibaut SBE page.")
    return response.content


def acquire(
    home: Path, archive: Path | None = None, *, offline: bool = False, delay: float = 0.5
) -> Path:
    """Cache every manifest page (resumable), validate all, then publish JSONL atomically."""
    root = home / "corpora" / "brahma-sutra-thibaut"
    cache = root / "html"
    cache.mkdir(parents=True, exist_ok=True)
    entries = manifest()
    if archive:
        for entry in entries:
            source = archive / entry["file"]
            if not source.is_file():
                raise PramanaError(f"Archive directory is missing {entry['file']}.")
            if source.resolve() != (cache / entry["file"]).resolve():
                shutil.copyfile(source, cache / entry["file"])
    missing = [e for e in entries if not (cache / e["file"]).exists()]
    if missing and offline:
        raise PramanaError(
            f"{len(missing)} cached pages missing. Supply --archive DIR with the saved pages."
        )
    if missing:
        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=60,
                headers={"User-Agent": "Pramana/0.1 (explicit corpus download)"},
            ) as client:
                for entry in missing:
                    content = _fetch(client, entry["url"])
                    temporary = cache / (entry["file"] + ".tmp")
                    temporary.write_bytes(content)
                    temporary.replace(cache / entry["file"])
                    time.sleep(delay)
        except httpx.HTTPError as exc:
            raise PramanaError(
                f"Source download failed ({type(exc).__name__}); already cached pages are kept. "
                "Rerun `pramana corpus download --source brahma-sutra` to resume."
            ) from exc
    receipt_path = root / "receipt.json"
    previous = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    known = {p["file"]: p for p in previous.get("pages", [])}
    records, receipt_pages = [], []
    for entry in entries:
        raw = (cache / entry["file"]).read_bytes()
        checksum = hashlib.sha256(raw).hexdigest()
        prior = known.get(entry["file"])
        retrieved = (
            prior["retrieved_at"]
            if prior and prior["checksum"] == checksum
            else datetime.now(UTC).isoformat()
        )
        source = Source(
            url=entry["url"],
            retrieved_at=retrieved,
            checksum=checksum,
            rights=RIGHTS,
            attribution=ATTRIBUTION,
        )
        try:
            html = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PramanaError(f"{entry['file']} is not UTF-8; delete it and rerun.") from exc
        records.append(parse_page(html, entry, source))
        receipt_pages.append({**entry, "checksum": checksum, "retrieved_at": retrieved})
    # Publish normalized records only after every manifest page validates.
    output = root / "chapters.jsonl"
    temporary = output.with_suffix(".tmp")
    temporary.write_text("\n".join(c.model_dump_json() for c in records) + "\n", encoding="utf-8")
    temporary.replace(output)
    receipt = {"indexes": INDEXES, "rights": RIGHTS, "attribution": ATTRIBUTION}
    receipt_path.write_text(json.dumps({**receipt, "pages": receipt_pages}, indent=2))
    return output
