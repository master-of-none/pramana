# Advaita benchmark v2

214 questions over every text in the library, with exact gold spans. **Every question was
drafted by an AI model (Claude) from passages it read in the stored editions, and none
has been reviewed by a person** (`review.status` is `unreviewed` throughout). Results are
engineering diagnostics, not validated measurements.

| File | Contents |
| --- | --- |
| [questions.json](questions.json) | The dataset (version 2) |
| [results.json](results.json) | Retrieval, chat's "All texts" scope (opt-in works excluded) |
| [results-with-opt-in.json](results-with-opt-in.json) | Retrieval over the whole index |
| [models.json](models.json) | BGE-small, BGE-base and BGE-large on the same passages |
| [routing.json](routing.json) | The off-topic routing call, question by question |
| [answers.json](answers.json) | Every question through chat with `gemma4:e4b`: status, citations, timing, answer text |

## What is in it

| Type | Questions | What it tests |
| --- | ---: | --- |
| fact | 65 | a specific statement in one text |
| concept | 100 | a doctrine or idea, in the asker's words |
| comparison | 12 | Śaṅkara and Rāmānuja on one sūtra; both thinkers' gold spans are needed (`match: all`) |
| objection | 13 | an objection or opponent's view and its reply |
| followup | 8 | an elliptical question after a prior turn (`history`), with a reference `standalone` rewrite |
| out_of_corpus | 16 | not answerable from the library; 7 far off-topic, 4 other traditions, 5 near-domain works not in the library |

Each answerable question names its `text` group (eleven groups, from the Principal
Upaniṣads to Barnett), its `scope` (Yoga Vāsiṣṭha questions use the `yoga-vasistha`
chat scope, since that work is opt-in), the `thinkers` it is about, and the status chat
should return (`expect`). The 50 v1 questions are included unchanged, with their ids and
frozen splits (`origin: v1`); the new ones are `origin: v2`.

**Gold spans.** Each `gold` entry is a code-point interval `[start, end)` in one stored
chapter plus its quote; the evaluator refuses any span that no longer matches the text.
A retrieved passage counts only if it contains the whole span. A quote that occurs in
several chapters (a refrain) is kept as alternatives (`match: any`). Every span fits
inside one indexed passage (`uncontainable_spans` is empty).

**Split.** Frozen at creation, before any run: in file order, positions 2 and 4 of every
five new questions are heldout (79 heldout, 119 dev, including v1's 20 and 30).

**Known bias.** The new questions were written from exact sentences, so their wording
is closer to the text than v1's. On the same index, hybrid R@10 is 0.780 for the new
questions and 0.620 for v1's; keyword 0.770 and 0.560 (`by_origin` in the results).
Compare runs within a dataset version, never v2 totals against v1.

## Results (23 October 2026)

8,851 passages, BGE-small, chat's "All texts" scope.

| Method | Dev R@10 | Dev MRR | Heldout R@10 | Heldout MRR | All R@10 | All MRR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Hybrid | 0.761 | 0.537 | 0.709 | 0.565 | 0.740 | 0.548 |
| Keyword | 0.697 | 0.538 | 0.747 | 0.509 | 0.717 | 0.526 |
| Semantic | 0.538 | 0.386 | 0.557 | 0.372 | 0.545 | 0.380 |

Hybrid by type: fact 0.831, concept 0.680, objection 0.692, comparison 0.625, follow-up
1.000 with the reference rewrite (0.625 searched as typed). With the Yoga Vāsiṣṭha also
searched, hybrid R@10 is 0.717.

Each result file also records, per strategy: `by_type`, `by_text`, `by_origin`,
`failure_kinds` (where the top hit landed), `failure_depth` (gold at ranks 11–50, or not
in the top 50), `comparison_coverage` (both thinkers, one, neither), `followup_raw` and
`followup_rewritten`, and for every failure its best rank in the top 50 and the top
three documents.

## Running it

```sh
uv run pramana evaluate-passages --dataset benchmarks/advaita/v2/questions.json \
    --output benchmarks/advaita/v2/results.json            # about 2 minutes on CPU
uv run pramana evaluate-answers --route-only               # routing only, about 30 s
uv run python scripts/compare_embeddings.py --download     # once: BGE-base 438 MB, BGE-large 1.34 GB
uv run python scripts/compare_embeddings.py                # about 7 minutes with a GPU
uv run python scripts/plot_benchmarks.py                   # README charts
uv run python scripts/benchmark_report.py                  # .pramana/reports/benchmark.html
```

The gold spans resolve only against the exact editions in the
[source notices](../../../docs/notices/sources.md); importing a different edition makes
the evaluator refuse the dataset rather than score it.

**Answer-level evaluation.** `uv run pramana evaluate-answers` sends every question
through chat with the local Ollama model. Per question it records whether the status
matches the expectation, whether a cited passage contains a gold span, whether a
single-thinker question's evidence comes from that thinker, whether a comparison returns a
view for each thinker, and latency. `--limit N` answers the next N unfinished questions
and keeps the rest for the next run (`answers.partial.jsonl`); an Ollama outage stops the
run without recording an answer. These checks are structural; none of them establishes
that an answer is correct.

Run of 23 October 2026 (`gemma4:e4b`, RTX 5070 Ti, about 6 minutes of answering in
batches of 20, with the model unloaded between batches; on a 15 GB machine with zram,
keeping it loaded let swapped model pages fill memory):

| Group | Questions | Expected outcome | Gold cited | Named thinker's evidence | Median time |
| --- | ---: | ---: | ---: | ---: | ---: |
| All | 214 | 0.93 | 0.66 | 0.96 | 1.1 s |
| fact | 65 | 0.89 | 0.71 | 0.94 | 1.1 s |
| concept | 100 | 0.96 | 0.63 | 0.98 | 1.1 s |
| comparison | 12 | 1.00 | 0.54 | – | 2.4 s |
| objection | 13 | 0.77 | 0.62 | 0.97 | 1.1 s |
| followup | 8 | 1.00 | 0.88 | 0.83 | 1.8 s |
| out_of_corpus | 16 | 1.00 (all declined) | – | – | 0.1 s |

Comparisons returned a view for each thinker in 11 of 12. Fourteen answerable questions
were not answered (184 of 198 were): adv-061 and adv-068 by routing, and adv-055, 069, 078, 079, 088, 114,
123, 151, 153, 158 and 162 by the answer step (insufficient evidence); adv-135 failed
validation. By text, the Crest-Jewel is weakest (gold cited 0.39, 15 of 18 answered).

Found and fixed during the run: comparisons only produced per-thinker views when the
question said "compare", "differ" and the like (1 of 12 before; naming two thinkers now
suffices), and a retry after failed validation was not trimmed to the request budget
(adv-111 exceeded it). The affected 21 questions, and 8 that hit an Ollama outage, were
re-run; nothing else was.

## Reviewing questions

Reviewing a question means checking that the question is fair, that the gold span
answers it, and that no other passage answers it equally well (or adding that passage as
an alternative). Set `review` to `{"status": "reviewed", "reviewed_by": "<name>", …}`.
Results report the review counts, so reviewed and unreviewed runs stay distinguishable.
