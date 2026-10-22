"""Regenerate the committed Sacred Texts plain-text manifests (explicit network use).

Run `uv run python scripts/build_sacredtexts_manifests.py`. Each manifest records the
archive URL, its repeated page header, the title-page rights statement, and the pages
included, grouped into works as the site's own index groups them. Curated choices
(excluded front matter, introductions, and the Hume page inserted into SBE 15) live
in CONFIG so they can be reviewed.
"""

import gzip
import html
import json
import re
import time
from collections import Counter
from pathlib import Path

import httpx

BASE = "https://archive.sacred-texts.com/hin/"
OUT = Path(__file__).parents[1] / "src/pramana/ingestion/sacredtexts"
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}
ORDINAL = {
    w: i
    for i, w in enumerate(
        "First Second Third Fourth Fifth Sixth Seventh Eighth Ninth Tenth Eleventh Twelfth "
        "Thirteenth Fourteenth Fifteenth Sixteenth Seventeenth Eighteenth".split(),
        1,
    )
}


def slug(text: str) -> str:
    import unicodedata

    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(c for c in folded if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", folded).strip("-")


def location(label: str) -> tuple[str, str]:
    """Printed divisions only; single-level divisions are book 1, chapter N."""
    if m := re.fullmatch(r"([IVX]+), (\d+)(?:, \d+)?", label):
        return str(ROMAN[m[1]]), m[2]
    if m := re.match(r"(?:Khanda|Adhy[âa]ya) ([IVX]+)$", label):
        return "1", str(ROMAN[m[1]])
    if m := re.match(r"(\w+) (?:Question|Prap[âa]thaka|Chapter)\b", label):
        return "1", str(ORDINAL[m[1]])
    return "1", "1"


UPANISHADS = {
    "Khândogya Upanishad": "Chandogya Upanishad",
    "Talavakâra or Kena-Upanishad": "Kena Upanishad",
    "Aitareya-Âranyaka": "Aitareya Aranyaka",
    "Kaushîtaki-Upanishad": "Kaushitaki Upanishad",
    "Vâgasaneyi-Samhitâ-Upanishad, sometimes called Îsâvâsya or Îsâ-Upanishad.": "Isa Upanishad",
    "Katha-Upanishad": "Katha Upanishad",
    "Mundaka Upanishad": "Mundaka Upanishad",
    "Taittirîyaka-Upanishad": "Taittiriya Upanishad",
    "Brihadâranyaka Upanishad": "Brihadaranyaka Upanishad",
    "Svetâsvatara Upanishad": "Svetasvatara Upanishad",
    "Prasña Upanishad": "Prasna Upanishad",
    "Maitrâyana Brâhmana Upanishad": "Maitrayana Upanishad",
}

CONFIG = {
    "wos": {
        "translator": "S. Venkataramanan",
        # Traditional attribution, as the edition presents it.
        "edition": (
            "Venkataramanan 1921, works attributed to Sankaracharya · Sacred Texts plain-text"
        ),
        "author": "Sankaracharya",
        "include": range(3, 11),
        "work": lambda group, label: label.rstrip("."),
        "content_type": lambda group, label: "translation",
    },
    "sbe01": {
        "translator": "F. Max Müller",
        "edition": "Max Müller, SBE 1 (1879) · Sacred Texts plain-text distribution",
        "author": "",
        "include": range(22, 244),
        "work": lambda group, label: UPANISHADS[group],
        "content_type": lambda group, label: "translation",
    },
    "sbe15": {
        "translator": "F. Max Müller",
        "edition": "Max Müller, SBE 15 (1884) · Sacred Texts plain-text distribution",
        "author": "",
        # Page 98 is a 1921 Hume translation inserted by the redactor: a different edition.
        "include": [n for n in range(10, 119) if n != 98],
        "work": lambda group, label: UPANISHADS[group],
        "content_type": lambda group, label: "translation",
    },
    "sbg": {
        "translator": "Swami Swarupananda",
        "edition": "Swarupananda 1909 · Sacred Texts plain-text distribution",
        "author": "Swami Swarupananda",
        "include": range(6, 24),
        "work": lambda group, label: "Bhagavad Gita",
        "content_type": lambda group, label: "mixed",
    },
    "tmu": {
        "translator": "K. Narayanasvami Aiyar",
        "edition": "Narayanasvami Aiyar 1914 · Sacred Texts plain-text distribution",
        "author": "",
        "include": range(3, 33),
        "work": lambda group, label: re.sub(r"^\d+\. | of [^ ]+$", "", label),
        "content_type": lambda group, label: "translation",
    },
    "brk": {
        "translator": "L. D. Barnett",
        "edition": "Barnett 1911 · Sacred Texts plain-text distribution",
        "author": "L. D. Barnett",
        "include": range(3, 45),
        "work": lambda group, label: "Brahma-Knowledge",
        # Part II contains Barnett's translations; the rest is his own exposition.
        "content_type": lambda group, label: (
            "translation" if group and group.startswith("Part II") else "commentary"
        ),
    },
}


def text_of(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(fragment))).strip()


