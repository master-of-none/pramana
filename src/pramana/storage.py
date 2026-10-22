import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from pramana.errors import PramanaError
from pramana.models import Chapter, Passage, SearchFilters

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chapters(
    id TEXT PRIMARY KEY, corpus_id TEXT NOT NULL, book TEXT NOT NULL, chapter TEXT NOT NULL,
    edition TEXT NOT NULL, language TEXT NOT NULL, translator TEXT NOT NULL, data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS passages(
    id TEXT PRIMARY KEY, chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    data TEXT NOT NULL, vector BLOB NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS passages_fts USING fts5(
    id UNINDEXED, text, tokenize='unicode61 remove_diacritics 2'
);
"""


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            try:
                db.executescript(SCHEMA)
            except sqlite3.OperationalError as exc:
                raise PramanaError(
                    "SQLite with FTS5 is required; use the documented Python 3.12."
                ) from exc
            db.execute("INSERT OR IGNORE INTO meta VALUES ('generation', '0')")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def chapters(self) -> list[Chapter]:
        with self.connect() as db:
            rows = db.execute("SELECT data FROM chapters ORDER BY id").fetchall()
        return [Chapter.model_validate_json(row[0]) for row in rows]

    def chapter(self, chapter_id: str) -> Chapter:
        with self.connect() as db:
            row = db.execute("SELECT data FROM chapters WHERE id=?", (chapter_id,)).fetchone()
        if row is None:
            raise KeyError(chapter_id)
        return Chapter.model_validate_json(row[0])

    def passage(self, passage_id: str) -> Passage:
        with self.connect() as db:
            row = db.execute("SELECT data FROM passages WHERE id=?", (passage_id,)).fetchone()
        if row is None:
            raise KeyError(passage_id)
        return Passage.model_validate_json(row[0])

    def get_meta(self, key: str):
        with self.connect() as db:
            row = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def status(self) -> dict:
        with self.connect() as db:
            chapters = db.execute("SELECT COUNT(*) FROM chapters").fetchone()[0]
            passages = db.execute("SELECT COUNT(*) FROM passages").fetchone()[0]
            corpus = db.execute(
                "SELECT corpus_id, edition, translator, language, book, chapter FROM chapters"
            ).fetchall()
        from pramana.config import CHUNK_CONFIG

        config = self.get_meta("index_config")
        state = "ready"
        if not chapters:
            state = "empty"
        elif config and (config.get("schema") != 2 or config.get("chunking") != CHUNK_CONFIG):
            state = "incompatible"
        elif not passages or self.get_meta("indexed_generation") != self.get_meta("generation"):
            state = "stale"
        return {
            "state": state,
            "chapters": chapters,
            "passages": passages,
            "indexed": state == "ready",
            "index": self.get_meta("index_config"),
            "locations": [dict(row) for row in corpus],
        }


def filter_sql(filters: SearchFilters) -> tuple[str, list[str]]:
    clauses, values = [], []
    for key, value in filters.model_dump(exclude_none=True).items():
        if key == "document_ids":
            # An empty list matches nothing rather than everything.
            clauses.append(
                f"json_extract(c.data, '$.document_id') IN ({','.join('?' * len(value))})"
                if value
                else "0"
            )
            values.extend(value)
            continue
        column = (
            f"json_extract(c.data, '$.{key}')"
            if key in {"document_id", "author", "content_type"}
            else f"c.{key}"
        )
        if key == "content_type":
            column = f"COALESCE({column}, 'translation')"
        elif key == "author":
            column = f"COALESCE({column}, '')"
        clauses.append(f"{column}=?")
        values.append(value)
    return (" AND " + " AND ".join(clauses) if clauses else ""), values
