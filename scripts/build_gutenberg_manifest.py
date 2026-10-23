"""Regenerate the committed Yoga Vasishtha manifest (explicit network use).

Run `uv run python scripts/build_gutenberg_manifest.py [DIR]`; with DIR, reads saved
`pg{N}.html` files instead of downloading. Pins each volume's SHA-256 and the chapter
counts per book observed with the adapter's own parser, for review before committing.
"""

import hashlib
import json
import sys
import time
from pathlib import Path

import httpx

from pramana.ingestion.gutenberg import MANIFESTS, parse_volume

# Book numbers follow the six prakaranas; the Nirvana book's two halves restart their
# chapter numbering, so they are books 6.1 and 6.2.
VOLUMES = [
    (71326, "Vol. 1", [("1", "I"), ("2", "II"), ("3", "III")]),
    (71063, "Vol. 2, Part 1", [("3", "III")]),
    (71064, "Vol. 2, Part 2", [("4", "IV"), ("5", "V")]),
    (71095, "Vol. 3, Part 1", [("5", "V")]),
    (46531, "Vol. 3, Part 2", [("6.1", "VI")]),
    (71248, "Vol. 4, Part 1", [("6.2", "VI")]),
    (71249, "Vol. 4, Part 2", [("6.2", "VI")]),
]


def main():
    saved = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    volumes = []
    with httpx.Client(follow_redirects=True, timeout=120) as client:
        for ebook, label, books in VOLUMES:
            url = f"https://www.gutenberg.org/cache/epub/{ebook}/pg{ebook}-images.html"
            if saved:
                raw = (saved / f"h{ebook}.html").read_bytes()
            else:
                raw = client.get(url).content
                time.sleep(1)
            volume = {
                "ebook": ebook,
                "label": label,
                "url": url,
                "page_url": f"https://www.gutenberg.org/ebooks/{ebook}",
                "sha256": hashlib.sha256(raw).hexdigest(),
                "books": [{"book": b, "printed": p} for b, p in books],
            }
            counts = {}
            for chapter in parse_volume(raw.decode("utf-8"), volume):
                counts[chapter["book"]] = counts.get(chapter["book"], 0) + 1
            for b in volume["books"]:
                b["chapters"] = counts.get(b["book"], 0)
            print(ebook, label, counts)
            volumes.append(volume)
    manifest = {
        "id": "yoga-vasistha-mitra",
        "document_id": "yoga-vasistha-mitra",
        "document": "Yoga Vasishtha Maharamayana",
        "translator": "Vihari-Lala Mitra",
        "author": "",
        "edition": (
            "Mitra translation, 1891-1899 (Low Price Publications reprint as transcribed); "
            "attributed to Valmiki by this edition · Project Gutenberg HTML"
        ),
        "content_type": "translation",
        "rights": (
            'Stated by the source: Project Gutenberg eBook "for the use of anyone anywhere in '
            "the United States and most other parts of the world at no cost and with almost no "
            'restrictions whatsoever"; outside the US, check local laws. Project Gutenberg is '
            "a trademark; this record keeps only the public-domain text."
        ),
        "attribution": (
            "Vihari-Lala Mitra (translator); transcribed by Project Gutenberg volunteers."
        ),
        "volumes": volumes,
    }
    MANIFESTS.mkdir(exist_ok=True)
    path = MANIFESTS / "yoga-vasistha.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print("wrote", path)


if __name__ == "__main__":
    main()
