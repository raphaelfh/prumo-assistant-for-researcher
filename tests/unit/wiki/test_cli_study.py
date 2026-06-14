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
    assert start.exit_code == 0, start.output
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
    assert start.exit_code == 0, start.output
    log_path = json.loads(start.stdout)["log_path"]
    result = runner.invoke(
        app, ["wiki", "study-step", "--log-path", log_path, "--step", "recall"], input=""
    )
    assert result.exit_code == 1


def test_study_finish_grava_frontmatter(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    start = runner.invoke(
        app, ["wiki", "study-start", "Z", "--date", "2026-06-14", "--path", str(pj), "--json"]
    )
    assert start.exit_code == 0, start.output
    log_path = json.loads(start.stdout)["log_path"]
    result = runner.invoke(
        app,
        [
            "wiki",
            "study-finish",
            "--log-path",
            log_path,
            "--duration",
            "20",
            "--status",
            "completed",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    text = Path(log_path).read_text(encoding="utf-8")
    assert "duration_minutes: 20" in text
    assert "status: completed" in text


def test_study_finish_status_invalido_falha(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    start = runner.invoke(
        app, ["wiki", "study-start", "W", "--date", "2026-06-14", "--path", str(pj), "--json"]
    )
    assert start.exit_code == 0, start.output
    log_path = json.loads(start.stdout)["log_path"]
    result = runner.invoke(
        app, ["wiki", "study-finish", "--log-path", log_path, "--duration", "5", "--status", "foo"]
    )
    assert result.exit_code == 1
    assert "--status deve ser completed|abandoned|partial" in result.output


def test_finding_arquiva_corpo_do_stdin(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    body = "## Pergunta\n\nO que é RWE?\n\n## Resposta\n\nReal-world evidence."
    result = runner.invoke(
        app,
        [
            "wiki",
            "finding",
            "--slug",
            "rwe-definicao",
            "--title",
            "RWE",
            "--date",
            "2026-06-14",
            "--generator",
            "active-learning",
            "--path",
            str(pj),
            "--json",
        ],
        input=body,
    )
    assert result.exit_code == 0, result.output
    out = Path(json.loads(result.stdout)["finding_path"])
    assert out.exists()
    assert "Real-world evidence." in out.read_text(encoding="utf-8")
