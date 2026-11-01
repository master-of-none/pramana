# Where they part ways: the divergence map

The Study page **Where they differ** (`#/study/map`) maps the whole Brahma Sūtra and
shades each stretch by how differently Śaṅkara's and Rāmānuja's commentaries treat it.
It is a heuristic built from the texts' words and citations. It shows where to read,
not which reading is right, and it makes no claim about doctrine. Implementation:
[`src/pramana/divergence.py`](../../src/pramana/divergence.py); API: `GET /api/divergence`;
CLI: `pramana divergence --top 20` (add `--least` for the closest stretches).

## Units and pairing

Each cell is one page of Śaṅkara's commentary (Thibaut, SBE 34/38). A page begins at a
printed sūtra, and its unit runs to the sūtra before his next page in the same pāda
(the last page of a pāda runs to its end).

The two recensions divide and number some sūtras differently. In the real library,
only about two in five of Śaṅkara's sūtras match the sūtra Rāmānuja (Thibaut, SBE 48)
prints under the same number. Each page prints its sūtra first ("43. (The soul is) a
part of the Lord…"), so pairs are matched on those printed words:

| Pairing | Rule | Real library (1 Nov 2026) |
| --- | --- | --- |
| same sūtra | the sūtra lines with the same number share at least half their words: the overlap coefficient, with glosses in parentheses and a few function words removed | 226 |
| renumbered | otherwise, a line up to three numbers away in the same pāda shares at least three quarters of its words; that page is used, and the detail panel gives Rāmānuja's number | 138 |
| unconfirmed | neither: paired by number only, hatched on the map, and left out of the "most different" lists | 188 |

An unconfirmed pair may be two different sūtras, or the same sūtra that Thibaut
translated differently for each commentator. Śaṅkara's 2.1.14 and Rāmānuja's 2.1.15,
both on the *ārambhaṇa* text, are one such case: their sūtra lines share too few words
to confirm. The thresholds were set by reading samples of each class: every renumbered
sample was the same sūtra. A wider window (up to ten numbers) was tried and dropped,
because its matches were wrong. Rāmānuja's pages for a unit are those numbered within
its range, shifted by the renumbering, including topic pages such as "The Great
Pūrvapakṣa". The sūtra line is looked for after any preamble or heading, as on the
first page of a pāda.

## Signals

Each signal is higher when the two sides differ more.

| Signal | Measured as | Not measured when |
| --- | --- | --- |
| Scripture cited | 1 − similarity of the scripture each side cites: half the Jaccard overlap of cited verses, half that of the scripture chapters. A citation is a printed reference resolved by the [citation index](architecture.md#study-view-services) | one side or neither cites resolvable scripture |
| Wording | 1 − cosine similarity of TF-IDF vectors over the two texts: accent-folded words of three or more letters, with common stop words removed and IDF taken over every unit of both commentaries | one side has no matched page |
| Dispute terms | occurrences per 1,000 words in **Rāmānuja's** text of terms that name doctrines distinctive of Śaṅkara's reading (below) | Rāmānuja has no matched page |

Both commentaries are Thibaut's translations, so a low wording overlap reflects what is
discussed rather than two translators' styles. It is still wording, not meaning: two
pages can share words while disagreeing, or differ in words while agreeing.

The dispute terms, in Thibaut's spellings, matched as whole words with accents folded:
nescience; avidyā; māyā; illusion, illusory, illusive; sublation and its forms;
non-differenced or "devoid of all difference"; unreal, unreality, falsity;
superimposition, superimposed, adhyāsa; and mere, pure or non-differenced intelligence.
A term counts wherever it occurs. That is usually where Rāmānuja argues against the
doctrine, but the count cannot tell a refutation from a mention, and the page says
"names", not "refutes".

## Bands

Each signal is banded by what its values mean. On the real library, ranking alone tied
most units:
- **Scripture**, measured only where both sides cite resolvable scripture: half
  verse overlap, half overlap of the scripture chapters cited. Low is the same
  scripture, moderate is at least half shared, marked or high is less, and very high
  is nothing in common. 92 of the 193 units with citations on both sides share
  nothing.
- **Wording**: quintiles of its rank among the confirmed pairs, so misaligned pairs do
  not stretch the scale.
- **Dispute terms**: low when none of the terms occurs (499 of 552 units). The
  units that name them are split into quartiles, moderate to very high.

The **overall** band is the rounded mean of a unit's measured bands. No dispute term is
not evidence of agreement, so it counts only where terms occur. One kind of evidence
alone reaches "high" at most; "very high" needs two that agree. The "most different"
list ranks confirmed pairs by overall band, then by how many signals are high or very
high. Only bands are shown in Study, never the underlying numbers.

## Limits

- **Matching:** by the printed sūtra's words. A third of the units remain unconfirmed
  (above).
- **Scripture:** relies on references Thibaut printed and the index could resolve. Bare
  references and works outside the library are not counted.
- **Wording:** is not doctrine.
- **Dispute terms:** an explicit list. It catches named disputes only, and only on
  Rāmānuja's side.
- **Not reviewed:** no scholar has checked the bands. What a reading of the
  highest- and lowest-ranked stretches found is recorded in the
  [verification notes](../verification/verification.md).
