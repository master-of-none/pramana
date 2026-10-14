# Local answers and chat API

Ollama must already be running with the chosen model installed. Pramana never pulls
an answer model automatically. Check `ollama list`; to acquire a missing model,
explicitly run `ollama pull gemma4:e4b` yourself. The default settings are:

```sh
export PRAMANA_OLLAMA_URL=http://localhost:11434
export PRAMANA_CHAT_MODEL=gemma4:e4b
uv run pramana serve
```

The provider uses Ollama's documented [`POST /api/chat`](https://docs.ollama.com/api/chat),
non-streaming structured JSON, temperature zero, a 16,384-token context setting,
and a 1,200-token output cap. It disables thinking output. Model availability,
connection failures, unfinished/malformed output, and timeouts produce actionable
errors. The total request can include two model calls for follow-ups, each with a
180-second read timeout; a format repair can add a third call. Serialized messages/schema are capped at 14,000 UTF-8 bytes, leaving output and
chat-template headroom within the configured context. Context budgets limit recent history and complete evidence
passages conservatively by UTF-8 bytes; no Gemma tokenizer is downloaded.

```sh
curl http://127.0.0.1:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"How does Chinmayananda explain acting without attachment?","history":[]}'
```

`ChatRequest` accepts `message` (1–2,000 characters) and up to six completed
user/assistant exchanges. History must alternate and end with an assistant. Each
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

A grounded response must name at least one supplied internal reference. Unknown
references and inconsistent status/reference combinations fail validation. A missing
retrieval result produces insufficient evidence without generation. Retrieved text
is delimited as evidence and the system prompt rejects instructions within it.
One bounded regeneration repairs invalid structured output, inconsistent status,
or reference/prose violations using the same supplied evidence. If it still fails,
the request returns an actionable error; references are never invented or assigned
automatically. Insufficient-evidence prose is normalized to a clear admission.
These controls validate reference membership and response shape, **not semantic
entailment, scholarly correctness, robust prompt-injection resistance, or perfect
abstention**. The model can misread material, overgeneralize, or overlook relevant
passages. Differing interpretations should be attributed in ordinary prose; this
is distinct from showing a source list. Unsupported-question checks are diagnostics.

The browser renders only the answer and conversation. It never renders the internal
mapping, passages, citations, scores, or source controls. History is kept in the
current tab's `sessionStorage`, survives reloads, and is cleared by **New chat**.
Stopping or reloading an unfinished answer leaves a retryable question. Only the
last 60 exchanges are retained in the browser; the last six completed exchanges
are sent. If storage is unavailable, a visible notice explains reload persistence
is unavailable. Responses are rendered as React text, not arbitrary HTML.

`POST /api/search`, `GET /api/status`, and `GET /api/chapters/{id}` remain available.
Source origins can be HTTP URLs or paths relative to `PRAMANA_HOME`; the API does
not expose a file-serving endpoint for PDFs. `status.state` distinguishes `empty`,
`stale`, `incompatible`, and `ready`. Index schema 2 includes local origins and
commentary metadata; rebuild older indexes with `pramana index --rebuild`.

```python
import asyncio
from pramana import Answerer, Corpus, Retriever
from pramana.models import ChatRequest

answerer = Answerer(Retriever(Corpus(".pramana")))
response = asyncio.run(answerer.answer(ChatRequest(message="What is detachment?")))
print(response.answer)
```

Retrieval remains independent: Python and CLI search require no Ollama service.
The default provider is local, but setting `PRAMANA_OLLAMA_URL` changes where prompt
and evidence text are sent. Keep it on localhost for private local processing.
