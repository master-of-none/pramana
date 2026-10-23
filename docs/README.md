# Pramana documentation

## Guides

- [Your first run](guides/first-run.md): from a fresh clone to your first question, with disk use, timings and fixes.
- [Quickstart](guides/quickstart.md): install, build the library, run the chat.
- [Building the library](guides/corpus.md): every source, download options, rights summary.
- [Chat and answers](guides/chat.md): local model settings, grounding, glossary,
  objection/reply roles, comparing thinkers, and limitations.
- [Private PDF books](guides/pdf-ingestion.md): local extraction and OCR of supplied PDFs.

## Reference

- [Architecture](reference/architecture.md): data model, ingestion, storage, indexing,
  retrieval, the answer pipeline, providers, the web app, invariants and where they are
  enforced.
- [HTTP API](reference/api.md): endpoints, request limits, response fields, streaming.
- [Import format](reference/import-format.md): the provenance-bearing JSONL contract.

## Notices

- [Source and model notices](notices/sources.md): editions, rights statements,
  attribution, exclusions, and measured parse results for every source.

## Verification

- [Local verification](verification/verification.md): checks actually performed.
- [Answer diagnostics](verification/chat-validation.md): real-model smoke checks and
  the recorded objection/reply interpretation failure.
- [v0.1 baseline](verification/verification-baseline-v0.1.md).
- The retrieval benchmark lives in [benchmarks/](../benchmarks/README.md).

## Plans

- [UX and feature plan](plans/ux.md): the Study view and the next features.
- [Hosted public deployment](plans/hosted-deployment.md): not deployed.
- The project [roadmap](../ROADMAP.md) sequences milestones.

`docs/sources/` is not documentation: it is the drop folder for your private PDFs
(see its [README](sources/README.md)); PDFs placed there are ignored by Git.
