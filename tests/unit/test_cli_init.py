"""Integration test: ``prumo init`` cria estrutura completa do pj_*."""

from __future__ import annotations

import json
import re
from pathlib import Path

from typer.testing import CliRunner

from prumo_assist.cli import app
from prumo_assist.core.paths import resolve_resource

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


def test_init_substitutes_name_placeholders(tmp_path: Path) -> None:
    """Projeto novo carrega o nome real — nada de ``pj-NOME`` residual.

    Bug: o pyproject ficava ``name = "pj-NOME"`` e o PyCharm/uv exibia o
    placeholder em vez do nome do projeto.
    """
    target = tmp_path / "pj_demo"
    result = runner.invoke(app, ["init", str(target), "--json"])
    assert result.exit_code == 0, result.output

    assert 'name = "pj_demo"' in (target / "pyproject.toml").read_text(encoding="utf-8")
    assert (target / "README.md").read_text(encoding="utf-8").startswith("# pj_demo")
    leftovers = [
        str(p.relative_to(target))
        for p in target.rglob("*")
        if p.is_file()
        and ".git" not in p.parts
        and "NOME" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert leftovers == []


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


def test_init_generates_zettlr_profile(tmp_path: Path) -> None:
    target = tmp_path / "pj_demo"
    result = runner.invoke(app, ["init", str(target), "--json"])
    assert result.exit_code == 0, result.output
    profile = target / "docs" / "templates" / "prumo-docx.yaml"
    assert profile.is_file()
    payload = json.loads(result.stdout)
    assert payload["zettlr_profile"] == str(profile)


def test_init_scaffold_is_pandoc_pure(tmp_path: Path) -> None:
    """pj_base v2: sem vault Obsidian e sem sintaxe Obsidian nos .md."""
    target = tmp_path / "pj_demo"
    assert runner.invoke(app, ["init", str(target), "--json"]).exit_code == 0
    assert not (target / ".obsidian").exists()
    assert not (target / "references" / "views").exists()
    assert not (target / "docs" / "canvas").exists()
    offenders: list[str] = []
    for md in target.rglob("*.md"):
        rel = md.relative_to(target)
        # .claude/skills/ vem do registry de skills do plugin (Task 11), não
        # do template pj_base; algumas skills mantêm menções deliberadas ao
        # wikilink legado e não são escopo desta checagem de pureza.
        if rel.parts[:2] == (".claude", "skills"):
            continue
        text = md.read_text(encoding="utf-8")
        if "[[@" in text or "![[" in text or "> [!" in text:
            offenders.append(str(rel))
    assert offenders == []


def test_templates_nao_usam_ancora_bibliografica_sem_arroba() -> None:
    """`[[citekey]]` (sem `@`) não é citação Pandoc válida: nenhum consumidor
    de citação a enxerga, e `PAGE_LINK_RE` a confunde com wikilink de página
    (vira `concept_candidate` no lint)."""
    ofensores: list[str] = []
    for path in resolve_resource("templates").rglob("*.md"):
        for m in re.finditer(r"\[\[([^\]|@#]+)\]\]", path.read_text(encoding="utf-8")):
            alvo = m.group(1)
            if "citekey" in alvo.lower():
                ofensores.append(f"{path}: [[{alvo}]]")
    assert not ofensores, "âncora bibliográfica sem `@`: " + "; ".join(ofensores)
