"""Tests da reescrita de invocações de skills antigas (spec D6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from par.core.skill_refs import (
    ObsoleteRef,
    RefChange,
    backup_plugin_copies,
    exclude_paths,
    migrate_skill_names,
    move_plugin_copies,
    obsolete_ref_issues,
    obsolete_refs,
    plugin_copies,
    rewrite_invocations,
    scan_obsolete_refs,
    scan_skill_refs,
)
from par.core.skills import SkillRef

LEGACY = {
    "paper-extract": SkillRef("paper", "extract"),
    "paper-extract-all": SkillRef("paper", "extract"),
    "paper-manager": SkillRef("paper", "library"),
    "wiki-query": SkillRef("wiki", "query"),
}


def test_reescreve_token_prefixado_preservando_barra_e_argumentos() -> None:
    out, n = rewrite_invocations("rode `/par:paper-manager sync` e /par:paper-extract @k", LEGACY)
    assert out == "rode `/par:paper library sync` e /par:paper extract @k"
    assert n == 2


def test_reescreve_prefixo_anterior_ao_par() -> None:
    """Projeto criado antes da ADR-0034 grava ``prumo-assist:<antigo>``; nunca ``par:<antigo>``."""
    out, n = rewrite_invocations("/prumo-assist:paper-manager e prumo-assist:wiki-query", LEGACY)
    assert out == "/par:paper library e par:wiki query"
    assert n == 2
    assert rewrite_invocations("/prumo-assist:start", LEGACY) == ("/prumo-assist:start", 0)


def test_nome_mais_longo_vence() -> None:
    out, n = rewrite_invocations("/par:paper-extract-all --limit 5", LEGACY)
    assert out == "/par:paper extract --limit 5"
    assert n == 1


def test_nao_toca_valor_sem_prefixo_nem_nome_desconhecido() -> None:
    text = "generator: wiki-query\n/par:start\npar:wiki-queryx\n"
    assert rewrite_invocations(text, LEGACY) == (text, 0)


def test_idempotente() -> None:
    once, _ = rewrite_invocations("/par:wiki-query", LEGACY)
    assert rewrite_invocations(once, LEGACY) == (once, 0)


def test_mapa_vazio_nao_faz_nada() -> None:
    assert rewrite_invocations("/par:wiki-query", {}) == ("/par:wiki-query", 0)


def _pj(tmp_path: Path) -> Path:
    pj = tmp_path / "pj_x"
    (pj / ".claude").mkdir(parents=True)
    (pj / "README.md").write_text("use /prumo-assist:paper-manager\n", encoding="utf-8")
    (pj / ".claude" / "pj_config.toml").write_text("# /par:paper-extract-all\n", encoding="utf-8")
    papers = pj / "docs" / "references" / "papers" / "k"
    papers.mkdir(parents=True)
    (papers / "_extract.md").write_text("/par:paper-extract\n", encoding="utf-8")
    (pj / ".venv").mkdir()
    (pj / ".venv" / "x.md").write_text("/par:wiki-query\n", encoding="utf-8")
    (pj / "notes.py").write_text("# /par:wiki-query\n", encoding="utf-8")
    return pj


def test_scan_lista_so_md_e_toml_fora_dos_excluidos(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    assert scan_skill_refs(pj, LEGACY) == [
        RefChange(".claude/pj_config.toml", 1),
        RefChange("README.md", 1),
    ]
    assert "paper-manager" in (pj / "README.md").read_text(encoding="utf-8")


def test_migrate_escreve_e_zera_o_scan(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    changes = migrate_skill_names(pj, LEGACY)
    assert [c.path for c in changes] == [".claude/pj_config.toml", "README.md"]
    assert (pj / "README.md").read_text(encoding="utf-8") == "use /par:paper library\n"
    assert scan_skill_refs(pj, LEGACY) == []
    extract = pj / "docs" / "references" / "papers" / "k" / "_extract.md"
    assert "paper-extract" in extract.read_text(encoding="utf-8")


SKILL_NAMES = {"paper", "wiki-query", "wiki"}
AGENT_FILES = {"reviewer.md", "reader.md"}


def _pj_com_copias(tmp_path: Path) -> Path:
    for name in ("paper", "wiki-query", "minha-skill"):
        d = tmp_path / ".claude" / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "reviewer.md").write_text("reviewer\n", encoding="utf-8")
    (agents / "meu-agent.md").write_text("meu\n", encoding="utf-8")
    return tmp_path


def test_plugin_copies_lista_so_nomes_do_par(tmp_path: Path) -> None:
    pj = _pj_com_copias(tmp_path)
    assert plugin_copies(pj, SKILL_NAMES, AGENT_FILES) == [
        ".claude/skills/paper",
        ".claude/skills/wiki-query",
        ".claude/agents/reviewer.md",
    ]


def test_plugin_copies_sem_claude_eh_vazio(tmp_path: Path) -> None:
    assert plugin_copies(tmp_path, SKILL_NAMES, AGENT_FILES) == []


def test_plugin_copies_ignora_arquivo_solto_em_skills(tmp_path: Path) -> None:
    skills = tmp_path / ".claude" / "skills"
    skills.mkdir(parents=True)
    (skills / "paper").write_text("não é diretório\n", encoding="utf-8")
    assert plugin_copies(tmp_path, SKILL_NAMES, AGENT_FILES) == []


def test_plugin_copies_aceita_link_para_diretorio(tmp_path: Path) -> None:
    alvo = tmp_path / "fora" / "paper"
    alvo.mkdir(parents=True)
    skills = tmp_path / ".claude" / "skills"
    skills.mkdir(parents=True)
    (skills / "paper").symlink_to(alvo, target_is_directory=True)
    assert plugin_copies(tmp_path, SKILL_NAMES, AGENT_FILES) == [".claude/skills/paper"]


def test_move_plugin_copies_preserva_estrutura_e_conteudo(tmp_path: Path) -> None:
    pj = _pj_com_copias(tmp_path)
    skill_bytes = (pj / ".claude/skills/paper/SKILL.md").read_bytes()
    agent_bytes = (pj / ".claude/agents/reviewer.md").read_bytes()
    rels = plugin_copies(pj, SKILL_NAMES, AGENT_FILES)
    dest = pj / ".prumo" / "legacy-copies" / "20261002-120000"

    assert move_plugin_copies(pj, rels, dest) == rels

    assert (dest / "skills" / "paper" / "SKILL.md").read_bytes() == skill_bytes
    assert (dest / "skills" / "wiki-query" / "SKILL.md").is_file()
    assert (dest / "agents" / "reviewer.md").read_bytes() == agent_bytes
    assert not (pj / ".claude/skills/paper").exists()
    assert not (pj / ".claude/skills/wiki-query").exists()
    assert not (pj / ".claude/agents/reviewer.md").exists()
    assert (pj / ".claude/skills/minha-skill/SKILL.md").is_file()
    assert (pj / ".claude/agents/meu-agent.md").is_file()


def test_move_plugin_copies_apaga_diretorios_vazios(tmp_path: Path) -> None:
    (tmp_path / ".claude/skills/paper").mkdir(parents=True)
    (tmp_path / ".claude/skills/paper/SKILL.md").write_text("x\n", encoding="utf-8")
    (tmp_path / ".claude/agents").mkdir(parents=True)
    (tmp_path / ".claude/agents/reviewer.md").write_text("y\n", encoding="utf-8")
    rels = plugin_copies(tmp_path, SKILL_NAMES, AGENT_FILES)

    move_plugin_copies(tmp_path, rels, tmp_path / ".prumo" / "legacy-copies" / "t")

    assert not (tmp_path / ".claude/skills").exists()
    assert not (tmp_path / ".claude/agents").exists()
    assert (tmp_path / ".claude").is_dir()


def test_move_plugin_copies_sem_rels_nao_cria_destino(tmp_path: Path) -> None:
    dest = tmp_path / ".prumo" / "legacy-copies" / "t"
    assert move_plugin_copies(tmp_path, [], dest) == []
    assert not dest.exists()


def _arvore_compartilhada(tmp_path: Path) -> Path:
    shared = tmp_path / "shared"
    for name in ("paper", "minha-skill"):
        (shared / name).mkdir(parents=True)
        (shared / name / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    return shared


def test_plugin_copies_ignora_skills_que_eh_link(tmp_path: Path) -> None:
    shared = _arvore_compartilhada(tmp_path)
    pj = tmp_path / "pj"
    (pj / ".claude").mkdir(parents=True)
    (pj / ".claude" / "skills").symlink_to(shared, target_is_directory=True)

    rels = plugin_copies(pj, SKILL_NAMES, AGENT_FILES)
    move_plugin_copies(pj, rels, pj / ".prumo" / "legacy-copies" / "t")

    assert rels == []
    assert (shared / "paper" / "SKILL.md").is_file()
    assert (pj / ".claude" / "skills").is_symlink()


def test_plugin_copies_ignora_agents_que_eh_link(tmp_path: Path) -> None:
    shared = tmp_path / "agents-compartilhados"
    shared.mkdir()
    (shared / "reviewer.md").write_text("r\n", encoding="utf-8")
    pj = tmp_path / "pj"
    (pj / ".claude").mkdir(parents=True)
    (pj / ".claude" / "agents").symlink_to(shared, target_is_directory=True)

    assert plugin_copies(pj, SKILL_NAMES, AGENT_FILES) == []
    assert (shared / "reviewer.md").is_file()


def test_plugin_copies_ignora_claude_que_eh_link(tmp_path: Path) -> None:
    fora = tmp_path / "fora"
    (fora / "skills" / "paper").mkdir(parents=True)
    pj = tmp_path / "pj"
    pj.mkdir()
    (pj / ".claude").symlink_to(fora, target_is_directory=True)

    assert plugin_copies(pj, SKILL_NAMES, AGENT_FILES) == []
    assert (fora / "skills" / "paper").is_dir()


def test_exclude_paths_tira_o_que_esta_dentro_das_copias() -> None:
    changes = [
        RefChange(".claude/skills/paper/SKILL.md", 2),
        RefChange(".claude/skills/paper-x/SKILL.md", 1),
        RefChange(".claude/agents/reviewer.md", 1),
        RefChange("README.md", 3),
    ]
    rels = [".claude/skills/paper", ".claude/agents/reviewer.md"]
    assert exclude_paths(changes, rels) == [
        RefChange(".claude/skills/paper-x/SKILL.md", 1),
        RefChange("README.md", 3),
    ]


def test_backup_plugin_copies_move_para_legacy_copies(tmp_path: Path) -> None:
    pj = _pj_com_copias(tmp_path)
    rels = plugin_copies(pj, SKILL_NAMES, AGENT_FILES)

    assert backup_plugin_copies(pj, rels, "20261002-120000") == (
        ".prumo/legacy-copies/20261002-120000"
    )
    assert (pj / ".prumo/legacy-copies/20261002-120000/skills/paper/SKILL.md").is_file()
    assert not (pj / ".claude/skills/paper").exists()


def test_backup_plugin_copies_sem_rels_devolve_none(tmp_path: Path) -> None:
    assert backup_plugin_copies(tmp_path, [], "t") is None
    assert not (tmp_path / ".prumo").exists()


# --- cópias fora de .claude/skills e .claude/agents (scripts, Codex, make) ------


def _pj_com_vendorizados(tmp_path: Path) -> Path:
    scripts = tmp_path / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    for name in ("_bib.py", "cite_graph.py", "README_zotero_annotations.md", "meu_script.py"):
        (scripts / name).write_text(f"# {name}\n", encoding="utf-8")
    (tmp_path / ".claude" / "make").mkdir()
    (tmp_path / ".claude" / "make" / ".gitkeep").write_text("", encoding="utf-8")
    codex = tmp_path / ".codex" / "agents"
    codex.mkdir(parents=True)
    (codex / "reader.toml").write_text(_PAR_AGENT_TOML, encoding="utf-8")
    (codex / "meu-agent.toml").write_text("# meu-agent.toml\n", encoding="utf-8")
    (tmp_path / ".codex" / "config.toml").write_text("model = 'x'\n", encoding="utf-8")
    for name in ("paper", "wiki-query", "minha-skill"):
        d = tmp_path / ".agents" / "skills" / name
        d.mkdir(parents=True)
        body = "# minha skill\n" if name == "minha-skill" else _par_skill_md(name)
        (d / "SKILL.md").write_text(body, encoding="utf-8")
    return tmp_path


#: Espelho do Codex de um agent do PAR: o corpo traz o bloco gerado ``prumo:runtime``.
_PAR_AGENT_TOML = (
    'name = "reader"\ndeveloper_instructions = """\n<!-- prumo:runtime:begin -->\n'
    'CLI: `prumo`.\n<!-- prumo:runtime:end -->\n"""\n'
)


