# Pramana roadmap

Pramana is becoming a local study companion for **Advaita Vedānta**: grounded answers
from a public-domain library of the Upaniṣads, the Gītā, and Śaṅkara's and Rāmānuja's
Brahma Sūtra commentaries. The next milestone is the **Study view**; the passage-level
reliability benchmark (below) remains the measure of retrieval quality. The full
UX and feature plan is in [docs/plans/ux.md](docs/plans/ux.md).

This roadmap guides sequencing. Implement the milestone requested by the current
task; a checklist here is not a standing instruction to start every item.

## Completed baseline: v0.1.0

Verified on 14 October 2026 at commit
[`54cfc9b`](https://github.com/master-of-none/pramana/commit/54cfc9b96a98881f84e74e31d2f01a5856ced5a9).

- [x] Python library, CLI, FastAPI endpoints, and React search/reader interface.
- [x] Wilson's English Vishnu Purana: 126 chapters across six books, indexed into
      587 passages with citations and exact offsets into stored chapter text.
- [x] Local lexical, dense, and hybrid retrieval; structured JSONL imports.
- [x] Separate translation bodies, chapter summaries, and translator notes.
- [x] 26 deterministic local tests and 2 actual-model acceptance tests passed.
- [x] Frontend build, offline indexing/search, and source/wheel packaging checked.
- [x] Initial [GitHub CI run](https://github.com/master-of-none/pramana/actions/runs/38517477904)
      passed. CI currently runs the deterministic suite, frontend build, and packaging;
      the actual-model acceptance tests were run locally.

The [initial benchmark](benchmarks/README.md) uses 20 development-visible questions
and chapter-level relevance labels:

| Method  | Recall@10 | MRR@10 |
| ------- | --------: | -----: |
| Lexical |    90.00% | 0.7406 |
| Dense   |   100.00% | 0.8026 |
| Hybrid  |    95.00% | 0.8250 |

These are historical engineering results, not scholarly validation. A hit in the
correct chapter does not establish that the retrieved passage supports the question.
See [local verification](docs/verification/verification.md) and [source notices](docs/notices/sources.md).

## Delivered: book-aware local chat

**Dependencies:** the retrieval baseline, three user-supplied PDFs, explicit local
Poppler/Tesseract setup, and an installed Ollama `gemma4:e4b` (or configured model).

- [x] Preserve/checksum originals in ignored local storage; catalog distinct authors,
      editions, actual coverage, and mixed translation/commentary.
- [x] Cache page extraction and local OCR by checksum/configuration; publish coverage
      and provenance-bearing imports without redistributing full text.
- [x] Extend citations to local origins and metadata filters to document/author/type;
      require rebuilding incompatible indexes and report readiness states.
- [x] Add an independent Answerer, follow-up rewriting/fresh retrieval, bounded inputs,
      internal reference validation, and actionable local-provider errors.
- [x] Add chat API while preserving search/context APIs; cancel disconnected requests.
- [x] Make the homepage conversational without rendered source metadata; retain tab
      session history, reset, retry, stop, keyboard support, and mobile layouts.
- [x] Migrate the existing chapter benchmark to explicit edition/source identities
      and reject missing, changed, or ambiguous evidence.
- [x] Finish real-model/source checks, browser QA, packaging checks, and publish
      measured results and extraction limitations in the verification notes.

Delivered locally with [verification evidence](docs/verification/verification.md). The eight
real-model diagnostics passed status/source checks; **manual comparison review found
an objection/reply interpretation error**. This remains an answer-quality limitation,
not a passed correctness check. No new GitHub CI run or scholarly verification is claimed.

**Completion gate:** all three coverage reports exist, local imports/indexing/search
work offline after setup, answers are checked across all four works and unsupported
questions, internal references resolve, deterministic regressions and browser/package
checks pass. Describe model/OCR limitations without claiming automatic verification.

## Delivered: Vedānta library and study features (October 2026)

Implemented and covered by deterministic tests; **no real-model answer review, browser
QA, or benchmark run has been recorded for these changes yet.**

- [x] Chat progress streaming (`/api/chat/stream`; validated answers only), dark mode,
      richer answer formatting, Advaita starter questions.
- [x] Curated Advaita glossary with hover cards and lexical query expansion.
- [x] Objection/reply roles from printed labels, translator formulas and headings,
      with the following reply supplied for objections that end a passage.
- [x] Public-domain sources: Śaṅkara's (SBE 34/38) and Rāmānuja's (SBE 48) Brahma
      Sūtra commentaries, Max Müller's Upaniṣads (SBE 1/15), Śaṅkara's select works,
      Swarupananda's Gītā, Thirty Minor Upaniṣads, Barnett's _Brahma-Knowledge_; each
      parsed completely on 22 October 2026 (see [source notices](docs/notices/sources.md)).
- [x] Attributed thinker comparisons: per-author retrieval and per-thinker views whose
      cited passages must be written by that thinker.
- [x] Documentation reorganised under `docs/` with a link check in CI.

**Still to do for this delivery:** index the full library, run real-model diagnostics
including Śaṅkara–Rāmānuja comparisons, and browser-check desktop, mobile and dark mode.

## Next milestone: Study view

Specified in [docs/plans/ux.md](docs/plans/ux.md). Chat stays answers-only; sources
appear only in Study.

- [x] Split the web UI into components with a hash router, theme toggle and font size.
- [x] Library and reader (`/api/library`, chapter roles, page marks, footnotes,
      glossary), with a tested code-point → UTF-16 offset helper. Search page.
- [x] Update the AGENTS.md web-UI invariant for the Study view before shipping it.
- [x] Evidence view and "Read in the texts" from chat answers.
- [x] Sūtra parallel reader (`/api/parallel`) for Śaṅkara and Rāmānuja.
- [x] Chat scope chips, Compare chip, and answer depth.

**Acceptance:** API tests for library, parallel and roles; offset tests with
supplementary characters; manual desktop/mobile/dark checks; chat still renders no
source metadata. API and offset tests pass; **manual browser checks have not been
performed yet.**

## Next milestone: retrieval reliability

Unchecked tasks below remain planned. Work through the numbered groups in order. After
group 1, corpus/index hardening and reader automation can be developed independently
of annotation work; complete all groups before closing the milestone.

### 1. Make evaluation edition-aware

**Dependency:** the existing structured source and chapter models.

- [x] Identify benchmark evidence by corpus, document, edition, language, and
      chapter location, including book and any deeper section path.
- [x] Resolve evidence to exactly one source chapter; reject missing or ambiguous
      identities and evidence quotes that no longer match the translation body.
- [x] Record source checksums and index/model configuration with evaluation results.
- [x] Add fixtures for two editions with the same book/chapter labels, missing
      source text, changed evidence, and ambiguous benchmark records.

**Acceptance:** evaluation cannot silently score evidence from another edition.
Existing benchmark labels are explicitly migrated to the source-aware format.

### 2. Measure passage-level retrieval

- [ ] Add answer/context diagnostics for the observed commentary objection/reply
      failure. Preserve correct discourse roles and evaluate cross-page context
      before relying on generated doctrinal comparisons.

**Dependency:** group 1's source identities and validation.

- [x] Annotate exact supporting text spans for 50 answerable questions across all
      six books. Record source identity, an exact quote, and zero-based Unicode
      code-point intervals in the stored chapter text.
- [x] Freeze a split of 30 development questions and 20 held-out questions before
      tuning. Record annotation provenance and review status; document any subsequent
      inspection or reuse of held-out questions.
- [x] Count a passage as relevant only when it contains an annotated supporting
      span from the correct source chapter. Keep gold spans independent of chunk IDs
      so chunking changes do not require inventing new evidence.
- [x] Report passage-level Recall@10 and MRR@10 for lexical, dense, and hybrid
      retrieval, with per-question failures and index/model configuration.
- [x] Keep passage-level results separate from the historical chapter-level
      benchmark; do not present the two as directly comparable measurements.
- [x] Add ten separate out-of-corpus diagnostic questions and record retrieved
      results. Document that the current engine may return nearby material; these
      diagnostics do not establish automatic abstention.

**Acceptance:** every positive label resolves to verified source text, evaluation
tests cover containment and source mismatches, and a reproducible baseline report
includes the dataset split, failures, and limitations. Establish the baseline before
choosing ranking changes or numerical improvement targets.

### 3. Strengthen corpus and index handling

**Dependency:** group 1's source-identity regression fixtures.

- [ ] Download or copy archives into temporary files and validate the complete
      corpus before replacing a usable cache, normalized records, or acquisition receipt.
- [ ] Check chapter headings against their expected manifest identities and fail
      clearly when source structure changes.
- [x] Make status reporting distinguish empty, stale, incompatible, and ready
      indexes, with actionable setup or rebuild instructions.
- [ ] Test malformed and truncated archives, interrupted acquisition, repeated
      imports, changed source text, model/chunking changes, and failed indexing.

**Acceptance:** failed acquisition or validation retains the last usable source
data; failed indexing retains the last committed index. Status and search agree
about readiness and compatibility, and repeated unchanged imports remain idempotent.

### 4. Automate reader and packaging checks

**Dependency:** stable source identities from group 1 and readiness behavior from
group 3 for the corresponding error-state tests.

- [ ] Automate chat browser regressions using deterministic fixtures for conversation,
      follow-ups, reload/reset, retry/cancellation, and absence of source metadata.
      Keep retrieval/context correctness covered through the API.
- [ ] Cover keyboard navigation and focus restoration, loading/empty/error states,
      and desktop/mobile layouts.
- [ ] Include supplementary Unicode characters before and within evidence spans to
      verify Python code-point offsets against JavaScript UTF-16 representation.
- [x] Extend CI to build the frontend and wheel, install the wheel in an isolated
      environment, and verify API behavior and compiled reader assets outside the checkout.
- [ ] Keep ordinary browser and packaging tests independent of downloaded models,
      source archives, and network services. Retain explicit real-model acceptance checks.

**Acceptance:** automated browser checks pass on desktop and mobile; the installed
wheel serves its compiled reader and API without relying on editable source paths.

### Completion gate

- [ ] Regression checks, browser tests, and installed-wheel checks pass.
- [ ] Failure paths preserve usable data, and readiness states are accurate.
- [x] Publish the reproducible passage-level benchmark with source identities,
      split membership, per-question results, and documented limitations.
- [ ] Update the quickstart, import/API documentation where interfaces changed,
      and verification notes with checks actually performed.

## Later milestones

- [x] **Concept pages** (October 2026): concept → strongest passages per group of
  texts, related concepts. Covered by API tests; not browser-checked.
- [x] **Argument outline** (October 2026): pūrvapakṣa → siddhānta steps from explicit
  cues in the reader and side-by-side view. Not browser-checked.
- [x] **Speaker-naming objection/reply cues** (October 2026): seven sampled patterns;
  Rāmānuja's detected cues 5 → 98.
- **Reviewed role annotations** for passages without printed cues.
- [x] **Claim check** (October 2026): optional per-sentence filter by the same local
  model; covered by deterministic tests, effect on answer quality not measured.
- [x] **Advaita passage benchmark** (October 2026): 50 AI-drafted, unreviewed questions
  with exact gold spans, frozen 30/20 split, first results published. **Human review
  of every question remains to be done.**
- [x] **Spelling tolerance** (October 2026): no change on either frozen benchmark;
  helps keyword ranking on a small spelling diagnostic set.
- [x] **Vichāra mode** (October 2026): short answer plus reflective questions; prompt
  guidance only.
- [x] **Reading paths** (October 2026): two curated paths with per-browser progress.
- [x] **Crest-Jewel of Wisdom** (October 2026): Johnston's Vivekacūḍāmaṇi and four
  more works, via a new HTML mode of the Sacred Texts adapter.
- [x] **Aṣṭāvakra Gītā** (October 2026): Richards' public-domain translation via a
  pinned single-text adapter.
- [x] **Yoga Vāsiṣṭha** (October 2026, opt-in): Mitra's translation from seven Gutenberg
  volumes; excluded from "All texts" because it measurably crowds retrieval.
- [x] **Madhavananda's Vivekacūḍāmaṇi** (October 2026): the 1921 scan OCRed locally
  with Chandra; English translation and notes kept, Sanskrit verses left out after
  Devanagari spot checks.
- [x] **Benchmark v2** (October 2026): 214 AI-drafted, unreviewed questions over every
  text, six types, per-type/per-text/failure breakdowns, an embedding model comparison
  (BGE-large best, not adopted), a real-model answer run (expected outcome 0.93, gold
  cited 0.66), an HTML report. **Human review of every question remains.**
- [x] **Śruti citation links** (October 2026): 1,609 printed references in Thibaut's
  translations resolved to the cited passages, 1,001 verified against the quoted words;
  "cited by" lists per verse and a most-cited ranking in Study.
- [x] **Ask about a passage; notes and highlights** (October 2026): a selection in the
  reader goes to the chat as a pointer only; highlights and notes stay in the browser,
  with Markdown/JSON export and import.
- [x] **OpenRouter free models** (October 2026): answers without a local model, `:free`
  models only, private books never sent; search stays local.
- [x] **Off-topic routing** (October 2026): a short model call declines questions about
  other fields before search; tuned on the v2 set.
- **More texts**: candidates and order in [docs/plans/texts.md](docs/plans/texts.md) (each
  text after its own rights check). See [docs/plans/ux.md](docs/plans/ux.md).
- **Hosted public site:** free, public-domain texts only; see the
  [hosted deployment plan](docs/plans/hosted-deployment.md). A local spike of the
  Turnstile check and atomic daily admission exists (October 2026); the cloud
  provider, Supabase port, export and deployment do not.

## Feature ideas (not started)

Candidates that would make Pramana distinctive as a study companion. Each builds on
what exists (citations, side by side, roles, notes, the benchmark) and keeps the rules:
chat answers only, sources in Study, nothing personal leaving the browser.

- **Mahāvākya explorer.** The four great sayings (*tat tvam asi*, *ahaṃ brahmāsmi*,
  *prajñānam brahma*, *ayam ātmā brahma*): where each occurs, every place Śaṅkara and
  Rāmānuja cite it (from the citation index), and their readings side by side.
- **Where the commentators part ways.** Rank Brahma Sūtras by how differently Śaṅkara
  and Rāmānuja treat them: different śruti cited, explicit refutations of the other's
  view, little shared vocabulary. A map of the real disputes, each opening side by side.
- **Verse with its commentaries.** An Upaniṣad or Gītā verse beside every commentary
  passage on it (Śaṅkara, Rāmānuja, Madhva once imported), using printed references, not
  guesses.
- **Argument graph.** Objection → reply chains from printed cues, linked to the
  scripture each side cites; follow one dispute across pages and works.
- **Translation comparison.** The same verse in every edition held (Müller, Thibaut's
  quotations, Johnston and Madhavananda for the Vivekacūḍāmaṇi), aligned only where
  printed numbers match.
- **Answer trail in Study.** For an answer opened in Study, each sentence beside the
  passage span that supports it (from the claim check), never shown in the chat itself.
- **Glossary review.** Spaced-repetition cards for the 110 terms and for verses the
  reader highlighted, kept in the browser.
- **Daily verse and vichāra.** One of the most-cited passages each day with a short
  reflective question, opening in the reader.
- **Study packs.** Export a reading path with its texts and the reader's notes as one
  Markdown or EPUB file for offline reading.
- **Answers without any model (extractive).** When no answer model is ready: rank the
  sentences of the retrieved passages against the question with the embedding model,
  keep 3–5 diverse ones, drop sentences in printed objection segments, and show them in
  reading order with natural attribution. Good for "what does X say about Y", poor for
  "why" or comparisons. Deferred (October 2026): in the chat it would need the "no
  excerpts" rule relaxed for this mode; the alternative is an answer card in Study search.
- **Sanskrit layer.** Devanagari verses from openly licensed sources, aligned by printed
  verse numbers, searchable by transliteration.

These are direction statements. Specify provider choices, interfaces, source rights,
and acceptance criteria when each milestone becomes active.

- **Answer-quality research:** stronger claim/evidence evaluation, unsupported-claim
  handling, and optional providers with explicit privacy and resource decisions.
- **Corpus expansion:** additional reusable texts, explicit edition selection,
  and source-specific adapters with complete provenance.
- **Multilingual and comparative research:** Sanskrit retrieval, translation
  alignment, and comparison across texts that preserves differing accounts.
