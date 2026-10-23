# Building the library

Pramana never downloads texts implicitly. Each source is fetched by an explicit
`pramana corpus download --source NAME`, validated completely, and written to
`PRAMANA_HOME/corpora/<source>/chapters.jsonl` with a receipt (URLs, SHA-256,
acquisition time, rights statement). Import and index it afterwards:

```sh
uv run pramana corpus download --source advaita     # every Vedanta source, ~15 minutes
for f in .pramana/corpora/*/chapters.jsonl; do uv run pramana ingest "$f"; done
uv run pramana index
```

Re-running a download is safe: cached archives and pages are reused, interrupted
page downloads resume, and an unchanged source imports zero chapters. `--offline`
rebuilds from the cache only; `--archive PATH` imports a file or directory you saved
yourself (for one source at a time).

## Public-domain sources

| `--source` | Edition | Records | Rights statement (source title page) |
| --- | --- | ---: | --- |
| `brahma-sutra` | Śaṅkara's Brahma Sūtra commentary, tr. Thibaut, SBE 34 and 38 | 552 | public domain worldwide; non-commercial use with attribution |
| `sribhashya` | Rāmānuja's Śrībhāṣya, tr. Thibaut, SBE 48 | 571 | public domain worldwide; non-commercial use with notice |
| `shankara-works` | _Select Works of Sri Sankaracharya_, tr. Venkataramanan, 1921 | 8 | public domain in the US (before 1923) |
| `upanishads-1` | Upaniṣads Part 1, tr. Max Müller, SBE 1 | 222 | public domain (before 1923) |
| `upanishads-2` | Upaniṣads Part 2, tr. Max Müller, SBE 15 | 108 | public domain (before 1923) |
| `gita-swarupananda` | _Srimad-Bhagavad-Gita_, tr. and comm. Swarupananda, 1909 | 18 | public domain in the US (before 1923) |
| `minor-upanishads` | _Thirty Minor Upanishads_, tr. Narayanasvami Aiyar, 1914 | 30 | public domain in the US (before 1923) |
| `crest-jewel` | _The Crest-Jewel of Wisdom_ (Vivekacūḍāmaṇi) and other works attributed to Śaṅkara, tr. Charles Johnston, 1946 | 17 | public domain in the US (copyright not renewed); non-commercial use with attribution |
| `ashtavakra-gita` | _The Heart of Awareness: Ashtavakra Gita_, tr. John Richards, 1996 | 20 | dedicated to the public domain by the translator |
| `brahma-knowledge` | _Brahma-Knowledge_, L. D. Barnett, 1911 | 42 | public domain in the US (before 1923) |
| `vishnu-purana` | _Vishnu Purana_, tr. H. H. Wilson, 1840 | 126 | public domain in the US |
| `yoga-vasistha` | _Yoga-Vásishtha Mahárámáyana_, tr. Vihari-Lala Mitra, 1891–99 (7 Gutenberg volumes) | 673 | public domain in the US (Project Gutenberg) |

`advaita` fetches every source above except `vishnu-purana` (the default when
`--source` is omitted) and `yoga-vasistha`, which is **opt-in**: it is larger than
the rest of the library together and would dominate answers to general questions.
It gets its own Study category and chat scope (**Yoga Vāsiṣṭha**) when imported. Record counts were measured on 22 October 2026 and
change only if the source site changes; the parsers then fail rather than import a
partial edition. Rights statements are recorded as the source states them, not as
legal advice. Details, exclusions and provenance are in the
[source notices](../notices/sources.md).

Different editions of the same work (for example Max Müller's Taittirīya and
Mahadeva Sastri's Ānanda-valli) remain separate documents, and Śaṅkara's and
Rāmānuja's commentaries on the same sūtra stay distinct.

## Vivekacūḍāmaṇi (Madhavananda, 1921): OCR with Chandra

Swami Madhavananda's 1921 translation (Advaita Ashrama, Mayavati) survives as a scan on
[archive.org](https://archive.org/details/vivekachudamanio00sankrich), listed as not in
copyright. Its archive OCR is unusable, so Pramana re-OCRs the pinned PDF locally with
[Chandra OCR](https://github.com/datalab-to/chandra) on your GPU. Install it explicitly
(it downloads PyTorch and, on first use, the `datalab-to/chandra-ocr-2` weights; the
weights are licensed for personal and research use):

```sh
uv tool install "chandra-ocr[hf]"
uv run pramana corpus download --source vivekachudamani   # download, then OCR pages 9-260
uv run pramana ingest PATH-PRINTED-ABOVE
uv run pramana index
```

OCR runs in batches of 12 pages with one model load each; finished pages are cached,
so an interrupted run resumes. Pages 261–264 (index), 265 (errata, not applied) and
266 are excluded. Records are physical PDF pages, as for the private PDFs.

## Private PDF books

Three user-supplied PDFs (Chinmayananda's _Holy Geeta_, Alladi Mahadeva Sastry's
translation of Śaṅkara's Gītā commentary, and A. Mahadeva Sastri's Taittirīya
Ānanda-valli) can be added locally with `pramana corpus import-books`; see the
[PDF guide](pdf-ingestion.md). They are never distributed or uploaded.

## Your own texts

Any provenance-bearing JSONL in the [import format](../reference/import-format.md)
can be added with `pramana ingest PATH`.
