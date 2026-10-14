# Pramana

**Every passage has a source.**

Pramana is a local retrieval library, command-line tool, and web reader. Search by
meaning and keyword, open each passage in its chapter, and copy its edition-aware
citation. The first corpus is H. H. Wilson's English Vishnu Purana.

- **Evidence first:** stable passage IDs, exact chapter offsets, original references,
  and separately labeled translator notes. No generated answers or invented verses.
- **Local by default:** SQLite FTS5 + NumPy cosine search, fused with reciprocal
  ranks; a pinned BGE embedding model runs on CPU after explicit download.
- **Extensible:** validated JSONL imports, typed Python interfaces, CLI JSON output,
  and FastAPI endpoints. No external database, API key, or LLM required.

See the [quickstart](docs/quickstart.md) for installation and offline use,
[import format](docs/import-format.md) for your own texts, and
[source notices](docs/sources.md) for the edition and model details.

```sh
uv sync --locked
npm --prefix web ci
npm --prefix web run build
uv run pramana model setup
uv run pramana corpus download
uv run pramana ingest .pramana/corpora/vishnu-purana/chapters.jsonl
uv run pramana index
uv run pramana serve
```

Open [localhost:8000](http://127.0.0.1:8000). If the source blocks automated downloads,
download its **Text [Zipped]** file in a browser and pass
`pramana corpus download --archive /path/to/vp.txt.gz`.

The [initial benchmark](benchmarks/README.md) measures retrieval against 20
source-checked chapter labels. Relevance scores are not factual confidence, and
this release does not certify interpretations or translations.

Code: [Apache 2.0](LICENSE). Source texts and model weights retain their own notices.
