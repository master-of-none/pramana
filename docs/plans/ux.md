# UX and feature plan

Status: **planned 23 October 2026; partly implemented.** The
[roadmap](../../ROADMAP.md) records what is delivered. The Study view (library,
reader, side-by-side sūtras, evidence, search) and the theme/text-size controls
exist, as do chat scope chips, the Compare chip and answer depth.

## Principles

- A quiet reading room: answers first, generous typography, IAST and Devanagari
  rendered well, light and dark themes.
- **Chat stays answers-only.** Sources, passages and provenance appear only in a
  separate **Study view**. One "Read in the texts" action on an answer opens Study
  with that answer's evidence.
- Every surface works at 360 px wide, with a keyboard, and with reduced motion.
- Conversations stay in the tab's `sessionStorage`; reading progress, if added, is a
  per-browser convenience in `localStorage`. No accounts or server-side history.

## Chat

- Scope chips above the composer: All · Upaniṣads · Śaṅkara · Rāmānuja · Gītā,
  sent as an optional request scope mapped to existing document/author filters.
- A Compare chip that picks two thinkers and pre-fills a comparison question; the
  answer shows one card per thinker (already implemented, with authorship checks).
- Depth: Brief / Explain / In depth, changing only length guidance and output limits.
- Themed starter questions (the Self, Brahman, māyā, liberation, Śaṅkara vs Rāmānuja).
- Glossary hover cards on Advaita terms (implemented).

## Study view

- **Library:** tradition → work → division, with each edition's rights and attribution.
- **Reader:** page marks in the margin, footnotes as popovers, glossary terms, and
  passages with explicit objection/reply cues tinted and labelled. Offsets are
  Python code points, converted to UTF-16 in one tested helper.
- **Evidence:** the passages behind a chat answer, spans highlighted, opening in the reader.
- **Search:** lexical or hybrid search across the library.
- **Sūtra parallel:** Śaṅkara and Rāmānuja side by side for the same adhyāya, pāda
  and sūtra; Rāmānuja's topic pages listed under their sūtra.

## Features, in priority order

1. Sūtra parallel reader with attributed comparisons.
2. Concept pages: a glossary entry, where each text discusses it, and how Śaṅkara
   and Rāmānuja differ; growing into a concept graph.
3. Argument view: pūrvapakṣa → siddhānta sequences from explicit cues plus a reviewed
   annotation file. No model-guessed roles.
4. Measured trust: a 50-question Advaita passage-level benchmark with exact gold
   spans and a frozen 30/20 split, and an optional claim-check pass. Publish results.
5. Study paths (Ātmabodha → Aparokṣānubhūti → Gītā 2 → Kaṭha → Muṇḍaka → Brahma
   Sūtra I.1.1–4) with local reading progress.
6. Vichāra mode: guided, evidence-grounded questions instead of lectures.
7. Transliteration-tolerant search (legacy Sacred Texts spellings, Harvard-Kyoto,
   IAST); later, rights-checked Sanskrit mūla texts aligned only where printed
   divisions match.
8. More texts after individual rights checks: Vivekacūḍāmaṇi (Madhavananda 1921),
   Māṇḍūkya Kārikā, Upadeśasāhasrī, Pañcadaśī.
