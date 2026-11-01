import datetime
import json
from pathlib import Path
from typing import Annotated

import typer

from pramana.config import data_dir
from pramana.corpus import Corpus
from pramana.embeddings import setup_model
from pramana.errors import PramanaError
from pramana.models import SearchFilters
from pramana.retrieval import Retriever

app = typer.Typer(help="Pramana — local retrieval with verifiable sources.", no_args_is_help=True)
corpus_app = typer.Typer(help="Acquire source editions explicitly.")
model_app = typer.Typer(help="Prepare the local embedding model; list free answer models.")
agent_app = typer.Typer(help="Set up the excerpt routes for agents and schedulers.")
excerpt_app = typer.Typer(help="Print an excerpt (verse, passage or sentence) without HTTP.")
app.add_typer(corpus_app, name="corpus")
app.add_typer(model_app, name="model")
app.add_typer(agent_app, name="agent")
app.add_typer(excerpt_app, name="excerpt")


def fail(exc: Exception):
    typer.echo(f"Error: {exc}", err=True)
    raise typer.Exit(1)


@model_app.command()
def setup():
    """Download the pinned model once; subsequent operations stay offline."""
    try:
        typer.echo(str(setup_model(data_dir())))
    except Exception as exc:
        fail(exc)


@model_app.command("free")
def free_models():
    """List OpenRouter's free models that support JSON-schema output (reads its public list)."""
    import httpx

    try:
        data = httpx.get("https://openrouter.ai/api/v1/models", timeout=30).json()["data"]
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        fail(PramanaError(f"Could not read OpenRouter's model list: {exc}"))
    usable = [
        m
        for m in data
        if m["id"].endswith(":free")
        and "structured_outputs" in (m.get("supported_parameters") or [])
    ]
    for m in sorted(usable, key=lambda m: -(m.get("context_length") or 0)):
        typer.echo(f"{m['id']}  (context {m.get('context_length') or '?':,})")
    if not usable:
        typer.echo("No free model currently offers structured output.")
    typer.echo("Choose one with PRAMANA_CHAT_MODEL=<id> and PRAMANA_PROVIDER=openrouter.")


# Public-domain editions; Sacred Texts plain-text books are keyed by their manifest ID.
SOURCES = {
    "vishnu-purana": "Wilson's Vishnu Purana (1840)",
    "brahma-sutra": "Sankara's Brahma Sutra commentary, Thibaut (SBE 34, 38)",
    "sribhashya": "Ramanuja's Brahma Sutra commentary, Thibaut (SBE 48)",
    "shankara-works": "Select Works of Sankaracharya, Venkataramanan (1921)",
    "upanishads-1": "Upanishads Part 1, Max Muller (SBE 1)",
    "upanishads-2": "Upanishads Part 2, Max Muller (SBE 15)",
    "gita-swarupananda": "Bhagavad Gita with commentary, Swarupananda (1909)",
    "minor-upanishads": "Thirty Minor Upanishads, Narayanasvami Aiyar (1914)",
    "brahma-knowledge": "Brahma-Knowledge, Barnett (1911)",
    "crest-jewel": "Crest-Jewel of Wisdom (Vivekachudamani) and other works, Johnston (1946)",
    "ashtavakra-gita": "Ashtavakra Gita, The Heart of Awareness, Richards (1996)",
    "yoga-vasistha": "Yoga Vasishtha, Mitra (1891-99), 7 Gutenberg volumes; opt-in, large",
    "vivekachudamani": "Vivekachudamani, Madhavananda (1921) scan; OCR with Chandra (GPU)",
}
# Single plain-text editions keyed by their manifest ID in ingestion/textfiles/.
TEXT_FILES = {"ashtavakra-gita": "ashtavakra-richards"}
SACRED_TEXTS = {
    "shankara-works": "wos",
    "upanishads-1": "sbe01",
    "upanishads-2": "sbe15",
    "gita-swarupananda": "sbg",
    "minor-upanishads": "tmu",
    "brahma-knowledge": "brk",
    "crest-jewel": "cjw",
}
# The Yoga Vasishtha is opt-in: it would double the library and crowd general answers.
# The Vivekachudamani scan needs an explicitly installed OCR model, so it is separate.
ADVAITA = [s for s in SOURCES if s not in {"vishnu-purana", "yoga-vasistha", "vivekachudamani"}]
# Just the editions the excerpt API may serve (excerpt_sources.json): enough for a small server
# that never answers questions. It leaves out the Brahma Sutra commentaries.
EXCERPTS = [
    "upanishads-1",
    "upanishads-2",
    "gita-swarupananda",
    "shankara-works",
    "ashtavakra-gita",
    "crest-jewel",
    "brahma-knowledge",
    "minor-upanishads",
    "vishnu-purana",
]
GROUPS = {"advaita": ADVAITA, "excerpts": EXCERPTS}


