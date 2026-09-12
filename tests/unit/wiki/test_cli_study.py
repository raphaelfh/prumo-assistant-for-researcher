"""Testa os subcomandos `prumo wiki study-*` e `finding` via CliRunner (sem rede/external)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from par.cli import app

runner = CliRunner()


def _pj(tmp_path: Path, *scopes: str) -> Path:
    """Raiz do pj_* com escopo(s) sob `docs/studies/`.

    `study-start` e `finding` gravam NOTA DE ESCOPO — o `--path` recebido é
    resolvido por `pj_layout.find_scope_root`, então o projeto precisa ter um
    escopo de verdade (não só `docs/`)."""
    (tmp_path / ".claude").mkdir(parents=True)
    (tmp_path / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    for slug in scopes or ("principal",):
        for sub in ("notes", "writing", "decisions"):
            (tmp_path / "docs" / "studies" / slug / sub).mkdir(parents=True)
    return tmp_path


def test_study_start_cria_log_sob_o_escopo(tmp_path: Path) -> None:
    """Regressão (Crítico #1 da review final): `--path <raiz do pj_*>` era
    repassado cru como `scope=`, e o log caía em `<pj>/notes/` — FORA de
    `docs/`, invisível pra `compose`, `wiki lint`/`stats` e o índice qmd, com
    exit 0. Assertar só `log_path.exists()` deixava o bug passar."""
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
    assert log_path.parent == pj / "docs" / "studies" / "principal" / "notes"


def test_study_start_sem_path_da_raiz_do_projeto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invocação bare da skill `active-learning` (`skills/active-learning/SKILL.md`
    chama sem `--path`, do cwd do agente = raiz do pj_*)."""
    pj = _pj(tmp_path)
    monkeypatch.chdir(pj)
    result = runner.invoke(app, ["wiki", "study-start", "Tópico", "--date", "2026-06-14", "--json"])
    assert result.exit_code == 0, result.output
    log_path = Path(json.loads(result.stdout)["log_path"])
    assert log_path.parent == pj / "docs" / "studies" / "principal" / "notes"


def test_study_start_com_varios_escopos_exige_escolha(tmp_path: Path) -> None:
    pj = _pj(tmp_path, "artigo-a", "artigo-b")
    result = runner.invoke(
        app,
        ["wiki", "study-start", "Tópico", "--date", "2026-06-14", "--path", str(pj)],
    )
    assert result.exit_code == 1
    assert "artigo-a" in result.output
    assert "artigo-b" in result.output


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


def test_finding_arquiva_corpo_do_stdin_sob_o_escopo(tmp_path: Path) -> None:
    """Regressão (Crítico #1 da review final): `--path <raiz do pj_*>` gravava o
    finding em `<pj>/notes/`, fora de `docs/` — invisível pra
    `compose._read_findings(<pj>/docs/studies/<slug>)`, enquanto
    `_append_to_index` já cunhava um wikilink morto em `docs/_index.md`."""
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
    assert out == pj / "docs" / "studies" / "principal" / "notes" / "rwe-definicao.md"


def test_finding_sem_path_da_raiz_do_projeto_cai_sob_o_escopo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invocação bare das skills `wiki-query` e `active-learning` (nenhuma passa
    `--path`; o cwd do agente é a raiz do pj_*). O finding tem de ser visível
    pra `compose`, `wiki lint`/`stats` e o índice qmd."""
    pj = _pj(tmp_path)
    monkeypatch.chdir(pj)
    result = runner.invoke(
        app,
        ["wiki", "finding", "--slug", "rwe", "--title", "RWE", "--date", "2026-06-14", "--json"],
        input="corpo",
    )
    assert result.exit_code == 0, result.output
    out = Path(json.loads(result.stdout)["finding_path"])
    assert out == pj / "docs" / "studies" / "principal" / "notes" / "rwe.md"

    # A prova que fecha o repro do revisor: o finding entra no contexto de
    # escrita em vez de virar arquivo invisível com exit 0.
    from par.domains.write.compose import _read_findings

    encontrados = _read_findings(pj / "docs" / "studies" / "principal")
    assert [f.path for f in encontrados] == [out]


def test_finding_com_varios_escopos_exige_escolha(tmp_path: Path) -> None:
    pj = _pj(tmp_path, "artigo-a", "artigo-b")
    result = runner.invoke(
        app,
        [
            "wiki",
            "finding",
            "--slug",
            "x",
            "--title",
            "X",
            "--date",
            "2026-06-14",
            "--path",
            str(pj),
        ],
        input="corpo",
    )
    assert result.exit_code == 1
    assert "artigo-a" in result.output
    assert "artigo-b" in result.output


def test_finding_sem_pj_config_falha_com_dica(tmp_path: Path) -> None:
    # tmp_path não tem .claude/pj_config.toml em nenhum ancestral -> raiz não
    # resolve; archive_as_finding levanta PjRootNotFoundError acionável.
    result = runner.invoke(
        app,
        [
            "wiki",
            "finding",
            "--slug",
            "x",
            "--title",
            "X",
            "--date",
            "2026-06-14",
            "--path",
            str(tmp_path),
        ],
        input="corpo",
    )
    assert result.exit_code == 1
    assert "pj_config.toml" in result.output
    assert "prumo init" in result.output
