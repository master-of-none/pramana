"""HTTP routes for excerpts: token-protected, and served alone by `serve --agent-only`.

The routes are off until a token is configured. They read stored text only; nothing here
loads the embedding model or calls a language model.
"""

import hmac
import logging
import os
import time
from collections import defaultdict, deque
from collections.abc import Mapping
from contextlib import AbstractContextManager
from datetime import date
from pathlib import Path
from threading import Lock
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from pramana import agent_excerpts as ex
from pramana.corpus import Corpus
from pramana.errors import PramanaError
from pramana.retrieval import Retriever, lexical_query

log = logging.getLogger("pramana.agent")
MIN_TOKEN = 32
Kind = Literal["verse", "passage", "sentence"]
Kinds = Annotated[list[Kind] | None, Query(description="verse, passage or sentence (repeatable)")]
Documents = Annotated[list[str] | None, Query(description="Document IDs (repeatable)")]
MinChars = Annotated[int, Query(ge=0)]
MaxChars = Annotated[int, Query(ge=1)]
Fmt = Annotated[Literal["json", "text", "markdown"], Query(alias="format")]


class AgentAuth:
    """Named bearer tokens and a per-token request limit. No tokens: the routes are disabled."""

    def __init__(
        self,
        tokens: Mapping[str, str] | None = None,
        *,
        limit: int = 60,
        window: float = 60.0,
        clock=time.monotonic,
    ):
        self.tokens = dict(tokens or {})
        for name, token in self.tokens.items():
            if len(token) < MIN_TOKEN:
                raise PramanaError(
                    f"The agent token {name!r} is shorter than {MIN_TOKEN} characters. "
                    "Create one with: pramana agent token"
                )
        self.limit, self.window, self.clock = limit, window, clock
        self.recent: dict[str, deque] = defaultdict(deque)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AgentAuth":
        env = os.environ if env is None else env
        tokens = {}
        if env.get("PRAMANA_AGENT_TOKEN"):
            tokens["default"] = env["PRAMANA_AGENT_TOKEN"].strip()
        for pair in filter(None, (env.get("PRAMANA_AGENT_TOKENS") or "").split(",")):
            name, _, token = pair.partition(":")
            if not name.strip() or not token.strip():
                raise PramanaError("PRAMANA_AGENT_TOKENS must look like name:token,name:token")
            tokens[name.strip()] = token.strip()
        return cls(tokens)

    @property
    def enabled(self) -> bool:
        return bool(self.tokens)

    def who(self, header: str | None) -> str:
        presented = (header or "").removeprefix("Bearer ").strip()
        matched = None
        for name, token in self.tokens.items():  # compare every token: no early exit on a match
            if hmac.compare_digest(presented.encode(), token.encode()):
                matched = name
        if matched is None:
            raise HTTPException(401, "Missing or wrong token.", {"WWW-Authenticate": "Bearer"})
        return matched

    def admit(self, name: str) -> None:
        now = self.clock()
        recent = self.recent[name]
        while recent and now - recent[0] >= self.window:
            recent.popleft()
        if len(recent) >= self.limit:
            wait = max(1, int(self.window - (now - recent[0])) + 1)
            raise HTTPException(429, "Too many requests.", {"Retry-After": str(wait)})
        recent.append(now)

    def require(self, request: Request) -> str:
        if not self.enabled:
            raise HTTPException(404, "Excerpt routes are off. Set PRAMANA_AGENT_TOKEN.")
        name = self.who(request.headers.get("authorization"))
        self.admit(name)
        log.info("excerpt request by %s: %s", name, request.url.path.split("/")[-1][:12])
        return name


