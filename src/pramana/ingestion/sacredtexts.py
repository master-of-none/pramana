"""Generic adapter for Sacred Texts plain-text distributions (`NAME.txt.gz`).

Each archive repeats one header line before every HTML page; section k is page file
k-1. Committed manifests in `sacredtexts/` (built by scripts/build_sacredtexts_manifests.py)
select the pages and map them to works and printed divisions. Text spelling is preserved.
"""

import gzip
import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

import httpx

from pramana.errors import PramanaError
from pramana.models import Chapter, Location, Note, PageMark, Source

MANIFESTS = Path(__file__).with_name("sacredtexts")
# Note markers: [*1], [*1b], [*], [**], [***], [*+], [*++], [* section]; footnotes: ^12:1,
# ^xlvi:2, ^40:*. Symbol markers without a matching footnote are removed as markup.
REF = re.compile(r"\[p\.\s*([^\]]+)\]|\[\*(\d+[a-z]?|\*{0,2}|\+\+?| section)\]")
NOTE = re.compile(r"(?m)^\^([0-9ivxlc]+):(\d+[a-z]?|\*|\+\+?)\s*")


def books() -> dict[str, dict]:
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(MANIFESTS.glob("*.json"))
    }


def _strip(raw: str):
    parts, pages, refs, length, cursor = [], [], {}, 0, 0
    for match in REF.finditer(raw):
        segment = raw[cursor : match.start()]
        parts.append(segment)
        length += len(segment)
        if match[1]:
            pages.append((length, match[1].strip()))
        else:
            refs.setdefault(match[2], []).append(length)
        cursor = match.end()
    parts.append(raw[cursor:])
    text = "".join(parts)
    leading = len(text) - len(text.lstrip())
    text = text.strip()

    def clamp(offset):
        return max(0, min(len(text), offset - leading))

    return (
        text,
        [(clamp(o), label) for o, label in pages],
        {k: [clamp(o) for o in v] for k, v in refs.items()},
    )


def parse_section(section: str, page: dict, manifest: dict, source: Source) -> Chapter:
    body, _, footnotes = section.partition("\nFootnotes\n")
    text, pages, refs = _strip(body)
    if not text.strip():
        raise PramanaError(f"Empty page {page['file']} in {manifest['id']}; source changed.")
    starts = list(NOTE.finditer(footnotes))
    notes = []
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(footnotes)
        anchors = refs.get(m[2], [])
        note_id = f"{m[1]}:{m[2]}"
        if any(n.id == note_id for n in notes):
            note_id += f"#{i}"  # The source repeats some page-qualified labels.
        notes.append(
            Note(
                id=note_id,
                text=re.sub(r"\s+", " ", footnotes[m.end() : end]).strip() or "(empty note)",
                anchor_offset=anchors.pop(0) if anchors else None,
            )
        )
    marks, last = [], -1
    for offset, label in pages:
        # Consecutive markers before any text (e.g. blank plates) collapse to the last one.
        if marks and offset == last:
            marks[-1] = PageMark(offset=offset, label=label)
        else:
            marks.append(PageMark(offset=offset, label=label))
        last = offset
    return Chapter(
        corpus_id=f"sacred-texts-{manifest['id']}",
        document_id=page["document_id"],
        document=page["document"],
        edition=manifest["edition"],
        translator=manifest["translator"],
        author=manifest["author"],
        content_type=page["content_type"],
        language="en",
        location=Location(book=page["book"], chapter=page["chapter"], sections=[page["label"]]),
        source=source,
        text=text,
        pages=marks,
        notes=notes,
    )


def acquire(home: Path, book: str, archive: Path | None = None, *, offline: bool = False) -> Path:
    manifests = books()
    if book not in manifests:
        raise PramanaError(f"Unknown Sacred Texts book {book!r}; choose from {sorted(manifests)}.")
    manifest = manifests[book]
    root = home / "corpora" / f"sacred-texts-{book}"
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"{book}.txt.gz"
    if archive:
        if archive.resolve() != target.resolve():
            shutil.copyfile(archive, target)
    elif not target.exists():
        if offline:
            raise PramanaError(f"Corpus cache missing. Supply --archive /path/to/{book}.txt.gz.")
        try:
            response = httpx.get(
                manifest["archive_url"],
                follow_redirects=True,
                timeout=60,
                headers={"User-Agent": "Pramana/0.1 (explicit corpus download)"},
            )
            response.raise_for_status()
            gzip.decompress(response.content)  # A challenge/error page must not be cached.
            temporary = target.with_suffix(".tmp")
            temporary.write_bytes(response.content)
            temporary.replace(target)
        except (httpx.HTTPError, OSError, EOFError) as exc:
            raise PramanaError(
                f"Source download failed ({type(exc).__name__}). Download "
                f"{manifest['archive_url']} in a browser, then pass --archive PATH."
            ) from exc
    raw = target.read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    receipt = root / "receipt.json"
    previous = json.loads(receipt.read_text()) if receipt.exists() else {}
    retrieved = (
        previous["retrieved_at"]
        if previous.get("checksum") == checksum
        else datetime.now(UTC).isoformat()
    )
    try:
        decoded = gzip.decompress(raw).decode("utf-8").replace("\r\n", "\n")
    except (OSError, EOFError, UnicodeDecodeError) as exc:
        raise PramanaError(f"Not a UTF-8 gzip archive; supply the original {book}.txt.gz.") from exc
    sections = decoded.split(manifest["header"])
    if len(sections) != manifest["sections"]:
        raise PramanaError(
            f"{book}.txt.gz has {len(sections)} sections, expected {manifest['sections']}; "
            "the source structure changed."
        )
    attribution = (
        f"{manifest['translator']}; digitized by Sacred Texts. Title page: {manifest['title_url']}"
    )
    records = []
    for page in manifest["pages"]:
        source = Source(
            url=page["url"],
            retrieved_at=retrieved,
            checksum=checksum,
            rights=manifest["rights"],
            attribution=attribution,
        )
        records.append(parse_section(sections[page["section"]], page, manifest, source))
    # Publish normalized records only after the complete manifest validates.
    output = root / "chapters.jsonl"
    temporary = output.with_suffix(".tmp")
    temporary.write_text("\n".join(c.model_dump_json() for c in records) + "\n", encoding="utf-8")
    temporary.replace(output)
    receipt.write_text(
        json.dumps(
            {
                "archive_url": manifest["archive_url"],
                "retrieved_at": retrieved,
                "checksum": checksum,
                "rights": manifest["rights"],
                "attribution": attribution,
                "pages": manifest["pages"],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return output
