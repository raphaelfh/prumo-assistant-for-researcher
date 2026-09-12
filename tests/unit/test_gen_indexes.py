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

from prumo_assist.core.skills import _TOOL_TOKEN_RE

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


def _mode(registry: Any, skill: str, mode: str) -> Any:
    from prumo_assist.core.skills import SkillRef

    found = registry.find_mode(SkillRef(skill, mode))
    assert found is not None, f"{skill}/{mode}"
    return found


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


def test_skills_table_tem_uma_linha_por_modo(gen: ModuleType, registry: Any) -> None:
    table = gen.render_skills_table(registry)
    assert "`/prumo-assist:start`" in table
    assert "`/prumo-assist:paper extract`" in table
    sem_modos = sum(1 for n in registry.names() if not registry.get(n).modes)
    # uma linha por modo + uma por skill sem modos + 2 de cabeçalho
    assert table.count("\n") + 1 == len(registry.iter_modes()) + sem_modos + 2


def test_superficie_eh_start_mais_cinco_dominios(registry: Any) -> None:
    assert registry.names() == ["paper", "protocol", "review", "start", "wiki", "write"]
    assert registry.get("start").modes == ()


def test_modes_table_lista_todas_as_frases(gen: ModuleType, registry: Any) -> None:
    skill = registry.get("paper")
    table = gen.render_modes_table(skill)
    for mode in skill.modes:
        for phrase in mode.phrases:
            assert phrase in table
        assert f"`{mode.name}`" in table


def test_frontmatter_derivado_une_tools_sem_duplicar(gen: ModuleType, registry: Any) -> None:
    derived = gen.derived_frontmatter(registry.get("write"))
    tools = _TOOL_TOKEN_RE.findall(derived["allowed-tools"].removeprefix("allowed-tools: "))
    assert "Read" in tools and tools.count("Read") == 1
    assert derived["argument-hint"].startswith('argument-hint: "[')
    assert derived["when_to_use"].startswith("when_to_use: |\n")


def test_skill_com_modos_carrega_o_frontmatter_derivado(registry: Any, gen: ModuleType) -> None:
    for name in registry.names():
        skill = registry.get(name)
        if not skill.modes:
            continue
        text = skill.path.read_text(encoding="utf-8")
        for rendered in gen.derived_frontmatter(skill).values():
            assert rendered in text, (name, rendered.split(":")[0])


def test_replace_frontmatter_key_troca_bloco_e_escalar(gen: ModuleType) -> None:
    text = (
        "---\nname: x\ndescription: d\nwhen_to_use: |\n  velho\n  velho2\n"
        "allowed-tools: Read\nprumo:\n  version: 1\n---\n\nbody\n"
    )
    out = gen.replace_frontmatter_key(text, "when_to_use", "when_to_use: |\n  novo", where="x")
    out = gen.replace_frontmatter_key(out, "allowed-tools", "allowed-tools: Read Grep", where="x")
    assert "velho" not in out and "  novo\n" in out
    assert "allowed-tools: Read Grep\n" in out
    assert out.endswith("---\n\nbody\n")


def test_replace_frontmatter_key_insere_antes_de_prumo(gen: ModuleType) -> None:
    text = "---\nname: x\ndescription: d\nprumo:\n  version: 1\n---\n"
    out = gen.replace_frontmatter_key(text, "argument-hint", 'argument-hint: "[a]"', where="x")
    assert 'description: d\nargument-hint: "[a]"\nprumo:' in out


def test_replace_frontmatter_key_eh_idempotente(gen: ModuleType) -> None:
    text = "---\nname: x\nwhen_to_use: |\n  a\nprumo:\n  v: 1\n---\nb\n"
    once = gen.replace_frontmatter_key(text, "when_to_use", "when_to_use: |\n  z", where="x")
    assert (
        gen.replace_frontmatter_key(once, "when_to_use", "when_to_use: |\n  z", where="x") == once
    )


def test_skill_md_com_modos_nao_carrega_preflight(gen: ModuleType, registry: Any) -> None:
    blocks = {tag: body for tag, body, _ in gen.render_skill_blocks(registry.get("paper"))}
    assert blocks["preflight"] == "" and blocks["prose"] == ""
    assert "`extract`" in blocks["modes-table"]


