# Source and model notices

## Vishnu Purana

- Translation: H. H. Wilson, _The Vishnu Purana_, John Murray, London, 1840.
- Digitization: John Bruno Hare, Sacred Texts, February/March 2006.
- [Edition and production notes](https://archive.sacred-texts.com/hin/vp/)
- [Publication and source rights statement](https://archive.sacred-texts.com/hin/vp/vp000.htm)
- [Official plain-text gzip distribution](https://archive.sacred-texts.com/hin/vp/vp.txt.gz)

The archive identifies the 1840 translation as public domain in the US. This
notice records the source's statement; Pramana's Apache license applies to code,
not to third-party source material. Acquisition stores attribution, rights notes,
the archive's SHA-256, source chapter URLs, and a timestamp in the local receipt.
The entire source archive is cached locally and is not committed to this repository.
The parser fixture is a public-domain excerpt of Book I, Chapter I from that archive.

The default importer uses the archive's **plain-text distribution**, whose Sanskrit
names use an ASCII transliteration (e.g. `Paras'ara`). This differs from the Unicode
HTML distribution. Pramana preserves the acquired text's spelling; it does not
silently restore accents or reconstruct Sanskrit. Structured imports and the legacy
HTML parser preserve Unicode. The edition identity distinguishes the distributions.

Source decoding normalizes CRLF line endings to LF, removes page/note markup into
structured metadata, separates summaries/footnotes, and strips chapter-edge
whitespace. It otherwise preserves text, including source typos, spacing, and
missing-word placeholders. Passage offsets point into this immutable parsed chapter
text, not into the compressed archive or HTML bytes. The cached source and receipt
retain the acquisition evidence. Page-qualified note IDs preserve repeated note
numbers present in the source.

The manifest explicitly includes 126 chapters across six books (22, 16, 18, 24, 38,
8). Front matter, indexes, and the supplementary Daksha, topographical, and
Parashurama texts are excluded. The source's prose and reference metadata are not
treated as verified historical or theological claims.

## Brahma Sutra Bhashya (Thibaut)

- Translation: George Thibaut, _The Vedânta-Sûtras with the Commentary by
  Sankarâkârya_, Sacred Books of the East 34 (1890; the scan is of the 1904 printing)
  and 38 (1896), Clarendon Press.
- Digitization: scanned by Srinivasan Sriram (sripedia.org initiative); OCRed and
  proofed at Distributed Proofing (Juliet Sutherland, project manager); formatted and
  proofed at Sacred Texts by J. B. Hare.
- Title pages with rights statements: [SBE 34](https://archive.sacred-texts.com/hin/sbe34/sbe34000.htm),
  [SBE 38](https://archive.sacred-texts.com/hin/sbe38/sbe38000.htm).

Both title pages state: "This text is in the public domain worldwide. These files may
be used for any non-commercial purpose provided this notice of attribution is left
intact." Pramana records that statement and the attribution in every record; this is
not a legal opinion, and the cached pages are not committed or redistributed. Acquisition is explicit:
`pramana corpus download --source brahma-sutra` fetches the 552 sūtra pages listed in
[`brahmasutra-manifest.json`](../src/pramana/ingestion/brahmasutra-manifest.json)
at a polite rate into `PRAMANA_HOME/corpora/brahma-sutra-thibaut/html/`. Downloads
resume from cached pages; a page that is not a Thibaut SBE page (for example a
challenge or error page) is never cached. Each record keeps its page URL, SHA-256
and acquisition time. `chapters.jsonl` is published only after every page parses.
`--archive DIR` imports a directory of saved pages instead.

Each record is one Sacred Texts page: Bādarāyaṇa's sūtra in Thibaut's English
followed by Śaṅkara's commentary, cataloged as `mixed` with author `Sankaracharya`.
Location is adhyāya (book), pāda (chapter) and the first sūtra number printed on
the page (section); a page may continue with later sūtras. The site's index labels
`sbe38008.htm` and `sbe38172.htm` as II, 3, 6 and III, 3, 28, but those pages print
sūtras 7 and 29; the manifest uses the printed numbers and records the index label.
The parser fails if a page's first printed sūtra number differs from the manifest.
Thibaut's introduction, adhyāya summaries, title pages and Sanskrit word index are
excluded. Page anchors become page marks and each page's own footnotes become notes;
footnotes repeated from an earlier page are omitted. The legacy HTML transliteration
(`Vaisvânara`, `pûrvapakshin`) is preserved, not converted to IAST.

Checked on 22 October 2026 against a complete download: 552 records, about 1.67
million characters, 859 page marks and 610 of 611 referenced footnotes. The note
marked 226:2 on `sbe34104.htm` is not attached because of malformed source markup.
Thibaut's explicit role formulas ("The pûrvapakshin maintains", "To this we make the
following reply") occur 125 times on 93 pages and feed the
[objection/reply roles](chat.md#objectionreply-roles); most arguments are not
introduced by such formulas and remain unmarked.

## Embedding model

[`BAAI/bge-small-en-v1.5`](https://huggingface.co/BAAI/bge-small-en-v1.5) is distributed
under MIT. Pramana pins revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` and records
it with the index. It produces 384-dimensional vectors with a 512-token context.
Passage chunks are limited to 448 tokens. The recommended retrieval instruction is
prepended to queries, not passages. Embeddings indicate relevance, not factual truth.

## Private PDF editions and answer model

The three user-supplied editions are cataloged in [PDF ingestion](pdf-ingestion.md).
They include copyrighted commentary and scans with unestablished redistribution
permission. Originals and all derived full text stay under ignored `PRAMANA_HOME`;
they are not supplied with Pramana. Chinmaya Mission's
[published digital-content policy](https://eshop.chinmayamission.com/page/copyright-policy)
reserves rights in its digital content. No permission to redistribute these files
is implied by this implementation or its code license.

The Taittiriya scan is the 1901 **Book II, Ananda-valli, A: Brahmavidya Expounded**
volume, with commentaries of Sankaracharya, Suresvaracharya and Sayana translated
by A. Mahadeva Sastri. It is not cataloged as the full Upanishad. Shankara's Gita
edition identifies Alladi Mahadeva Sastry as translator and Samata Books' seventh
edition (1977); the Holy Geeta PDF identifies Swami Chinmayananda, with no verified
publication date. All three are indexed as mixed translation/commentary.

Ollama serves the user's installed `gemma4:e4b` by default. Model weights are not
bundled, pulled, or relicensed by Pramana. Consult the installed model's own license
and Ollama metadata before other uses. Prompts and evidence use the configured
Ollama endpoint; localhost is the default. See [chat behavior](chat.md).
