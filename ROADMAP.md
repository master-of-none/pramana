# Pramana roadmap

Pramana's active milestone is **book-aware local chat**: private commentary ingestion
and concise grounded answers through the installed Ollama model. This brings forward
source identity, cache preservation, and index compatibility work needed for answers.
The passage-level reliability benchmark remains a separate subsequent milestone.

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
See [local verification](docs/verification.md) and [source notices](docs/sources.md).

## Active milestone: book-aware local chat

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

Delivered locally with [verification evidence](docs/verification.md). The eight
real-model diagnostics passed status/source checks; **manual comparison review found
an objection/reply interpretation error**. This remains an answer-quality limitation,
not a passed correctness check. No new GitHub CI run or scholarly verification is claimed.

**Completion gate:** all three coverage reports exist, local imports/indexing/search
work offline after setup, answers are checked across all four works and unsupported
questions, internal references resolve, deterministic regressions and browser/package
checks pass. Describe model/OCR limitations without claiming automatic verification.

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

- [ ] Annotate exact supporting text spans for 50 answerable questions across all
      six books. Record source identity, an exact quote, and zero-based Unicode
      code-point intervals in the stored chapter text.
- [ ] Freeze a split of 30 development questions and 20 held-out questions before
      tuning. Record annotation provenance and review status; document any subsequent
      inspection or reuse of held-out questions.
- [ ] Count a passage as relevant only when it contains an annotated supporting
      span from the correct source chapter. Keep gold spans independent of chunk IDs
      so chunking changes do not require inventing new evidence.
- [ ] Report passage-level Recall@10 and MRR@10 for lexical, dense, and hybrid
      retrieval, with per-question failures and index/model configuration.
- [ ] Keep passage-level results separate from the historical chapter-level
      benchmark; do not present the two as directly comparable measurements.
- [ ] Add ten separate out-of-corpus diagnostic questions and record retrieved
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
- [ ] Publish the reproducible passage-level benchmark with source identities,
      split membership, per-question results, and documented limitations.
- [ ] Update the quickstart, import/API documentation where interfaces changed,
      and verification notes with checks actually performed.

## Later milestones

These are direction statements. Specify provider choices, interfaces, source rights,
and acceptance criteria when each milestone becomes active.

- **Answer-quality research:** stronger claim/evidence evaluation, unsupported-claim
  handling, and optional providers with explicit privacy and resource decisions.
- **Corpus expansion:** additional reusable texts, explicit edition selection,
  and source-specific adapters with complete provenance.
- **Multilingual and comparative research:** Sanskrit retrieval, translation
  alignment, and comparison across texts that preserves differing accounts.
