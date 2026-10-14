import json

from typer.testing import CliRunner

from pramana.cli import app


def test_cli_machine_output_and_status(monkeypatch, indexed):
    monkeypatch.setenv("PRAMANA_HOME", str(indexed.home))
    runner = CliRunner()
    result = runner.invoke(app, ["search", "Vishnu", "--strategy", "lexical", "--json"])
    assert result.exit_code == 0, result.output
    hits = json.loads(result.stdout)
    assert hits[0]["passage"]["citation"]["translator"] == "Test translator"
    status = runner.invoke(app, ["status"])
    assert json.loads(status.stdout)["chapters"] == 2


def test_cli_invalid_import_is_actionable(monkeypatch, tmp_path):
    monkeypatch.setenv("PRAMANA_HOME", str(tmp_path / "home"))
    file = tmp_path / "invalid.jsonl"
    file.write_text('{"text":"No provenance"}')
    result = CliRunner().invoke(app, ["ingest", str(file)])
    assert result.exit_code == 1
    assert "invalid chapter provenance" in result.output
    assert "Traceback" not in result.output
