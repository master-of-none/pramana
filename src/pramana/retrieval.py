import re
import unicodedata

import numpy as np

from pramana.config import CHUNK_CONFIG
from pramana.corpus import Corpus
from pramana.embeddings import LocalEmbedder
from pramana.errors import PramanaError
from pramana.glossary import expansions
from pramana.models import Passage, SearchFilters, SearchHit, Strategy
from pramana.storage import filter_sql

# Old SBE transliteration writes k for c, kh for ch, g for j (Khândogya, Pragâpati,
# gñâna); readers type sh/ri for ś, ṣ, ṛ. Words sharing a key are spelling variants.
PHONETIC = [
    (r"[ck]h|c|q", "k"),
    (r"[jg]h|j", "g"),
    (r"sh|z|x", "s"),
    (r"([tdbp])h", r"\1"),
    (r"ri(?=[^aeiou]|$)", "r"),
    (r"w", "v"),
    (r"([aeiou])\1+", r"\1"),  # Vowels only: "later" must not become "latter".
]
# A thinker's name in a question means authorship, which answer scoping handles; it is
# not a word to look for (Śaṅkara's commentary rarely names Śaṅkara, Rāmānuja's does).
AUTHOR_NAMES = {
    "shankara",
    "sankara",
    "sankaracharya",
    "shankaracharya",
    "ramanuja",
    "ramanuga",
    "chinmayananda",
    "swarupananda",
    "barnett",
}


def fold_word(word: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", word.casefold()) if not unicodedata.combining(c)
    )


def phonetic(word: str) -> str:
    key = fold_word(word)
    for pattern, replacement in PHONETIC:
        key = re.sub(pattern, replacement, key)
    return key


def lexical_query(query: str, expand: bool = False, variants=None) -> str:
    """FTS OR-query; `expand` adds glossary synonyms (e.g. adhyasa -> superimposition).

    `variants` maps a folded query word to spellings of it found in the index.
    """
    if expand:
        query = " ".join([query, *expansions(query)])
    folded = "".join(
        c for c in unicodedata.normalize("NFKD", query) if not unicodedata.combining(c)
    )
    words = re.findall(r"[^\W_]+", folded, re.UNICODE)
    if variants:
        words += [v for w in words for v in variants(w.casefold())]
    return " OR ".join('"' + w + '"' for w in dict.fromkeys(words))


def fuse(rankings: list[list[str]], limit: int = 10) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, pid in enumerate(dict.fromkeys(ranking), 1):
            scores[pid] = scores.get(pid, 0.0) + 1 / (60 + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit]


