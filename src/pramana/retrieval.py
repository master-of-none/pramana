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


def lexical_query(query: str, expand: bool = False) -> str:
    """FTS OR-query; `expand` adds glossary synonyms (e.g. adhyasa -> superimposition)."""
    if expand:
        query = " ".join([query, *expansions(query)])
    folded = "".join(
        c for c in unicodedata.normalize("NFKD", query) if not unicodedata.combining(c)
    )
    words = re.findall(r"[^\W_]+", folded, re.UNICODE)
    return " OR ".join('"' + w + '"' for w in dict.fromkeys(words))


def fuse(rankings: list[list[str]], limit: int = 10) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, pid in enumerate(dict.fromkeys(ranking), 1):
            scores[pid] = scores.get(pid, 0.0) + 1 / (60 + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:limit]


class Retriever:
    def __init__(self, corpus: Corpus, *, embedder=None):
        self.corpus = corpus
        self._embedder = embedder

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
                    [lexical_query(query, expand=True), *params],
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
