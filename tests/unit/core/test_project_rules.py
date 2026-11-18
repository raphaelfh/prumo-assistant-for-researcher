"""Tests do bloco ``prumo:project-rules`` do AGENTS.md (ADR-0046). Fixtures sintéticas."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

import pytest

from par import ConfigError
from par.core import project_rules as pr
from par.core.config import DEFAULTS
from par.core.paths import resolve_resource


def _cfg(**over: Any) -> dict[str, Any]:
    cfg = copy.deepcopy(DEFAULTS)
    for dotted, value in over.items():
        section, key = dotted.split("__")
        cfg[section][key] = value
    return cfg


def _pj(tmp_path: Path, agents: str, toml: str = "") -> Path:
    pj = tmp_path / "pj_exemplo"
    (pj / ".claude").mkdir(parents=True)
    (pj / ".claude" / "pj_config.toml").write_text(toml, encoding="utf-8")
    (pj / "AGENTS.md").write_text(agents, encoding="utf-8")
    return pj


def test_bloco_default_traz_idioma_e_as_tres_instrucoes() -> None:
    out = pr.render_project_rules(_cfg())
    assert out.startswith(pr.BLOCK_BEGIN) and out.endswith(pr.BLOCK_END)
    assert "Idioma de **interação**: pt-BR" in out
    assert "en-US (`[writing].language`)" in out
    assert "Mínimo necessário" in out
    assert "Célula mínima = 5" in out and "entre 1 e 4" in out
    assert "Dado fora do git" in out


def test_bloco_com_limiar_do_projeto_e_idioma_ingles() -> None:
    out = pr.render_project_rules(_cfg(safe_outputs__min_cell=11, interaction__language="en-US"))
    assert "Célula mínima = 11" in out and "entre 1 e 10" in out
    assert "Idioma de **interação**: en-US" in out and "em inglês" in out


def test_bloco_com_supressao_desligada() -> None:
    out = pr.render_project_rules(_cfg(safe_outputs__min_cell=0))
    assert "Célula mínima" not in out
    assert "supressão de célula pequena está desligada" in out
    assert "Mínimo necessário" in out and "Dado fora do git" in out


def test_bloco_sem_dado_de_paciente_so_mantem_dado_fora_do_git() -> None:
    out = pr.render_project_rules(_cfg(safe_outputs__patient_data=False))
    assert "não trabalha com dado de paciente" in out
    assert "Célula mínima" not in out and "Mínimo necessário" not in out
    assert "Dado fora do git" in out


def test_template_do_pj_base_traz_o_bloco_dos_defaults() -> None:
    """O AGENTS.md empacotado não pode divergir do renderizador (Princípio VII)."""
    agents = (resolve_resource("templates") / "pj_base" / "AGENTS.md").read_text(encoding="utf-8")
    assert pr.render_project_rules(_cfg()) in agents
    assert "Idioma de **interação**: pt-BR. Idioma" not in agents.split(pr.BLOCK_BEGIN)[0]


def test_sync_atualiza_bloco_e_preserva_texto_humano(tmp_path: Path) -> None:
    antigo = pr.render_project_rules(_cfg())
    pj = _pj(
        tmp_path,
        f"# Persona\n\nminha nota\n\n{antigo}\n\n## Como operar\n\ntexto meu\n",
        "[safe_outputs]\nmin_cell = 10\n",
    )

    assert pr.sync_project_rules(pj, write=False) == "updated"
    assert "Célula mínima = 5" in (pj / "AGENTS.md").read_text(encoding="utf-8")
    assert pr.sync_project_rules(pj) == "updated"

    texto = (pj / "AGENTS.md").read_text(encoding="utf-8")
    assert "Célula mínima = 10" in texto and "Célula mínima = 5" not in texto
    assert "minha nota" in texto and "texto meu" in texto
    assert pr.sync_project_rules(pj) is None  # idempotente


def test_sync_troca_a_linha_fixa_antiga_pelo_bloco(tmp_path: Path) -> None:
    legado = (
        "# Persona e filosofia\n\nVocê é um assistente.\n\n"
        "Idioma de **interação**: pt-BR. Idioma de **escrita científica**: `[writing].language`\n"
        "em `.claude/pj_config.toml` (default `en-US`); documento de CEP/CONEP é sempre pt-BR.\n\n"
        "## Como operar\n"
    )
    pj = _pj(tmp_path, legado)

    assert pr.sync_project_rules(pj) == "inserted"

    texto = (pj / "AGENTS.md").read_text(encoding="utf-8")
    assert texto.count("Idioma de **interação**") == 1
    assert texto.index("Você é um assistente.") < texto.index(pr.BLOCK_BEGIN)
    assert texto.index(pr.BLOCK_END) < texto.index("## Como operar")


def test_sync_insere_depois_do_titulo_quando_nao_ha_linha_antiga(tmp_path: Path) -> None:
    pj = _pj(tmp_path, "# Meu AGENTS\n\ntexto meu\n")
    assert pr.sync_project_rules(pj) == "inserted"
    texto = (pj / "AGENTS.md").read_text(encoding="utf-8")
    assert texto.startswith("# Meu AGENTS\n\n" + pr.BLOCK_BEGIN)
    assert texto.rstrip().endswith("texto meu")


def test_sync_sem_agents_nao_faz_nada(tmp_path: Path) -> None:
    assert pr.sync_project_rules(tmp_path) is None


def test_delimitador_corrompido_e_erro_com_a_correcao(tmp_path: Path) -> None:
    pj = _pj(tmp_path, f"# A\n\n{pr.BLOCK_BEGIN}\nsem fim\n")
    with pytest.raises(ConfigError, match="prumo update"):
        pr.sync_project_rules(pj)


def test_rule_antiga_intacta_sai_e_editada_fica(tmp_path: Path) -> None:
    rule = tmp_path / ".claude" / "rules" / "safe_outputs.md"
    rule.parent.mkdir(parents=True)
    assert pr.retire_legacy_rule(tmp_path) is None

    rule.write_text("rule editada pelo projeto\n", encoding="utf-8")
    assert pr.retire_legacy_rule(tmp_path, write=False) == "kept"
    assert pr.retire_legacy_rule(tmp_path) == "kept" and rule.exists()

    # conteúdo qualquer com o hash "conhecido" trocado pelo do teste
    conteudo = b"rule sintetica identica ao template antigo\n"
    rule.write_bytes(conteudo)
    known = frozenset({hashlib.sha256(conteudo).hexdigest()})
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(pr, "_LEGACY_RULE_SHA256", known)
        assert pr.retire_legacy_rule(tmp_path, write=False) == "removed" and rule.exists()
        assert pr.retire_legacy_rule(tmp_path) == "removed"
    assert not rule.exists()


def test_aviso_de_celula_minima_baixa() -> None:
    assert pr.low_min_cell_warning(_cfg()) is None
    assert pr.low_min_cell_warning(_cfg(safe_outputs__min_cell=10)) is None
    assert (
        pr.low_min_cell_warning(_cfg(safe_outputs__min_cell=3, safe_outputs__patient_data=False))
        is None
    )
    aviso = pr.low_min_cell_warning(_cfg(safe_outputs__min_cell=3))
    assert aviso is not None and "[celula_minima_baixa]" in aviso and "min_cell = 5" in aviso
    assert "[celula_minima_baixa]" in (
        pr.low_min_cell_warning(_cfg(safe_outputs__min_cell=0)) or ""
    )
