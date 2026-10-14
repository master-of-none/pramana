# Pramana

**Old wisdom. New conversations.**

Pramana is a local, book-aware chat app, Python retrieval library, and CLI. Ask a
question, follow an idea, and get a concise explanation from the books in your
private library. Answers run through your installed Ollama model, `gemma4:e4b` by
default. The chat page shows the conversation; edition-aware evidence stays in the
API for inspection and evaluation.

- **Local:** SQLite FTS5 and pinned BGE embeddings retrieve passages; Ollama explains
  them. No accounts, hosted provider, API key, or server-side conversation storage.
- **Book-aware:** Wilson's Vishnu Purana plus private PDF adapters for Chinmayananda's
  Holy Geeta, Shankara's Gita commentary translated by Alladi Mahadeva Sastry, and
  Sastri's Taittiriya-Upanishad Book II volume. Editions remain separate.
- **Traceable internally:** original checksums, physical PDF pages, exact canonical
  text offsets, commentary attribution, and evidence mappings. No invented verses.
- **Independent retrieval:** typed Python interfaces, CLI search, and existing search
  and chapter APIs remain available without an answer model.

See the [quickstart](docs/quickstart.md), [PDF ingestion guide](docs/pdf-ingestion.md),
[chat API and limitations](docs/chat.md), [import format](docs/import-format.md), and
[source notices](docs/sources.md). The [roadmap](ROADMAP.md) describes active work
and the later reliability and research milestones.

The current website runs locally with Ollama. A planned invite-only hosted version
for sharing with friends is described in the [Vercel deployment plan](VERCEL_DEPLOYMENT_PLAN.md);
it uses hosted inference and an approved cloud corpus, and has not been deployed.

```sh
uv sync --locked
npm --prefix web ci
npm --prefix web run build
uv run pramana model setup
uv run pramana corpus download
uv run pramana ingest .pramana/corpora/vishnu-purana/chapters.jsonl
# Optional supplied PDFs: first install Poppler and Tesseract; see the PDF guide.
uv run pramana corpus import-books
uv run pramana index --rebuild
ollama list  # gemma4:e4b must already be installed; no automatic pull
uv run pramana serve
```

Open [localhost:8000](http://127.0.0.1:8000). Skip `import-books` if you do not have
the private PDFs. If the archive blocks acquisition, download its **Text [Zipped]**
file in a browser and use `pramana corpus download --archive /path/to/vp.txt.gz`.

The [initial benchmark](benchmarks/README.md) measures chapter-level retrieval,
not answer quality. Evidence-reference validation checks that references were
supplied to the model; it does not establish that every generated claim is correct.
Manual comparison review found an objection/reply interpretation error; see the
[answer diagnostics](docs/chat-validation.md) before relying on doctrinal comparisons.

Code: [Apache 2.0](LICENSE). Third-party texts and model weights retain their own
rights. The private PDFs, OCR output, and extracted full text are **not distributed**.
