# Initial engineering benchmark

Twenty questions cover all six books of Wilson's Vishnu Purana. Each gold label
includes a book/chapter, original source URL, and an exact supporting excerpt
checked against the acquired translation body. Evaluation rejects missing or changed
gold source text. These labels test retrieval and are not scholarly validation.

Run after importing and indexing the complete corpus:

```sh
uv run pramana evaluate --output benchmarks/results.json
```

The command evaluates lexical BM25, local dense cosine search, and reciprocal rank
fusion independently. Each method retrieves 50 candidates and returns ten passages.
Metadata filters apply before ranking. RRF uses `sum(1 / (60 + rank))`.

**Recall@10** is the fraction of relevant gold chapters represented in the first ten
passages, averaged over questions. **MRR@10** averages the reciprocal rank of the
first passage from a relevant gold chapter, with zero for a miss. Multiple passages
from one chapter count once toward recall. Scores use passage rank, not a deduplicated
chapter rank. Chapter relevance does not establish that every retrieved passage in
that chapter answers the question; passage-level labels are a future improvement.

`results.json` records the actual index/model configuration, per-question results,
and aggregates. This small, development-visible set is a smoke benchmark, not a
held-out measurement of general retrieval quality. Query phrasing and corpus
spelling can affect lexical and hybrid rankings. No claim/citation correctness or
answer-faithfulness metric applies because this release does not generate answers.

## Recorded local run

| Method | Recall@10 | MRR@10 |
| --- | ---: | ---: |
| Lexical | 90.00% | 0.7406 |
| Dense | 100.00% | 0.8026 |
| Hybrid | 95.00% | 0.8250 |

Run on 14 October 2026 with the pinned BGE revision and chunking configuration
recorded in `results.json`; 126 chapters, 587 passages.
