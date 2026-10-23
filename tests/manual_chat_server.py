"""Deterministic localhost fixture for browser QA; never touches the user's library.

Run `uv run python tests/manual_chat_server.py`, then open http://127.0.0.1:8001.
Ask 'slow' to exercise Stop; ask 'fail' for a retryable error on the first attempt;
ask 'How do Shankara and Ramanuja differ?' for comparison cards; turn on Check to
see an unsupported sentence removed. The Study view has
two fixture Brahma Sutra commentaries (open #/study/sutra/1/1/1) with role cues,
footnotes, page marks and supplementary characters. Chat must still show no
HIDDEN_* metadata; Study may show it.

`--hosted` adds the hosted guards with Cloudflare's published Turnstile testing keys
(always pass; needs network for the widget) and a tiny quota: 3 questions a day per
visitor, 2 a minute, so the limit messages are easy to see.
"""

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from conftest import FakeEmbedder

from pramana import Answerer, Corpus, Retriever
from pramana.answering import AnswerError
from pramana.api import create_app
from pramana.models import Chapter, Location, Note, PageMark, Source, digest


class FixtureProvider:
    model = "browser-fixture"

    def __init__(self):
        self.failed = False

    async def chat(self, messages, schema):
        if "question" in schema["properties"]:
            return {"question": "How does action relate to understanding?", "document_ids": []}
        payload = json.loads(messages[-1]["content"])
        if "verdicts" in schema["properties"]:
            # Claim check: the fixture's sentence about the conversation is not in any passage.
            return {
                "verdicts": [
                    {
                        "id": s["id"],
                        "verdict": "unsupported" if "conversation" in s["text"] else "supported",
                    }
                    for s in payload["statements"]
                ]
            }
        question = payload["question"]
        if "perspectives" in schema["properties"]:
            by_author = {e["author"]: e["id"] for e in payload["evidence"] if e["author"]}
            return {
                "answer": "They read the same sūtra differently.",
                "status": "grounded",
                "evidence_ids": list(by_author.values())[:1],
                "perspectives": [
                    {
                        "thinker": author,
                        "view": f"{author} reads Brahman through **adhyāsa** and the Self.",
                        "evidence_ids": [ref],
                    }
                    for author, ref in by_author.items()
                ],
            }
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
        commentaries = [
            chapter.model_copy(
                update={
                    "corpus_id": "browser-bs",
                    "document_id": f"brahma-sutra-{author.lower()}-fixture",
                    "document": f"Brahma Sutra commentary ({author})",
                    "edition": f"Fixture edition {author}",
                    "author": author,
                    "content_type": "mixed",
                    "location": Location(book="1", chapter="1", sections=["1"]),
                    "text": text,
                    "pages": [
                        PageMark(offset=0, label="1"),
                        PageMark(offset=text.index("To this"), label="2"),
                    ],
                    "notes": [
                        Note(
                            id="1:1",
                            text="A fixture footnote.",
                            anchor_offset=text.index(" enquiry"),
                        )
                    ],
                    "source": chapter.source.model_copy(
                        update={"local_path": None, "url": "https://example.org/fixture"}
                    ),
                }
            )
            for author, text in (
                (
                    "Sankaracharya",
                    "1. Then therefore the enquiry into Brahman. 𑀅 Ātman.\n\n"
                    "The pûrvapakshin maintains that the Self is the body.\n\n"
                    "To this we make the following reply. The Self is the witness; adhyāsa "
                    "is superimposition.",
                ),
                (
                    "Ramanuja",
                    "1. Then therefore the enquiry into Brahman.\n\nTHE GREAT PÛRVAPAKSHA.\n\n"
                    "Difference is unreal.\n\nTo this we reply. Brahman is qualified by "
                    "real souls and matter; māyā is not illusion here.",
                ),
            )
        ]
        path = home / "fixture.jsonl"
        path.write_text("\n".join(c.model_dump_json() for c in [chapter, *commentaries]))
        corpus.import_jsonl(path)
        embedder = FakeEmbedder()
        corpus.index(embedder=embedder)
        retriever = Retriever(corpus, embedder=embedder)
        hosted = None
        if "--hosted" in sys.argv:
            from pramana.hosted import Admission, HostedGuard, Limits, TurnstileVerifier

            # Cloudflare's documented testing keys: the widget and siteverify always pass.
            hosted = HostedGuard(
                TurnstileVerifier("1x0000000000000000000000000000000AA"),
                Admission(home / "quota.sqlite3", "fixture-secret", Limits(10, 3, 2)),
                site_key="1x00000000000000000000AA",
            )
        uvicorn.run(
            create_app(
                retriever=retriever,
                answerer=Answerer(retriever, provider=FixtureProvider()),
                hosted=hosted,
            ),
            host="127.0.0.1",
            port=8001,
        )


if __name__ == "__main__":
    main()
