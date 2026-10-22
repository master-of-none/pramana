"""Adapter for Thibaut's Brahma Sutra commentaries as distributed by Sacred Texts.

Two volumes: Sankara's commentary (SBE 34, 38) and Ramanuja's Sribhashya (SBE 48),
kept as separate documents. One chapter record per Sacred Texts page, keyed by
adhyaya, pada and printed sutra number; a page's first printed sutra number must
match its manifest entry. Ramanuja's topic pages within a sutra keep their title.
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
VOLUMES = {
    "shankara": {
        "manifest": "brahmasutra-manifest.json",
        "root": "brahma-sutra-thibaut",
        "source": "brahma-sutra",
        "identify": HEADER,
        "corpus_id": "brahma-sutra-thibaut",
        "document_id": "brahma-sutra-shankara-thibaut",
        "document": "Brahma Sutra Bhashya",
        "author": "Sankaracharya",
        "edition": EDITION,
        "rights": RIGHTS,
        "attribution": ATTRIBUTION,
        "indexes": [
            "https://archive.sacred-texts.com/hin/sbe34/",
            "https://archive.sacred-texts.com/hin/sbe38/",
        ],
    },
    "ramanuja": {
        "manifest": "sribhashya-manifest.json",
        "root": "sribhashya-thibaut",
        "source": "sribhashya",
        "identify": re.compile(r"commentary by Ramanuja, George Thibaut"),
        "corpus_id": "sribhashya-thibaut",
        "document_id": "brahma-sutra-ramanuja-thibaut",
        "document": "Sribhashya (Brahma Sutra commentary)",
        "author": "Ramanuja",
        "edition": "Thibaut, SBE 48 (1904) · Sacred Texts HTML",
        "rights": (
            "Stated by the source: public domain worldwide; this file may be used for any "
            "non-commercial purpose provided this notice is left intact."
        ),
        "attribution": (
            "Ramanuja, commentary; English: George Thibaut, Sacred Books of the East 48, "
            "Clarendon Press, 1904. Scanned by Srinivasan Sriram (sripedia.org initiative); "
            "OCRed and proofed at Distributed Proofing (Juliet Sutherland, project manager); "
            "formatting and proofreading at sacred-texts.com by J. B. Hare."
        ),
        "indexes": ["https://archive.sacred-texts.com/hin/sbe48/"],
    },
}


def manifest(volume: str = "shankara") -> list[dict]:
    path = Path(__file__).with_name(VOLUMES[volume]["manifest"])
    return json.loads(path.read_text(encoding="utf-8"))


def parse_page(html: str, entry: dict, source: Source, volume: str = "shankara") -> Chapter:
    """Body text after the edition header (or top navigation); anchors and own notes kept."""
    config = VOLUMES[volume]
    if not config["identify"].search(html):
        raise PramanaError(f"{entry['file']} is not a Thibaut SBE page; source format changed.")
    soup = BeautifulSoup(html, "html.parser")
    header = soup.find(lambda tag: tag.name == "p" and HEADER.search(tag.get_text()))
    header = header or soup.find("hr")
    if header is None:
        raise PramanaError(f"{entry['file']} has no recognisable body; source format changed.")
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
    first = re.search(r"(?m)(?:^|\n\n)(?:[A-Za-zâ ]+: )?(\d+)\. ", text)
    if entry.get("sutra") and (not first or first.group(1) != entry["sutra"]):
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
    sutra = entry.get("sutra") or entry.get("location_sutra")
    sections = [sutra] if sutra else []
    if entry.get("topic"):
        sections.append(entry["topic"])
    return Chapter(
        corpus_id=config["corpus_id"],
        document_id=config["document_id"],
        document=config["document"],
        edition=config["edition"],
        translator="George Thibaut",
        author=config["author"],
        content_type="mixed",
        language="en",
        location=Location(book=entry["adhyaya"], chapter=entry["pada"], sections=sections),
        source=source,
        text=text,
        pages=[PageMark(offset=min(offset, len(text)), label=label) for offset, label in pages],
        notes=notes,
    )


def _fetch(client: httpx.Client, url: str, identify: re.Pattern) -> bytes:
    response = client.get(url)
    response.raise_for_status()
    # A challenge or error page must never enter the cache.
    if not identify.search(response.text):
        raise PramanaError(f"{url} did not return a Thibaut SBE page.")
    return response.content


def acquire(
    home: Path,
    archive: Path | None = None,
    *,
    offline: bool = False,
    delay: float = 0.5,
    volume: str = "shankara",
) -> Path:
    """Cache every manifest page (resumable), validate all, then publish JSONL atomically."""
    config = VOLUMES[volume]
    root = home / "corpora" / config["root"]
    cache = root / "html"
    cache.mkdir(parents=True, exist_ok=True)
    entries = manifest(volume)
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
                    content = _fetch(client, entry["url"], config["identify"])
                    temporary = cache / (entry["file"] + ".tmp")
                    temporary.write_bytes(content)
                    temporary.replace(cache / entry["file"])
                    time.sleep(delay)
        except httpx.HTTPError as exc:
            raise PramanaError(
                f"Source download failed ({type(exc).__name__}); already cached pages are kept. "
                f"Rerun `pramana corpus download --source {config['source']}` to resume."
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
            rights=config["rights"],
            attribution=config["attribution"],
        )
        try:
            html = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PramanaError(f"{entry['file']} is not UTF-8; delete it and rerun.") from exc
        records.append(parse_page(html, entry, source, volume))
        receipt_pages.append({**entry, "checksum": checksum, "retrieved_at": retrieved})
    # Publish normalized records only after every manifest page validates.
    output = root / "chapters.jsonl"
    temporary = output.with_suffix(".tmp")
    temporary.write_text("\n".join(c.model_dump_json() for c in records) + "\n", encoding="utf-8")
    temporary.replace(output)
    receipt = {k: config[k] for k in ("indexes", "rights", "attribution")}
    receipt_path.write_text(json.dumps({**receipt, "pages": receipt_pages}, indent=2))
    return output