def acquire_source(source: str, archive: Path | None, offline: bool) -> Path:
    if source == "vivekachudamani":
        from pramana.ingestion.pdf import acquire_public

        return acquire_public(data_dir(), source, archive, offline=offline)
    if source == "yoga-vasistha":
        from pramana.ingestion.gutenberg import acquire

        return acquire(data_dir(), "yoga-vasistha-mitra", archive, offline=offline)
    if source in TEXT_FILES:
        from pramana.ingestion.textfile import acquire

        return acquire(data_dir(), TEXT_FILES[source], archive, offline=offline)
    if source in SACRED_TEXTS:
        from pramana.ingestion.sacredtexts import acquire

        return acquire(data_dir(), SACRED_TEXTS[source], archive, offline=offline)
    if source in {"brahma-sutra", "sribhashya"}:
        from pramana.ingestion.brahmasutra import acquire

        volume = "shankara" if source == "brahma-sutra" else "ramanuja"
        return acquire(data_dir(), archive, offline=offline, volume=volume)
    from pramana.ingestion.vishnu import acquire

    return acquire(data_dir(), archive, offline=offline)


@corpus_app.command()
def download(
    archive: Annotated[
        Path | None,
        typer.Option(help="A saved archive (.txt.gz), or a directory of saved HTML pages"),
    ] = None,
    offline: bool = False,
    source: Annotated[
        str,
        typer.Option(
            help="One of: "
            + ", ".join(SOURCES)
            + "; `advaita` for every Vedanta source; or `excerpts` for what the excerpt API uses"
        ),
    ] = "vishnu-purana",
):
    """Download/cache complete public-domain editions and emit validated JSONL."""
    if source not in GROUPS and source not in SOURCES:
        fail(
            PramanaError(
                f"Unknown --source {source!r}. Choose: {', '.join(SOURCES)}, {', '.join(GROUPS)}."
            )
        )
    if source in GROUPS and archive:
        fail(PramanaError(f"--archive applies to one source; omit it with --source {source}."))
    try:
        for name in GROUPS.get(source, [source]):
            typer.echo(str(acquire_source(name, archive, offline)))
    except (PramanaError, OSError) as exc:
        fail(exc)


@corpus_app.command("import-books")
def import_local_books(source_directory: Path = Path("docs/sources")):
    """Preserve the three supplied PDFs locally, extract/OCR, report coverage, and import."""
    from pramana.ingestion.pdf import import_books

    try:
        typer.echo(json.dumps(import_books(data_dir(), source_directory), indent=2))
    except (PramanaError, OSError, ValueError) as exc:
        fail(exc)


@app.command()
def ingest(path: Path):
    """Import chapters from provenance-bearing JSONL; unchanged records are skipped."""
    try:
        typer.echo(f"Imported {Corpus().import_jsonl(path)} new or changed chapters.")
    except (PramanaError, OSError) as exc:
        fail(exc)


@app.command()
def index(rebuild: bool = False):
    """Chunk and embed the corpus locally; atomically replace the search index."""
    try:
        typer.echo(f"Indexed {Corpus().index(rebuild=rebuild)} passages (0 means already current).")
    except PramanaError as exc:
        fail(exc)


