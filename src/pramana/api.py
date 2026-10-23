import asyncio
import json
import time
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from pramana.answering import Answerer, AnswerError, OpenRouterProvider
from pramana.citations import for_chapter
from pramana.citations import summary as citation_summary
from pramana.corpus import Corpus
from pramana.errors import PramanaError
from pramana.glossary import terms
from pramana.hosted import HostedGuard, Refused
from pramana.library import (
    catalogue,
    concept,
    concepts,
    neighbours,
    parallel,
    paths,
    role_spans,
    scopes,
)
from pramana.models import ChatRequest, ChatResponse, SearchHit, SearchRequest
from pramana.retrieval import Retriever


def create_app(
    home: Path | None = None,
    *,
    retriever: Retriever | None = None,
    answerer: Answerer | None = None,
    hosted: HostedGuard | None = None,
) -> FastAPI:
    """`hosted` puts bot verification and daily admission before every chat request."""
    api = FastAPI(title="Pramana", version="0.1.0")
    corpus = retriever.corpus if retriever else Corpus(home)
    engine = retriever or Retriever(corpus)
    search_lock = Lock()
    chat_engine = answerer or Answerer(engine, search_lock=search_lock)
    chat_slots = asyncio.Semaphore(1)

    async def guard(payload: ChatRequest, request: Request):
        """Hosted mode only: refuse before retrieval or any model call."""
        if hosted is None:
            return
        await hosted.check(
            request.client.host if request.client else "",
            request.headers.get("x-turnstile-token", ""),
            request.headers.get("x-request-id", ""),
            payload.model_dump(mode="json"),
        )

    readiness: dict = {}

    async def provider_ready() -> tuple[bool, str]:
        # A ready model is rechecked every 30 s; a missing one every 5 s, so starting
        # Ollama is noticed at once.
        now = time.monotonic()
        wait = 30 if readiness.get("value", (False, ""))[0] else 5
        if now - readiness.get("at", -60) > wait:
            check = getattr(chat_engine.provider, "ready", None)
            readiness.update(at=now, value=await check() if check else (True, ""))
        return readiness["value"]

    @api.get("/api/config")
    async def config():
        ready, reason = await provider_ready()
        # Public settings only; no secrets or quota internals.
        return {
            "hosted": hosted is not None,
            "turnstile_site_key": hosted.site_key if hosted else "",
            # Who writes answers, so the chat can say where questions go; never the key.
            "provider": {
                "name": "openrouter"
                if isinstance(chat_engine.provider, OpenRouterProvider)
                else "ollama",
                # True when questions leave this machine (OpenRouter, or a remote Ollama).
                "remote": bool(getattr(chat_engine.provider, "hosted", False)),
                "model": chat_engine.provider.model,
                # False: no answer model is usable; search and the Study view still are.
                "ready": ready,
                "reason": reason,
            },
        }

    @api.exception_handler(Refused)
    async def refused(request, exc: Refused):
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        return JSONResponse(
            status_code=exc.status_code, content={"detail": str(exc)}, headers=headers
        )

    @api.exception_handler(PramanaError)
    async def actionable_error(request, exc: PramanaError):
        return JSONResponse(
            status_code=exc.status_code if isinstance(exc, AnswerError) else 409,
            content={"detail": str(exc)},
        )

    @api.get("/api/status")
    def status():
        return corpus.store.status()

    @api.get("/api/glossary")
    def glossary():
        return [t.model_dump() for t in terms()]

    @api.post("/api/search", response_model=list[SearchHit])
    def search(request: SearchRequest):
        with search_lock:
            return engine.search(**request.model_dump(exclude={"filters"}), filters=request.filters)

    @api.post("/api/chat", response_model=ChatResponse)
    async def chat(payload: ChatRequest, request: Request):
        await guard(payload, request)

        async def work():
            async with chat_slots:
                return await chat_engine.answer(payload)

        async def disconnected():
            while not await request.is_disconnected():
                await asyncio.sleep(0.2)

        task = asyncio.create_task(work())
        watcher = asyncio.create_task(disconnected())
        try:
            done, _ = await asyncio.wait({task, watcher}, return_when=asyncio.FIRST_COMPLETED)
            if watcher in done:
                raise HTTPException(499, "Request cancelled")
            return await task
        finally:
            task.cancel()
            watcher.cancel()
            await asyncio.gather(task, watcher, return_exceptions=True)

    @api.post("/api/chat/stream")
    async def chat_stream(payload: ChatRequest, request: Request):
        """NDJSON: progress stages, then one validated answer or error event.

        Answer prose is sent only after validation, never as unchecked model tokens.
        """
        await guard(payload, request)  # Refusals are plain HTTP errors, before streaming.
        events: asyncio.Queue[dict | None] = asyncio.Queue()

        async def progress(stage):
            await events.put({"type": "stage", "stage": stage})

        async def work():
            try:
                async with chat_slots:
                    result = await chat_engine.answer(payload, progress)
                await events.put({"type": "answer", **result.model_dump(mode="json")})
            except PramanaError as exc:
                code = exc.status_code if isinstance(exc, AnswerError) else 409
                await events.put({"type": "error", "status": code, "detail": str(exc)})
            finally:
                await events.put(None)

        async def stream():
            # Starlette cancels this generator on disconnect, which cancels the model call.
            task = asyncio.create_task(work())
            try:
                while (event := await events.get()) is not None:
                    yield json.dumps(event, ensure_ascii=False) + "\n"
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    @api.get("/api/chapters/{chapter_id}")
    def context(chapter_id: str, passage_id: str | None = None):
        try:
            chapter = corpus.store.chapter(chapter_id)
            selected = corpus.store.passage(passage_id) if passage_id else None
        except KeyError as exc:
            raise HTTPException(404, "Chapter or passage not found; repeat your search.") from exc
        if selected and selected.chapter_id != chapter_id:
            raise HTTPException(422, "Passage does not belong to this chapter.")
        return {
            "id": chapter_id,
            "chapter": chapter,
            "selected": selected,
            # Study view only: explicit objection/reply cues and reading order.
            "roles": role_spans(chapter.text),
            **neighbours(corpus.store, chapter),
        }

    @api.get("/api/library")
    def library():
        return catalogue(corpus.store)

    @api.get("/api/concepts")
    def concept_list():
        return concepts()

    @api.get("/api/concepts/{key}")
    def concept_page(key: str):
        found = concept(corpus.store, key)
        if found is None:
            raise HTTPException(404, "No glossary concept by that name.")
        return found

    @api.get("/api/paths")
    def reading_paths():
        return paths(corpus.store)

    @api.get("/api/scopes")
    def chat_scopes():
        return scopes(corpus.store)

    @api.get("/api/citations")
    def citation_index():
        # Study view only: the most-cited scripture passages and how references resolved.
        return citation_summary(corpus.store)

    @api.get("/api/citations/{chapter_id}")
    def chapter_citations(chapter_id: str):
        try:
            corpus.store.chapter(chapter_id)
        except KeyError as exc:
            raise HTTPException(404, "Chapter not found.") from exc
        return for_chapter(corpus.store, chapter_id)

    @api.get("/api/parallel")
    def sutra_parallel(book: str, chapter: str, sutra: str):
        return parallel(corpus.store, book, chapter, sutra)

    static = Path(__file__).parent / "static"
    if (static / "assets").is_dir():
        api.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @api.get("/", include_in_schema=False)
    def index():
        if not (static / "index.html").exists():
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Web assets missing. Run: cd web && npm ci && npm run build",
                },
            )
        return FileResponse(static / "index.html")

    return api
