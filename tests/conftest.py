import hashlib
import re
from datetime import UTC, datetime

import numpy as np
import pytest

from pramana.models import Chapter, Location, Source, digest


class WordTokenizer:
    """Offline tokenizer fixture: each non-whitespace word is a token."""

    def __call__(self, text, **kwargs):
        return {"offset_mapping": [m.span() for m in re.finditer(r"\S+", text)]}

    def encode(self, text, **kwargs):
        return re.findall(r"\S+", text)


class FakeEmbedder:
    tokenizer = WordTokenizer()
    identity = {"model": "test-only-bag-of-words", "revision": "1"}

    def documents(self, texts):
        vectors = np.zeros((len(texts), 128), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in re.findall(r"\w+", text.lower()):
                slot = int(hashlib.sha256(word.encode()).hexdigest()[:8], 16) % 128
                vectors[row, slot] += 1
        return vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9)

    def query(self, text):
        return self.documents([text])[0]


@pytest.fixture
def embedder():
    return FakeEmbedder()


@pytest.fixture
def make_chapter():
    def make(
        text="Vishnu preserves the universe. Brahma creates the world.", book="1", chapter="1"
    ):
        return Chapter(
            corpus_id="fixture",
            document_id="fixture",
            document="Fixture text",
            edition="Fixture edition",
            translator="Test translator",
            language="en",
            location=Location(book=book, chapter=chapter),
            text=text,
            source=Source(
                url="https://example.org/source",
                retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
                checksum=digest(text),
                rights="Test fixture",
                attribution="Pramana tests",
            ),
        )

    return make


@pytest.fixture
def indexed(tmp_path, make_chapter, embedder):
    from pramana import Corpus

    corpus = Corpus(tmp_path / "library")
    chapters = [
        make_chapter(),
        make_chapter("Krishna shelters the cattle beneath the mountain.", book="5"),
    ]
    source = tmp_path / "import.jsonl"
    source.write_text("\n".join(c.model_dump_json() for c in chapters), encoding="utf-8")
    corpus.import_jsonl(source)
    corpus.index(embedder=embedder)
    return corpus
