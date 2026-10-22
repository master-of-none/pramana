# Local answer diagnostics

Run the explicit, real-model smoke checks after preparing all four works and the
installed Ollama model:

```sh
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run python scripts/check_chat.py
```

The question set is [chat-questions.json](../../benchmarks/chat-questions.json). It
covers each supplied edition, the Wilson corpus, a follow-up, a two-commentator
comparison, an unsupported technical question, and a named work absent from the
library. Supporting review locations and conceptual review points are metadata;
private book text is not published with this benchmark. Page references are
physical PDF pages, not inferred verses or printed page numbers.

The script records full responses and supplied evidence only in
`PRAMANA_HOME/chat-smoke.json`. It checks answer status and exact source membership;
**these are not measures of correctness**. Manual review must compare actual claims
with supplied passages and the indicated originals, especially where a commentary
presents an objection before its conclusion. No statistical accuracy, comprehensive
scholarly review, or reliable automatic abstention is claimed.

See [local verification](verification.md) for the measured run, reviewed outcomes,
and extraction limits. The historical chapter retrieval benchmark is separate.

## Recorded run — 14 October 2026

Ollama `gemma4:e4b`, installed ID `c6eb396dbd59`, with the default local provider
settings. All eight requests completed and matched expected status/source membership.
Those checks are **structural results, not eight correct answers**. Times in this
run ranged from 15.87–27.48 seconds; follow-up rewriting used two calls, all other
questions used one. The bounded repair path was covered by deterministic tests;
the final diagnostic did not require regeneration.

| Question                         | Manual source review outcome                                                                                                                                                                                                                 |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Chinmayananda / detachment       | Main explanation matches necessary action and relinquishing ego/result attachment. Some phrasing remains broad and repetitive.                                                                                                               |
| Follow-up / work                 | Resolves the reference to detachment and retrieves fresh Chinmayananda material; the explanation stays fairly abstract rather than giving concrete workplace examples.                                                                       |
| Shankara / action and liberation | Identifies renunciation/knowledge rather than action alone. Its strong wording needs the surrounding distinction between classes of aspirants.                                                                                               |
| Taittiriya / liberated soul      | Matches the conclusion that the liberated soul is not distinct from Brahman; checked against the scan at physical page 50.                                                                                                                   |
| Wilson / rain                    | Matches Book V, Chapter XI: Govarddhana shelters the cowherds from Indra's storm.                                                                                                                                                            |
| Kubernetes                       | Clear insufficient-evidence admission, no technical instructions.                                                                                                                                                                            |
| Absent Gospel of Matthew         | Clear insufficient-evidence admission, no answer from outside knowledge.                                                                                                                                                                     |
| Two-commentator comparison       | **Semantic failure remains:** it discusses both thinkers, but reverses the relevance of Arjuna's question from the questioner's standpoint in an objection/reply passage at physical page 170. Correct source membership did not catch this. |

The comparison failure persists despite an explicit prompt distinguishing objections
from conclusions. The supplied page also ends mid-argument, and noisy OCR labels
can make discourse roles harder to follow. A source list or valid internal mapping
would not fix this interpretation. Treat comparative doctrinal answers as material
for review; further answer-quality/context evaluation is roadmap work. The current
release is a usable local conversational interface, **not a claim verifier**.

Earlier checks also exposed omitted/inconsistent evidence fields and a machine
status token rendered as prose. Required evidence fields, allowed-ID schemas, one
bounded repair attempt, and normalized insufficient-evidence replies address those
response-shape problems. They do not solve the remaining semantic error.