def _par_skill_md(name: str) -> str:
    """SKILL.md como o PAR publica: frontmatter com o bloco ``prumo:``."""
    return f"---\nname: {name}\nprumo:\n  version: 2.0.0\n---\n# {name}\nRode `prumo paper sync`.\n"


def test_plugin_copies_lista_scripts_antigos_espelhos_do_codex_e_make_vazio(
    tmp_path: Path,
) -> None:
    pj = _pj_com_vendorizados(tmp_path)
    assert plugin_copies(pj, SKILL_NAMES, AGENT_FILES) == [
        ".claude/scripts/README_zotero_annotations.md",
        ".claude/scripts/_bib.py",
        ".claude/scripts/cite_graph.py",
        ".claude/make",
        ".codex/agents/reader.toml",
        ".agents/skills/paper",
        ".agents/skills/wiki-query",
    ]


def test_plugin_copies_ignora_make_com_arquivo_do_pesquisador(tmp_path: Path) -> None:
    make = tmp_path / ".claude" / "make"
    make.mkdir(parents=True)
    (make / "meu.mk").write_text("x:\n", encoding="utf-8")
    assert plugin_copies(tmp_path, SKILL_NAMES, AGENT_FILES) == []


def test_plugin_copies_aceita_make_sem_nada(tmp_path: Path) -> None:
    (tmp_path / ".claude" / "make").mkdir(parents=True)
    assert plugin_copies(tmp_path, SKILL_NAMES, AGENT_FILES) == [".claude/make"]


