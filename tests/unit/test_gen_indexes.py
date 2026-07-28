"""Testa o gerador de índices (.github/scripts/gen_indexes.py).

O script é carregado via importlib (vive fora de src/). Testa as funções puras
de renderização/substituição contra o repo real (o contrato --check é exercido
no CI, depois que os marcadores existem nos alvos).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "gen_indexes.py"


@pytest.fixture(scope="module")
def gen() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_indexes", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def registry(gen: ModuleType) -> Any:
    reg, _ = gen.load_skill_registry(gen.REPO / "skills", strict=True)
    return reg


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


def test_replace_block_nao_interpreta_template_de_regex(gen: ModuleType) -> None:
    text = "<!-- prumo:x:begin -->\na\n<!-- prumo:x:end -->\n"
    out = gen.replace_block(text, "x", r"usa regex \d+ e \g<0> literais")
    assert r"usa regex \d+ e \g<0> literais" in out


def test_skills_table_cobre_o_registry_inteiro(gen: ModuleType, registry: Any) -> None:
    table = gen.render_skills_table(registry)
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


def test_render_prose_usa_a_cascata_livre_por_default(gen: ModuleType, registry: Any) -> None:
    body = gen.render_prose(registry.get("scientific-writing"))
    assert "Contrato de prosa" in body
    assert "default `en-US`" in body
    assert "Nunca traduza" in body
    assert "Citação no fim do período" in body
    assert "travado" not in body


def test_render_prose_interpola_o_locale_travado(gen: ModuleType, registry: Any) -> None:
    body = gen.render_prose(registry.get("write-projeto-cep"))
    assert "Idioma travado em `pt-BR`" in body
    assert "{locale}" not in body
    # a trava substitui a cascata, mas o core continua presente
    assert "default `en-US`" not in body
    assert "Citação no fim do período" in body


def test_stamp_block_ancora_depois_do_after(gen: ModuleType) -> None:
    text = (
        "---\nname: x\n---\n\n# Título\n\n"
        "<!-- prumo:preflight:begin -->\n> pf\n<!-- prumo:preflight:end -->\n\ncorpo\n"
    )
    out = gen.stamp_block(
        text, "prose", "> contrato", where="x", after="<!-- prumo:preflight:end -->\n"
    )
    assert out.index("<!-- prumo:preflight:end -->") < out.index("<!-- prumo:prose:begin -->")
    assert out.index("<!-- prumo:prose:end -->") < out.index("corpo")


def test_stamp_block_cai_no_h1_sem_after(gen: ModuleType) -> None:
    out = gen.stamp_block("# Título\n\ncorpo\n", "prose", "> contrato", where="x")
    assert out.index("# Título") < out.index("<!-- prumo:prose:begin -->")


def test_stamp_block_eh_idempotente(gen: ModuleType) -> None:
    text = "# T\n\n<!-- prumo:preflight:begin -->\n> pf\n<!-- prumo:preflight:end -->\n"
    once = gen.stamp_block(text, "prose", "> contrato", where="x")
    twice = gen.stamp_block(once, "prose", "> contrato", where="x")
    assert once == twice


def test_stamp_block_sem_ancora_aborta(gen: ModuleType) -> None:
    with pytest.raises(SystemExit):
        gen.stamp_block("sem h1 nem preflight\n", "prose", "> contrato", where="x")


def test_strip_block_remove_bloco_orfao(gen: ModuleType) -> None:
    text = "# T\n\n<!-- prumo:prose:begin -->\n> velho\n<!-- prumo:prose:end -->\ncorpo\n"
    out = gen.strip_block(text, "prose")
    assert "prumo:prose" not in out
    assert out == "# T\ncorpo\n"


def test_strip_block_eh_no_op_sem_bloco(gen: ModuleType) -> None:
    text = "# T\n\ncorpo\n"
    assert gen.strip_block(text, "prose") == text


def test_render_skill_blocks_zera_o_corpo_de_prosa_quando_nao_declarada(
    gen: ModuleType, registry: Any
) -> None:
    blocks = {tag: body for tag, body, _ in gen.render_skill_blocks(registry.get("paper-extract"))}
    assert blocks["preflight"]
    assert blocks["prose"] == ""


def test_fragmento_ausente_aborta(gen: ModuleType) -> None:
    with pytest.raises(SystemExit):
        gen._fragment("inexistente")


def test_todas_as_skills_de_prosa_carregam_o_bloco(registry: Any) -> None:
    prose_skills = [n for n in registry.names() if registry.get(n).prose]
    assert set(prose_skills) == {
        "peer-review",
        "scientific-writing",
        "write-paper",
        "write-projeto-cep",
        "write-scientific",
        "write-statistics",
    }
    for name in registry.names():
        # `body` é o SKILL.md pós-frontmatter, já lido pelo parser
        has_block = "<!-- prumo:prose:begin -->" in registry.get(name).body
        assert has_block is (name in prose_skills), name


def test_render_prose_usa_a_variante_cli_quando_a_skill_tem_cli(
    gen: ModuleType, registry: Any
) -> None:
    """Skill com CLI não recompõe a cascata em prosa — lê o `language` do prep."""
    body = gen.render_prose(registry.get("write-paper"))
    assert "`prumo write prep --json` devolve `language`" in body
    assert "não releia `pj_config.toml`" in body
    # a variante livre (cascata em prosa) não aparece nessas skills
    assert "Resolva nesta ordem" not in body


def test_locale_lock_vence_a_variante_cli(gen: ModuleType, registry: Any) -> None:
    """write-projeto-cep é `requires: [cli]` E travada — a trava ganha."""
    manifest = registry.get("write-projeto-cep")
    assert "cli" in manifest.requires
    body = gen.render_prose(manifest)
    assert "Idioma travado em `pt-BR`" in body
    assert "prumo write prep" not in body


def test_julgamento_puro_mantem_a_cascata_em_prosa(gen: ModuleType, registry: Any) -> None:
    """Sem CLI para consultar, a cascata precisa estar no texto (ADR-0019)."""
    manifest = registry.get("scientific-writing")
    assert manifest.requires == ()
    body = gen.render_prose(manifest)
    assert "Resolva nesta ordem" in body
    assert "prumo write prep" not in body
