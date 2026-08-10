"""Integração: init cria núcleo mínimo; add reconstrói camadas."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from prumo_assist.cli import app
from prumo_assist.core.paths import resolve_resource

runner = CliRunner()


def test_pj_base_e_o_nucleo_universal() -> None:
    base = resolve_resource("templates") / "pj_base"
    assert (base / "docs" / "references" / "papers").is_dir()
    assert (base / "docs" / "studies" / "principal" / "writing").is_dir()
    # nada de codigo no nucleo
    for proibido in ("src", "tests", "notebooks", "content", "pyproject.toml"):
        assert not (base / proibido).exists(), f"{proibido} nao pertence ao nucleo"
    # a bibliografia nao mora mais na raiz
    assert not (base / "references").exists()


def test_gitignore_do_pj_base_protege_o_essencial() -> None:
    base = resolve_resource("templates") / "pj_base"
    texto = (base / ".gitignore").read_text(encoding="utf-8")
    assert ".prumo/" in texto
    assert "~$*" in texto
    assert "uv.lock" not in texto  # lockfile passa a ser versionado


def test_gitignore_da_bibliografia_e_local_e_nao_ancorado() -> None:
    base = resolve_resource("templates") / "pj_base"
    texto = (base / "docs" / "references" / ".gitignore").read_text(encoding="utf-8")
    assert texto.splitlines()[:2] == ["pdfs/*.pdf", "!pdfs/.gitkeep"]


def test_core_is_minimal_and_modules_rebuild(tmp_path: Path) -> None:
    target = tmp_path / "pj_e2e"
    assert runner.invoke(app, ["init", str(target), "--json"]).exit_code == 0

    # Núcleo: presentes
    for rel in [
        "CLAUDE.md",
        "README.md",
        "Makefile",
        "docs/project_guide.md",
        "docs/templates/reference.docx",
        ".claude/rules/documentation.md",
        ".claude/rules/project_context.md",
        ".claude/make",
        "docs/references/_references.bib",
        "docs/studies/principal/writing",
        "docs/studies/principal/notes",
        "docs/studies/principal/decisions",
    ]:
        assert (target / rel).exists(), f"faltou núcleo: {rel}"

    # Núcleo: ausentes (são módulo / nascem on-demand)
    # (docs/templates/ existe desde o core — o perfil Zettlr é gerado ali no
    # próprio init; "docs/templates/README.md" é conteúdo do módulo clinical.
    # pyproject.toml/src/tests saem do núcleo — passam a ser a camada `code`.)
    for rel in [
        "docs/protocol.md",
        "docs/templates/README.md",
        ".claude/rules/ml_stack.md",
        ".claude/rules/coding_style.md",
        "docs/concepts",
        "docs/findings",
        "pyproject.toml",
        "src",
        "tests",
        "notebooks",
        "content",
    ]:
        assert not (target / rel).exists(), f"núcleo não deveria ter: {rel}"

    # Núcleo: perfil de export do Zettlr é gerado por init, não por módulo.
    assert (target / "docs" / "templates" / "prumo-docx.yaml").is_file()

    # CLAUDE.md genérico (sem ML), com Início rápido
    claude = (target / "CLAUDE.md").read_text()
    assert "Início rápido" in claude
    assert "PyTorch" not in claude and "timm" not in claude

    # add reconstrói
    assert runner.invoke(app, ["add", "clinical", "-t", str(target)]).exit_code == 0
    assert runner.invoke(app, ["add", "ml", "-t", str(target)]).exit_code == 0
    assert (target / "docs" / "studies" / "principal" / "writing" / "protocol.md").is_file()
    assert (target / ".claude" / "rules" / "ml_stack.md").is_file()
    assert (target / ".claude" / "make" / "ml.mk").is_file()
