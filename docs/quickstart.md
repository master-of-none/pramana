# Run Pramana locally

Requires Python 3.12, [uv](https://docs.astral.sh/uv/), and Node.js 22.12+ with npm.
The runtime uses SQLite FTS5 (included in uv's managed Python builds). No GPU,
database server or API key is needed. Chat additionally requires a running local
[Ollama](https://ollama.com/) installation and the chosen model already installed
(`gemma4:e4b` by default). Retrieval alone does not require Ollama. Run commands from
the repository root.

```sh
uv python install 3.12
uv sync --locked
npm --prefix web ci
npm --prefix web run build
uv run pramana model setup
uv run pramana corpus download
uv run pramana ingest .pramana/corpora/vishnu-purana/chapters.jsonl
uv run pramana index --rebuild
ollama list  # verify gemma4:e4b is present
uv run pramana serve
```

Open [the chat app](http://127.0.0.1:8000). The API documentation is at
[localhost:8000/docs](http://127.0.0.1:8000/docs). The server binds only to
127.0.0.1; this is a local, single-user application.

The embedding model and corpus download commands explicitly access the network. Searching,
reading, importing, indexing, and evaluating use local resources. The pinned model
runs on CPU. Its weights are approximately 133 MB; Python's ML dependencies take
additional disk space. Initial indexing takes longer than subsequent searches.

## Add the supplied PDF books

Install Poppler and Tesseract explicitly (`brew install poppler tesseract` on macOS).
Place the three supplied PDFs in `docs/sources/`, then run:

```sh
uv run pramana corpus import-books
uv run pramana index --rebuild
```

The importer preserves the originals under `.pramana/sources/pdfs/`, checks their
checksums, extracts text or runs local English OCR, and imports distinct editions.
It prints paths to coverage reports. Repeat to resume or confirm unchanged imports.
These private PDFs are optional and are not included in this repository. See the
[PDF guide](pdf-ingestion.md) for filenames, actual coverage, and extraction limits.

Ask questions in the homepage, continue with follow-ups, and use **Stop answer** or
**New chat** as needed. Completed conversations survive reload in the current tab.
No citation/source details appear on the page; inspect internal provenance through
the [chat API](chat.md). `PRAMANA_OLLAMA_URL` and `PRAMANA_CHAT_MODEL` select the
local answer service and installed model. No answer model is downloaded by Pramana.

## If the archive blocks automated downloads

The archive may return a browser challenge to command-line requests. Open
[its edition index](https://archive.sacred-texts.com/hin/vp/) in your browser and
choose **Text [Zipped]**. Supply that unmodified file:

```sh
uv run pramana corpus download --archive /absolute/path/to/vp.txt.gz
uv run pramana ingest .pramana/corpora/vishnu-purana/chapters.jsonl
uv run pramana index
```

The downloader does not bypass challenges. A complete local archive is sufficient;
it validates all 126 chapters before publishing normalized JSONL. Reusing the cache
does not change the original acquisition timestamp or checksum.

## Search and inspect

```sh
uv run pramana search "How did Krishna protect the cowherds from rain?"
uv run pramana search "Govarddhana" --strategy lexical --book 5 --json
uv run pramana status
```

Results identify the translation, book, chapter, available printed pages, source URL,
and stable local passage ID. No Sanskrit verse numbers are inferred. BM25 values
sort ascending; cosine and reciprocal-rank fusion values sort descending. These
are retrieval relevance scores, not factual confidence or scholarly verification.

## Offline operation and data location

By default, `.pramana/` in the working directory contains SQLite, source archives,
the manifest receipt, and the model. Set `PRAMANA_HOME` to an absolute directory to
share a library across working directories. Raw PDFs, OCR caches, and extracted
records also remain under this root; do not commit or redistribute them. Use the same value for all commands.
It must contain the downloaded model before indexing or semantic search.

```sh
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pramana search "What is a Kalpa?"
uv run pramana corpus download --offline
```

Model loading always uses `local_files_only=True`; a missing cache produces the
`pramana model setup` instruction. Keyword search works with an existing index
even if the model cache is unavailable. Imports invalidate an old index when text
or provenance changes. Run `pramana index` after an import; use `--rebuild` when the
model or chunking configuration changes. Index schema 2 requires rebuilding indexes from the initial release.
Stop the server while importing/indexing
large collections; the server otherwise reads current SQLite state on each request.

## Python API

```python
from pramana import Corpus, Retriever, SearchFilters

corpus = Corpus(".pramana")
hits = Retriever(corpus).search(
    "How was the world created?",
    limit=10,
    strategy="hybrid",
    filters=SearchFilters(corpus_id="vishnu-purana", book="1"),
)
for hit in hits:
    passage = hit.passage
    chapter = corpus.store.chapter(passage.chapter_id)
    assert chapter.text[passage.start:passage.end] == passage.text
    print(passage.citation.label)
```

## Development and validation

```sh
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run pytest
npm --prefix web run typecheck
npm --prefix web run build
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run pytest -m model
uv run pramana evaluate --output benchmarks/results.json
```

Ordinary tests use deterministic vectors and require no model or network. The model
smoke test requires `pramana model setup`. The evaluation command needs the complete
demo corpus and local model. See [benchmark methodology](../benchmarks/README.md).

For frontend development, run `uv run pramana serve` and `npm --prefix web run dev`
in separate terminals. Vite proxies `/api` to port 8000. Production builds copy the
chat app into the Python package. Before packaging, build the reader, then run
`uv build`; both the wheel and source distribution include compiled assets.
