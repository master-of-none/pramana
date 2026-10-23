# HTTP API reference

`pramana serve` binds FastAPI to `127.0.0.1:8000`; interactive schema documentation
is served at `/docs`. All endpoints are local and unauthenticated. Behaviour, limits
and validation are described in the [chat guide](../guides/chat.md).

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/status` | Index readiness: `empty`, `stale`, `incompatible` or `ready` |
| `POST` | `/api/search` | Lexical, dense or hybrid passage search with metadata filters |
| `GET` | `/api/chapters/{id}` | A stored chapter (`?passage_id=` selects one), its explicit role spans, and previous/next IDs |
| `GET` | `/api/concepts` | Glossary concepts with their page slugs |
| `GET` | `/api/concepts/{slug}` | A concept with its strongest passages per group of texts |
| `GET` | `/api/scopes` | Chat scopes that contain imported books, with document counts |
| `GET` | `/api/library` | Every document with its divisions in reading order, without text |
| `GET` | `/api/parallel?book=&chapter=&sutra=` | Each Brahma Sūtra commentary's pages for one sūtra |
| `POST` | `/api/chat` | One grounded answer (`ChatResponse`) |
| `POST` | `/api/chat/stream` | Progress events, then one validated answer, as NDJSON |
| `GET` | `/api/glossary` | The curated Advaita glossary |

## Chat

```sh
curl http://127.0.0.1:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"How does Chinmayananda explain acting without attachment?","history":[]}'
```

`POST /api/chat/stream` accepts the same request and returns newline-delimited JSON
(`application/x-ndjson`): zero or more `{"type":"stage","stage":...}` progress events
(`understanding` for follow-up rewriting, `searching`, `composing`, `checking`), then one final
`{"type":"answer", ...ChatResponse}` or `{"type":"error","status":...,"detail":...}`.
Answer prose is sent only after validation; unchecked model tokens are never streamed.
The web chat uses this endpoint to show progress.

`ChatRequest` accepts `message` (1–2,000 characters), up to six completed
user/assistant exchanges, an optional `scope` (`all`, `upanishads`, `gita`,
`shankara`, `ramanuja`; an empty scope returns 409) and `depth` (`brief`, `explain`,
`deep`), `mode` (`answer` or `vichara`), and `check` (default `false`; see
[checking answers](../guides/chat.md#checking-answers)). History must alternate and end with an assistant. Each
history message is limited to 6,000 characters. The server retains no conversation.
For follow-ups, recent bounded history forms a standalone retrieval question;
previous assistant text is not supplied as evidence to the final answer call.
Every question retrieves fresh evidence. Explicitly requested editions can be
filtered and their evidence interleaved for comparison. Otherwise retrieval covers
the indexed library. The local app serializes model requests and shares a retrieval
lock with search. Disconnecting cancels the provider HTTP request; runtime unloading
or GPU release is controlled by Ollama.

`ChatResponse` returns:

- `answer`: English prose or short lists, without citation controls or source metadata.
- `status`: `grounded` or `insufficient_evidence`, as assessed by the answer model.
- `retrieval_question`: the standalone question used for this retrieval.
- `evidence`: internal references, complete supplied passages/citations, and labeled
  retrieval relevance scores for the references used by the answer.
- `model`: configured answer model name.
- `check`: present when `check` was requested: `status` (`checked` or
  `unavailable`), `reason`, `removed`, and per-sentence `{part, text, verdict}`.
- `perspectives`: for comparisons, one `{thinker, view, evidence}` entry per thinker;
  see [comparing thinkers](../guides/chat.md#comparing-thinkers).

## Search, status and chapters

Search and chapter endpoints work without an answer model. Source origins can be HTTP URLs or paths relative to `PRAMANA_HOME`; the API does
not expose a file-serving endpoint for PDFs. `status.state` distinguishes `empty`,
`stale`, `incompatible`, and `ready`. Index schema 2 includes local origins and
commentary metadata; rebuild older indexes with `pramana index --rebuild`.

`/api/chapters/{id}` also returns `roles` (code-point `start`/`end` spans of explicitly
cued `objection`/`reply` segments), `previous` and `next` within the same document
and edition. `/api/library` groups documents into display categories derived from
titles; categories make no claim about tradition or authenticity. `/api/parallel`
matches commentaries on printed adhyāya, pāda and sūtra numbers; `exact: false` marks a
page that begins at an earlier sūtra and continues through the requested one.

Search filters also accept `document_ids`, a list matching any of those documents;
an empty list matches nothing.
