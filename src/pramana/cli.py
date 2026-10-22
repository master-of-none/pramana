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
model_app = typer.Typer(help="Prepare the local embedding model explicitly.")
app.add_typer(corpus_app, name="corpus")
app.add_typer(model_app, name="model")


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


@corpus_app.command()
def download(
    archive: Annotated[
        Path | None,
        typer.Option(help="Saved vp.txt.gz, or a directory of saved Brahma Sutra pages"),
    ] = None,
    offline: bool = False,
    source: Annotated[
        str, typer.Option(help="vishnu-purana (Wilson) or brahma-sutra (Thibaut, SBE 34/38)")
    ] = "vishnu-purana",
):
    """Download/cache a complete public-domain edition and emit validated JSONL."""
    if source == "brahma-sutra":
        from pramana.ingestion.brahmasutra import acquire
    elif source == "vishnu-purana":
        from pramana.ingestion.vishnu import acquire
    else:
        fail(PramanaError("Unknown --source; choose vishnu-purana or brahma-sutra."))

    try:
        typer.echo(str(acquire(data_dir(), archive, offline=offline)))
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


@app.command()
def serve(port: int = 8000):
    """Serve the API and compiled reader on localhost."""
    import uvicorn

    from pramana.api import create_app

    uvicorn.run(create_app(), host="127.0.0.1", port=port)
