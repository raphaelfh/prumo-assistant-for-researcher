"""Tests pro carregador de pj_config.toml."""

from __future__ import annotations

from pathlib import Path

import pytest

from par import ConfigError
from par.core.config import DEFAULTS, load_project_config


def test_returns_defaults_when_no_config(tmp_path: Path) -> None:
    cfg = load_project_config(tmp_path)
    assert cfg == DEFAULTS
    # garantia de imutabilidade do default
    cfg["paper_extract"]["language"] = "en"
    fresh = load_project_config(tmp_path)
    assert fresh["paper_extract"]["language"] == "pt-BR"


def test_user_overrides_merge_into_defaults(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "pj_config.toml").write_text(
        '[paper_extract]\nlanguage = "en"\n', encoding="utf-8"
    )
    cfg = load_project_config(tmp_path)
    assert cfg["paper_extract"]["language"] == "en"
    # merged: defaults preservados pra outros campos
    assert cfg["paper_extract"]["batch"]["default_limit"] == 20


def test_invalid_language_raises(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "pj_config.toml").write_text(
        '[paper_extract]\nlanguage = "klingon"\n', encoding="utf-8"
    )
    with pytest.raises(ConfigError) as ei:
        load_project_config(tmp_path)
    assert "klingon" in str(ei.value)


def test_writing_language_default_is_en_us(tmp_path: Path) -> None:
    cfg = load_project_config(tmp_path)
    assert cfg["writing"]["language"] == "en-US"


def test_writing_language_override(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "pj_config.toml").write_text(
        '[writing]\nlanguage = "pt-BR"\n', encoding="utf-8"
    )
    cfg = load_project_config(tmp_path)
    assert cfg["writing"]["language"] == "pt-BR"
    assert cfg["paper_extract"]["language"] == "pt-BR"


def test_legacy_config_without_writing_section_falls_back(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "pj_config.toml").write_text(
        '[paper_extract]\nlanguage = "es"\n', encoding="utf-8"
    )
    cfg = load_project_config(tmp_path)
    assert cfg["writing"]["language"] == "en-US"


def test_invalid_writing_language_raises(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "pj_config.toml").write_text(
        '[writing]\nlanguage = "en"\n', encoding="utf-8"
    )
    with pytest.raises(ConfigError) as ei:
        load_project_config(tmp_path)
    assert "writing.language" in str(ei.value)
    assert "en-US" in str(ei.value)


def test_defaults_de_interacao_e_saidas_seguras(tmp_path: Path) -> None:
    """Sem as chaves novas, o projeto se comporta como antes (ADR-0046)."""
    cfg = load_project_config(tmp_path)
    assert cfg["interaction"]["language"] == "pt-BR"
    assert cfg["safe_outputs"] == {"patient_data": True, "min_cell": 5}


@pytest.mark.parametrize(
    ("toml", "trecho"),
    [
        ('[interaction]\nlanguage = "en"\n', "interaction.language"),
        ('[safe_outputs]\npatient_data = "sim"\n', "safe_outputs.patient_data"),
        ("[safe_outputs]\nmin_cell = -1\n", "safe_outputs.min_cell"),
        ("[safe_outputs]\nmin_cell = 2.5\n", "safe_outputs.min_cell"),
        ("[safe_outputs]\nmin_cell = true\n", "safe_outputs.min_cell"),
    ],
)
def test_chaves_novas_invalidas_dao_erro_com_a_correcao(
    tmp_path: Path, toml: str, trecho: str
) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "pj_config.toml").write_text(toml, encoding="utf-8")
    with pytest.raises(ConfigError, match=trecho) as exc:
        load_project_config(tmp_path)
    assert "use " in str(exc.value)


def test_set_config_values_troca_insere_e_cria_secao(tmp_path: Path) -> None:
    from par.core.config import set_config_values

    cfg = tmp_path / ".claude" / "pj_config.toml"
    cfg.parent.mkdir()
    cfg.write_text(
        '# comentário humano\n[interaction]\n# idioma\nlanguage = "pt-BR"\n\n[writing]\nlanguage = "en-US"\n',
        encoding="utf-8",
    )

    set_config_values(
        tmp_path,
        {
            ("interaction", "language"): "en-US",
            ("writing", "extra"): 3,
            ("safe_outputs", "patient_data"): False,
        },
    )

    texto = cfg.read_text(encoding="utf-8")
    assert "# comentário humano" in texto and "# idioma" in texto
    loaded = load_project_config(tmp_path)
    assert loaded["interaction"]["language"] == "en-US"
    assert loaded["writing"] == {"language": "en-US", "extra": 3}
    assert loaded["safe_outputs"]["patient_data"] is False
