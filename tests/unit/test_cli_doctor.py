"""Integration tests do prumo doctor com seção de dependências externas."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from prumo_assist.cli import app
from prumo_assist.core.deps import DepStatus

runner = CliRunner()


def _project(tmp_path: Path) -> Path:
    """Projeto no layout ATUAL: `.claude/pj_config.toml` + `docs/references/`."""
    pj = tmp_path / "pj_x"
    (pj / ".claude").mkdir(parents=True)
    (pj / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    (pj / ".claude" / "skills").mkdir()
    (pj / "docs" / "references").mkdir(parents=True)
    return pj


def test_doctor_json_includes_external_deps(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    fake = [
        DepStatus(name="qmd", present=True, required_by=["wiki-query"], detail="ok", hint=""),
        DepStatus(
            name="zotero",
            present=False,
            required_by=["paper sync-annotations"],
            detail="down",
            hint="abra o Zotero",
        ),
    ]
    with patch("prumo_assist.cli.check_external_deps", return_value=fake):
        result = runner.invoke(app, ["doctor", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    names = {d["name"] for d in payload["external_deps"]}
    assert names == {"qmd", "zotero"}


def test_doctor_missing_dep_does_not_fail_exit_code(tmp_path: Path) -> None:
    """Dep externa ausente é informativa: não derruba o exit code (só estrutura derruba)."""
    pj = _project(tmp_path)
    fake = [
        DepStatus(
            name="qmd", present=False, required_by=["wiki-query"], detail="missing", hint="instale"
        ),
    ]
    with patch("prumo_assist.cli.check_external_deps", return_value=fake):
        result = runner.invoke(app, ["doctor", str(pj), "--json"])
    # estrutura do projeto está OK → exit 0 mesmo com qmd ausente
    assert result.exit_code == 0, result.output


def test_doctor_human_output_shows_missing_dep_hint(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    fake = [
        DepStatus(
            name="qmd",
            present=False,
            required_by=["wiki-query"],
            detail="qmd não está no PATH",
            hint="bun install -g @tobilu/qmd",
        ),
    ]
    with patch("prumo_assist.cli.check_external_deps", return_value=fake):
        result = runner.invoke(app, ["doctor", str(pj)])
    assert "qmd" in result.output
    assert "bun install -g @tobilu/qmd" in result.output


def test_doctor_flags_broken_zettlr_profile(tmp_path: Path) -> None:
    import yaml

    pj = _project(tmp_path)
    profile = pj / "docs" / "templates" / "prumo-docx.yaml"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(
        yaml.safe_dump({"reader": "markdown", "writer": "docx", "filters": ["/nao/existe.lua"]}),
        encoding="utf-8",
    )
    with patch("prumo_assist.cli.check_external_deps", return_value=[]):
        result = runner.invoke(app, ["doctor", str(pj)])
    assert result.exit_code == 1
    assert "prumo write zettlr-profile" in result.output


def test_doctor_silent_when_no_zettlr_profile(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    with patch("prumo_assist.cli.check_external_deps", return_value=[]):
        result = runner.invoke(app, ["doctor", str(pj)])
    assert result.exit_code == 0, result.output


def test_doctor_avisa_bib_placeholder(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    (pj / "docs" / "references" / "_references.bib").write_text(
        "% Bibliografia do projeto — formato Better BibTeX (BBT).\n%\n% Fluxo...\n",
        encoding="utf-8",
    )
    with patch("prumo_assist.cli.check_external_deps", return_value=[]):
        result = runner.invoke(app, ["doctor", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert any("prumo paper connect" in w for w in payload["warnings"])


def test_doctor_sem_aviso_com_bib_real(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    (pj / "docs" / "references" / "_references.bib").write_text(
        "@article{x2020,\n  title = {T},\n}\n", encoding="utf-8"
    )
    with patch("prumo_assist.cli.check_external_deps", return_value=[]):
        result = runner.invoke(app, ["doctor", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["warnings"] == []


def test_doctor_acusa_layout_legado(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    (tmp_path / "references").mkdir()
    (tmp_path / "docs").mkdir()
    result = runner.invoke(app, ["doctor", str(tmp_path), "--json"])
    assert "legacy_layout" in result.stdout


def test_doctor_acusa_references_ressuscitado_pelo_zotero(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "references").mkdir()
    result = runner.invoke(app, ["doctor", str(root), "--json"])
    assert "references_ressuscitado" in result.stdout


# ---------------------------------------------------------------------------
# Empacotamento (ADR-0027)
# ---------------------------------------------------------------------------


def test_doctor_acusa_projeto_com_codigo_e_sem_build_system(tmp_path: Path) -> None:
    """O caso que motivou a ADR-0027: `src/` com código, pyproject sem
    `[build-system]`, e notebooks recorrendo a `sys.path.insert`."""
    pj = _project(tmp_path)
    (pj / "pyproject.toml").write_text(
        '[project]\nname = "pj_x"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (pj / "src" / "x").mkdir(parents=True)
    (pj / "src" / "x" / "prep.py").write_text("x = 1\n", encoding="utf-8")

    result = runner.invoke(app, ["doctor", str(pj), "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert any("projeto_nao_instalavel" in i for i in payload["issues"])


def test_doctor_nao_opina_sobre_projeto_sem_o_modulo_code(tmp_path: Path) -> None:
    """`pj_*` de revisão sistemática não tem código — o doctor fica quieto."""
    pj = _project(tmp_path)

    result = runner.invoke(app, ["doctor", str(pj), "--json"])

    payload = json.loads(result.stdout)
    assert not any("projeto_nao_instalavel" in i for i in payload["issues"])
    assert not any("sys_path_hack" in i for i in payload["issues"])
