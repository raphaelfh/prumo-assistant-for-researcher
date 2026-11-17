"""Tests pra resolução de recursos empacotados (`core/paths.py`)."""

from __future__ import annotations

from pathlib import Path

import pytest

from par import ConfigError
from par.core.paths import resolve_resource, user_dir, user_dir_location


def test_recurso_ausente_ensina_a_reinstalar_o_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("par.core.paths.find_resource", lambda _n: None)

    with pytest.raises(ConfigError) as exc:
        resolve_resource("templates")

    message = str(exc.value)
    assert "Recurso 'templates' não encontrado" in message
    assert "/plugin install par@prumo-assistant-for-researcher" in message
    assert "uv run prumo" in message


def test_user_dir_existente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "xdg" / "prumo"
    root.mkdir(parents=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    assert user_dir() == root


def test_user_dir_ausente_e_none() -> None:
    assert user_dir() is None


def test_user_dir_arquivo_nao_conta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "xdg").mkdir()
    (tmp_path / "xdg" / "prumo").write_text("x", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    assert user_dir() is None


def test_user_dir_sem_xdg_usa_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / ".config" / "prumo"
    root.mkdir(parents=True)
    monkeypatch.delenv("XDG_CONFIG_HOME")
    monkeypatch.setenv("HOME", str(tmp_path))

    assert user_dir() == root


def test_user_dir_location_respeita_xdg_mesmo_sem_a_pasta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    assert user_dir_location() == tmp_path / "xdg" / "prumo"
    assert user_dir() is None
