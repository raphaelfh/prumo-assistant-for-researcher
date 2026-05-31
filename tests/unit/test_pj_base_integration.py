"""Integração: init cria núcleo mínimo; add reconstrói camadas."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from prumo_assist.cli import app

runner = CliRunner()


def test_core_is_minimal_and_modules_rebuild(tmp_path: Path) -> None:
    target = tmp_path / "pj_e2e"
    assert runner.invoke(app, ["init", str(target), "--json"]).exit_code == 0

    # Núcleo: presentes
    for rel in [
        "CLAUDE.md", "README.md", "Makefile", "pyproject.toml",
        "docs/project_guide.md", "docs/canvas/project.canvas",
        ".claude/rules/documentation.md", ".claude/rules/project_context.md",
        ".claude/make", "references/_references.bib",
    ]:
        assert (target / rel).exists(), f"faltou núcleo: {rel}"

    # Núcleo: ausentes (são módulo / nascem on-demand)
    for rel in [
        "docs/protocol.md", "docs/templates",
        ".claude/rules/ml_stack.md", ".claude/rules/coding_style.md",
        "docs/concepts", "docs/findings",
    ]:
        assert not (target / rel).exists(), f"núcleo não deveria ter: {rel}"

    # CLAUDE.md genérico (sem ML), com Início rápido
    claude = (target / "CLAUDE.md").read_text()
    assert "Início rápido" in claude
    assert "PyTorch" not in claude and "timm" not in claude

    # add reconstrói
    assert runner.invoke(app, ["add", "clinical", "-t", str(target)]).exit_code == 0
    assert runner.invoke(app, ["add", "ml", "-t", str(target)]).exit_code == 0
    assert (target / "docs" / "protocol.md").is_file()
    assert (target / ".claude" / "rules" / "ml_stack.md").is_file()
    assert (target / ".claude" / "make" / "ml.mk").is_file()