class Retriever:
    def __init__(self, corpus: Corpus, *, embedder=None, spelling: bool = True):
        self.corpus = corpus
        self._embedder = embedder
        # Spelling-tolerant lexical search; dense retrieval is unaffected.
        self.spelling = spelling
        self._vocabulary: tuple[object, tuple[dict, dict]] | None = None

    def _spellings(self, db) -> tuple[dict[str, list[str]], dict[str, int]]:
        """Indexed words grouped by phonetic key, most frequent first; cached per index."""
        generation = self.corpus.store.get_meta("indexed_generation")
        if self._vocabulary and self._vocabulary[0] == generation:
            return self._vocabulary[1]
        groups: dict[str, list[str]] = {}
        counts: dict[str, int] = {}
        for term, docs in db.execute(
            "SELECT term, doc FROM passages_vocab WHERE length(term) >= 4 ORDER BY doc DESC, term"
        ):
            groups.setdefault(phonetic(term), []).append(term)
            counts[term] = docs
        self._vocabulary = (generation, (groups, counts))
        return groups, counts

    def variants(self, db):
        groups, counts = self._spellings(db)

        def lookup(word: str) -> list[str]:
            folded = fold_word(word)
            # Only words the library spells differently: absent or near-absent as typed.
            if (
                len(word) < 4
                or word.isdigit()
                or folded in AUTHOR_NAMES
                or counts.get(folded, 0) >= 2
            ):
                return []
            return [t for t in groups.get(phonetic(word), []) if t != fold_word(word)][:4]

        return lookup

    @property
    def embedder(self):
        if self._embedder is None:
            self._embedder = LocalEmbedder(self.corpus.home)
        return self._embedder

    def search(
        self,
        query: str,
        limit: int = 10,
        strategy: Strategy = "hybrid",
        filters: SearchFilters | None = None,
    ) -> list[SearchHit]:
        if not query.strip() or not lexical_query(query):
            raise PramanaError("Enter a question or search terms containing letters or numbers.")
        if len(query) > 2000 or not 1 <= limit <= 50:
            raise PramanaError("Queries must be at most 2000 characters; limit must be 1–50.")
        if strategy not in ("lexical", "dense", "hybrid"):
            raise PramanaError("Strategy must be lexical, dense, or hybrid.")
        store = self.corpus.store
        status = store.status()
        if status["state"] == "incompatible":
            raise PramanaError("Index is incompatible. Run: pramana index --rebuild")
        if not status["indexed"]:
            raise PramanaError("Search index is missing or stale. Run: pramana index")
        config = status["index"]
        if config["schema"] != 2 or config["chunking"] != CHUNK_CONFIG:
            raise PramanaError("Index is incompatible. Run: pramana index --rebuild")
        where, params = filter_sql(filters or SearchFilters())
        lexical, dense, payloads = [], [], {}
        with store.connect() as db:
            if strategy in ("lexical", "hybrid"):
                rows = db.execute(
                    "SELECT p.data, bm25(passages_fts) AS score FROM passages_fts "
                    "JOIN passages p ON p.id=passages_fts.id JOIN chapters c ON c.id=p.chapter_id "
                    "WHERE passages_fts MATCH ?" + where + " ORDER BY score, p.id LIMIT 50",
                    [
                        lexical_query(
                            query,
                            expand=True,
                            variants=self.variants(db) if self.spelling else None,
                        ),
                        *params,
                    ],
                ).fetchall()
                for row in rows:
                    p = Passage.model_validate_json(row[0])
                    payloads[p.id] = p
                    lexical.append((p.id, float(row[1])))
            if strategy in ("dense", "hybrid"):
                if config["embedding"] != self.embedder.identity:
                    raise PramanaError(
                        "Embedding model differs from index. Run: pramana index --rebuild"
                    )
                rows = db.execute(
                    "SELECT p.id, p.data, p.vector FROM passages p "
                    "JOIN chapters c ON c.id=p.chapter_id "
                    "WHERE 1=1" + where + " ORDER BY p.id",
                    params,
                ).fetchall()
                if rows:
                    matrix = np.stack([np.frombuffer(row[2], dtype=np.float32) for row in rows])
                    q = np.asarray(self.embedder.query(query), dtype=np.float32)
                    norm = np.linalg.norm(q)
                    if not np.isfinite(q).all() or norm == 0:
                        raise PramanaError("Embedding provider returned an invalid query vector.")
                    similarities = matrix @ (q / norm)
                    for i in np.argsort(-similarities, kind="stable")[:50]:
                        row = rows[int(i)]
                        payloads[row[0]] = Passage.model_validate_json(row[1])
                        dense.append((row[0], float(similarities[i])))
        if strategy == "hybrid":
            ranked = fuse([[p for p, _ in lexical], [p for p, _ in dense]], limit)
        else:
            ranked = (lexical if strategy == "lexical" else dense)[:limit]
        kind = {"lexical": "bm25", "dense": "cosine", "hybrid": "rrf"}[strategy]
        return [
            SearchHit(
                passage=payloads[pid],
                snippet=payloads[pid].text[:420],
                score=score,
                score_kind=kind,
            )
            for pid, score in ranked
        ]
