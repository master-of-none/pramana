"""Multi-volume Project Gutenberg editions from their HTML files, by committed manifest.

A chapter starts at a heading element (h1–h3) reading "CHAPTER …"; contents tables are
never headings, so front matter, contents and the translator's introduction before the
first chapter are excluded, as is the footnote section at the end. Records are numbered
by position within each book, because printed chapter numbers contain misprints (e.g.
"CHAPTER CV." between CXIV and CXVI); the printed heading is kept as the section label.
Each volume's SHA-256, book sequence and chapter counts are pinned in the manifest.
"""

import hashlib
import json
import re
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup, NavigableString

from pramana.errors import PramanaError
from pramana.models import Chapter, Location, Note, PageMark, Source

MANIFESTS = Path(__file__).with_name("gutenberg")
CHAPTER = re.compile(r"\bCHAPTER\s+([IVXLC]+)\b", re.I)
BOOK = re.compile(r"\bBOOK\s+([IVX]+)\b", re.I)
BLOCKS = ["p", "h3", "h4", "h5", "blockquote"]
ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def manifests() -> dict[str, dict]:
    return {
        m["id"]: m
        for m in (json.loads(p.read_text("utf-8")) for p in sorted(MANIFESTS.glob("*.json")))
    }


def roman(numeral: str) -> int:
    values = [ROMAN[c] for c in numeral.upper()]
    return sum(-v if i + 1 < len(values) and values[i + 1] > v else v for i, v in enumerate(values))


def _heading_text(tag) -> str:
    return re.sub(r"\s+", " ", tag.get_text(" ")).strip()


def parse_volume(html: str, volume: dict) -> list[dict]:
    """Chapters of one volume as dicts: book, position, printed heading, text, notes."""
    soup = BeautifulSoup(html, "html.parser")
    # Footnote bodies, keyed by their anchor id; removed so they never enter chapter text.
    footnotes: dict[str, str] = {}
    for target in soup.select('a[id^="Footnote_"]'):
        holder = target.find_parent(["p", "div"])
        if holder is None:
            continue
        label = target.get_text("", strip=True)
        text = re.sub(r"\s+", " ", holder.get_text("")).strip()
        footnotes[target["id"]] = text[len(label) :].strip() if text.startswith(label) else text
        holder.decompose()
    headings = []
    book = volume["books"][0]["book"]
    for tag in soup.find_all(["h1", "h2", "h3"]):
        text = _heading_text(tag)
        if b := BOOK.search(text):
            book = next((x["book"] for x in volume["books"] if x["printed"] == b[1].upper()), book)
        if CHAPTER.search(text):
            headings.append((tag, book, text))
        elif re.match(r"FOOTNOTES", text, re.I):
            headings.append((tag, None, text))  # Stop marker for the last chapter.
    chapters, counts = [], {}
    for i, (tag, book, text) in enumerate(headings):
        if book is None:
            continue
        stop = headings[i + 1][0] if i + 1 < len(headings) else None
        parts, notes, length, pages, pending = [], [], 0, [], []
        for element in tag.find_all_next():
            if element is stop:
                break
            if element.name not in BLOCKS or element.find_parent(BLOCKS):
                continue
            for anchor in element.select('a[href^="#Footnote_"]'):
                anchor.replace_with(NavigableString(f"\x00{anchor['href'][1:]}\x00"))
            # Printed page numbers ("[Pg 816]" spans) become page marks, not text.
            for span in element.select("span.pagenum"):
                label = re.sub(r"[\[\]]|Pg\s*", "", span.get_text("")).strip()
                span.replace_with(NavigableString(f"\x00PAGE:{label}\x00" if label else ""))
            for br in element.find_all("br"):
                br.replace_with(NavigableString(" "))
            # No separator: drop capitals are separate elements ("O" + "m" is "Om").
            raw = re.sub(r"\s+", " ", element.get_text("")).strip()
            # Some volumes print page numbers as bare "[816]": 404-982 in this edition,
            # while its unlinked footnote markers run 1-23. Numbers >= 30 are pages.
            raw = re.sub(
                r"\[(\d{2,4})\]",
                lambda m: f"\x00PAGE:{m[1]}\x00" if int(m[1]) >= 30 else m[0],
                raw,
            )
            raw = re.sub(r"\s*(\x00[^\x00]+\x00)", r"\1", raw).strip()
            if not raw:
                continue
            tokens = raw.split("\x00")
            if not "".join(tokens[0::2]).strip():
                # A paragraph that is only a page number marks the next paragraph.
                pending += [t[5:] for t in tokens[1::2] if t.startswith("PAGE:")]
                continue
            if parts:
                parts.append("\n\n")
                length += 2
            pages += [(length, label) for label in pending]
            pending = []
            for j, piece in enumerate(tokens):
                if j % 2 and piece.startswith("PAGE:"):
                    pages.append((length, piece[5:]))
                elif j % 2:
                    if piece in footnotes:
                        notes.append(
                            Note(
                                id=piece.removeprefix("Footnote_"),
                                text=footnotes[piece],
                                anchor_offset=length,
                            )
                        )
                else:
                    parts.append(piece)
                    length += len(piece)
        counts[book] = counts.get(book, 0) + 1
        # The printed heading opens the record; note offsets shift past it.
        shift = len(text) + 2
        chapters.append(
            {
                "book": book,
                "position": counts[book],
                "heading": text,
                "text": f"{text}\n\n{''.join(parts)}",
                "notes": [
                    n.model_copy(update={"anchor_offset": n.anchor_offset + shift}) for n in notes
                ],
                "pages": [(offset + shift, label) for offset, label in pages],
            }
        )
    expected = {x["book"]: x["chapters"] for x in volume["books"] if "chapters" in x}
    if expected and counts != expected:
        raise PramanaError(
            f"Volume {volume['ebook']}: expected chapters per book {expected}, found {counts}; "
            "the source structure changed."
        )
    return chapters