def test_toda_frase_de_modo_eh_unica_no_plugin(registry: Any) -> None:
    vistas: dict[str, str] = {}
    for ref, mode in registry.iter_modes():
        for phrase in mode.phrases:
            assert phrase not in vistas, f"'{phrase}' em {vistas.get(phrase)} e {ref.slug}"
            vistas[phrase] = ref.slug


def test_adr_index_lista_todos_os_adrs(gen: ModuleType) -> None:
    body = gen.render_adr_index()
    n_adrs = len(list((gen.REPO / "docs" / "adr").glob("adr-*.md")))
    assert n_adrs >= 14
    assert body.count("[[adr/adr-") == n_adrs


def test_render_prose_usa_a_cascata_livre_por_default(gen: ModuleType, registry: Any) -> None:
    body = gen.render_prose(_mode(registry, "write", "style"))
    assert "Contrato de prosa" in body
    assert "default `en-US`" in body
    assert "Nunca traduza" in body
    assert "Citação no fim do período" in body
    assert "travado" not in body


def test_render_prose_interpola_o_locale_travado(gen: ModuleType, registry: Any) -> None:
    body = gen.render_prose(_mode(registry, "protocol", "cep"))
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
    blocks = {
        tag: body for tag, body, _ in gen.render_skill_blocks(_mode(registry, "paper", "extract"))
    }
    assert blocks["preflight"]
    assert blocks["prose"] == ""


def test_fragmento_ausente_aborta(gen: ModuleType) -> None:
    with pytest.raises(SystemExit):
        gen._fragment("inexistente")


def test_todos_os_modos_de_prosa_carregam_o_bloco(registry: Any) -> None:
    prose_modes = {ref.slug for ref, m in registry.iter_modes() if m.prose}
    assert prose_modes == {
        "protocol/cep",
        "protocol/sap",
        "write/manuscript",
        "write/section",
        "write/style",
    }
    for ref, mode in registry.iter_modes():
        # `body` é o arquivo do modo pós-frontmatter, já lido pelo parser
        has_block = "<!-- prumo:prose:begin -->" in mode.body
        assert has_block is (ref.slug in prose_modes), ref.slug
    for name in registry.names():
        assert "<!-- prumo:prose:begin -->" not in registry.get(name).body, name


def test_render_prose_usa_a_variante_cli_quando_a_skill_tem_cli(
    gen: ModuleType, registry: Any
) -> None:
    """Skill com CLI não recompõe a cascata em prosa — lê o `language` do prep."""
    body = gen.render_prose(_mode(registry, "write", "manuscript"))
    assert "`prumo write prep --json` devolve `language`" in body
    assert "não releia `pj_config.toml`" in body
    # a variante livre (cascata em prosa) não aparece nessas skills
    assert "Resolva nesta ordem" not in body


def test_locale_lock_vence_a_variante_cli(gen: ModuleType, registry: Any) -> None:
    """protocol cep é `requires: [cli]` E travada — a trava ganha."""
    manifest = _mode(registry, "protocol", "cep")
    assert "cli" in manifest.requires
    body = gen.render_prose(manifest)
    assert "Idioma travado em `pt-BR`" in body
    assert "prumo write prep" not in body


def test_julgamento_puro_mantem_a_cascata_em_prosa(gen: ModuleType, registry: Any) -> None:
    """Sem CLI para consultar, a cascata precisa estar no texto (ADR-0019)."""
    manifest = _mode(registry, "write", "style")
    assert manifest.requires == ()
    body = gen.render_prose(manifest)
    assert "Resolva nesta ordem" in body
    assert "prumo write prep" not in body


def test_kb_index_lista_os_guias_de_docs(gen: ModuleType) -> None:
    """Página nova em docs/ entra no catálogo gerado, sem edição à mão."""
    body = gen.render_kb_index()
    assert "- [[positioning]] · Posicionamento e claims do prumo-assist" in body
    assert "[[_index]]" not in body
