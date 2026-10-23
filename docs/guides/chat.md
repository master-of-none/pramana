# Chat and answers

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

The HTTP endpoints, request limits and response fields are in the
[API reference](../reference/api.md).

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

The chat renders only the answer and conversation (with per-thinker cards for
comparisons). It never renders the internal mapping, passages, citations, scores, or
source controls; one **Read in the texts** link opens the separate
[Study view](#study-view) with the passages that answer cited. History is kept in the
current tab's `sessionStorage`, survives reloads, and is cleared by **New chat**.
Stopping or reloading an unfinished answer leaves a retryable question. Only the
last 60 exchanges are retained in the browser; the last six completed exchanges
are sent. If storage is unavailable, a visible notice explains reload persistence
is unavailable. Responses are rendered as React text, not arbitrary HTML.

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

## Advaita glossary

`src/pramana/glossary.json` holds 110 Advaita concepts (IAST term, Devanagari, ASCII
spellings, English renderings, a one-line meaning): Brahman and the world (saccidānanda,
nirguṇa/saguṇa, vivarta, mithyā, the three levels of reality), the seeker's
qualifications and disciplines, the inner instrument, the three bodies and states,
karma and liberation, the great sayings, the means of knowledge, and the schools.
The definitions are general editorial explanations, not quotations or evidence from
the library. `GET /api/glossary` serves it. The web chat underlines the first mention
of each term in an answer and shows its meaning on hover, focus, or tap; in the Study
view the card links to the concept's page.

Lexical search also expands queries that name a concept with its other spellings and
English renderings (for example `adhyāsa` ↔ `superimposition`) — **for the original
23 entries only** (`"expand": true`). The 87 added on 23 October 2026 are display-only:
enabling them lowered dev MRR@10 (hybrid 0.412 → 0.397, lexical 0.396 → 0.362), largely
from work titles such as "Kaivalya Upaniṣad" triggering "aloneness". Dense retrieval and
the index are unchanged.

## Objection/reply roles

Commentaries often print an objection (`Objection:`, `Question:—`, `(Doubt)`) before
the author's reply (`Answer:`, `Reply. —`). [`discourse.py`](../../src/pramana/discourse.py)
recognises only these printed labels; unlabelled prose is never assigned a role.
When a supplied passage contains, or directly follows, a label, the model receives
its text as consecutive `segments` (`objection`, `reply` or `unmarked`) that rejoin
exactly to the passage. A label up to 3,000 characters before the passage sets the
role at its start. If a passage ends inside an objection, the next labelled reply
within 1,500 characters is supplied as `following_reply`, for reading context only.
Roles are computed at answer time from stored chapter text, so no rebuild is needed.

The prompt also asks the model to attribute interpretations to the author named in
each evidence item, and not to name schools or sub-commentators (Vivaraṇa, Bhāmatī,
Viśiṣṭādvaita, Dvaita) unless the evidence does. Label detection depends on OCR
quality and has not yet been measured against the private PDFs; the recorded
comparison failure in [chat validation](../verification/chat-validation.md) has not been re-run.

## Comparing thinkers

When a question compares (`compare`, `differ`, `versus`, `agree`, …) and the supplied
evidence comes from two or more distinct authors, the model must also return
`perspectives`: one entry per thinker with a `thinker`, a `view` and `evidence_ids`.
`thinker` is restricted by the JSON schema to authors actually present in the
evidence. Pramana then checks that **every passage a view cites was written by that
thinker**; a view credited to Rāmānuja that rests on Śaṅkara's text is rejected and
regenerated once. The short `answer` gives the neutral agreement or difference. A
grounded comparison must contain at least one perspective. `ChatResponse.perspectives`
returns each view with its internal references; the web chat shows each thinker's
view in its own labelled card, without sources.

Naming two or more known thinkers (Śaṅkara, Rāmānuja or "Viśiṣṭādvaita",
Chinmayananda, Swarupananda, Barnett) retrieves evidence separately for each author
and interleaves it; the thinkers' names are dropped from each author-filtered search,
since the filter already expresses authorship. If a view still cites another thinker's
passages after one regeneration, no answer is given and the reply suggests asking about
one thinker at a time. Naming a scriptural work ("Katha Upanishad", "Chandogya", "the
Gita") searches that work itself; titles of short works are not treated this way. The authorship check confirms whose text supports a view; it
does not confirm that the view is a correct reading of that text.

## Scope and answer length

Chips above the composer limit a question to **All texts**, **Upaniṣads**, **Bhagavad
Gītā**, **Śaṅkara** or **Rāmānuja**; only scopes with imported books are offered.
Scopes are resolved from the library catalogue, so every document in a group is
searched in one query. Editions or thinkers named in the question narrow a scope but
never widen it. **All texts leaves out opt-in works** (currently the Yoga Vāsiṣṭha):
they are searched only with their chip or when the question names them ("…in the Yoga
Vasishtha"), because the Yoga Vāsiṣṭha alone is larger than the rest of the library and
measurably crowded other passages out of the benchmarks. **Compare Śaṅkara & Rāmānuja** starts a comparison question across all
texts. **Brief / Explain / In depth** changes only the length guidance given to the
model; evidence, validation and the output cap are unchanged. **Vichāra** asks for a
two-to-four-sentence answer followed by "To reflect on:" and two or three questions
that lead back into the same passages (a distinction, an objection and reply, an image);
it replaces the length setting. It is prompt guidance only: the questions are
generated by the model and are not checked for depth or fidelity. The browser remembers
both choices in `localStorage`.

## Checking answers

**Check** (off by default; `ChatRequest.check`) adds one more local model call after
an answer passes validation. The answer and each comparison view are split into
sentences (list items count as sentences), and the model rates each one
`supported`, `partly` or `unsupported` against the same passages it answered from.
Unsupported sentences are removed in place and a note says so; if nothing remains,
the reply becomes an insufficient-evidence answer. `partly` sentences are kept.
`ChatResponse.check` reports every verdict. If the check cannot run (too long for the
context budget, malformed verdicts, or a provider error), the answer is returned
unchanged with `check.status: "unavailable"`, and the chat says the check did not run.

In a comparison, each thinker's statements (their card, and summary sentences naming
only that thinker) are judged only against that thinker's own passages, one check call
per group, so content borrowed from another author's text is not counted as support.

**This is a filter, not verification.** The same local model judges its own answer,
so it can miss errors, wrongly remove correct sentences, and repeat a misreading of
an objection. Its effect on answer quality has not been measured.

## Study view

**Study** in the header (`#/study`) is where the texts themselves are shown; the chat
stays answers-only. It needs no answer model.

- **Library:** every imported work, grouped (Brahma Sūtra, Upaniṣads, Bhagavad Gītā,
  Purāṇas, other works) with translator, edition, rights and attribution.
- **Reader:** chapter text with page marks, footnotes on hover or focus, glossary terms,
  previous/next navigation, and passages tinted **Objection** or **Reply** only where
  the book itself labels them (see [objection/reply roles](#objectionreply-roles)).
- **Argument outline:** on a page with at least two explicitly cued steps, an outline
  lists each objection and reply in order with its opening words (a bare cue such as
  "To this we make the following reply." is skipped) and jumps to it in the text. It
  also heads each column of the side-by-side view. Unmarked discussion is omitted, so
  the outline shows the argument as the translator marks it, not a full analysis;
  83 Brahma Sūtra pages have one.
- **Side by side:** `#/study/sutra/1/1/1` shows Śaṅkara's and Rāmānuja's commentary
  pages for the same sūtra. When a commentary treats the sūtra on a page that begins
  with an earlier one, that page is shown and labelled as such.
- **Passages behind an answer:** opened from the chat, from evidence pointers kept with
  the conversation in the tab's `sessionStorage`; they disappear with New chat.
- **Reading paths:** `#/study/paths` offers curated sequences ("First steps in
  Advaita"; Śaṅkara and Rāmānuja on the first four sūtras) defined in
  `src/pramana/paths.json` by printed location. Steps for editions you have not
  imported are listed but not linked. Marking steps read is stored per browser in
  `localStorage`. The step notes are short editorial descriptions.
- **Search:** hybrid (needs the embedding model) or exact-word search.
- **Concepts:** each glossary concept (`#/study/concept/adhyasa`) shows its editorial
  definition and the passages that mention it most strongly for Śaṅkara, Rāmānuja,
  the Upaniṣads, the Gītā and other works, plus concepts discussed alongside it.
  Glossary cards in the reader link there. Matching uses phrase search on the
  concept's IAST, ASCII and English names and rejects hyphenated compounds
  (`anna-maya` is not `māyā`); English renderings can still match ordinary phrases
  (for example "that thou art" in an unrelated sentence). Ranking shows where a
  concept is discussed, not what an author concludes about it.

Offsets from the API are Python code points; the UI converts them to JavaScript
UTF-16 positions in one helper tested with supplementary characters
(`npm --prefix web test`). Theme (system, light, dark) and text size are remembered
per browser in `localStorage`.
