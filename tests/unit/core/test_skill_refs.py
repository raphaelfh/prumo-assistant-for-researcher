"""Tests da reescrita de invocações de skills antigas (spec D6)."""

from __future__ import annotations

from pathlib import Path

from par.core.skill_refs import (
    RefChange,
    migrate_skill_names,
    move_plugin_copies,
    plugin_copies,
    rewrite_invocations,
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
