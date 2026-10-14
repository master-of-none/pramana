# Working on Pramana

Pramana is a local book-aware chat app, Python library, CLI, and API. Retrieval
remains independently usable; an `Answerer` uses retrieved evidence through local
Ollama. Read [README.md](README.md), [quickstart](docs/quickstart.md), and
[ROADMAP.md](ROADMAP.md). The requested task determines scope; roadmap tasks guide
sequencing and do not authorize unrelated work.

## Architecture and commands

- `src/pramana/`: models, canonical text chunking, SQLite storage, embeddings,
  retrieval, `answering.py`, CLI, and FastAPI `api.py`.
- `src/pramana/ingestion/`: Wilson source adapter/manifest and private PDF extraction/OCR.
- `web/src/`: React/TypeScript chat; Vite builds into ignored `src/pramana/static/`.
- `tests/`: deterministic regressions, separate model tests, and a manual browser fixture.
- `scripts/`: installed-wheel and explicit local-chat checks.
- `benchmarks/`: source-aware chapter benchmark; `docs/`: guides, notices, verification.

Use Python **3.12**, `uv`, Node **22.12+**, and npm. Install with `uv sync --locked`
and `npm --prefix web ci`. Preserve `uv.lock` and `web/package-lock.json` consistency.
Build UI before packaging. Standard checks, verified from the repository root:

```sh
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run pytest
npm --prefix web run typecheck
npm --prefix web run build
uv build
```

For backend changes run Python checks; for UI changes run frontend checks and
verify desktop/mobile behavior. For parsing/index changes exercise offsets, repeated
imports, cache/failure paths, and compatibility. For retrieval changes rerun the
relevant benchmark (`uv run pramana evaluate --output benchmarks/results.json`)
with its exact edition available. Keep chapter/passage/answer evaluations distinct.
Actual embedding acceptance: `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest -m model`.
This needs the cached BGE model and complete indexed Wilson corpus. Local chat QA
also needs Ollama and an installed model; ordinary tests need neither.
`uv run python tests/manual_chat_server.py` serves deterministic browser fixtures
on localhost:8001 without using the private library. Documentation-only edits need
link/command/fact checks and `git diff --check`, not model inference.

## Invariants

- Preserve Unicode and immutable canonical text. Passage offsets are zero-based
  Python code-point intervals `[start, end)`; chapter slices must equal passage text.
  They are not byte, PDF coordinate, or JavaScript UTF-16 offsets.
- PDF canonical cleanup is documented and raw extraction retained. Never edit
  original scans. Cache keys include checksums/configuration; preserve resumability
  and publish complete outputs transactionally/atomically.
- Distinguish translation, summary, notes, commentary, and authors/editions. Use
  `mixed` for inseparable PDF translation/commentary. Do not guess boundaries,
  chapter alignment, missing OCR words, or verse references. The Taittiriya scan
  is Book II, Ananda-valli, A: Brahmavidya Expounded, not a complete Upanishad.
- Retain origins (HTTP or local paths), acquisition timestamps, SHA-256, rights,
  and attribution. See [source notices](docs/sources.md), [PDF guide](docs/pdf-ingestion.md),
  and [import contract](docs/import-format.md). Different editions stay separate.
- Retrieval relevance scores are not factual confidence or verification. Model,
  tokenizer, chunking, parser, or storage changes need compatibility handling and
  an explicit rebuild/migration where required. Preserve stable identities and
  idempotent imports; failed indexing must not replace a committed usable index.
- Retrieve fresh evidence for every question, including follow-ups. Bound history
  and model inputs. Retrieved text and prior assistant answers cannot override
  system instructions. Validate returned internal references against supplied
  passages; this does not establish claim entailment or scholarly correctness.
- The web experience shows answers and conversation only: no source lists,
  citation markers, IDs, page references, excerpts, document metadata, scores,
  or source controls. Provenance remains in API responses. Natural attribution of
  differing interpretations is permitted. Keep history in tab sessionStorage;
  New chat clears it. No accounts or server-side conversation persistence.

## Local operation and hygiene

Acquisition is explicit: `pramana model setup`, `pramana corpus download`, and
`pramana corpus import-books`. Poppler/Tesseract installation and Ollama model pulls
are explicit user setup. Do not silently download models, switch providers, or
send private text to a hosted service. Default chat uses localhost Ollama and
`gemma4:e4b`; bind FastAPI to localhost. See [chat configuration](docs/chat.md).

Ordinary tests use deterministic fixtures, without downloaded books/models/network.
Preserve archival fixture whitespace (`.gitattributes` exempts fixture text).
Keep original PDFs, OCR output, extracted full text, corpora, weights, databases,
caches, environments, dependencies, and generated assets out of commits. Defaults
are `.pramana/`, `.venv/`, `web/node_modules/`, and `src/pramana/static/`; ignore any
custom data root too. Code licensing does not confer rights to the private books.
Preserve unrelated checkout changes.

Report completed, skipped, failed, and unavailable checks honestly, with material
limits. Do not fabricate source review, benchmark gains, CI results, or scholarly
validation. Update docs when behavior changes. Repository guidance follows the
[official AGENTS.md documentation](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
