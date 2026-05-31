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


def test_init_refuses_existing_dir_with_content_without_flag(tmp_path: Path) -> None:
    target = tmp_path / "pj_existing"
    target.mkdir()
    (target / "preexisting.txt").write_text("keep me")
    result = runner.invoke(app, ["init", str(target), "--yes"])
    assert result.exit_code != 0
    # Rich pode quebrar linha se o terminal for estreito (CI roda em ~80 cols).
    # Normalizar whitespace antes de buscar o trecho canônico.
    out = " ".join(result.output.split())
    assert "já existe" in out


def test_init_merge_preserves_existing_files(tmp_path: Path) -> None:
    """`--merge` adiciona scaffold sem destruir arquivos do usuário."""
    target = tmp_path / "pj_demo"
    target.mkdir()
    custom = target / "my_notebook.ipynb"
    custom.write_text("custom user content")

    result = runner.invoke(app, ["init", str(target), "--merge", "--json"])
    assert result.exit_code == 0, result.output

    # Arquivo customizado preservado.
    assert custom.read_text() == "custom user content"
    # Scaffold adicionado.
    assert (target / "CLAUDE.md").is_file()
    assert (target / "docs" / "_index.md").is_file()
    assert (target / "docs" / "project_guide.md").is_file()

    payload = json.loads(result.stdout)
    assert payload["mode"] == "merge"
    assert payload["files_copied"] > 0


def test_init_merge_does_not_clobber_existing_scaffold_file(tmp_path: Path) -> None:
    """Se o usuário já tem um CLAUDE.md customizado, `--merge` NÃO sobrescreve."""
    target = tmp_path / "pj_demo"
    target.mkdir()
    claude_md = target / "CLAUDE.md"
    claude_md.write_text("MY OWN CLAUDE.md — DO NOT TOUCH")

    result = runner.invoke(app, ["init", str(target), "--merge", "--json"])
    assert result.exit_code == 0, result.output
    assert claude_md.read_text() == "MY OWN CLAUDE.md — DO NOT TOUCH"

    payload = json.loads(result.stdout)
    assert payload["files_skipped"] >= 1  # ao menos o CLAUDE.md foi pulado


def test_init_merge_and_force_are_mutually_exclusive(tmp_path: Path) -> None:
    target = tmp_path / "pj_x"
    target.mkdir()
    result = runner.invoke(app, ["init", str(target), "--merge", "--force", "--json"])
    assert result.exit_code != 0
    out = " ".join(result.output.split())
    assert "mutuamente exclusivos" in out


def test_init_rejects_invalid_prefix(tmp_path: Path) -> None:
    target = tmp_path / "my_project"  # falta o prefixo srpj_/pj_
    result = runner.invoke(app, ["init", str(target), "--yes"])
    assert result.exit_code != 0


def test_init_force_overwrites_existing_content(tmp_path: Path) -> None:
    target = tmp_path / "pj_force"
    target.mkdir()
    (target / "old.txt").write_text("delete me")
    result = runner.invoke(app, ["init", str(target), "--force", "--json"])
    assert result.exit_code == 0, result.output
    assert not (target / "old.txt").exists()
    assert (target / "CLAUDE.md").is_file()
    payload = json.loads(result.stdout)
    assert payload["mode"] == "force"


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


def test_doctor_runs_with_guideline_check(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from typer.testing import CliRunner

    from prumo_assist.cli import app

    for d in (".claude", "docs", "references"):
        (tmp_path / d).mkdir()
    result = CliRunner().invoke(app, ["doctor", str(tmp_path), "--json"])
    # Real plugin skills are fresh today, so the guideline path adds no issue;
    # the assertion is that the new code path runs without crashing.
    assert result.exit_code in (0, 1)
    assert '"project"' in result.stdout


def test_init_rejects_srpj_prefix(tmp_path: Path) -> None:
    """srpj_ deixou de ser aceito; só pj_."""
    target = tmp_path / "srpj_old"
    result = runner.invoke(app, ["init", str(target), "--yes"])
    assert result.exit_code != 0


def test_init_accepts_pj_prefix(tmp_path: Path) -> None:
    target = tmp_path / "pj_ok"
    result = runner.invoke(app, ["init", str(target), "--json"])
    assert result.exit_code == 0, result.output


def test_init_with_modules_applies_them(tmp_path: Path) -> None:
    target = tmp_path / "pj_full"
    result = runner.invoke(app, ["init", str(target), "--with", "clinical,ml", "--json"])
    assert result.exit_code == 0, result.output
    assert (target / "docs" / "protocol.md").is_file()  # clinical
    assert (target / ".claude" / "rules" / "ml_stack.md").is_file()  # ml
    payload = json.loads(result.stdout)
    assert sorted(payload["modules_applied"]) == ["clinical", "ml"]


def test_init_without_modules_is_minimal(tmp_path: Path) -> None:
    target = tmp_path / "pj_min"
    result = runner.invoke(app, ["init", str(target), "--json"])
    assert result.exit_code == 0, result.output
    assert not (target / "docs" / "protocol.md").exists()
    assert not (target / ".claude" / "rules" / "ml_stack.md").exists()
    assert json.loads(result.stdout)["modules_applied"] == []
