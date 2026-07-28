"""Tests da cascata de idioma de escrita (ADR-0021) resolvida no CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist import ConfigError
from prumo_assist.domains.write.compose import locale_lock, prep, resolve_language
from prumo_assist.domains.write.errors import WriteError


def _config(pj_path: Path, body: str) -> None:
    (pj_path / ".claude").mkdir(parents=True, exist_ok=True)
    (pj_path / ".claude" / "pj_config.toml").write_text(body, encoding="utf-8")


def test_default_en_us_sem_config(tmp_path: Path) -> None:
    assert resolve_language(tmp_path, kind="paper") == ("en-US", "default")


def test_pj_config_vence_o_default(tmp_path: Path) -> None:
    _config(tmp_path, '[writing]\nlanguage = "pt-BR"\n')
    assert resolve_language(tmp_path, kind="paper") == ("pt-BR", "pj_config")


def test_config_sem_secao_writing_reporta_default(tmp_path: Path) -> None:
    """`language_source` separa "o projeto escolheu" de "ninguém escolheu"."""
    _config(tmp_path, '[paper_extract]\nlanguage = "pt-BR"\n')
    assert resolve_language(tmp_path, kind="paper") == ("en-US", "default")


def test_flag_vence_o_pj_config(tmp_path: Path) -> None:
    _config(tmp_path, '[writing]\nlanguage = "pt-BR"\n')
    assert resolve_language(tmp_path, kind="paper", lang="en-US") == ("en-US", "flag")


def test_flag_invalida_recusa(tmp_path: Path) -> None:
    with pytest.raises(WriteError) as ei:
        resolve_language(tmp_path, kind="paper", lang="en")
    assert "en-US" in str(ei.value)


def test_locale_lock_vence_tudo(tmp_path: Path) -> None:
    """CEP é documento regulatório brasileiro: nem flag nem config o destravam."""
    _config(tmp_path, '[writing]\nlanguage = "en-US"\n')
    assert resolve_language(tmp_path, kind="projeto-cep", lang="en-US") == ("pt-BR", "locale_lock")


def test_locale_lock_sai_do_manifesto_da_skill() -> None:
    assert locale_lock("projeto-cep") == "pt-BR"
    assert locale_lock("paper") is None


def test_writing_language_invalido_estoura_no_caminho_de_escrita(tmp_path: Path) -> None:
    """O motivo desta cascata viver no CLI: validação onde a chave importa.

    `load_project_config` só era chamado por `paper extract`, então um typo em
    `[writing].language` quebrava a extração e era honrado em silêncio na escrita.
    """
    _config(tmp_path, '[writing]\nlanguage = "en"\n')
    with pytest.raises(ConfigError) as ei:
        resolve_language(tmp_path, kind="paper")
    assert "writing.language" in str(ei.value)


def test_prep_carrega_idioma_junto_do_template(tmp_path: Path) -> None:
    _config(tmp_path, '[writing]\nlanguage = "pt-BR"\n')
    result = prep(tmp_path, kind="paper")
    assert result.language == "pt-BR"
    assert result.language_source == "pj_config"
    assert result.template_path.name == "template.md"
