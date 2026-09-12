"""Tests do recálculo determinístico de estatísticas relatadas (``stat_mismatch``)."""

from __future__ import annotations

from pathlib import Path

from par.domains.wiki.lint import lint
from par.domains.wiki.stats_check import (
    benjamini_hochberg,
    stat_mismatches,
    wilson_interval,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "wiki"


def test_wilson_interval_reproduz_o_draft() -> None:
    lo, hi = wilson_interval(29, 35)
    assert (round(lo * 100, 1), round(hi * 100, 1)) == (67.3, 91.9)


def test_benjamini_hochberg_step_up_com_empates() -> None:
    q = benjamini_hochberg([0.01, 0.04, 0.03, 0.02])
    assert [round(v, 4) for v in q] == [0.04, 0.04, 0.04, 0.04]
    assert benjamini_hochberg([0.5, 0.5]) == [0.5, 0.5]


def test_recorte_real_nao_tem_divergencia() -> None:
    text = (FIXTURES / "stats_real_excerpt.md").read_text(encoding="utf-8")
    assert stat_mismatches(text) == []


def test_fixture_sintetica_aponta_ic_e_q_errados() -> None:
    text = (FIXTURES / "stats_wrong.md").read_text(encoding="utf-8")
    [message] = stat_mismatches(text)
    assert "2 estatística(s)" in message
    assert "relatado 60.0 a 91.9" in message
    assert "recalculado 67.3 a 91.9" in message
    assert '"B"' in message
    assert "relatado 0.100" in message
    assert "recalculado 0.040" in message
    assert "prumo wiki lint" in message


def test_porcentagem_errada_e_apontada() -> None:
    [message] = stat_mismatches("Foram 29 of 35 (80.0%).")
    assert "relatado 80.0%" in message
    assert "recalculado 82.9%" in message


def test_padroes_nao_parseaveis_sao_pulados() -> None:
    text = (
        "About 29 respondents (80%, 95% CI 1.0 to 2.0).\n"
        "Foram 29 of 35 (cerca de 80%).\n\n"
        "| Teste | p | q |\n|---|---|---|\n| A | <0,001 | 0,900 |\n| B | 0,0400 | 0,900 |\n"
    )
    assert stat_mismatches(text) == []


def test_coluna_global_agrupa_todas_as_tabelas_da_pagina() -> None:
    text = (
        "## A\n\n| T | p | q (FDR família) | q (FDR global) |\n|---|---|---|---|\n"
        "| a1 | 0,0100 | 0,020 | 0,040 |\n| a2 | 0,0400 | 0,040 | 0,040 |\n\n"
        "## B\n\n| T | p | q (FDR família) | q (FDR global) |\n|---|---|---|---|\n"
        "| b1 | 0,0200 | 0,030 | 0,040 |\n| b2 | 0,0300 | 0,030 | 0,040 |\n"
    )
    assert stat_mismatches(text) == []


def test_lint_emite_stat_mismatch_na_pagina(tmp_path: Path) -> None:
    root = tmp_path
    (root / ".claude").mkdir()
    (root / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    writing = root / "docs" / "studies" / "a" / "writing"
    writing.mkdir(parents=True)
    (root / "docs" / "_index.md").write_text("# i", encoding="utf-8")
    (root / "docs" / "_log.md").write_text("# l", encoding="utf-8")
    (writing / "draft.md").write_text(
        (FIXTURES / "stats_wrong.md").read_text(encoding="utf-8"), encoding="utf-8"
    )

    [issue] = [i for i in lint(root)["issues"] if i["code"] == "stat_mismatch"]
    assert issue["severity"] == "warning"
    assert issue["page"] == "docs/studies/a/writing/draft.md"
    assert issue["scope"] == "a"
