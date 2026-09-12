"""Integration tests: `prumo update` reflui o `pj_base` num projeto vivo."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from prumo_assist.cli import app

runner = CliRunner()


def _init(target: Path) -> None:
    res = runner.invoke(app, ["init", str(target), "--json"])
    assert res.exit_code == 0, res.output


def test_update_restaura_arquivo_do_nucleo_apagado(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    (pj / "docs" / "project_guide.md").unlink()

    res = runner.invoke(app, ["update", str(pj), "--json"])

    assert res.exit_code == 0, res.output
    assert (pj / "docs" / "project_guide.md").is_file()
    payload = json.loads(res.output)
    assert "docs/project_guide.md" in payload["copied"]


def test_update_nao_injeta_escopo_do_template(tmp_path: Path) -> None:
    """A armadilha do desenho: o `pj_base` traz `docs/studies/principal/`, e
    recopiá-lo num projeto que renomeou o escopo criaria um segundo escopo
    órfão — fazendo todo comando por-escopo passar a exigir `--scope`."""
    pj = tmp_path / "pj_demo"
    _init(pj)
    (pj / "docs" / "studies" / "principal").rename(pj / "docs" / "studies" / "01_estudo")

    res = runner.invoke(app, ["update", str(pj), "--json"])

    assert res.exit_code == 0, res.output
    assert not (pj / "docs" / "studies" / "principal").exists()
    assert [p.name for p in (pj / "docs" / "studies").iterdir()] == ["01_estudo"]


def test_update_dry_run_nao_escreve(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    (pj / "docs" / "project_guide.md").unlink()

    res = runner.invoke(app, ["update", str(pj), "--dry-run", "--json"])

    assert res.exit_code == 0, res.output
    assert not (pj / "docs" / "project_guide.md").exists()
    payload = json.loads(res.output)
    assert payload["dry_run"] is True
    assert "docs/project_guide.md" in payload["missing"]


def test_update_em_projeto_no_padrao_nao_faz_nada(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)

    res = runner.invoke(app, ["update", str(pj), "--json"])

    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["copied"] == []
    assert payload["updated"] == []


def test_update_fora_de_projeto_falha_com_instrucao(tmp_path: Path) -> None:
    res = runner.invoke(app, ["update", str(tmp_path), "--json"])
    assert res.exit_code == 1
    assert "prumo init" in res.output or "pj_config.toml" in res.output


def test_update_reescreve_invocacoes_antigas(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    (pj / "README.md").write_text("use /prumo-assist:paper-manager sync\n", encoding="utf-8")

    res = runner.invoke(app, ["update", str(pj), "--json"])

    assert res.exit_code == 0, res.output
    assert (pj / "README.md").read_text(
        encoding="utf-8"
    ) == "use /prumo-assist:paper library sync\n"
    assert {"path": "README.md", "count": 1} in json.loads(res.output)["skill_refs"]


def test_update_dry_run_lista_invocacoes_sem_escrever(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    (pj / "README.md").write_text("/prumo-assist:wiki-query\n", encoding="utf-8")

    res = runner.invoke(app, ["update", str(pj), "--dry-run", "--json"])

    assert res.exit_code == 0, res.output
    assert (pj / "README.md").read_text(encoding="utf-8") == "/prumo-assist:wiki-query\n"
    assert {"path": "README.md", "count": 1} in json.loads(res.output)["skill_refs"]


def test_update_nao_reescreve_proveniencia(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    _init(pj)
    nota = pj / "docs" / "studies" / "principal" / "notes" / "f.md"
    nota.parent.mkdir(parents=True, exist_ok=True)
    nota.write_text("---\ntype: finding\ngenerator: wiki-query\n---\n", encoding="utf-8")

    res = runner.invoke(app, ["update", str(pj), "--json"])

    assert res.exit_code == 0, res.output
    assert "generator: wiki-query" in nota.read_text(encoding="utf-8")
