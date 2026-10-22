import asyncio
import json
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from pramana.answering import Answerer, AnswerError
from pramana.corpus import Corpus
from pramana.errors import PramanaError
from pramana.glossary import terms
from pramana.models import ChatRequest, ChatResponse, SearchHit, SearchRequest
from pramana.retrieval import Retriever


def create_app(
    home: Path | None = None,
    *,
    retriever: Retriever | None = None,
    answerer: Answerer | None = None,
) -> FastAPI:
    api = FastAPI(title="Pramana", version="0.1.0")
    corpus = retriever.corpus if retriever else Corpus(home)
    engine = retriever or Retriever(corpus)
    search_lock = Lock()
    chat_engine = answerer or Answerer(engine, search_lock=search_lock)
    chat_slots = asyncio.Semaphore(1)

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
    async def chat_stream(payload: ChatRequest):
        """NDJSON: progress stages, then one validated answer or error event.

        Answer prose is sent only after validation, never as unchecked model tokens.
        """
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
        return {"id": chapter_id, "chapter": chapter, "selected": selected}

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
