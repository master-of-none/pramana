import json
from pathlib import Path

import numpy as np
from pydantic import ValidationError

from pramana.chunking import chunk_chapter
from pramana.config import CHUNK_CONFIG, data_dir
from pramana.embeddings import LocalEmbedder
from pramana.errors import PramanaError
from pramana.models import Chapter
from pramana.storage import Store


class Corpus:
    def __init__(self, home: str | Path | None = None):
        self.home = Path(home) if home else data_dir()
        self.store = Store(self.home / "pramana.sqlite3")

    def import_jsonl(self, path: str | Path) -> int:
        records = []
        for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                records.append(Chapter.model_validate_json(line))
            except ValidationError as exc:
                raise PramanaError(
                    f"{path}:{line_number}: invalid chapter provenance or text: {exc}"
                ) from exc
        if not records:
            raise PramanaError("Import contains no chapters.")
        if len({c.id for c in records}) != len(records):
            raise PramanaError(
                "Import contains duplicate chapter identities; "
                "use unique document/location metadata."
            )
        changed = 0
        with self.store.connect() as db:
            for chapter in records:
                payload = chapter.model_dump_json()
                existing = db.execute(
                    "SELECT data FROM chapters WHERE id=?", (chapter.id,)
                ).fetchone()
                if existing and existing[0] == payload:
                    continue
                if existing:
                    db.execute(
                        "DELETE FROM passages_fts WHERE id IN "
                        "(SELECT id FROM passages WHERE chapter_id=?)",
                        (chapter.id,),
                    )
                    db.execute("DELETE FROM passages WHERE chapter_id=?", (chapter.id,))
                db.execute(
                    "INSERT OR REPLACE INTO chapters VALUES (?,?,?,?,?,?,?,?)",
                    (
                        chapter.id,
                        chapter.corpus_id,
                        chapter.location.book,
                        chapter.location.chapter,
                        chapter.edition,
                        chapter.language,
                        chapter.translator,
                        payload,
                    ),
                )
                changed += 1
            if changed:
                db.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='generation'")
        return changed

    def index(self, *, rebuild: bool = False, embedder=None) -> int:
        embedder = embedder or LocalEmbedder(self.home)
        config = {"schema": 1, "embedding": embedder.identity, "chunking": CHUNK_CONFIG}
        old = self.store.get_meta("index_config")
        if old is not None and old != config and not rebuild:
            raise PramanaError("Index configuration changed. Run: pramana index --rebuild")
        generation = self.store.get_meta("generation")
        if (
            old == config
            and self.store.get_meta("indexed_generation") == generation
            and not rebuild
        ):
            return 0
        chapters = self.store.chapters()
        if not chapters:
            raise PramanaError(
                "Corpus is empty. Run: pramana corpus download, then pramana ingest PATH"
            )
        passages = [p for ch in chapters for p in chunk_chapter(ch, embedder.tokenizer)]
        vectors = np.asarray(embedder.documents([p.text for p in passages]), dtype=np.float32)
        if vectors.ndim != 2 or len(vectors) != len(passages) or not np.isfinite(vectors).all():
            raise PramanaError(
                "Embedding provider returned invalid vectors; previous index was retained."
            )
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if (norms == 0).any():
            raise PramanaError(
                "Embedding provider returned zero vectors; previous index was retained."
            )
        vectors /= norms
        with self.store.connect() as db:
            current = json.loads(
                db.execute("SELECT value FROM meta WHERE key='generation'").fetchone()[0]
            )
            if current != generation:
                raise PramanaError("Corpus changed while indexing. Run pramana index again.")
            db.execute("DELETE FROM passages_fts")
            db.execute("DELETE FROM passages")
            db.executemany(
                "INSERT INTO passages VALUES (?,?,?,?)",
                [
                    (p.id, p.chapter_id, p.model_dump_json(), v.tobytes())
                    for p, v in zip(passages, vectors, strict=True)
                ],
            )
            db.executemany(
                "INSERT INTO passages_fts VALUES (?,?)", [(p.id, p.text) for p in passages]
            )
            db.executemany(
                "INSERT OR REPLACE INTO meta VALUES (?,?)",
                [
                    ("index_config", json.dumps(config, sort_keys=True)),
                    ("indexed_generation", json.dumps(generation)),
                ],
            )
        return len(passages)
