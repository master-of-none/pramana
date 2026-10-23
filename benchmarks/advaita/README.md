# Advaita passage-level benchmark

A retrieval benchmark over the public-domain Vedānta library (`--source advaita`):
does search put a passage that **contains the exact supporting text** in its top 10?
It is separate from the historical [chapter benchmark](../README.md) and from answer
evaluation; the numbers are not comparable with either.

```sh
uv run pramana evaluate-passages --output benchmarks/advaita/results.json
```

## Dataset rules

- [`questions.json`](questions.json) holds answerable questions, each with one or more
  gold spans: source identity (corpus, document, edition, language, book, chapter,
  sections), zero-based Python code-point `start`/`end` into the stored chapter text,
  and the exact `quote`. The harness refuses to run if any span no longer matches.
- A retrieved passage is relevant only when it is in the gold chapter **and contains a
  whole gold span**. Gold spans are independent of chunk IDs, so re-chunking cannot
  invent or erase evidence; a span crossing a chunk boundary simply cannot be hit.
- Search is unfiltered across the whole library, as in chat.
- **Split:** 30 `dev` and 20 `heldout` questions, frozen when the dataset was created
  (23 October 2026), before any ranking change. Tune only against `dev`; record any
  inspection or reuse of `heldout` questions here.
- `out_of_corpus` questions are diagnostics: the report records what was retrieved.
  Nearby material is expected; the engine has no abstention, and these are not scored.

## Review status

Every question was **drafted by an AI model (Claude) on 23 October 2026 and is
`unreviewed`**. Drafting meant reading the cited passage and checking that the span
answers the question, but no human reviewer has confirmed the questions, spans, or
that the spans are the best evidence. Until questions are marked `reviewed` with a
reviewer, results are engineering diagnostics, not validated measurements. To review
a question, read its span in the Study view (`#/study/read/<chapter>`), then set
`review.status` to `reviewed`, add `review.reviewed_by`, and note any change.

Private PDF editions are excluded: their text cannot be published in quotes.
