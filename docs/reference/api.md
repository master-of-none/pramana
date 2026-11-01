# HTTP API reference

`pramana serve` binds FastAPI to `127.0.0.1:8000`; interactive schema documentation
is served at `/docs`. All endpoints are local and unauthenticated, except `/api/excerpts`, which needs a token. Behaviour, limits
and validation are described in the [chat guide](../guides/chat.md).

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/status` | Index readiness: `empty`, `stale`, `incompatible` or `ready` |
| `POST` | `/api/search` | Lexical, dense or hybrid passage search with metadata filters |
| `GET` | `/api/chapters/{id}` | A stored chapter (`?passage_id=` selects one), its explicit role spans, and previous/next IDs |
| `GET` | `/api/concepts` | Glossary concepts with their page slugs |
| `GET` | `/api/concepts/{slug}` | A concept with its strongest passages per group of texts |
| `GET` | `/api/paths` | Curated reading paths resolved against the imported library |
| `GET` | `/api/scopes` | Chat scopes that contain imported books, with document counts |
| `GET` | `/api/library` | Every document with its divisions in reading order, without text |
| `GET` | `/api/parallel?book=&chapter=&sutra=` | Each Brahma Sūtra commentary's pages for one sūtra |
| `GET` | `/api/citations` | Most-cited scripture passages with counts per citing author, and how references resolved |
| `GET` | `/api/citations/{chapter_id}` | A chapter's printed references (`outgoing`, with target span and `status`) and where it is cited (`incoming`) |
| `GET` | `/api/divergence` | The [divergence map](divergence.md): Śaṅkara's commentary in units with Rāmānuja's matched pages, a band per signal, scripture cited by only one side, dispute terms, and a ranking (bands only, no numeric scores) |
| `GET` | `/api/verse?chapter_id=&start=&end=` | One verse (code-point span) and every printed reference to it, grouped by citing author, each with the words around it and its role (objection or reply) where a printed cue or page title gives one; chapter-level references listed apart |
| `GET` | `/api/sayings` | The four great sayings: each resolved in the stored text (or `found: false`), with citation and quotation counts per author |
| `GET` | `/api/sayings/{key}` | One saying: its verse page, plus places that use its words without a printed reference |
| `GET` | `/api/locate?ref=` | A typed scripture reference (`Ch 6.8.7`, `Kh. Up. VI, 8, 7`, `BG 2.47`) resolved to its passage; 404 when the work or division is not in the library |
| `POST` | `/api/chat` | One grounded answer (`ChatResponse`) |
| `POST` | `/api/chat/stream` | Progress events, then one validated answer, as NDJSON |
| `GET` | `/api/glossary` | The curated Advaita glossary |
| `GET` | `/api/config` | Whether hosted mode is on, and its public Turnstile site key |
| `GET` | `/api/excerpts/today` | The excerpt of the day (a verse, passage or sentence), the same for every caller on a date, timezone and seed; needs a token |
| `GET` | `/api/excerpts/random` | A random excerpt, optionally excluding IDs already sent; needs a token |
| `GET` | `/api/excerpts/{id}` | One excerpt by ID; needs a token |
| `GET` | `/api/excerpts/sources` | The documents that may supply excerpts, with counts and rights lines; needs a token |

## Chat

```sh
curl http://127.0.0.1:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"How does Chinmayananda explain acting without attachment?","history":[]}'
```

`POST /api/chat/stream` accepts the same request and returns newline-delimited JSON
(`application/x-ndjson`): zero or more `{"type":"stage","stage":...}` progress events
(`understanding` for routing and follow-up rewriting, `searching`, `composing`, `checking`), then one final
`{"type":"answer", ...ChatResponse}` or `{"type":"error","status":...,"detail":...}`.
Answer prose is sent only after validation; unchecked model tokens are never streamed.
The web chat uses this endpoint to show progress.

`ChatRequest` accepts `message` (1–2,000 characters), up to six completed
user/assistant exchanges, an optional `scope` (`all`, `upanishads`, `gita`,
`shankara`, `ramanuja`; an empty scope returns 409) and `depth` (`brief`, `explain`,
`deep`), `mode` (`answer` or `vichara`), `check` (default `false`; see
[checking answers](../guides/chat.md#checking-answers)), and `focus`: an optional
`{"chapter_id", "start", "end"}` span of 1–6,000 code points that the reader selected
in the Study view. A focused question skips off-topic routing; the indexed passages
covering the span (at most two) lead the evidence, marked `selected`, and the search
adds the selection's opening words to the question. An unknown chapter returns 404 and
a span beyond the text 422. History must alternate and end with an assistant. Each
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
  `unavailable`), `reason`, `removed`, and per-sentence `{part, text, verdict, passages}`.
  `passages` are the IDs of passages the check named as support for a kept sentence,
  limited to that sentence's own evidence; they are added to `evidence` if the answer
  did not cite them.
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

## Hosted mode

Only when the app is created with `hosted=HostedGuard(...)` (never by `pramana serve`),
chat requests need an `X-Turnstile-Token` and a unique `X-Request-Id` (8–80
characters). Refusals happen before retrieval: 403 (human check failed), 400 (missing
request ID), 409 (request ID reused), 429 (burst or daily limit, with `Retry-After`)
and 503 (paused). See the [hosted plan](../plans/hosted-deployment.md#spike-status).

## Excerpts for agents and schedulers

`/api/excerpts/*` returns one verse, passage or sentence from a reviewed allowlist of
public-domain texts (`src/pramana/excerpt_sources.json`), so an agent or a scheduled job can
deliver it. It is **off until a token is set**: set `PRAMANA_AGENT_TOKEN` (at least 32
characters; `pramana agent token` prints one) or named tokens in
`PRAMANA_AGENT_TOKENS=name:token,name:token`, and send `Authorization: Bearer <token>`. Without
a token the routes return 404; a missing or wrong one returns 401; more than 60 requests a
minute per token returns 429 with `Retry-After`.

`pramana serve --agent-only` serves **only** these routes (and the OpenAPI schema), still on
`127.0.0.1`. Use it, never the normal server, for anything beyond your own machine: the normal
server's search, chat and library routes are unauthenticated and cover the whole library.

| Query parameter | Routes | Meaning |
| --- | --- | --- |
| `kind` | `today`, `random` | `verse`, `passage` or `sentence` (repeatable); default all |
| `document` | `today`, `random` | Restrict to document IDs in the pool (repeatable); others return 422 |
| `min_chars`, `max_chars` | `today`, `random` | Length bounds |
| `format` | all | `json` (default), `text` or `markdown`: a ready-to-send message |
| `context` | all | `true` adds the paragraph around the excerpt |
| `tz`, `date`, `seed` | `today` | Which day it is (IANA zone, default `UTC`), a date to replay, and an independent sequence |
| `exclude` | `random` | Excerpt IDs not to return (at most 100) |
| `topic`, `strategy` | `random` | An excerpt chosen from the best matches for a word or phrase, using the local retriever over the pool only (`strategy=hybrid` needs the local model and index; `lexical` does not). The response adds `topic` and `retrieval`, and no score |

```sh
curl -H "Authorization: Bearer $PRAMANA_AGENT_TOKEN" \
     "http://127.0.0.1:8000/api/excerpts/today?tz=Asia/Kolkata&format=text"
```

An excerpt's `text` is the exact slice of the stored chapter; `boundary` is `printed` for a
verse (a number the edition prints) and `derived` for a passage or sentence (found by splitting
sentences, never numbered). Responses carry the edition, translator, source URL and a reviewed
`rights` and `attribution` line, and no relevance score. `excerpt_id` is
`<chapter_id>:<start>-<end>` in code points. Private local editions, and the Brahma Sūtra
commentaries (whose sentences may be an opponent's argument), are never in the pool. The
routes read stored text only; they need neither Ollama nor the embedding model. See the
[setup guide](../guides/agent-excerpts.md) and the [plan](../plans/agent-excerpts.md) for the design and its limits.
