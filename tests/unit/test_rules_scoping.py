"""Escopo das rules distribuídas: o glob tem que casar do pj_* pra dentro.

Claude Code casa ``paths:`` contra o caminho RELATIVO à raiz da sessão, e a
raiz é o próprio ``pj_*``. Um glob com o segmento ``pj_*`` no meio nunca casa
— a rule fica muda em silêncio, que foi o bug de 0.68.1 pra trás.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist.core.paths import resolve_resource


def _rules() -> list[Path]:
    raiz = resolve_resource("templates")
    return sorted(p for p in raiz.rglob("*.md") if ".claude/rules/" in p.as_posix())


def _globs(rule: Path) -> list[str]:
    """Valores de ``paths:`` do frontmatter. Lista vazia = rule sempre-on."""
    linhas = rule.read_text(encoding="utf-8").splitlines()
    if not linhas or linhas[0].strip() != "---":
        return []
    fim = next((i for i, ln in enumerate(linhas[1:], 1) if ln.strip() == "---"), len(linhas))
    fm = linhas[1:fim]
    if not any(ln.startswith("paths:") for ln in fm):
        return []
    return [
        ln.strip().removeprefix("- ").strip('"').strip("'") for ln in fm if ln.startswith("  - ")
    ]


def test_ha_rules_para_auditar() -> None:
    assert _rules(), "nenhuma rule encontrada nos templates — o resolver mudou?"


@pytest.mark.parametrize("rule", _rules(), ids=lambda p: p.name)
def test_glob_de_rule_nao_depende_do_segmento_pj(rule: Path) -> None:
    """``pj_*`` no glob não casa: a sessão abre DENTRO do ``pj_*``."""
    ruins = [g for g in _globs(rule) if "pj_" in g]
    assert not ruins, (
        f"{rule.name}: glob(s) {ruins} contêm o segmento `pj_*`. O caminho "
        "relativo à raiz da sessão não tem esse segmento, então a rule nunca "
        "carrega. Use um glob relativo ao projeto (ex.: `docs/**`) ou remova "
        "`paths:` para deixá-la sempre-on."
    )