@app.command()
def search(
    query: str,
    limit: int = 10,
    strategy: str = "hybrid",
    book: str | None = None,
    chapter: str | None = None,
    corpus: str | None = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
):
    """Find source passages. Scores are retrieval relevance, not factual confidence."""
    try:
        hits = Retriever(Corpus()).search(
            query,
            limit=limit,
            strategy=strategy,
            filters=SearchFilters(book=book, chapter=chapter, corpus_id=corpus),
        )
        if json_output:
            typer.echo(json.dumps([h.model_dump() for h in hits], ensure_ascii=False, indent=2))
        else:
            for i, hit in enumerate(hits, 1):
                typer.echo(
                    f"\n{i}. {hit.passage.citation.label}\n{hit.snippet}\n"
                    f"{hit.passage.citation.source_url}\n"
                    f"Retrieval relevance: {hit.score:.5f} ({hit.score_kind})"
                )
            if not hits:
                typer.echo("No matching passages. Try broader terms or filters.")
    except PramanaError as exc:
        fail(exc)


@app.command()
def status():
    """Show corpus and index status."""
    typer.echo(json.dumps(Corpus().store.status(), indent=2))


@app.command()
def evaluate(questions: Path = Path("benchmarks/questions.json"), output: Path | None = None):
    """Report Recall@10 and MRR@10 for each retrieval strategy."""
    from pramana.evaluation import evaluate as run

    try:
        report = json.dumps(run(Retriever(Corpus()), questions), indent=2, ensure_ascii=False)
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(report + "\n", encoding="utf-8")
        typer.echo(report)
    except (PramanaError, OSError) as exc:
        fail(exc)


@app.command("evaluate-passages")
def evaluate_passages(
    dataset: Path = Path("benchmarks/advaita/questions.json"),
    output: Path | None = None,
    include_opt_in: bool = False,
):
    """Passage-level Recall@10 and MRR@10 against exact gold spans, per split."""
    from pramana.evaluation import evaluate_passages as run

    try:
        result = run(Retriever(Corpus()), dataset, include_opt_in=include_opt_in)
        report = json.dumps(result, indent=2, ensure_ascii=False)
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(report + "\n", encoding="utf-8")
        typer.echo(report)
    except (PramanaError, OSError) as exc:
        fail(exc)


