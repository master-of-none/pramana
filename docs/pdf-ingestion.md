# Private PDF library

Install local tools explicitly, then run from the repository root:

```sh
# macOS
brew install poppler tesseract
# Debian/Ubuntu alternative:
# sudo apt install poppler-utils tesseract-ocr tesseract-ocr-eng
uv sync --locked
uv run pramana corpus import-books
uv run pramana index --rebuild
```

`import-books --source-directory /path/to/pdfs` accepts a different input folder.
It expects these filenames, or reuses originals already preserved in the library:

| Filename                                                          | Catalog identity and actual coverage                                                                                                                                                                          |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Holy Geetapdf.pdf`                                               | Swami Chinmayananda, _The Holy Geeta_: 1,358 pages, English translation/commentary. Publication date unverified.                                                                                              |
| `The Bhagavad-Gita, with the Commentary of Sri Sankaracharya.pdf` | Shankara commentary translated by Alladi Mahadeva Sastry; Samata Books, seventh edition 1977, first published 1897; 538 pages.                                                                                |
| `Taittiriya-upanishadbook.pdf`                                    | Commentaries of Sankaracharya, Suresvaracharya and Sayana, translated by A. Mahadeva Sastri; Mysore 1901; **Book II, Ananda-valli, A: Brahmavidya Expounded**, 324 pages. This is not the complete Upanishad. |

The importer copies an original to `PRAMANA_HOME/sources/pdfs/`, verifies its
SHA-256 before publishing, verifies again, and then removes the input. A conflicting
existing destination leaves the original intact. Original scans are never rewritten.
The default data root is `.pramana/`; set an absolute `PRAMANA_HOME` consistently
before import, indexing, evaluation, or serving if you want another location.
Do not put a custom data root inside a tracked directory without ignoring it.

## Extraction and resumption

Pypdf extracts the first two books' text layers. Poppler rasterizes the scanned
Taittiriya pages at 200 DPI; Tesseract recognizes English locally. No OCR service,
Sanskrit model, or implicit network download is used. OCR runs on two pages at a
time, with per-page subprocess timeouts. Repeating the command resumes cached pages.

`extractions/<source-sha256>-<configuration-hash>/` contains:

- `receipt.json`: stable acquisition timestamp.
- `pages/NNNN.json`: raw and canonical text, quality flags, and OCR diagnostics.
- `coverage.json`: every physical page, extraction status, reasons, and whether indexed.
- `records.jsonl`: validated, provenance-bearing records used for import.

The key includes source checksum, parser settings/version, Pypdf version, OCR tool
versions, and edition configuration. Different configurations get separate caches.
Complete records and coverage are published atomically after all pages finish;
a failed OCR attempt retains completed pages and any previous published records.
Imports validate before database writes and unchanged records are skipped. PDF
imports replace the corresponding document edition transactionally, removing pages
excluded by the new complete configuration while preserving other editions.
`PRAMANA_HOME/sources/<document-id>.json` points to the current coverage and records.

Canonical cleanup removes known repeating headers and margin page numbers,
normalizes extracted line wrapping, and joins explicit line-end hyphenation.
It preserves Unicode and does not guess corrections for broken words or noisy OCR.
Raw extraction is retained. Passage offsets refer to the **exact cleaned canonical
page text**, not PDF byte positions or coordinates. Physical pages are represented
as page records; textual chapter/verse references are deliberately unassigned.

Translations and commentary cannot reliably be separated in these PDFs, so their
records are explicitly `mixed`, with author, translator, and edition metadata.
Front matter before configured start pages is excluded (2, 17, and 6 respectively).
The Taittiriya contents insert at physical pages 10–16 is also excluded.
Pages with fewer than 15 recognized English words are retained in extraction but
excluded from search. Other questionable pages can be indexed and are flagged.

## Coverage and limitations

Coverage distinguishes extracted, blank, and questionable pages. OCR word confidence
and ink detection are heuristics about extraction, **not factual confidence**.
A blank flag means no recognized text and little detected ink; it is not an editorial
assessment. Existing noisy OCR is not automatically replaced. Sanskrit in scans
may appear as Latin gibberish in English OCR and affect retrieval. Headers,
footnotes, split words, and punctuation errors can remain. Review individual raw
pages and the original scan before making scholarly claims.

The local verification report records actual coverage and reviewed samples.
This importer does not claim complete editorial correction or chapter/verse alignment.

The originals and all derived full text are private local data. Redistribution
permission has not been established. Chinmaya Mission's published digital-content
policy reserves rights; see [source notices](sources.md). Code licensing does not
license the books.
