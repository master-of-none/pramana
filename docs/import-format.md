# Structured chapter imports

One UTF-8 JSON object per line, one complete chapter per object. Blank lines are
ignored. Import with `pramana ingest /path/to/chapters.jsonl` or
`Corpus(home).import_jsonl(path)`. The entire input validates before database writes.
Unknown properties, empty text, missing provenance, invalid offsets, and duplicate
chapter identities within a file produce actionable line-numbered errors.

```json
{
  "corpus_id": "my-collection",
  "document_id": "my-text",
  "document": "Example Text",
  "edition": "Example edition 2026",
  "translator": "Original author (English)",
  "language": "en",
  "location": { "book": "1", "chapter": "1", "sections": [] },
  "source": {
    "url": "https://example.org/original",
    "retrieved_at": "2026-10-14T00:00:00Z",
    "checksum": "a7f8f9c06abed734f9f3af014a85b2f430a1e2c04ee6caf83b72c03692c2a34d",
    "rights": "Reuse terms for this source",
    "attribution": "Author and publisher"
  },
  "text": "The immutable chapter text.",
  "summary": "Optional editorial summary, not indexed.",
  "pages": [{ "offset": 0, "label": "1" }],
  "notes": [
    {
      "id": "1:1",
      "text": "Translator commentary, not indexed.",
      "anchor_offset": 4
    }
  ]
}
```

The checksum above is illustrative. Supply the actual SHA-256 of the acquired
source bytes, not a fabricated value. Provide exactly one origin: `source.url` as an HTTP(S) reference, or
`source.local_path` as a POSIX path relative to `PRAMANA_HOME` (for example,
`sources/pdfs/book.pdf`). Absolute paths and `..` traversal are rejected. `source.retrieved_at`, `rights`, and `attribution` document acquisition
and reuse. For an untranslated source, identify the original author in `translator`
and state that no translation was used.

`corpus_id` and `document_id` use letters, numbers, underscores, or hyphens.
`edition`, `translator`, `language`, `location.book`, and `location.chapter` are
required nonempty strings. `location.sections` optionally records deeper hierarchy.
Book/chapter labels can be nonnumeric, although the demo labels are numeric.

`summary`, `pages`, and `notes` are optional. Page offsets must be ordered and within
the chapter. Note IDs must be unique per chapter; a null anchor records an unlinked
note. Offsets are zero-based Python Unicode code-point positions in the exact
stored `text`; intervals are `[start, end)`. They are not UTF-8 byte positions or
JavaScript UTF-16 indices. Text is never accent-folded for storage or display.

Pramana hashes corpus/document identity, edition, language, and location to create
chapter IDs. Passage IDs also include the chapter text hash and character span.
Importing unchanged records is a no-op. Changing text or provenance updates that
chapter and invalidates the index. Different editions remain separate chapters.
Ordinary imports add/update chapters; they do not delete chapters omitted from a file.
The PDF adapter uses `Corpus.import_jsonl(path, replace_document=True)` to atomically
replace one complete document edition, removing omitted pages only in that edition.

Search filters include corpus ID, document ID, author, content type, book, chapter,
edition, language, and translator.
Optional `author` and `content_type` (`translation`, `commentary`, or `mixed`)
preserve commentary attribution. The default remains `translation`. PDF pages use
physical-page locations without inferred chapter/verse references. The main `text`
body is indexed for all content types. Footnotes and summaries remain available
through the chapter endpoint. The initial engine normalizes Latin diacritics for
keyword search; it does not perform general Sanskrit transliteration or map every
spelling variant (for example, `Visnu` and `Vishnu` are distinct spellings).