def test_move_vendorizados_vai_para_o_backup_e_poupa_o_resto(tmp_path: Path) -> None:
    pj = _pj_com_vendorizados(tmp_path)
    rels = plugin_copies(pj, SKILL_NAMES, AGENT_FILES)

    assert backup_plugin_copies(pj, rels, "t") == ".prumo/legacy-copies/t"

    bk = pj / ".prumo" / "legacy-copies" / "t"
    assert (bk / "scripts" / "_bib.py").read_text(encoding="utf-8") == "# _bib.py\n"
    assert (bk / "make" / ".gitkeep").is_file()
    assert (bk / ".codex" / "agents" / "reader.toml").is_file()
    assert (bk / ".agents" / "skills" / "paper" / "SKILL.md").is_file()
    assert (pj / ".claude" / "scripts" / "meu_script.py").is_file()
    assert not (pj / ".claude" / "scripts" / "_bib.py").exists()
    assert not (pj / ".claude" / "make").exists()
    assert (pj / ".codex" / "agents" / "meu-agent.toml").is_file()
    assert (pj / ".codex" / "config.toml").is_file()
    assert (pj / ".agents" / "skills" / "minha-skill" / "SKILL.md").is_file()
    assert plugin_copies(pj, SKILL_NAMES, AGENT_FILES) == []


