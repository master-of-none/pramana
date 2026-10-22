# Optional private PDF inputs

Place the three PDFs described in [the PDF guide](../guides/pdf-ingestion.md) here and run
`uv run pramana corpus import-books`. The command verifies and relocates originals
to `PRAMANA_HOME/sources/pdfs/`, extracts/OCRs locally, and imports distinct editions.
On this prepared library they have already been moved to `.pramana/sources/pdfs/`.

PDFs in this folder are ignored. Never commit original PDFs or derived full text;
redistribution permission has not been established. The source/model notices are
in [sources.md](../notices/sources.md).
