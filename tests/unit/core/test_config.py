"""Tests pro carregador de pj_config.toml."""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist import ConfigError
from prumo_assist.core.config import DEFAULTS, load_project_config


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