def test_move_vendorizados_apaga_so_diretorios_que_ficam_vazios(tmp_path: Path) -> None:
    (tmp_path / ".claude" / "scripts").mkdir(parents=True)
    (tmp_path / ".claude" / "scripts" / "_csl.py").write_text("x\n", encoding="utf-8")
    (tmp_path / ".codex" / "agents").mkdir(parents=True)
    (tmp_path / ".codex" / "agents" / "verifier.toml").write_text(_PAR_AGENT_TOML, encoding="utf-8")
    (tmp_path / ".agents" / "skills" / "wiki").mkdir(parents=True)
    (tmp_path / ".agents" / "skills" / "wiki" / "SKILL.md").write_text(
        _par_skill_md("wiki"), encoding="utf-8"
    )
    rels = plugin_copies(tmp_path, SKILL_NAMES | {"wiki"}, AGENT_FILES | {"verifier.md"})
    assert len(rels) == 3, rels

    move_plugin_copies(tmp_path, rels, tmp_path / ".prumo" / "legacy-copies" / "t")

    assert not (tmp_path / ".claude" / "scripts").exists()
    assert not (tmp_path / ".codex").exists()
    assert not (tmp_path / ".agents").exists()
    assert (tmp_path / ".claude").is_dir()


def test_move_poupa_diretorio_vazio_que_nao_guardava_copia(tmp_path: Path) -> None:
    """Só sai o diretório que guardava uma cópia movida; vazio criado pelo pesquisador fica."""
    (tmp_path / ".claude" / "skills" / "paper").mkdir(parents=True)
    (tmp_path / ".claude" / "skills" / "paper" / "SKILL.md").write_text("x\n", encoding="utf-8")
    vazios = (".codex/agents", ".agents/skills", ".claude/scripts", ".claude/agents")
    for rel in vazios:
        (tmp_path / rel).mkdir(parents=True)

    move_plugin_copies(tmp_path, [".claude/skills/paper"], tmp_path / ".prumo" / "lc" / "t")

    assert not (tmp_path / ".claude" / "skills").exists()
    for rel in vazios:
        assert (tmp_path / rel).is_dir(), rel


