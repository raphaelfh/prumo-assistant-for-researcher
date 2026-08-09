"""Integração: módulos opcionais do núcleo (code, data, notebooks, clinical, ml)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from prumo_assist.cli import app

runner = CliRunner()


def _project(tmp_path: Path) -> Path:
    """Raiz do projeto no layout ATUAL: só o marcador `.claude/pj_config.toml`."""
    root = tmp_path / "pj_x"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    (root / "docs").mkdir(parents=True, exist_ok=True)
    return root


def _scope(root: Path, slug: str) -> Path:
    """Escopo `docs/studies/<slug>/{notes,writing,decisions}`."""
    scope = root / "docs" / "studies" / slug
    for sub in ("notes", "writing", "decisions"):
        (scope / sub).mkdir(parents=True)
    return scope


def test_modulos_do_nucleo_existem_e_sao_descobriveis() -> None:
    from prumo_assist.core.scaffold import discover_modules

    nomes = {m.name for m in discover_modules()}
    assert {"code", "data", "notebooks", "clinical", "ml"} <= nomes


def test_add_clinical_nao_cria_protocolo_fora_do_escopo(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _scope(root, "principal")
    result = runner.invoke(app, ["add", "clinical", "--target", str(root)])
    assert result.exit_code == 0, result.output
    assert (root / "docs" / "studies" / "principal" / "writing" / "protocol.md").is_file()
    assert not (root / "docs" / "protocol.md").exists()


def test_add_code_cria_camada_de_codigo(tmp_path: Path) -> None:
    root = _project(tmp_path)
    result = runner.invoke(app, ["add", "code", "--target", str(root)])
    assert result.exit_code == 0, result.output
    assert (root / "src").is_dir()
    assert (root / "tests").is_dir()
    assert (root / "pyproject.toml").is_file()


def test_add_code_substitutes_project_name(tmp_path: Path) -> None:
    """O pyproject.toml do módulo `code` ainda carrega o placeholder `pj-NOME`
    (bug histórico do núcleo, ver test_cli_init.py) — `prumo add` precisa
    aplicar a mesma substituição de nome que `prumo init` aplica."""
    root = tmp_path / "pj_demo"
    assert runner.invoke(app, ["init", str(root), "--json"]).exit_code == 0
    result = runner.invoke(app, ["add", "code", "--target", str(root)])
    assert result.exit_code == 0, result.output
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "pj_demo"' in text
    assert "pj-NOME" not in text


def test_add_data_cria_camadas_de_dado(tmp_path: Path) -> None:
    root = _project(tmp_path)
    result = runner.invoke(app, ["add", "data", "--target", str(root)])
    assert result.exit_code == 0, result.output
    assert (root / "content" / "01_raw").is_dir()
    assert (root / "content" / "02_processed").is_dir()


def test_add_notebooks_cria_pasta_de_notebooks(tmp_path: Path) -> None:
    root = _project(tmp_path)
    result = runner.invoke(app, ["add", "notebooks", "--target", str(root)])
    assert result.exit_code == 0, result.output
    assert (root / "notebooks").is_dir()
