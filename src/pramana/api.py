from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pramana.corpus import Corpus
from pramana.errors import PramanaError
from pramana.models import SearchHit, SearchRequest
from pramana.retrieval import Retriever


def create_app(home: Path | None = None, *, retriever: Retriever | None = None) -> FastAPI:
    api = FastAPI(title="Pramana", version="0.1.0")
    corpus = retriever.corpus if retriever else Corpus(home)
    engine = retriever or Retriever(corpus)
    search_lock = Lock()

    @api.exception_handler(PramanaError)
    async def actionable_error(request, exc: PramanaError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @api.get("/api/status")
    def status():
        return corpus.store.status()

    @api.post("/api/search", response_model=list[SearchHit])
    def search(request: SearchRequest):
        with search_lock:
            return engine.search(**request.model_dump(exclude={"filters"}), filters=request.filters)

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
