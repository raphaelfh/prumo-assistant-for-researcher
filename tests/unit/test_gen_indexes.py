"""Testa o gerador de índices (.github/scripts/gen_indexes.py).

O script é carregado via importlib (vive fora de src/). Testa as funções puras
de renderização/substituição e o contrato --check contra o repo real.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "gen_indexes.py"


@pytest.fixture(scope="module")
def gen() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_indexes", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_replace_block_substitui_apenas_o_miolo(gen: ModuleType) -> None:
    text = "antes\n<!-- prumo:x:begin -->\nvelho\n<!-- prumo:x:end -->\ndepois\n"
    out = gen.replace_block(text, "x", "novo")
    assert "velho" not in out
    assert "novo" in out
    assert out.startswith("antes\n") and out.endswith("depois\n")


def test_replace_block_eh_idempotente(gen: ModuleType) -> None:
    text = "<!-- prumo:x:begin -->\na\n<!-- prumo:x:end -->\n"
    once = gen.replace_block(text, "x", "corpo")
    twice = gen.replace_block(once, "x", "corpo")
    assert once == twice


def test_replace_block_falha_sem_marcadores(gen: ModuleType) -> None:
    with pytest.raises(SystemExit):
        gen.replace_block("sem marcadores", "x", "corpo")


def test_skills_table_cobre_o_registry_inteiro(gen: ModuleType) -> None:
    table = gen.render_skills_table()
    assert "`/prumo-assist:start`" in table
    assert "`/prumo-assist:paper-extract`" in table
    # uma linha por skill + 2 de cabeçalho
    n_skills = len(list((gen.REPO / "skills").glob("*/SKILL.md")))
    assert table.count("\n") + 1 == n_skills + 2


def test_adr_index_lista_todos_os_adrs(gen: ModuleType) -> None:
    body = gen.render_adr_index()
    n_adrs = len(list((gen.REPO / "docs" / "adr").glob("adr-*.md")))
    assert n_adrs >= 14
    assert body.count("[[adr/adr-") == n_adrs