def index_entries(page: str, book: str) -> list[tuple[str | None, str, str]]:
    entries, group, seen = [], None, set()
    pattern = rf'(?is)<h3[^>]*>(.*?)</h3>|href="({book}\d+\.htm)"[^>]*>(.*?)</a>'
    for m in re.finditer(pattern, page):
        if m[1] is not None:
            group = text_of(m[1])
        elif m[2] not in seen:
            seen.add(m[2])
            entries.append((group, m[2], text_of(m[3])))
    return entries


def sribhashya(client: httpx.Client):
    """SBE 48 (HTML only): pages grouped by pada; topic pages nest under their sutra."""
    index = client.get(f"{BASE}sbe48/index.htm").text
    pages, adhyaya, group, sutra = [], 0, None, None
    padas = {"First Pâda": "1", "Second Pâda": "2", "Third Pâda": "3", "Fourth Pâda": "4"}
    for pada_group, file, label in index_entries(index, "sbe48"):
        number = int(file[5:-4])
        if not 3 <= number <= 573:  # Title, contents, introduction and word index.
            continue
        if pada_group != group:
            adhyaya += pada_group == "First Pâda"
            group, sutra = pada_group, None
        entry = {
            "file": file,
            "adhyaya": str(adhyaya),
            "pada": padas[pada_group],
            "url": f"{BASE}sbe48/{file}",
        }
        if m := re.match(r"(?:\w+ P[âa]da: )?(\d+)\.", label):
            sutra = entry["sutra"] = m[1]
        else:
            entry["topic"] = label.rstrip(".")
            if sutra:
                entry["location_sutra"] = sutra
        pages.append(entry)
    path = OUT.parent / "sribhashya-manifest.json"
    path.write_text(json.dumps(pages, indent=2, ensure_ascii=False) + "\n")
    print("sbe48", len(pages), "pages")


def main():
    OUT.mkdir(exist_ok=True)
    headers = {"User-Agent": "Pramana/0.1 (manifest generation)"}
    with httpx.Client(follow_redirects=True, timeout=60, headers=headers) as client:
        for book, config in CONFIG.items():
            index = client.get(f"{BASE}{book}/index.htm").text
            entries = index_entries(index, book)
            title = text_of(client.get(f"{BASE}{book}/{entries[0][1]}").text)
            rights = re.search(
                r"This (?:text|file) is in the public domain[^.]*\.(?: [^.]*\.)?", title
            )
            archive = client.get(f"{BASE}{book}/{book}.txt.gz").content
            lines = gzip.decompress(archive).decode("utf-8").replace("\r\n", "\n").split("\n")
            header = Counter(line for line in lines if "sacred-texts.com" in line).most_common(1)
            time.sleep(1)
            pages = []
            for group, file, label in entries:
                number = int(file[len(book) : -4])
                if number not in config["include"]:
                    continue
                work = config["work"](group, label)
                book_no, chapter = (
                    location(label)
                    if work not in {"Brahma-Knowledge"}
                    else (
                        "2" if group and group.startswith("Part II") else "1",
                        str(number),
                    )
                )
                pages.append(
                    {
                        "file": file,
                        "section": number + 1,
                        "url": f"{BASE}{book}/{file}",
                        "document_id": f"{slug(work)}-{book}",
                        "document": work,
                        "book": book_no,
                        "chapter": chapter,
                        "label": label,
                        "content_type": config["content_type"](group, label),
                    }
                )
            keys = [(p["document_id"], p["book"], p["chapter"], p["label"]) for p in pages]
            assert len(set(keys)) == len(keys), f"duplicate identities in {book}"
            manifest = {
                "id": book,
                "archive_url": f"{BASE}{book}/{book}.txt.gz",
                "title_url": f"{BASE}{book}/{entries[0][1]}",
                "header": header[0][0].strip(),
                "sections": len(entries) + 1,
                "translator": config["translator"],
                "author": config["author"],
                "edition": config["edition"],
                "rights": "Stated by the source: " + rights[0] if rights else None,
                "pages": pages,
            }
            assert manifest["rights"], f"no rights statement found for {book}"
            path = OUT / f"{book}.json"
            path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
            print(book, len(pages), "pages", len({p["document_id"] for p in pages}), "works")
        sribhashya(client)


if __name__ == "__main__":
    main()
