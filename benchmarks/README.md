# Initial engineering benchmark

Twenty questions cover all six books of Wilson's Vishnu Purana. Each gold label
includes corpus, document, edition, language, book/chapter/sections, original source
URL, and an exact supporting excerpt
checked against the acquired translation body. Evaluation rejects incomplete identities, empty evidence, missing/ambiguous sources,
and changed gold source text. These labels test retrieval and are not scholarly validation.

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
that chapter answers the question; the separate [Advaita passage-level
benchmark](advaita/README.md) uses exact gold spans.

`results.json` records the actual index/model configuration, per-question results,
and aggregates. This small, development-visible set is a smoke benchmark, not a
held-out measurement of general retrieval quality. Query phrasing and corpus
spelling can affect lexical and hybrid rankings. This benchmark does not measure generated-answer faithfulness or correctness.
[Chat verification](../docs/verification/chat-validation.md) records separate, small manual
diagnostics with the local answer model.

## Historical v0.1 run

| Method  | Recall@10 | MRR@10 |
| ------- | --------: | -----: |
| Lexical |    90.00% | 0.7406 |
| Dense   |   100.00% | 0.8026 |
| Hybrid  |    95.00% | 0.8250 |

Run on 14 October 2026 with the pinned BGE revision and chunking configuration
recorded in `results-baseline-v0.1.json`; 126 chapters, 587 passages.

## Combined-library run

`results.json` is the rerun after private commentary ingestion and source-aware
evaluation. It records checksums and resolved chapter identities as well as the
index configuration. Searches are filtered to the exact Wilson edition; lexical
IDF statistics still depend on the complete FTS corpus. Changed BM25/hybrid ranks
after adding books do not alone demonstrate a ranking improvement. No held-out
tuning or passage/answer-level performance claim is made.

| Combined-library method | Recall@10 | MRR@10 |
| ----------------------- | --------: | -----: |
| Lexical                 |    95.00% | 0.7583 |
| Dense                   |   100.00% | 0.8026 |
| Hybrid                  |   100.00% | 0.8306 |

Run on 14 October 2026: 2,313 chapter/page records and 3,367 passages overall;
126 Wilson chapters / 587 Wilson passages within the evaluated edition.

## Run of 23 October 2026

Same 20 questions, rerun because retrieval changed (glossary expansion, spelling
tolerance). The index now holds the whole library (1,677 chapters, 4,352 passages)
rather than Wilson alone; lexical BM25 statistics are computed over that larger
index, so the runs are not directly comparable and the cause of each change was not
isolated. Spelling tolerance on and off gave identical results here.

| Method  | Recall@10 | MRR@10 |
| ------- | --------: | -----: |
| Lexical |    95.00% | 0.7321 |
| Dense   |   100.00% | 0.8026 |
| Hybrid  |    95.00% | 0.8229 |
