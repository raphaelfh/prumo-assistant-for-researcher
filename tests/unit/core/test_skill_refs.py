"""Tests da reescrita de invocações de skills antigas (spec D6)."""

from __future__ import annotations

from pathlib import Path

from par.core.skill_refs import (
    RefChange,
    legacy_installed_dirs,
    migrate_skill_names,
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


def test_legacy_installed_dirs(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    (pj / ".claude" / "skills" / "wiki-query").mkdir(parents=True)
    (pj / ".claude" / "skills" / "wiki").mkdir(parents=True)
    assert legacy_installed_dirs(pj, LEGACY) == [".claude/skills/wiki-query"]


def test_legacy_installed_dirs_sem_diretorio(tmp_path: Path) -> None:
    assert legacy_installed_dirs(tmp_path, LEGACY) == []
