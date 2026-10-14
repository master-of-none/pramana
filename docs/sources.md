# Source and model notices

## Vishnu Purana

- Translation: H. H. Wilson, *The Vishnu Purana*, John Murray, London, 1840.
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

## Embedding model

[`BAAI/bge-small-en-v1.5`](https://huggingface.co/BAAI/bge-small-en-v1.5) is distributed
under MIT. Pramana pins revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` and records
it with the index. It produces 384-dimensional vectors with a 512-token context.
Passage chunks are limited to 448 tokens. The recommended retrieval instruction is
prepended to queries, not passages. Embeddings indicate relevance, not factual truth.
