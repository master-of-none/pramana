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
            help="One of: " + ", ".join(SOURCES) + "; or `advaita` for every Vedanta source"
        ),
    ] = "vishnu-purana",
):
    """Download/cache complete public-domain editions and emit validated JSONL."""
    if source != "advaita" and source not in SOURCES:
        fail(PramanaError(f"Unknown --source {source!r}. Choose: {', '.join(SOURCES)}, advaita."))
    if source == "advaita" and archive:
        fail(PramanaError("--archive applies to one source; omit it with --source advaita."))
    try:
        for name in ADVAITA if source == "advaita" else [source]:
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


@app.command()
def serve(port: int = 8000):
    """Serve the API and compiled reader on localhost."""
    import uvicorn

    from pramana.api import create_app

    uvicorn.run(create_app(), host="127.0.0.1", port=port)
