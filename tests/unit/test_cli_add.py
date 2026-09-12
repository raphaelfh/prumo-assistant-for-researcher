"""Integration test: `prumo add` aplica overlays de módulo."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from par.cli import app

runner = CliRunner()


def _init(target: Path) -> None:
    res = runner.invoke(app, ["init", str(target), "--json"])
    assert res.exit_code == 0, res.output


def test_add_clinical_restores_protocol(tmp_path: Path) -> None:
    target = tmp_path / "pj_demo"
    _init(target)
    assert not (target / "docs" / "studies" / "principal" / "writing" / "protocol.md").exists()

    res = runner.invoke(app, ["add", "clinical", "--target", str(target), "--json"])
    assert res.exit_code == 0, res.output
    assert (target / "docs" / "studies" / "principal" / "writing" / "protocol.md").is_file()
    assert (target / "docs" / "studies" / "principal" / "writing" / "projeto-cep.md").is_file()
    assert (target / "docs" / "templates" / "data_dictionary_skeleton.md").is_file()
    payload = json.loads(res.stdout)
    assert payload["module"] == "clinical"
    assert payload["files_copied"] > 0


def test_add_ml_restores_stack(tmp_path: Path) -> None:
    target = tmp_path / "pj_demo"
    _init(target)
    res = runner.invoke(app, ["add", "ml", "--target", str(target), "--json"])
    assert res.exit_code == 0, res.output
    assert (target / ".claude" / "rules" / "ml_stack.md").is_file()


def test_add_unknown_module_errors(tmp_path: Path) -> None:
    target = tmp_path / "pj_demo"
    _init(target)
    res = runner.invoke(app, ["add", "nope", "--target", str(target)])
    assert res.exit_code != 0


def test_add_is_non_destructive(tmp_path: Path) -> None:
    target = tmp_path / "pj_demo"
    _init(target)
    protocol = target / "docs" / "studies" / "principal" / "writing" / "protocol.md"
    runner.invoke(app, ["add", "clinical", "--target", str(target)])
    protocol.write_text("EDITADO PELO USUÁRIO")
    runner.invoke(app, ["add", "clinical", "--target", str(target)])  # reaplica
    assert protocol.read_text() == "EDITADO PELO USUÁRIO"


def test_add_list_marks_applied(tmp_path: Path) -> None:
    target = tmp_path / "pj_demo"
    _init(target)
    runner.invoke(app, ["add", "clinical", "--target", str(target)])
    res = runner.invoke(app, ["add", "--list", "--target", str(target), "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.stdout)
    by = {m["name"]: m for m in payload["modules"]}
    assert by["clinical"]["applied"] is True
    assert by["ml"]["applied"] is False
    assert by["ml"]["description"]


def test_add_no_arg_non_tty_lists(tmp_path: Path) -> None:
    target = tmp_path / "pj_demo"
    _init(target)
    res = runner.invoke(app, ["add", "--target", str(target), "--json"])
    assert res.exit_code == 0, res.output
    assert "modules" in json.loads(res.stdout)


def test_add_interactive_picks_by_number(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    target = tmp_path / "pj_demo"
    _init(target)
    # módulos ordenados: clinical(1), code(2), data(3), ml(4), notebooks(5).
    # Input "4" → ml.
    res = runner.invoke(app, ["add", "--target", str(target)], input="4\n")
    assert res.exit_code == 0, res.output
    assert (target / ".claude" / "rules" / "ml_stack.md").is_file()


def test_add_study_says_the_path_once(tmp_path: Path) -> None:
    # Regressão do Princípio VIII: `success` + `emit` imprimiam o caminho
    # absoluto duas vezes em modo texto, e o segundo quebrava no wrap do
    # Rich, dando impressão de erro num comando que funcionou.
    target = tmp_path / "pj_demo"
    _init(target)
    res = runner.invoke(app, ["add", "study", "02_novo", "--target", str(target)])
    assert res.exit_code == 0, res.output
    assert res.output.strip() == "✓ Escopo criado em docs/studies/02_novo."
    assert "scope:" not in res.output


def test_add_study_json_keeps_machine_payload(tmp_path: Path) -> None:
    target = tmp_path / "pj_demo"
    _init(target)
    res = runner.invoke(app, ["add", "study", "02_novo", "--target", str(target), "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["slug"] == "02_novo"
    assert payload["scope"].endswith("docs/studies/02_novo")


def test_add_ml_cria_casa_das_rodadas(tmp_path: Path) -> None:
    # ADR-0031: saída de máquina fica ao lado de `build/` e `reviews/`, nunca
    # sob `docs/`, que é a raiz única de leitura indexada pelo qmd.
    target = tmp_path / "pj_demo"
    _init(target)
    res = runner.invoke(app, ["add", "ml", "--target", str(target), "--json"])
    assert res.exit_code == 0, res.output
    assert (target / "experiments" / "README.md").is_file()
    ignore = (target / "experiments" / ".gitignore").read_text(encoding="utf-8")
    assert "*.joblib" in ignore
