# Chat and answers

Answers are written by one of two providers, chosen explicitly with `PRAMANA_PROVIDER`:
the local **Ollama** model (the default, below) or **OpenRouter's free models**
([without a local model](#without-a-local-model-openrouters-free-models)). Search, the
Study view, citations and notes need neither.

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
errors. Every question first makes one short routing call (below). The total request can include two more model calls for follow-ups, each with a
180-second read timeout; a format repair can add a third call. Serialized messages/schema are capped at 14,000 UTF-8 bytes, leaving output and
chat-template headroom within the configured context; the budget is re-applied before a
repair attempt, whose added instructions could otherwise exceed it. Context budgets limit recent history and complete evidence
passages conservatively by UTF-8 bytes; no Gemma tokenizer is downloaded.

The HTTP endpoints, request limits and response fields are in the
[API reference](../reference/api.md).

**Off-topic questions.** Before any search, one short call to the same model asks
whether the question is about the texts (their teachings, stories, people and terms, or
how a teaching applies to the asker's life) or about another field (programming,
technology, mathematics, science facts, careers as such, news, sport, trivia, recipes).
It sees only the standalone question, never the library text, and is shown six worked
examples. An unrelated question gets a fixed reply ("Neti, neti: not this, not this. I
give knowledge, but this is not the knowledge you seek…") with status
`insufficient_evidence` and no evidence; nothing is retrieved. An invalid routing reply
counts as "about the texts", so the evidence-based refusal below still applies. Measured
on benchmark v2 (tuned on that set, not held out): 196 of 198 answerable questions
routed to the texts; all 7 clearly off-topic probes declined
([routing.json](../../benchmarks/advaita/v2/routing.json)). Asking the answer model to
make the same judgement inside its answer did not work: it still answered all four
programming and career questions tried.

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

When a question compares (`compare`, `differ`, `versus`, `agree`, …) or names two known
thinkers ("How do Śaṅkara and Rāmānuja read this sūtra?"), and the supplied evidence
comes from two or more distinct authors, the model must also return
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
- **Śruti citation links:** printed references in Thibaut's Brahma Sūtra translations
  ("(Kh. Up. VI, 8, 7)", "(Bri. Up. IV, 4, 22)", "(Bha. Gî. XIII, 31)") open the cited
  passage. A reference is resolved only from what is printed: the abbreviation names the
  edition and its numbers its printed division (Thibaut's Kaṭha "II, 1-3" are Müller's
  vallīs "II, 4-6"). Underlines show how far a link was checked: **solid** when the
  words quoted just before the reference occur in that passage (as consecutive word
  pairs; the best-matching paragraph is used when the translator's verse number points
  elsewhere), **dashed** for the numbered verse when there is no quotation to check, and
  **dotted** for the chapter alone. Bare references that rely on an earlier one, and
  numbers naming no division, stay plain text. On the cited side, each verse shows
  "Cited · Śaṅkara n · Rāmānuja m" with links back, and `#/study/citations` ranks the
  most-cited passages. Of 1,609 resolved references, 1,001 were verified, 203 linked by
  number and 405 to the chapter (23 October 2026).
- **Ask about, highlight or note part of an answer:** in the chat, select words in an
  answer. **Ask about this** starts the question box with *About “…”:* for you to
  finish: an ordinary follow-up in your own words, with fresh retrieval. **Highlight** and
  **Note** save the words, with the question they answered, to **My notes** under
  "From conversations" (in this browser only), so they outlive New chat; while the
  conversation is open the words are tinted in the answer (CSS Highlight API, so the
  answer's markup is untouched; browsers without the API show no tint).
- **Ask about this passage:** select text in the reader (or open a highlighted
  passage) and choose **Ask about this**. Only a pointer to the span travels to the
  chat, in this tab's `sessionStorage`; the chat shows "Asking about the passage you
  selected in Study" and never the text or its location. The selected passages lead the
  evidence for that one question, which then works like any other: its answer's **Read
  in the texts** shows them. A selection whose exact words occur more than once in the
  touched paragraphs falls back to those whole paragraphs.
- **Notes and highlights:** the same selection offers **Highlight** and **Note**.
  They are drawn in the reader (a note shows a ✎ marker; click to edit or delete) and
  listed under **My notes** (`#/study/notes`) by work, with **Export Markdown**, **Export
  JSON** and **Import JSON** (merged by note, the later edit winning). They are kept in
  this browser's `localStorage` only and never sent to the server or a model. Each note
  stores the words it covers; if a text changes so they no longer match, the note is
  listed but not drawn.
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

## Without a local model: OpenRouter's free models

To get answers on a machine without Ollama or a GPU, use a free model on
[OpenRouter](https://openrouter.ai/). Search stays local (BGE-small on the CPU); only
writing the answer is sent out.

```sh
export PRAMANA_PROVIDER=openrouter
export OPENROUTER_API_KEY=sk-or-...            # from openrouter.ai/keys
uv run pramana model free                       # free models with JSON-schema output
export PRAMANA_CHAT_MODEL=nvidia/nemotron-3-super-120b-a12b:free   # the default
uv run pramana serve
```

- **Free models only.** Any `PRAMANA_CHAT_MODEL` that does not end in `:free` is refused
  at startup, so nothing can be billed. The free list changes; `pramana model free` reads
  OpenRouter's public model list and shows the ones that support structured output.
  Requests ask for JSON-schema output and route only to endpoints that support it
  (`require_parameters`); a model with none returns an error naming the command above.
- **Limits.** OpenRouter's free plan allows 20 requests a minute and 50 a day for
  accounts that have not bought credits (1,000 a day after buying 10 credits; checked
  23 October 2026 in its [limits documentation](https://openrouter.ai/docs/api-reference/limits)).
  A question uses one routing call and one answer call, plus one more for a follow-up's
  rewrite, a format repair or the optional check, so expect roughly 15–25 questions a
  day. When the limit is reached the chat says so.
- **What is sent.** Your question, recent conversation turns for follow-ups, and the
  retrieved **public-domain** passages. **Private local books are never sent:** their
  passages are dropped from the evidence and their titles from the catalogue, and asking
  about a selected passage from one is refused. The chat says which model answers and
  that questions go to OpenRouter.
- **Privacy settings.** Each provider behind OpenRouter has its own data policy, and
  OpenRouter has separate privacy settings for free models; some free endpoints may log
  or train on prompts. Review the free-model settings in your OpenRouter account
  ([privacy and logging](https://openrouter.ai/docs/features/privacy-and-logging)).
- **Evaluation.** `pramana evaluate-answers --limit 20` works with either provider;
  at about two requests a question, the free plan fits roughly 20 questions a day, so
  the 214-question set takes several days in batches.

Unset `PRAMANA_PROVIDER` (or set it to `ollama`) to return to the local model.