def _terceiros_com_nome_do_par(pj: Path) -> Path:
    """Skills de um pacote de terceiros (instaladas em ``.agents/skills/``) e um agent do
    pesquisador, todos com nomes que o PAR já usou e nenhuma marca do PAR."""
    for name in ("peer-review", "scientific-writing"):
        d = pj / ".agents" / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: third-party\n---\n# {name}\n", encoding="utf-8"
        )
    (pj / ".agents" / "skills" / "wiki").mkdir()  # sem SKILL.md: nada a reconhecer
    (pj / ".codex" / "agents").mkdir(parents=True)
    (pj / ".codex" / "agents" / "reviewer.toml").write_text(
        'name = "reviewer"\ndeveloper_instructions = "Revise o diff do código."\n',
        encoding="utf-8",
    )
    return pj


_NOMES_DE_TERCEIROS = SKILL_NAMES | {"peer-review", "scientific-writing"}


def test_plugin_copies_poupa_espelho_sem_a_marca_do_par(tmp_path: Path) -> None:
    """O Claude Code não lê ``.agents/`` nem ``.codex/``: um homônimo de outro pacote não
    sombreia nada, então só o conteúdo do PAR faz de um espelho uma cópia."""
    pj = _terceiros_com_nome_do_par(tmp_path)

    rels = plugin_copies(pj, _NOMES_DE_TERCEIROS, AGENT_FILES)
    assert rels == []
    assert backup_plugin_copies(pj, rels, "t") is None
    assert (pj / ".agents" / "skills" / "peer-review" / "SKILL.md").is_file()
    assert (pj / ".codex" / "agents" / "reviewer.toml").is_file()