def excerpt_router(
    corpus: Corpus,
    auth: AgentAuth,
    sources: dict[str, ex.Entry] | None = None,
    retriever: Retriever | None = None,
    lock: AbstractContextManager | None = None,
) -> APIRouter:
    """`retriever` serves `topic` only, and is created (not loaded) on first use."""
    router = APIRouter(prefix="/api/excerpts", dependencies=[Depends(auth.require)])
    state: dict = {"retriever": retriever}
    lock = lock or Lock()

    def pool() -> ex.Pool:
        found = ex.pool_for(corpus.store, sources)
        if not found.items:
            raise PramanaError(
                "No allowlisted texts are imported. Run: pramana corpus download --source "
                "advaita, then pramana ingest PATH."
            )
        return found

    def answer(found: ex.Pool, item: ex.Item, meta: dict, fmt: str, with_context: bool, **extra):
        data, body = ex.render(corpus.store, found, item, with_context=with_context)
        if fmt != "json":
            media = "text/markdown" if fmt == "markdown" else "text/plain"
            return PlainTextResponse(ex.message(data, body, fmt), media_type=media)
        return {**data, **extra, "pool": meta}

    def chosen(found: ex.Pool, kind, document, min_chars, max_chars) -> list[ex.Item]:
        try:
            items = ex.candidates(found, kind, document, min_chars, max_chars)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if not items:
            raise HTTPException(404, "No excerpt matches those filters.")
        return items

    @router.get("/sources")
    def sources_report():
        found = pool()
        return {"excerpts": len(found.items), "documents": ex.report(found)}

    @router.get("/today")
    def excerpt_of_the_day(
        kind: Kinds = None,
        document: Documents = None,
        min_chars: MinChars = 0,
        max_chars: MaxChars = 10**6,
        context: bool = False,
        fmt: Fmt = "json",
        tz: str = "UTC",
        on: Annotated[date | None, Query(alias="date")] = None,
        seed: Annotated[str, Query(max_length=80)] = "",
    ):
        found = pool()
        try:
            day = ex.day_in(tz, on)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        items = chosen(found, kind, document, min_chars, max_chars)
        item, meta = ex.today(found, items, day=day, seed=seed)
        return answer(found, item, meta, fmt, context, date=day.isoformat())

    @router.get("/random")
    def random_excerpt(
        kind: Kinds = None,
        document: Documents = None,
        min_chars: MinChars = 0,
        max_chars: MaxChars = 10**6,
        exclude: Annotated[list[str] | None, Query(max_length=100)] = None,
        topic: Annotated[str | None, Query(min_length=2, max_length=200)] = None,
        strategy: Annotated[Literal["hybrid", "lexical"], Query()] = "hybrid",
        context: bool = False,
        fmt: Fmt = "json",
    ):
        found = pool()
        items = chosen(found, kind, document, min_chars, max_chars)
        exclude = set(exclude or [])
        if topic is not None:
            if not lexical_query(topic):
                raise HTTPException(422, "The topic needs letters or numbers.")
            state["retriever"] = state["retriever"] or Retriever(corpus)
            try:
                with lock:
                    item, meta = ex.about(
                        found,
                        corpus.store,
                        state["retriever"],
                        topic,
                        items,
                        exclude,
                        strategy=strategy,
                    )
            except ex.NoMatch as exc:
                raise HTTPException(404, str(exc)) from exc
            return answer(found, item, meta, fmt, context, topic=topic, retrieval=strategy)
        if all(i.id in exclude for i in items):
            raise HTTPException(404, "Every matching excerpt is excluded.")
        item, meta = ex.pick_random(found, items, exclude)
        return answer(found, item, meta, fmt, context)

    @router.get("/{excerpt_id}")
    def excerpt_by_id(excerpt_id: str, context: bool = False, fmt: Fmt = "json"):
        found = pool()
        item = found.by_id.get(excerpt_id)
        if item is None:
            raise HTTPException(404, "No such excerpt; it may be outside the pool or changed.")
        meta = {"size": len(found.items), "version": ex.pool_version(list(found.items))}
        return answer(found, item, meta, fmt, context)

    return router


def create_agent_app(
    home: Path | None = None,
    *,
    auth: AgentAuth | None = None,
    sources: dict[str, ex.Entry] | None = None,
    retriever: Retriever | None = None,
) -> FastAPI:
    """Only the excerpt routes (and the OpenAPI schema): the app to put behind a tunnel."""
    auth = auth or AgentAuth.from_env()
    api = FastAPI(title="Pramana excerpts", version="0.1.0")
    corpus = retriever.corpus if retriever else Corpus(home)
    api.include_router(excerpt_router(corpus, auth, sources, retriever))

    @api.exception_handler(PramanaError)
    async def actionable_error(request, exc: PramanaError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    return api
