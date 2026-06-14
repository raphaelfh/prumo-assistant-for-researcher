"""Testa os subcomandos `prumo wiki study-*` e `finding` via CliRunner (sem rede/external)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from prumo_assist.cli import app

runner = CliRunner()


def _pj(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "wiki").mkdir(parents=True)
    return tmp_path


def test_study_start_cria_log_e_emite_path(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    result = runner.invoke(
        app,
        [
            "wiki",
            "study-start",
            "Insuficiência Cardíaca em Diabéticos",
            "--date",
            "2026-06-14",
            "--path",
            str(pj),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["slug"] == "insuficiencia-cardiaca-em-diab"  # slugify trunca em 30 chars
    log_path = Path(payload["log_path"])
    assert log_path.exists()
    assert "2026-06-14" in log_path.name


def test_study_step_anexa_step_do_stdin(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    start = runner.invoke(
        app,
        ["wiki", "study-start", "Tópico X", "--date", "2026-06-14", "--path", str(pj), "--json"],
    )
    log_path = json.loads(start.stdout)["log_path"]
    step_json = json.dumps({"question": "O que é PECO?", "answer": "Exposição..."})
    result = runner.invoke(
        app,
        ["wiki", "study-step", "--log-path", log_path, "--step", "recall", "--json"],
        input=step_json,
    )
    assert result.exit_code == 0, result.output
    text = Path(log_path).read_text(encoding="utf-8")
    assert "## 1. Recall" in text
    assert "O que é PECO?" in text


def test_study_step_json_invalido_falha_limpo(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    start = runner.invoke(
        app, ["wiki", "study-start", "Y", "--date", "2026-06-14", "--path", str(pj), "--json"]
    )
    log_path = json.loads(start.stdout)["log_path"]
    result = runner.invoke(
        app, ["wiki", "study-step", "--log-path", log_path, "--step", "recall"], input=""
    )
    assert result.exit_code == 1