@app.command("evaluate-answers")
def evaluate_answers(
    dataset: Path = Path("benchmarks/advaita/v2/questions.json"),
    output: Path = Path("benchmarks/advaita/v2/answers.json"),
    split: str | None = None,
    limit: int | None = None,
    check: bool = False,
    route_only: bool = False,
):
    """Answer-level evaluation with the local Ollama model (slow; resumable in batches).

    --route-only runs just the short routing call per question (fast) and writes
    routing.json beside the output.
    """
    import asyncio

    from pramana.answering import Answerer
    from pramana.evaluation import evaluate_answers as run
    from pramana.evaluation import evaluate_routing

    partial = output.with_suffix(".partial.jsonl")
    if route_only:
        try:
            result = asyncio.run(evaluate_routing(Answerer(Retriever(Corpus())), dataset))
            target = output.with_name("routing.json")
            target.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", "utf-8")
            summary = {k: v for k, v in result.items() if k not in ("details",)}
            typer.echo(json.dumps(summary, indent=2, ensure_ascii=False))
        except (PramanaError, OSError) as exc:
            fail(exc)
        return
    try:
        result = asyncio.run(
            run(
                Answerer(Retriever(Corpus())),
                dataset,
                split=split,
                limit=limit,
                check=check,
                partial=partial,
                progress=typer.echo,
            )
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", "utf-8")
        if not result["remaining"]:
            partial.unlink(missing_ok=True)  # every selected question is finished
        typer.echo(json.dumps(result["overall"], indent=2))
        typer.echo(f"{result['answered']} answered, {result['remaining']} remaining.")
    except (PramanaError, OSError) as exc:
        fail(exc)


@app.command()
def divergence(top: int = 20, least: bool = False):
    """List where Śaṅkara and Rāmānuja differ most (or least) on the Brahma Sūtra."""
    from pramana.divergence import divergence as compute
    from pramana.divergence import most_different

    data = compute(Corpus().store)
    if not data["available"]:
        fail(PramanaError(data["reason"]))
    for unit in most_different(data, top, least=least):
        bands = unit["bands"]
        reasons = [f"{s} {bands[s]}" for s in ("scripture", "wording", "dispute") if bands[s]]
        terms = ", ".join(f"{t} ×{n}" for t, n in list(unit["terms"].items())[:3])
        pair = (
            f" (Rāmānuja numbers it {unit['ramanuja_sutra']})"
            if unit["pairing"] == "renumbered"
            else ""
        )
        typer.echo(f"{unit['label']:<12} {bands['overall']:<10} {'; '.join(reasons)}{pair}")
        if terms:
            typer.echo(f"{'':<12} disputes: {terms}")


@agent_app.command("token")
def agent_token():
    """Print a new random token for PRAMANA_AGENT_TOKEN (or one name in PRAMANA_AGENT_TOKENS)."""
    import secrets

    typer.echo(secrets.token_urlsafe(32))


def show_excerpt(pick: str, fmt: str, kind, document, **options):
    """Shared by `excerpt today` and `excerpt random`: print what the HTTP routes return."""
    from pramana import agent_excerpts as ex

    try:
        store = Corpus().store
        pool = ex.pool_for(store)
        if not pool.items:
            raise PramanaError("No allowlisted texts are imported. Run: pramana corpus download.")
        items = ex.candidates(pool, kind or None, document or None)
        if not items:
            raise PramanaError("No excerpt matches those filters.")
        if pick == "today":
            day = ex.day_in(options["tz"], options["date"])
            item, _ = ex.today(pool, items, day=day, seed=options["seed"])
        elif options.get("topic"):
            item, _ = ex.about(
                pool,
                store,
                Retriever(Corpus()),
                options["topic"],
                items,
                strategy=options["strategy"],
            )
        else:
            item, _ = ex.pick_random(pool, items, set())
        data, body = ex.render(store, pool, item)
    except (PramanaError, ValueError) as exc:
        fail(exc)
    if fmt == "json":
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        typer.echo(ex.message(data, body, fmt), nl=False)


@excerpt_app.command("today")
def excerpt_today(
    kind: Annotated[list[str] | None, typer.Option(help="verse, passage or sentence")] = None,
    document: Annotated[list[str] | None, typer.Option(help="Document ID (repeatable)")] = None,
    tz: str = "UTC",
    date: Annotated[
        datetime.datetime | None, typer.Option(formats=["%Y-%m-%d"], help="YYYY-MM-DD")
    ] = None,
    seed: str = "",
    fmt: Annotated[str, typer.Option("--format", help="json, text or markdown")] = "text",
):
    """The excerpt of the day: the same for everyone on a date, timezone and seed."""
    show_excerpt("today", fmt, kind, document, tz=tz, seed=seed, date=date.date() if date else None)


@excerpt_app.command("random")
def excerpt_random(
    kind: Annotated[list[str] | None, typer.Option(help="verse, passage or sentence")] = None,
    document: Annotated[list[str] | None, typer.Option(help="Document ID (repeatable)")] = None,
    topic: Annotated[
        str | None, typer.Option(help="Choose among excerpts about this (needs the local model)")
    ] = None,
    strategy: Annotated[str, typer.Option(help="hybrid or lexical, for --topic")] = "hybrid",
    fmt: Annotated[str, typer.Option("--format", help="json, text or markdown")] = "text",
):
    """A random excerpt, optionally about a topic."""
    show_excerpt("random", fmt, kind, document, topic=topic, strategy=strategy)


@excerpt_app.command("sources")
def excerpt_sources():
    """Documents in the pool: excerpts by kind, rejected verse units and rights lines."""
    from pramana import agent_excerpts as ex

    typer.echo(json.dumps(ex.report(ex.pool_for(Corpus().store)), ensure_ascii=False, indent=2))


@app.command()
def serve(
    port: int = 8000,
    agent_only: Annotated[
        bool, typer.Option(help="Serve only the token-protected excerpt routes")
    ] = False,
):
    """Serve the API and compiled reader on localhost."""
    import uvicorn

    if agent_only:
        from pramana.agent_api import AgentAuth, create_agent_app

        try:
            auth = AgentAuth.from_env()
        except PramanaError as exc:
            fail(exc)
        if not auth.enabled:
            fail(
                PramanaError(
                    "--agent-only needs a token. Run: pramana agent token, then set "
                    "PRAMANA_AGENT_TOKEN to it."
                )
            )
        uvicorn.run(create_agent_app(auth=auth), host="127.0.0.1", port=port)
        return

    from pramana.api import create_app

    uvicorn.run(create_app(), host="127.0.0.1", port=port)