@pytest.mark.parametrize(
    "corpo",
    [
        "---\nname: peer-review\nprumo:\n  version: 1.2.0\n---\n",
        "<!-- prumo:runtime:begin -->\n**PAR 0.70.0**\n<!-- prumo:runtime:end -->\n",
        'devolva o JSON no contrato "PeerReviewReport/v1"\n',
        "Devolve SupportReport/v1.\n",
    ],
)
def test_plugin_copies_reconhece_espelho_com_a_marca_do_par(tmp_path: Path, corpo: str) -> None:
    (tmp_path / ".codex" / "agents").mkdir(parents=True)
    (tmp_path / ".codex" / "agents" / "reviewer.toml").write_text(corpo, encoding="utf-8")
    d = tmp_path / ".agents" / "skills" / "peer-review"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(corpo, encoding="utf-8")

    assert plugin_copies(tmp_path, _NOMES_DE_TERCEIROS, AGENT_FILES) == [
        ".codex/agents/reviewer.toml",
        ".agents/skills/peer-review",
    ]


@pytest.mark.parametrize(
    "corpo",
    [
        "Revise o manuscrito em pj_estudo/docs.\n",
        "Antes de tudo, rode `prumo status`.\n",
        "Mantenha o prumo da arquitetura.\n",
        "Escreva com aprumo.\n",
        "Use prumo paper find antes.\n",
        "Rode `prumo paper sync` no pj_leg1.\n",
        "Depois rode /prumo-assist:peer-review e /par:review critique.\n",
        "---\nname: review\ndescription: revisa o pj_alpha com o PAR\n---\n",
    ],
)
def test_plugin_copies_poupa_espelho_do_pesquisador_que_cita_o_par(
    tmp_path: Path, corpo: str
) -> None:
    """Skill ou agent escrito pelo pesquisador num ``pj_*`` cita o projeto, o CLI ``prumo``
    ou a palavra "prumo" sem ser cópia: só o que o PAR publica (bloco ``prumo:`` do
    frontmatter, bloco ``prumo:runtime``, contrato ``<Schema>/vN``) marca um espelho."""
    (tmp_path / ".codex" / "agents").mkdir(parents=True)
    (tmp_path / ".codex" / "agents" / "reviewer.toml").write_text(corpo, encoding="utf-8")
    for name in ("review", "start", "write"):
        d = tmp_path / ".agents" / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(corpo, encoding="utf-8")

    assert plugin_copies(tmp_path, SKILL_NAMES | {"review", "start", "write"}, AGENT_FILES) == []


