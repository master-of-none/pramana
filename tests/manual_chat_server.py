"""Deterministic localhost fixture for browser QA; never touches the user's library.

Run `uv run python tests/manual_chat_server.py`, then open http://127.0.0.1:8001.
Ask 'slow' to exercise Stop; ask 'fail' for a retryable error on the first attempt.
"""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from conftest import FakeEmbedder

from pramana import Answerer, Corpus, Retriever
from pramana.answering import AnswerError
from pramana.api import create_app
from pramana.models import Chapter, Location, Source, digest


class FixtureProvider:
    model = "browser-fixture"

    def __init__(self):
        self.failed = False

    async def chat(self, messages, schema):
        if "question" in schema["properties"]:
            return {"question": "How does action relate to understanding?", "document_ids": []}
        question = json.loads(messages[-1]["content"])["question"]
        if "slow" in question.lower():
            await asyncio.sleep(20)
        if "fail" in question.lower() and not self.failed:
            self.failed = True
            raise AnswerError("The local model is temporarily unavailable. Try again.", 503)
        return {
            "answer": "Understanding grows through thoughtful action and patient inquiry. "
            "Ānanda and 𑀅 remain intact in this conversation.\n\n"
            "- Give the work your attention.\n- Reflect on what it teaches you.",
            "status": "grounded",
            "evidence_ids": ["E1"],
        }


def main():
    with TemporaryDirectory(prefix="pramana-browser-") as directory:
        home = Path(directory)
        corpus = Corpus(home)
        chapter = Chapter(
            corpus_id="browser",
            document_id="browser",
            document="HIDDEN_DOCUMENT_METADATA",
            edition="HIDDEN_EDITION_METADATA",
            translator="Fixture author",
            language="en",
            location=Location(book="1", chapter="1"),
            text="Understanding grows through thoughtful action and patient inquiry. Ānanda 𑀅.",
            source=Source(
                local_path="sources/pdfs/hidden.pdf",
                retrieved_at=datetime.now(UTC),
                checksum=digest("fixture"),
                rights="Original test fixture",
                attribution="Pramana tests",
            ),
        )
        path = home / "fixture.jsonl"
        path.write_text(chapter.model_dump_json())
        corpus.import_jsonl(path)
        embedder = FakeEmbedder()
        corpus.index(embedder=embedder)
        retriever = Retriever(corpus, embedder=embedder)
        uvicorn.run(
            create_app(
                retriever=retriever, answerer=Answerer(retriever, provider=FixtureProvider())
            ),
            host="127.0.0.1",
            port=8001,
        )


if __name__ == "__main__":
    main()
