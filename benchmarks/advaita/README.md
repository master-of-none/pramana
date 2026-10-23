# Advaita passage-level benchmark

A retrieval benchmark over the public-domain Vedānta library (`--source advaita`):
does search put a passage that **contains the exact supporting text** in its top 10?
It is separate from the historical [chapter benchmark](../README.md) and from answer
evaluation; the numbers are not comparable with either.

```sh
uv run pramana evaluate-passages --output benchmarks/advaita/results.json
uv run pramana evaluate-passages --include-opt-in --output benchmarks/advaita/results-with-opt-in.json
uv run python scripts/plot_benchmarks.py   # README charts from these files
```

By default the search scope matches chat's "All texts" (opt-in works such as the Yoga
Vāsiṣṭha excluded); `--include-opt-in` searches the whole index. `history.json` records
the hybrid results of each run as the library grew.

## Dataset rules

- [`questions.json`](questions.json) holds answerable questions, each with one or more
  gold spans: source identity (corpus, document, edition, language, book, chapter,
  sections), zero-based Python code-point `start`/`end` into the stored chapter text,
  and the exact `quote`. The harness refuses to run if any span no longer matches.
- A retrieved passage is relevant only when it is in the gold chapter **and contains a
  whole gold span**. Gold spans are independent of chunk IDs, so re-chunking cannot
  invent or erase evidence; a span crossing a chunk boundary simply cannot be hit.
- Search covers what chat's "All texts" covers (see above).
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

## Results: 23 October 2026

BGE-small (pinned revision) over the whole indexed library: 1,677 chapters, 4,352
passages. The dataset is unreviewed, so these are engineering diagnostics, not
validated measurements. Full per-question output: [`results.json`](results.json).

| Method  | Dev R@10 | Dev MRR@10 | Heldout R@10 | Heldout MRR@10 |
| ------- | -------: | ---------: | -----------: | -------------: |
| Lexical |    0.567 |      0.412 |        0.650 |          0.423 |
| Dense   |    0.400 |      0.339 |        0.450 |          0.333 |
| Hybrid  |    0.633 |      0.416 |        0.750 |          0.545 |

Dense retrieval alone is clearly weakest at this level. Of its 29 misses, the gold
chapter was in the top 10 for 6 (wrong passage), only the right work for 12, and
neither for 11. Out-of-corpus
diagnostics retrieved nearby material for all ten questions (e.g. a Brahma Sūtra page
for "What is the capital of Australia?"), as expected without abstention.

**Spelling tolerance.** Results above were identical with spelling tolerance off
(the pre-change baseline) and on. The first versions of the feature lowered some
scores; while diagnosing them, per-question differences for **all 50 questions,
including the 20 heldout ones, were inspected** on 23 October 2026. Two fixes
followed from that inspection (thinker names are not spelling-expanded; only words
absent or near-absent from the index get variants), so heldout results for this
feature are not untouched. No question gives a variant under the final rule, so the
frozen set cannot show a benefit. A separate four-question
[spelling diagnostic set](spelling.json), written after the baseline to probe the
feature, gave lexical MRR@10 0.65 → 1.00 and hybrid 0.80 → 0.81 (Recall@10 1.00 both
ways); see [`spelling-results.json`](spelling-results.json). Four questions are too few
to generalise from.

**After adding the Crest-Jewel edition** (same day, 4,469 passages): Recall@10 unchanged
for every method and split; hybrid dev MRR 0.416 → 0.414 and lexical heldout MRR
0.423 → 0.420, from changed keyword statistics. `results.json` is the earlier run.

**After also adding the Aṣṭāvakra Gītā** (4,507 passages): Recall@10 still unchanged
everywhere; hybrid dev MRR 0.431, lexical chapter-benchmark MRR 0.7338. These small MRR
shifts come from keyword statistics over a growing library, not from tuning.

**With the opt-in Yoga Vāsiṣṭha also indexed** (8,681 passages; the benchmark searches the
whole index unfiltered): hybrid dev R@10 0.633 → 0.600 and heldout 0.750 → 0.650;
lexical heldout 0.650 → 0.550; dense dev 0.400 → 0.367. Yoga Vāsiṣṭha passages took 16
of the 150 hybrid top-3 slots. This crowding is why it is opt-in and why chat's "All
texts" excludes it unless the question names it or its scope is chosen. The chapter
benchmark (edition-filtered) was unaffected.

**Fusion tuning (dev split only, 23 October 2026).** With opt-in works excluded as chat
does, the current hybrid (equal weights, RRF constant 60) gives dev R@10 0.667, MRR 0.412.
A grid of keyword weights 1–3 against semantic weight 1, and constants 10/30/60, gave
R@10 0.600–0.667 and MRR 0.382–0.418: every setting within one question of the current
one. No change was made; heldout questions were not used.
