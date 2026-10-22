# Book-aware chat verification — 14 October 2026

Local environment: macOS arm64, Python 3.12.15, Node 26.11.1. The
[historical v0.1 verification](verification-baseline-v0.1.md) is retained separately.

## Local library and extraction

| Private edition                         | Physical pages | Extracted | Blank | Questionable | Indexed page records |
| --------------------------------------- | -------------: | --------: | ----: | -----------: | -------------------: |
| Chinmayananda, Holy Geeta               |          1,358 |     1,357 |     0 |            1 |                1,357 |
| Shankara Gita / Alladi Mahadeva Sastry  |            538 |       534 |     0 |            4 |                  522 |
| Taittiriya Book II / A. Mahadeva Sastri |            324 |       315 |     7 |            2 |                  308 |

Quality categories describe all physical pages; indexing separately excludes front
matter, short/blank pages, and the Taittiriya contents insert at pages 10–16.
One questionable Shankara page (physical page 27) remains indexed. Quality flags
are extraction heuristics, not editorial certification. All originals were moved
to `.pramana/sources/pdfs/` with SHA-256 checks before/after preservation. The saved
files were checked again against their acquisition/coverage records. Repeated
imports reported **zero changed pages for all three editions**.

Together with Wilson's 126 chapters / 587 passages, the prepared library contains
**2,313 chapter/page records and 3,367 passages**. Index schema 2 records the pinned
BGE revision and existing 384/448/48 chunk settings. Offline rebuild/search uses
local weights. Every stored passage was checked against its exact canonical text
slice, token limit, citation origin, and commentary attribution.

Representative source review included PDF title pages; English extraction from
both Gita editions; Taittiriya physical pages 1–6 rendered for scan/title/coverage
inspection; and physical page 50 rendered to confirm the knowledge/liberation
passage against OCR. Additional OCR samples at pages 50, 100, 200, and 300 were
inspected. This is sample review, **not a correction of every page**. OCR can retain
broken words, Sanskrit rendered as Latin noise, page headings, punctuation errors,
and footnotes mixed into the main flow. Physical PDF pages are retained internally;
no textual chapter/verse mapping is asserted. See [the PDF guide](../guides/pdf-ingestion.md).

## Checks

- Locked dependency synchronization with the prepared local cache: passed.
- Ruff lint/format checks and **61 deterministic tests**: passed. These use fake
  embeddings/providers, synthetic PDFs, and mocked OCR without books or services.
- **Two actual embedding-model tests** with offline flags: passed, including all
  126 manifest chapters and all 3,367 stored passage/citation offsets.
- TypeScript checking and Vite production build: passed; fonts/assets need no
  external web service.
- Source distribution/wheel built after frontend compilation; packaged assets
  matched the build byte-for-byte. Neither package contains PDFs, private full
  text, library databases, or model weights.
- Installed wheel checked from `/private/tmp`: compiled homepage/assets, empty
  library status, chat/search setup errors, and missing context behavior passed.
  This local isolated-wheel check reused prepared dependencies. A completely fresh
  dependency resolution was not repeated; CI now installs wheel dependencies in
  a separate environment before the same check.
- The new GitHub workflow has **not been run for these uncommitted changes**.
  The successful historical CI run remains linked in the roadmap.

## Retrieval and answers

The existing 20-question chapter benchmark was migrated to explicit source
identities and rerun, filtered to Wilson's exact edition:

| Method  | Recall@10 | MRR@10 |
| ------- | --------: | -----: |
| Lexical |    95.00% | 0.7583 |
| Dense   |   100.00% | 0.8026 |
| Hybrid  |   100.00% | 0.8306 |

This is an initial engineering benchmark. Added books change global FTS statistics;
these differences from the historical run do not demonstrate tuned retrieval gains.
The benchmark does not score passage support or answer quality. Source identities,
checksums, index configuration and per-question results are in
[results.json](../../benchmarks/results.json).

All eight real-model requests completed with expected status and source membership,
but the comparison answer contains a documented objection/reply interpretation error.
These structural checks must not be described as eight factually correct answers.
Real local-answer diagnostics and interpretation review are recorded in
[chat validation](chat-validation.md). Full answers/evidence remain private under
`.pramana/chat-smoke.json`; published question metadata contains no private book text.

## Browser workflow

A deterministic fixture server (`uv run python tests/manual_chat_server.py`) was
used to check suggested questions, follow-ups, Enter/Shift+Enter, focus behavior,
Unicode including supplementary characters, answer copying, pending/Stop, model
failure/retry, reload persistence, interrupted reload recovery, and reset followed
by reload. Desktop and 390 × 844 mobile layouts had no horizontal overflow; the
composer remained visible. No source controls or hidden provenance fields appeared
in the rendered conversation. Observed browser console warnings/errors: none.
These are local browser checks; automated browser CI remains roadmap work.

The actual Ollama model also answered the Wilson rain/Govarddhana question through
the final web interface. The answer survived reload and displayed without citation
markers or source metadata. Desktop and mobile screenshots were saved; the
viewport override was reset. Temporary preview servers are stopped after checking.
Start the prepared app with `uv run pramana serve` and open
[localhost:8000](http://127.0.0.1:8000).

![Verified chat homepage](../images/chat-home.jpg)

![Real local-model conversation](../images/chat.jpg)
