"""Explicit real local-model diagnostics; never run in ordinary CI.

uv run python scripts/check_chat.py
Full responses/evidence remain under the ignored PRAMANA_HOME, not in benchmarks/.
"""

import asyncio
import json
import time
from pathlib import Path

from pramana import Answerer, ChatRequest, Corpus, Retriever
from pramana.answering import OllamaProvider
from pramana.config import data_dir
from pramana.models import ChatMessage


class CountedProvider(OllamaProvider):
    def __init__(self):
        super().__init__()
        self.calls = 0

    async def chat(self, messages, schema):
        self.calls += 1
        return await super().chat(messages, schema)


async def main():
    home = data_dir()
    corpus = Corpus(home)
    provider = CountedProvider()
    answerer = Answerer(Retriever(corpus), provider=provider)
    questions = json.loads(Path("benchmarks/chat-questions.json").read_text())["questions"]
    reports, completed = [], {}
    for question in questions:
        started, before = time.monotonic(), provider.calls
        report = {"id": question["id"], "question": question["question"]}
        try:
            history = []
            if follows := question.get("follows"):
                prior_question, prior_answer = completed[follows]
                history = [
                    ChatMessage(role="user", content=prior_question),
                    ChatMessage(role="assistant", content=prior_answer),
                ]
            result = await answerer.answer(
                ChatRequest(message=question["question"], history=history)
            )
            completed[question["id"]] = (question["question"], result.answer)
            found = {
                corpus.store.chapter(e.passage.chapter_id).document_id for e in result.evidence
            }
            report.update(
                response=result.model_dump(mode="json"),
                status_matches=result.status == question["expected_status"],
                source_reference_check=found == set(question["documents"]),
                manual_review_required=True,
            )
        except Exception as exc:
            report["error"] = str(exc)
        report.update(
            seconds=round(time.monotonic() - started, 2), model_calls=provider.calls - before
        )
        reports.append(report)
        (home / "chat-smoke.json").write_text(
            json.dumps(reports, ensure_ascii=False, indent=2) + "\n"
        )
        print({key: value for key, value in report.items() if key != "response"}, flush=True)
    print(f"Private full report: {home / 'chat-smoke.json'}", flush=True)
    if any(
        row.get("error") or not row.get("status_matches") or not row.get("source_reference_check")
        for row in reports
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
