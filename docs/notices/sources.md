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
[`brahmasutra-manifest.json`](../../src/pramana/ingestion/brahmasutra-manifest.json)
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
[objection/reply roles](../guides/chat.md#objectionreply-roles); most arguments are not
introduced by such formulas and remain unmarked.

## Śrībhāṣya (Rāmānuja, Thibaut)

- Translation: George Thibaut, _The Vedânta-Sûtras with the Commentary by Râmânuja_,
  Sacred Books of the East 48, Clarendon Press, 1904.
- Digitization: scanned by Srinivasan Sriram (sripedia.org initiative); OCRed and
  proofed at Distributed Proofing (Juliet Sutherland, project manager); formatted and
  proofread at Sacred Texts by J. B. Hare.
- [Title page with rights statement](https://archive.sacred-texts.com/hin/sbe48/sbe48000.htm):
  "This text is in the public domain worldwide. This file may be used for any
  non-commercial purpose provided this notice is left intact."

`pramana corpus download --source sribhashya` fetches 571 HTML pages listed in
[`sribhashya-manifest.json`](../../src/pramana/ingestion/sribhashya-manifest.json)
with the same resumable, validated process as Śaṅkara's commentary. It is a separate
document (`brahma-sutra-ramanuja-thibaut`, author `Ramanuja`), never merged with
Śaṅkara's, so the two Viśiṣṭādvaita and Advaita readings of the same sūtras remain
distinct. Rāmānuja's topic pages within a sūtra (e.g. "The Great Pûrvapaksha" under
I, 1, 1) keep their printed title as a section and sit under that sūtra, as the
site's index nests them. Pāda heading pages carry no sūtra number. Thibaut's
introduction and the Sanskrit word index are excluded.

Checked on 22 October 2026 against a complete download: 571 records, about 1.6
million characters, 42 of 42 referenced footnotes, no navigation text or duplicated
paragraphs. Only five explicit role cues (role headings or formulas) occur, so most
of Rāmānuja's arguments reach the model unmarked.

## Sacred Texts plain-text editions

Each is fetched explicitly as the site's `NAME.txt.gz` plain-text distribution and
selected by a committed manifest in
[`src/pramana/ingestion/sacredtexts/`](../../src/pramana/ingestion/sacredtexts/).
`scripts/build_sacredtexts_manifests.py` regenerates the manifests from the site
indexes and title pages (explicit network use); it records each title page's rights
statement, which every imported record repeats.

| `--source` | Edition | Works | Content type | Rights statement (title page) |
| --- | --- | --- | --- | --- |
| `shankara-works` | S. Venkataramanan, _Select Works of Sri Sankaracharya_, 1921 | 8 (hymns and short treatises, under their printed English titles) | translation | public domain in the US, published before 1923 |
| `upanishads-1` | F. Max Müller, SBE 1, 1879 | Chandogya, Kena, Aitareya Aranyaka, Kaushitaki, Isa | translation | public domain, published before 1923 |
| `upanishads-2` | F. Max Müller, SBE 15, 1884 | Katha, Mundaka, Taittiriya, Brihadaranyaka, Svetasvatara, Prasna, Maitrayana | translation | public domain, published before 1923 |
| `gita-swarupananda` | Swami Swarupananda, _Srimad-Bhagavad-Gita_, 1909 | 18 chapters | mixed (translation with notes) | public domain in the US, published before 1923 |
| `minor-upanishads` | K. Narayanasvami Aiyar, _Thirty Minor Upanishads_, 1914 | 30 | translation | public domain in the US, published before 1923 |
| `brahma-knowledge` | L. D. Barnett, _Brahma-Knowledge_, 1911 | 1 | commentary (Part I), translation (Part II) | public domain in the US, published before 1923 |

The Select Works edition presents its works as Śaṅkara's; the record keeps
`Sankaracharya` as author and says "works attributed to" in the edition, without
judging authenticity. Upaniṣads have no author. Locations follow the printed
divisions: `I, 1` becomes book 1, chapter 1; single-level divisions (Khanda, Adhyâya,
Question, Gita chapter) become book 1, chapter N; single-page works are book 1,
chapter 1. The printed index label is kept as the section. Front matter, translators'
introductions and indexes are excluded. SBE 15 page 98 is excluded: the redactor
inserted R. E. Hume's 1921 translation of Bṛhadāraṇyaka VI, 4 there, which is a
different edition. The two Taittirīya editions (Max Müller's and Mahadeva Sastri's
Ānanda-valli) stay separate documents. Spellings, including Aiyar's unusual
transliteration (`Mukṭikopanishaḍ`), are preserved.

The parser checks the archive's section count against the manifest and publishes
`chapters.jsonl` only after every page parses. Checked on 22 October 2026 with
archives fetched that day:

| Source | Records | Characters | Footnotes (anchored) |
| --- | ---: | ---: | ---: |
| `shankara-works` | 8 | 139,783 | 190 (188) |
| `upanishads-1` | 222 | 348,994 | 711 (685) |
| `upanishads-2` | 108 | 350,012 | 1,075 (1,056) |
| `gita-swarupananda` | 18 | 111,243 | 398 (398) |
| `minor-upanishads` | 30 | 527,475 | 258 (258) |
| `brahma-knowledge` | 42 | 118,007 | 95 (85) |

Unanchored footnotes have no matching marker on their page in the source.

## Crest-Jewel of Wisdom (Johnston)

- Edition: Charles Johnston, _The Crest-Jewel of Wisdom and other writings of
  Śankarâchârya_, Theosophical University Press, Covina, first edition 1946.
- Digitization: scanned at Sacred Texts, November 2004; proofed by John Bruno Hare.
- [Title page with rights statement](https://archive.sacred-texts.com/hin/cjw/cjw00.htm):
  "This text is in the public domain in the US because the copyright was not renewed
  in a timely fashion as required by law at the time. These files may be used for any
  non-commercial purpose, provided this notice of attribution is left intact in all
  copies."

`--source crest-jewel` fetches 17 HTML pages listed in
[`sacredtexts/cjw.json`](../../src/pramana/ingestion/sacredtexts/cjw.json), using the same
page extraction as the Brahma Sūtra commentaries (cached, resumable, a page that is not
from this edition is never cached or parsed). Works carry the English and Sanskrit
titles printed on their pages: the Vivekacūḍāmaṇi (ten parts), Ātma Bodha, Tattva
Bodha, Vākya Sudhā and Siddhānta-Tattva-Vindu, attributed to Śaṅkara as the edition
presents them (the edition string says "works attributed to"). Johnston's own essays
("The Heritage of the Brâhmans", "The Teachings of Śankara", and the explanatory part
of "Śankara's Catechism") are recorded as commentary by Charles Johnston; his
introduction ("Śankara, the Teacher") and the appendix symposium on Śaṅkara's life
are excluded. One page anchor without a page number is skipped rather than guessed.
Checked on 23 October 2026: 17 records, about 181,000 characters, 145 page marks.

This is not Swami Madhavananda's 1921 translation. That edition is on
[archive.org](https://archive.org/details/vivekachudamanio00sankrich) (marked not in
copyright), but its OCR is too damaged to import without guessing words; it could be
re-OCRed locally once Tesseract is installed.

## Aṣṭāvakra Gītā (Richards)

- Translation: John Richards, _The Heart of Awareness: Ashtavakra Gita_, second edition,
  1996. The translator's introduction states: "The translation here is by John
  Richards, and is presented to the public domain with his affection."
- Copy used: the text file of an [archive.org item](https://archive.org/details/AshtavakraGita_201904)
  uploaded without uploader, date or rights metadata. The rights rest on the
  translator's own statement in the text, which the importer requires.

`--source ashtavakra-gita` uses a single-text adapter
([`textfile.py`](../../src/pramana/ingestion/textfile.py)) and a committed manifest
([`textfiles/ashtavakra.json`](../../src/pramana/ingestion/textfiles/ashtavakra.json))
that pins the file's SHA-256 (any other file is refused), requires the rights sentence,
and checks 20 chapter headings and 298 numbered verses. Cleanup is limited to removing
the exact running header "The Heart of Awareness: Ashtavakra Gita" and collapsing runs
of blank lines; the translator's introduction and contents list before chapter 1 are
excluded. Verse numbers printed at the end of each verse (e.g. `1.2`) stay in the text.
No author is recorded: the translator notes only that tradition ascribes the work to
the sage Aṣṭāvakra. Checked on 23 October 2026: 20 records, about 48,000 characters.

## Yoga Vāsiṣṭha (Mitra)

- Translation: Vihari-Lala Mitra, _The Yoga-Vásishtha Mahárámáyana of Válmíki_, four
  volumes (1891–1899); the Gutenberg transcriptions name the India: Low Price
  Publications printing. The edition attributes the work to Vālmīki; Pramana records
  no author and says "attributed to Valmiki by this edition".
- Copy used: seven Project Gutenberg HTML ebooks (71326, 71063, 71064, 71095, 46531,
  71248, 71249). Each states it is "for the use of anyone anywhere in the United
  States and most other parts of the world at no cost and with almost no restrictions
  whatsoever"; outside the US, check local laws. "Project Gutenberg" is a trademark:
  records keep only the text, not the Gutenberg licence or name.

**Opt-in:** `pramana corpus download --source yoga-vasistha` (not part of `advaita`;
about 6.2 million characters, more than the rest of the library together). The
adapter ([`gutenberg.py`](../../src/pramana/ingestion/gutenberg.py)) and manifest
([`gutenberg/yoga-vasistha.json`](../../src/pramana/ingestion/gutenberg/yoga-vasistha.json))
pin each volume's SHA-256 and the chapter count of each book; any other file or
structure is refused. Downloads use HTTP/1.1, because Gutenberg's HTTP/2 endpoint
truncated large files in testing.

A chapter starts at a heading element reading "CHAPTER …"; contents tables are not
headings, so transcriber's notes, front matter, contents, Mitra's introduction ("The
Yoga Philosophy") and the footnote sections are excluded; linked footnotes become
notes. Books: 1 Vairāgya (33), 2 Mumukṣu (20), 3 Utpatti (122), 4 Sthiti (62),
5 Upaśama (92), 6.1 Nirvāṇa first half (128), 6.2 Nirvāṇa second half (216); books
spanning two volumes continue their numbering. **`chapter` is the position within the
book, not the printed number**, because the transcription's printed numbers contain
misprints and repeats (e.g. two "CHAPTER CV." headings in 6.2, and Upaśama has no
"CHAPTER XV." heading, so that chapter's text is inside the record headed "CHAPTER XIV.";
Upaśama therefore has 92 records against its printed 93). The printed heading is kept
as the section label. Drop capitals are joined ("Om"). Printed page numbers become page
marks, not text: the `[Pg 816]` spans, the bare `287` page spans of volumes 71063 and
71248, and in volume 2.2 (71064) bare bracketed numbers of 30 or more (its pages run
404–982), while that volume's unlinked footnote markers `[1]`–`[23]` stay in the text.
Checked on 23 October 2026: 673 records, 6,175,179 characters, 56 notes, 2,829 page marks.

## Embedding model

[`BAAI/bge-small-en-v1.5`](https://huggingface.co/BAAI/bge-small-en-v1.5) is distributed
under MIT. Pramana pins revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` and records
it with the index. It produces 384-dimensional vectors with a 512-token context.
Passage chunks are limited to 448 tokens. The recommended retrieval instruction is
prepended to queries, not passages. Embeddings indicate relevance, not factual truth.

## Private PDF editions and answer model

The three user-supplied editions are cataloged in [PDF ingestion](../guides/pdf-ingestion.md).
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
Ollama endpoint; localhost is the default. See [chat behavior](../guides/chat.md).
