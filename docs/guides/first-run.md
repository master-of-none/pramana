# Your first run, from a fresh clone

This guide takes you from `git clone` to asking your first question, then shows what to
explore and how to fix the usual problems. It assumes you have not used Pramana before.
Every command runs from the repository root.

**What you will end up with:** a local web app at <http://127.0.0.1:8000> that answers
questions from about twelve public-domain Vedānta editions, a reader for those texts,
and a command-line tool. Nothing you ask leaves your machine.

## 1. Check what you need

| Need | Why | How to check |
| --- | --- | --- |
| Linux or macOS | tested on Fedora Linux; Windows via WSL is untested | |
| [uv](https://docs.astral.sh/uv/) | installs Python 3.12 and the locked dependencies | `uv --version` |
| Node.js **22.12+** and npm | builds the web interface once | `node --version` |
| [Ollama](https://ollama.com/) with `gemma4:e4b` | writes the answers locally | `ollama list` |
| About **13 GB** of free disk | see the breakdown below | `df -h .` |
| Internet, once | the downloads in steps 3–5; afterwards everything works offline | |

Measured disk use on a full setup:

| Item | Size |
| --- | ---: |
| Python environment `.venv/` (includes PyTorch for the embedding model) | 5.6 GB |
| `gemma4:e4b` in Ollama | 6.6 GB |
| Embedding model `.pramana/models/` | 129 MB |
| Downloaded sources `.pramana/corpora/` | 39 MB |
| Library and index `.pramana/pramana.sqlite3` (with the Yoga Vāsiṣṭha) | 86 MB |
| Web dependencies `web/node_modules/` | 116 MB |

A GPU is optional. Ollama uses one if it can; the embedding and search steps run on the
CPU. Only the optional Vivekacūḍāmaṇi OCR in step 8 needs an NVIDIA GPU.

If you don't have the answer model yet:

```sh
ollama pull gemma4:e4b
```

Pramana never pulls models for you. To use a different Ollama model, set
`PRAMANA_CHAT_MODEL` (see [chat and answers](chat.md)).

## 2. Clone and install

```sh
git clone https://github.com/master-of-none/pramana.git
cd pramana
uv sync --locked               # Python 3.12 + dependencies, exactly as locked
npm --prefix web ci            # web dependencies
npm --prefix web run build     # builds the interface into src/pramana/static/
```

`uv sync` is the slow one the first time, because it fetches PyTorch.

## 3. Download the embedding model (once)

```sh
uv run pramana model setup
```

This fetches the pinned `BAAI/bge-small-en-v1.5` revision (about 130 MB) into
`.pramana/models/`. Later commands use it offline.

## 4. Download the library

```sh
uv run pramana corpus download --source advaita
```

This takes **about 15 minutes**. The two Brahma Sūtra commentaries are fetched page by
page (1,123 pages) at a polite rate; the other books are single files. Each command
prints the path of the `chapters.jsonl` it wrote. If it is interrupted, run it again: the
pages it already has are reused.

Optional extras, each its own command:

```sh
uv run pramana corpus download --source vishnu-purana   # Wilson's Vishnu Purana
uv run pramana corpus download --source yoga-vasistha   # large; see step 7
```

`uv run pramana corpus download --help` lists every source.

## 5. Import and index

```sh
for f in .pramana/corpora/*/chapters.jsonl; do uv run pramana ingest "$f"; done
uv run pramana index
```

Importing prints `Imported N new or changed chapters.` for each source; running it again
prints `Imported 0 …`, which is expected. Indexing embeds every passage: about **3
minutes for 4,500 passages** on a 16-thread CPU, and about 6 minutes for 8,681 passages
with the Yoga Vāsiṣṭha. Check the result:

```sh
uv run pramana status     # "state": "ready" means you're set
```

## 6. Start Pramana and ask

```sh
uv run pramana serve
```

Open <http://127.0.0.1:8000>. Good first questions:

- How does Śaṅkara define superimposition?
- How do Śaṅkara and Rāmānuja differ on the nature of the individual soul?
- What does the Kaṭha Upaniṣad say about the Self?
- What does Aṣṭāvakra tell Janaka about bondage and liberation?

Then try the controls above the question box: **scope** chips (Upaniṣads, Gītā,
Śaṅkara, Rāmānuja), **Brief / Explain / In depth**, **Vichāra** (answers with questions
to reflect on) and **Check** (a slower second pass that removes unsupported sentences).
Under each answer, **Read in the texts** opens the passages it used.

Switch to **Study** in the header to:

- browse the **library** and read any text, with page marks, footnotes and marked
  objections and replies;
- open **Śaṅkara and Rāmānuja side by side** on a sūtra (try `#/study/sutra/1/1/1`);
- open a **concept page** from the list (for example *adhyāsa*);
- follow a **reading path** such as "First steps in Advaita";
- **search** every text, by meaning or by exact words.

The header buttons switch the theme (system, light, dark) and text size. Your
conversation lives only in that browser tab; **New chat** clears it.

## 7. Optional: the Yoga Vāsiṣṭha

```sh
uv run pramana corpus download --source yoga-vasistha
uv run pramana ingest .pramana/corpora/yoga-vasistha-mitra/chapters.jsonl
uv run pramana index
```

Mitra's complete translation in seven Project Gutenberg volumes (about 6.2 million
characters, 673 chapters). It is **opt-in** because it is larger than everything else
together: chat's **All texts** leaves it out unless you pick the **Yoga Vāsiṣṭha** chip or
name it in your question ("…in the Yoga Vasishtha"). Importing it also makes the next
`index` take longer.

## 8. Optional: Madhavananda's Vivekacūḍāmaṇi (needs an NVIDIA GPU)

Swami Madhavananda's 1921 translation exists only as a scan, so Pramana reads it with
[Chandra OCR](https://github.com/datalab-to/chandra) on your GPU:

```sh
uv tool install "chandra-ocr[hf]"     # its own environment; ~5.5 GB, plus model weights on first use
uv run pramana corpus download --source vivekachudamani
```

The OCR runs in batches with one model load each; finished pages are cached, so an
interrupted run resumes. It was run on an RTX 5070 Ti (16 GB). The command prints the
path of the records to import with `pramana ingest`, then run `pramana index`. If the
archive.org download stalls, download the PDF in a browser and pass it with
`--archive path/to/vivekachudamanio00sankrich.pdf` (its checksum is still verified).
The weights' licence allows personal and research use.

## 9. Optional: your own PDF books

Three specific private PDFs can be OCRed locally with Tesseract; see the
[PDF guide](pdf-ingestion.md). Any other text in the
[import format](../reference/import-format.md) can be added with `pramana ingest`.

## Where everything lives

| Path | Contents | Safe to delete? |
| --- | --- | --- |
| `.pramana/corpora/` | downloaded sources, receipts, normalized `chapters.jsonl` | yes, but you must download again |
| `.pramana/models/` | the embedding model | yes; run `pramana model setup` again |
| `.pramana/pramana.sqlite3` | the library and its search index | yes; import and index again |
| `.pramana/sources/`, `.pramana/extractions/` | scans and OCR caches | yes; OCR runs again |
| `src/pramana/static/` | the built web interface | yes; run `npm --prefix web run build` |

All of these are ignored by Git. To start completely fresh, delete `.pramana/`. To keep
the library somewhere else, set an absolute `PRAMANA_HOME` for every command.

## Updating after `git pull`

```sh
uv sync --locked
npm --prefix web ci && npm --prefix web run build
uv run pramana status
```

If `status` reports `stale` or `incompatible`, run `uv run pramana index` (or
`uv run pramana index --rebuild` when it says so). New sources need their own
`corpus download` and `ingest`.

## When something goes wrong

| You see | What it means | Fix |
| --- | --- | --- |
| `Web assets missing. Run: cd web && npm ci && npm run build` | the interface was not built | `npm --prefix web ci && npm --prefix web run build` |
| `Library is empty. Import your books, then run pramana index.` | nothing imported yet | steps 4 and 5 |
| `Search index is missing or stale. Run: pramana index` | books changed since the last index | `uv run pramana index` |
| `Index is incompatible. Run: pramana index --rebuild` | the index was built by an older version | `uv run pramana index --rebuild` |
| `Local model is missing. Run: pramana model setup` | embedding model not downloaded | step 3 |
| `Cannot reach Ollama at http://localhost:11434…` | Ollama is not running | start Ollama (`ollama serve` or the app) |
| `Ollama model 'gemma4:e4b' is unavailable…` | model not pulled | `ollama pull gemma4:e4b` |
| `This question exceeds the local model context budget…` | very long question or chat | shorten it or start a new chat |
| `Pramana could not tie each view to that thinker's own texts…` | a comparison failed its authorship check | ask about one thinker at a time |
| `No imported books are in the … scope` | that scope's books aren't imported | choose All texts, or download those sources |
| `… differs from the reviewed edition` | a downloaded file changed upstream | the file is refused on purpose; report it so the pinned manifest can be updated |
| `This edition is OCRed with Chandra; install it explicitly first…` | Chandra not installed | step 8 |
| port 8000 already in use | another server is running | `uv run pramana serve --port 8010` |

Answers are a starting point, not a verdict: the model can misread an argument. The
Study view shows the passages behind every answer.

## For developers

```sh
uv run ruff check src tests scripts && uv run ruff format --check src tests scripts
uv run pytest                          # 120 deterministic tests; no downloads or models
uv run python scripts/check_links.py
npm --prefix web run typecheck && npm --prefix web test && npm --prefix web run build
uv run python tests/manual_chat_server.py    # fixture app on :8001, no library or model needed
```

Retrieval benchmarks: `uv run pramana evaluate-passages` and `uv run pramana evaluate`;
regenerate the README charts with `uv run python scripts/plot_benchmarks.py`. See
[AGENTS.md](../../AGENTS.md) for the project's rules and invariants.