def acquire(home: Path, key: str, archive: Path | None = None, *, offline: bool = False) -> Path:
    """Fetch (or copy from --archive DIR) every volume, verify pins, parse all, publish."""
    found = manifests()
    if key not in found:
        raise PramanaError(f"Unknown Gutenberg edition {key!r}; choose from {sorted(found)}.")
    manifest = found[key]
    root = home / "corpora" / key
    cache = root / "html"
    cache.mkdir(parents=True, exist_ok=True)
    for volume in manifest["volumes"]:
        target = cache / f"pg{volume['ebook']}.html"
        if archive:
            source = archive / target.name
            if not source.is_file():
                raise PramanaError(f"Archive directory is missing {target.name}.")
            if source.resolve() != target.resolve():
                shutil.copyfile(source, target)
        pinned = volume["sha256"]
        if archive or (
            target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == pinned
        ):
            continue  # A supplied archive is verified below, never replaced by a download.
        if offline:
            raise PramanaError(f"{target.name} is missing or changed; supply --archive DIR.")
        try:
            # HTTP/1.1: Gutenberg's HTTP/2 endpoint has truncated large downloads.
            with httpx.Client(
                http2=False,
                follow_redirects=True,
                timeout=120,
                headers={"User-Agent": "Pramana/0.1 (explicit corpus download)"},
            ) as client:
                response = client.get(volume["url"])
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PramanaError(
                f"Download of {volume['url']} failed ({type(exc).__name__}); cached volumes "
                "are kept. Rerun to resume."
            ) from exc
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(response.content)
        temporary.replace(target)
        time.sleep(1)
    receipt_path = root / "receipt.json"
    previous = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    known = {v["ebook"]: v for v in previous.get("volumes", [])}
    records, receipt = [], []
    # Books continue across volumes (e.g. Utpatti in vol. 1 and 2): positions run on.
    offset: dict[str, int] = {}
    for volume in manifest["volumes"]:
        raw = (cache / f"pg{volume['ebook']}.html").read_bytes()
        checksum = hashlib.sha256(raw).hexdigest()
        if checksum != volume["sha256"]:
            raise PramanaError(
                f"pg{volume['ebook']}.html differs from the reviewed edition "
                f"(SHA-256 {checksum[:12]}…); it was not imported."
            )
        prior = known.get(volume["ebook"])
        retrieved = (
            prior["retrieved_at"]
            if prior and prior["checksum"] == checksum
            else datetime.now(UTC).isoformat()
        )
        source = Source(
            url=volume["page_url"],
            retrieved_at=retrieved,
            checksum=checksum,
            rights=manifest["rights"],
            attribution=manifest["attribution"],
        )
        chapters = parse_volume(raw.decode("utf-8"), volume)
        for chapter in chapters:
            records.append(
                Chapter(
                    corpus_id=key,
                    document_id=manifest["document_id"],
                    document=manifest["document"],
                    edition=manifest["edition"],
                    translator=manifest["translator"],
                    author=manifest["author"],
                    content_type=manifest["content_type"],
                    language="en",
                    location=Location(
                        book=chapter["book"],
                        chapter=str(offset.get(chapter["book"], 0) + chapter["position"]),
                        sections=[chapter["heading"]],
                    ),
                    source=source,
                    text=chapter["text"],
                    notes=chapter["notes"],
                    pages=[PageMark(offset=o, label=lab) for o, lab in chapter["pages"]],
                )
            )
        for book in {c["book"] for c in chapters}:
            offset[book] = offset.get(book, 0) + sum(c["book"] == book for c in chapters)
        receipt.append({"ebook": volume["ebook"], "checksum": checksum, "retrieved_at": retrieved})
    ids = [r.id for r in records]
    if len(set(ids)) != len(ids):
        raise PramanaError(f"{key}: duplicate chapter identities; the manifest needs review.")
    output = root / "chapters.jsonl"
    temporary = output.with_suffix(".tmp")
    temporary.write_text("\n".join(c.model_dump_json() for c in records) + "\n", encoding="utf-8")
    temporary.replace(output)
    receipt_path.write_text(
        json.dumps({"rights": manifest["rights"], "volumes": receipt}, indent=2)
    )
    return output
