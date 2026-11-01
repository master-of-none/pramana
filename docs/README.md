# Pramana documentation

## Guides

- [Your first run](guides/first-run.md): from a fresh clone to your first question, with disk use, timings and fixes.
- [Quickstart](guides/quickstart.md): install, build the library, run the chat.
- [Building the library](guides/corpus.md): every source, download options, rights summary.
- [Chat and answers](guides/chat.md): local model settings, grounding, glossary,
  objection/reply roles, comparing thinkers, and limitations.
- [Private PDF books](guides/pdf-ingestion.md): local extraction and OCR of supplied PDFs.
- [Excerpts for agents](guides/agent-excerpts.md): send yourself a verse, passage or sentence on a
  schedule, with cron, OpenClaw, Hermes, Claude or Gemini.
- [Hermes on a VPS](guides/agent-excerpts-vps.md): the same, on a small server with Hermes, a
  free LLM provider and Telegram or WhatsApp.

## Reference

- [Architecture](reference/architecture.md): data model, ingestion, storage, indexing,
  retrieval, the answer pipeline, providers, the web app, invariants and where they are
  enforced.
- [HTTP API](reference/api.md): endpoints, request limits, response fields, streaming.
- [Divergence map](reference/divergence.md): how "Where they part ways" measures the
  two commentaries, and its limits.
- [Import format](reference/import-format.md): the provenance-bearing JSONL contract.

## Notices

- [Source and model notices](notices/sources.md): editions, rights statements,
  attribution, exclusions, and measured parse results for every source.
- [Font notices](notices/fonts.md): the bundled typefaces, their licences and the IAST
  coverage check.

## Verification

- [Local verification](verification/verification.md): checks actually performed.
- [Answer diagnostics](verification/chat-validation.md): real-model smoke checks and
  the recorded objection/reply interpretation failure.
- [v0.1 baseline](verification/verification-baseline-v0.1.md).
- The retrieval benchmark lives in [benchmarks/](../benchmarks/README.md).

## Plans

- [UX and feature plan](plans/ux.md): the Study view and the next features.
- [Hosted public deployment](plans/hosted-deployment.md): not deployed.
- [A public Pramana on a VPS](plans/vps-hosting.md): one server, SQLite, a cloud answer model.
- [Excerpt endpoint for agents](plans/agent-excerpts.md): a token-protected daily and random
  verse, passage or sentence API for OpenClaw, Hermes, Claude, Gemini and schedulers.
- [Texts to add](plans/texts.md): candidate texts, translations to verify, and priority.
- The project [roadmap](../ROADMAP.md) sequences milestones.

`docs/sources/` is not documentation: it is the drop folder for your private PDFs
(see its [README](sources/README.md)); PDFs placed there are ignored by Git.