def test_plugin_copies_reconhece_espelho_de_cada_skill_e_agent_do_plugin(tmp_path: Path) -> None:
    """A marca não pode sumir do que o PAR publica hoje: o espelho de cada um é reconhecido."""
    raiz = Path(__file__).resolve().parents[3]
    skills = sorted(p.parent.name for p in (raiz / "skills").glob("*/SKILL.md"))
    agents = sorted(p.name for p in (raiz / "agents").glob("*.md"))
    for name in skills:
        (tmp_path / ".agents" / "skills" / name).mkdir(parents=True)
        texto = (raiz / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        (tmp_path / ".agents" / "skills" / name / "SKILL.md").write_text(texto, encoding="utf-8")
    (tmp_path / ".codex" / "agents").mkdir(parents=True)
    for name in agents:
        texto = (raiz / "agents" / name).read_text(encoding="utf-8")
        (tmp_path / ".codex" / "agents" / f"{Path(name).stem}.toml").write_text(
            f"developer_instructions = {texto!r}\n", encoding="utf-8"
        )

    assert skills and agents
    assert plugin_copies(tmp_path, set(skills), set(agents)) == [
        *(f".codex/agents/{Path(a).stem}.toml" for a in agents),
        *(f".agents/skills/{s}" for s in skills),
    ]


def test_plugin_copies_ignora_codex_e_agents_que_sao_link(tmp_path: Path) -> None:
    fora = _pj_com_vendorizados(tmp_path / "fora")
    pj = tmp_path / "pj"
    pj.mkdir()
    (pj / ".codex").symlink_to(fora / ".codex", target_is_directory=True)
    (pj / ".agents").mkdir()
    (pj / ".agents" / "skills").symlink_to(fora / ".agents" / "skills", target_is_directory=True)
    (pj / ".claude").mkdir()
    (pj / ".claude" / "scripts").symlink_to(fora / ".claude" / "scripts", target_is_directory=True)

    assert plugin_copies(pj, SKILL_NAMES, AGENT_FILES) == []
    assert (fora / ".codex" / "agents" / "reader.toml").is_file()


# --- [referencia_obsoleta]: linhas de instrução que ensinam o que saiu ----------


@pytest.mark.parametrize(
    "line",
    [
        "/plugin install prumo-assist",
        "rode /prumo-assist:start",
        "plugin prumo-assist.",
        "use mcp__qmd__query para buscar",
        "o MCP `qmd` indexa o wiki",
        "busque pelo MCP qmd",
        "o qmd (MCP) responde",
        "qmd via MCP",
        "use o MCP do qmd",
        "Plugin: skills + agents + MCP qmd",
        "os agents e o MCP `qmd` (busca no wiki).",
        "MCP qmd (busca no wiki)",
        "não use Grep: chame mcp__qmd__search",
        "exporte com prumo-zettlr-export doc.md",
        "uv tool install git+https://github.com/raphaelfh/prumo-assistant-for-researcher",
        "veja .Codex/rules/safe_outputs.md",
        "\t@python3 .claude/scripts/paper_sync.py .",
        'rode python3 .claude/scripts/cite_lookup.py . "termo"',
        "python3 ../.claude/scripts/cite_graph.py <pj_path_absoluto>",
        "anotações: .claude/scripts/README_zotero_annotations.md",
    ],
)
def test_obsolete_refs_acha_referencia_que_saiu(line: str) -> None:
    hits = obsolete_refs(f"# título\n{line}\n")
    assert [n for n, _ in hits] == [2], hits


@pytest.mark.parametrize(
    "line",
    [
        "/plugin install par@prumo-assistant-for-researcher",
        "github.com/raphaelfh/prumo-assistant-for-researcher",
        "texto prumo-assisted pelo agente",
        'qmd query "fator de risco"',
        "busca semântica: qmd search, qmd embed",
        "tools mcp__plugin_par_prumo__paper_find",
        "uv tool install ruff",
        ".codex/config.toml é do Codex",
        "o servidor MCP do PAR sobe pelo lançador; o CLI qmd é opcional",
        # dizem o certo sobre o qmd (a própria redação do README do plugin entre elas)
        "qmd é CLI opcional (ver Pré-requisitos); não há servidor MCP do qmd no plugin.",
        "É CLI: não há servidor MCP do qmd no plugin.",
        "o qmd não é MCP",
        "qmd não usa MCP",
        "Busca com qmd (não há MCP)",
        "qmd é só CLI, sem MCP",
        "Não há MCP do qmd; use o CLI.",
        "o MCP do qmd saiu",
        "MCP prumo + qmd CLI",
        "Use as ferramentas MCP e o qmd",
        "- MCP `prumo`; qmd pelo terminal",
        "Tools: MCP, qmd, pandoc",
        "| qmd | CLI | MCP |",
        "Bash(qmd *)",
        "python3 .claude/scripts/meu_script.py",
        ".claude/scripts/paper_sync.pyc é lixo",
    ],
)
def test_obsolete_refs_poupa_o_que_vale_hoje(line: str) -> None:
    assert obsolete_refs(line) == []


def test_obsolete_refs_poupa_a_redacao_do_readme_do_plugin() -> None:
    readme = Path(__file__).resolve().parents[3] / "README.md"
    assert obsolete_refs(readme.read_text(encoding="utf-8")) == []


def test_obsolete_refs_mesma_linha_com_dois_motivos() -> None:
    hits = obsolete_refs("prumo-assist com mcp__qmd__search\n")
    assert [n for n, _ in hits] == [1, 1]
    assert len({label for _, label in hits}) == 2


def _pj_com_referencias(tmp_path: Path) -> Path:
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / "CLAUDE.md").write_text("# pj\n\nqmd via MCP `qmd`\n", encoding="utf-8")
    (tmp_path / ".claude" / "rules" / "wiki.md").write_text(
        "use .Codex/rules/x.md\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text(
        "/prumo-assist:paper-manager sync\n/plugin install prumo-assist\n", encoding="utf-8"
    )
    (tmp_path / "Makefile").write_text("x:\n\tprumo-zettlr-export a.md\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "_log.md").write_text("mcp__qmd__query (histórico)\n", encoding="utf-8")
    (tmp_path / "notas.md").write_text("mcp__qmd__query\n", encoding="utf-8")
    return tmp_path


def test_scan_obsolete_refs_so_olha_arquivos_de_instrucao(tmp_path: Path) -> None:
    pj = _pj_com_referencias(tmp_path)
    refs = scan_obsolete_refs(pj, LEGACY)
    assert [(r.path, r.line) for r in refs] == [
        ("CLAUDE.md", 3),
        ("README.md", 2),
        ("Makefile", 2),
        (".claude/rules/wiki.md", 1),
    ]
    assert all(isinstance(r, ObsoleteRef) for r in refs)


def test_scan_obsolete_refs_le_link_para_o_mesmo_arquivo_uma_vez(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("mcp__qmd__query\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").symlink_to(tmp_path / "CLAUDE.md")
    assert [(r.path, r.line) for r in scan_obsolete_refs(tmp_path, LEGACY)] == [("CLAUDE.md", 1)]


def test_obsolete_ref_issues_uma_issue_agrupada_por_motivo(tmp_path: Path) -> None:
    pj = _pj_com_referencias(tmp_path)
    (pj / "AGENTS.md").write_text("veja .Codex/agents/\n", encoding="utf-8")

    (issue,) = obsolete_ref_issues(pj, LEGACY)

    assert issue.startswith("[referencia_obsoleta]")
    assert "AGENTS.md:1, .claude/rules/wiki.md:1" in issue
    for trecho in ("CLAUDE.md:3", "README.md:2", "Makefile:2", "Edite estas linhas"):
        assert trecho in issue, issue
    assert "README.md:1" not in issue
    assert "_log.md" not in issue
    assert issue.count(".Codex/") == 1


def test_obsolete_ref_issues_aponta_receita_que_chama_script_antigo(tmp_path: Path) -> None:
    """O ``prumo update`` move o script; a receita que o chama quebraria calada."""
    (tmp_path / "Makefile").write_text(
        "sync-paper:\n\t@python3 .claude/scripts/paper_sync.py .\n"
        "\t@python3 .claude/scripts/cite_graph.py .\n"
        "meu:\n\t@python3 .claude/scripts/meu_script.py\n",
        encoding="utf-8",
    )

    (issue,) = obsolete_ref_issues(tmp_path, LEGACY)

    assert "Makefile:2, Makefile:3" in issue, issue
    assert "Makefile:5" not in issue
    assert "`.claude/scripts/`" in issue
    assert "prumo update" in issue


def test_obsolete_ref_issues_sem_referencia_eh_vazio(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text('rode `qmd query "x"` e /par:start\n', encoding="utf-8")
    assert obsolete_ref_issues(tmp_path, LEGACY) == []
