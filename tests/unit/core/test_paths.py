"""Tests pra resolução de recursos empacotados (`core/paths.py`)."""

from __future__ import annotations

import pytest

from par import ConfigError
from par.core.paths import resolve_resource


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
