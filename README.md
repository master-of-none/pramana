# Pramana

**Ask the Upaniṣads, Śaṅkara and Rāmānuja — on your own machine.**

Pramana (_pramāṇa_, a means of valid knowledge) is a local study companion for
Advaita Vedānta. It answers questions from a library of public-domain translations
of the Upaniṣads, the Bhagavad Gītā, and the great Brahma Sūtra commentaries, using
your installed [Ollama](https://ollama.com/) model (`gemma4:e4b` by default).
Answers are generated from retrieved passages, and your questions and books stay on
your computer: the only network use is the explicit download commands.

## What it does

- **Grounded answers.** Each question retrieves fresh passages (SQLite FTS5 plus
  pinned BGE embeddings); the model must answer from them or say the library does
  not support an answer. The chat shows only the conversation; provenance stays in
  the API.
- **Compare thinkers.** Ask how Śaṅkara and Rāmānuja differ, and each thinker's view
  appears separately. Pramana checks that every passage a view cites was written by
  that thinker.
- **Reads commentary structure.** Printed objection/reply cues (_pūrvapakṣa_,
  _siddhānta_, "To this we reply") are passed to the model so an objection is not
  mistaken for the author's conclusion.
- **Advaita glossary.** Terms such as _adhyāsa_, _māyā_ and _sākṣin_ get hover
  cards in answers, and searches match Sanskrit and English names for a concept.
- **Careful sources.** Editions stay separate, every record keeps its URL, SHA-256,
  rights statement and attribution, and nothing is downloaded without an explicit
  command.
- **Study view.** Read every text with page marks, footnotes and marked
  objections/replies, open Śaṅkara and Rāmānuja side by side on any sūtra, see the
  passages behind an answer, and search, all without a model.
- **A library, not just a chat.** Python API, CLI search and HTTP endpoints all work
  without a model.

## The library

| Texts | Translation | Command |
| --- | --- | --- |
| Brahma Sūtra with Śaṅkara's commentary | Thibaut, SBE 34 and 38 | `--source brahma-sutra` |
| Brahma Sūtra with Rāmānuja's Śrībhāṣya | Thibaut, SBE 48 | `--source sribhashya` |
| Chāndogya, Bṛhadāraṇyaka, Kaṭha, Muṇḍaka, Kena, Īśa and five more Upaniṣads, with the Aitareya Āraṇyaka | Max Müller, SBE 1 and 15 | `--source upanishads-1`, `upanishads-2` |
| _Knowledge of Self_, _Direct Realisation_ and six more works attributed to Śaṅkara | Venkataramanan, 1921 | `--source shankara-works` |
| Vivekacūḍāmaṇi (_The Crest-Jewel of Wisdom_), Ātma Bodha, Tattva Bodha and other works | Charles Johnston, 1946 | `--source crest-jewel` |
| Aṣṭāvakra Gītā (_The Heart of Awareness_) | John Richards, 1996 | `--source ashtavakra-gita` |
| Bhagavad Gītā with commentary | Swami Swarupananda, 1909 | `--source gita-swarupananda` |
| Thirty Minor Upaniṣads | Narayanasvami Aiyar, 1914 | `--source minor-upanishads` |
| _Brahma-Knowledge_ | L. D. Barnett, 1911 | `--source brahma-knowledge` |
| Yoga Vāsiṣṭha (opt-in; larger than the rest together) | Vihari-Lala Mitra, 1891–99 | `--source yoga-vasistha` |
| Vishnu Purana | H. H. Wilson, 1840 | `--source vishnu-purana` |

`--source advaita` fetches every Vedānta source above except the Yoga Vāsiṣṭha. You can also add three
private PDFs locally (Chinmayananda's _Holy Geeta_, Śaṅkara's Gītā commentary
translated by Alladi Mahadeva Sastry, and the Taittirīya Ānanda-valli); they are
never distributed. See [building the library](docs/guides/corpus.md) and the
[source notices](docs/notices/sources.md) for rights statements and exclusions.

## Quickstart

Requires Python 3.12 with [uv](https://docs.astral.sh/uv/), Node.js 22.12+, and
Ollama with your chosen model already pulled.

```sh
uv sync --locked && npm --prefix web ci && npm --prefix web run build
uv run pramana model setup                       # pinned embedding model, once
uv run pramana corpus download --source advaita  # about 15 minutes
for f in .pramana/corpora/*/chapters.jsonl; do uv run pramana ingest "$f"; done
uv run pramana index
uv run pramana serve                             # http://127.0.0.1:8000
```

Try "How do Śaṅkara and Rāmānuja differ on whether the world is real?" or "What
does the Kaṭha Upaniṣad say about the Self?". The [quickstart](docs/guides/quickstart.md)
covers offline use, PDFs, search and the Python API.

## Limits

Pramana checks that answers cite passages they were given, and that a thinker's view
cites that thinker's own text. It does **not** verify that a reading is correct: the
model can still misread an argument or overgeneralise. One recorded comparison
misread an objection/reply passage; see the
[answer diagnostics](docs/verification/chat-validation.md). The
[retrieval benchmark](benchmarks/README.md) measures chapter-level retrieval, not
answer quality. Treat answers as a starting point for reading the texts.

## Documentation and plans

Everything is indexed in [docs/](docs/README.md): guides, the
[HTTP API](docs/reference/api.md), notices and verification. Upcoming work is in the
[roadmap](ROADMAP.md): concept pages, an argument view and a published Advaita benchmark
([UX plan](docs/plans/ux.md)), and a free public site with public-domain texts only
([hosted plan](docs/plans/hosted-deployment.md), not deployed).

## License

Code: [Apache 2.0](LICENSE). Source texts and model weights keep their own terms;
the SBE Brahma Sūtra editions permit non-commercial use only. Private PDFs, OCR
output and extracted text are **not distributed**.
