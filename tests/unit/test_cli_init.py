"""Integration test: ``prumo init`` cria estrutura completa do pj_*."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from prumo_assist.cli import app

runner = CliRunner()


def test_init_creates_project_structure(tmp_path: Path) -> None:
    target = tmp_path / "pj_demo"
    result = runner.invoke(
        app,
        ["init", str(target), "--integration", "claude_code", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["project"] == str(target.resolve())
    assert payload["version"]
    assert any(i["integration"] == "claude_code" for i in payload["integrations"])

    # Estrutura essencial existe
    assert (target / "CLAUDE.md").is_file()
    assert (target / "docs" / "_index.md").is_file()
    assert (target / "references" / "_references.bib").is_file()
    assert (target / ".claude" / "pj_config.toml").is_file()


def test_init_refuses_existing_dir_without_force(tmp_path: Path) -> None:
    target = tmp_path / "pj_existing"
    target.mkdir()
    result = runner.invoke(app, ["init", str(target)])
    assert result.exit_code != 0
    # Rich pode quebrar linha se o terminal for estreito (CI roda em ~80 cols).
    # Normalizar whitespace antes de buscar o trecho canônico.
    assert "já existe" in " ".join(result.output.split())


def test_doctor_on_fresh_project_passes(tmp_path: Path) -> None:
    target = tmp_path / "pj_demo"
    runner.invoke(app, ["init", str(target), "--json"])
    result = runner.invoke(app, ["doctor", str(target), "--json"])
    assert result.stdout
    # Doctor pode emitir várias linhas (warnings + JSON final).
    # Pegamos a última linha JSON-parseable como o payload primário.
    last_json: dict[str, object] | None = None
    for line in result.stdout.splitlines():
        try:
            last_json = json.loads(line)
        except json.JSONDecodeError:
            continue
    assert last_json is not None
    assert "ok" in last_json
    assert "issues" in last_json


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "prumo" in result.stdout
