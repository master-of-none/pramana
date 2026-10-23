"""Single plain-text editions (e.g. an archive.org text), described by committed manifests.

Each manifest in `textfiles/` pins the file's SHA-256, a rights sentence that must occur
in the text, and the expected chapter and verse counts, so a changed or wrong file fails
instead of importing. Cleanup is limited to removing exact running-header lines and
normalising line endings; the translator's front matter before chapter 1 is excluded.
"""

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

import httpx

from pramana.errors import PramanaError
from pramana.models import Chapter, Location, Source

MANIFESTS = Path(__file__).with_name("textfiles")


def manifests() -> dict[str, dict]:
    return {
        m["id"]: m
        for m in (json.loads(p.read_text("utf-8")) for p in sorted(MANIFESTS.glob("*.json")))
    }


def parse(text: str, manifest: dict, source: Source) -> list[Chapter]:
    if manifest["rights_quote"] not in text:
        raise PramanaError(f"{manifest['id']}: the expected rights statement is missing.")
    text = text.replace("\r\n", "\n")
    strip = set(manifest.get("strip_lines", []))
    text = "\n".join(line for line in text.split("\n") if line.strip() not in strip)
    headings = list(re.finditer(manifest["chapter_pattern"], text))
    numbers = [int(h[1]) for h in headings]
    if numbers != list(range(1, manifest["chapters"] + 1)):
        raise PramanaError(
            f"{manifest['id']}: expected chapters 1–{manifest['chapters']}, found {numbers}."
        )
    verses = re.findall(manifest["verse_pattern"], text)
    if len(verses) != manifest["verses"]:
        raise PramanaError(
            f"{manifest['id']}: expected {manifest['verses']} numbered verses, found {len(verses)}."
        )
    chapters = []
    for i, heading in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = re.sub(r"\n{3,}", "\n\n", text[heading.start() : end]).strip()
        chapters.append(
            Chapter(
                corpus_id=manifest["id"],
                document_id=manifest["document_id"],
                document=manifest["document"],
                edition=manifest["edition"],
                translator=manifest["translator"],
                author=manifest["author"],
                content_type=manifest["content_type"],
                language="en",
                location=Location(book="1", chapter=heading[1], sections=[heading[2].strip()]),
                source=source,
                text=body,
            )
        )
    return chapters


def acquire(home: Path, key: str, archive: Path | None = None, *, offline: bool = False) -> Path:
    found = manifests()
    if key not in found:
        raise PramanaError(f"Unknown text edition {key!r}; choose from {sorted(found)}.")
    manifest = found[key]
    root = home / "corpora" / key
    root.mkdir(parents=True, exist_ok=True)
    target = root / "source.txt"
    if archive:
        if archive.resolve() != target.resolve():
            shutil.copyfile(archive, target)
    elif not target.exists():
        if offline:
            raise PramanaError("Corpus cache missing. Supply --archive /path/to/the/text file.")
        try:
            response = httpx.get(
                manifest["url"],
                follow_redirects=True,
                timeout=60,
                headers={"User-Agent": "Pramana/0.1 (explicit corpus download)"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise PramanaError(
                f"Source download failed ({type(exc).__name__}). Download {manifest['url']} "
                "in a browser, then pass --archive PATH."
            ) from exc
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(response.content)
        temporary.replace(target)
    raw = target.read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    if checksum != manifest["sha256"]:
        raise PramanaError(
            f"{key}: the text differs from the reviewed edition (SHA-256 {checksum[:12]}…); "
            "it was not imported."
        )
    receipt_path = root / "receipt.json"
    previous = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    retrieved = (
        previous["retrieved_at"]
        if previous.get("checksum") == checksum
        else datetime.now(UTC).isoformat()
    )
    source = Source(
        url=manifest["item_url"],
        retrieved_at=retrieved,
        checksum=checksum,
        rights=manifest["rights"],
        attribution=manifest["attribution"],
    )
    try:
        records = parse(raw.decode("utf-8"), manifest, source)
    except UnicodeDecodeError as exc:
        raise PramanaError(f"{key}: the text is not UTF-8.") from exc
    output = root / "chapters.jsonl"
    temporary = output.with_suffix(".tmp")
    temporary.write_text("\n".join(c.model_dump_json() for c in records) + "\n", encoding="utf-8")
    temporary.replace(output)
    receipt = {"url": manifest["url"], "retrieved_at": retrieved, "checksum": checksum}
    receipt_path.write_text(json.dumps({**receipt, "rights": manifest["rights"]}, indent=2))
    return output
