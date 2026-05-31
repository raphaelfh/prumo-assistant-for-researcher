"""Tests para detecção de dependências externas."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from prumo_assist.core.deps import DepStatus, check_external_deps


def test_qmd_present_when_on_path() -> None:
    with (
        patch("prumo_assist.core.deps._binary_on_path", return_value="/usr/local/bin/qmd"),
        patch("prumo_assist.core.deps._port_open", return_value=False),
    ):
        statuses = check_external_deps()
    qmd = _by_name(statuses, "qmd")
    assert qmd.present is True
    assert qmd.detail and "qmd" in qmd.detail


def test_qmd_absent_includes_install_hint() -> None:
    with (
        patch("prumo_assist.core.deps._binary_on_path", return_value=None),
        patch("prumo_assist.core.deps._port_open", return_value=False),
    ):
        statuses = check_external_deps()
    qmd = _by_name(statuses, "qmd")
    assert qmd.present is False
    assert "bun install -g @tobilu/qmd" in qmd.hint
    assert "github.com/tobi/qmd" in qmd.hint


def test_zotero_present_when_port_open() -> None:
    with (
        patch("prumo_assist.core.deps._binary_on_path", return_value=None),
        patch("prumo_assist.core.deps._port_open", return_value=True),
    ):
        statuses = check_external_deps()
    zot = _by_name(statuses, "zotero")
    assert zot.present is True


def test_zotero_absent_hint_mentions_port_and_bbt() -> None:
    with (
        patch("prumo_assist.core.deps._binary_on_path", return_value=None),
        patch("prumo_assist.core.deps._port_open", return_value=False),
    ):
        statuses = check_external_deps()
    zot = _by_name(statuses, "zotero")
    assert zot.present is False
    assert "23119" in zot.hint
    assert "Better BibTeX" in zot.hint


def test_dep_status_is_serializable() -> None:
    s = DepStatus(name="x", present=True, required_by=["foo"], detail="d", hint="h")
    assert s.as_dict() == {
        "name": "x",
        "present": True,
        "required_by": ["foo"],
        "detail": "d",
        "hint": "h",
    }


def test_zotero_check_honors_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRUMO_ZOTERO_BASE", "http://example.test:1234")
    captured: dict[str, object] = {}

    def fake_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
        captured["host"] = host
        captured["port"] = port
        return False

    monkeypatch.setattr("prumo_assist.core.deps._port_open", fake_port_open)
    monkeypatch.setattr("prumo_assist.core.deps._binary_on_path", lambda name: None)
    check_external_deps()
    assert captured == {"host": "example.test", "port": 1234}


def _by_name(statuses: list[DepStatus], name: str) -> DepStatus:
    for s in statuses:
        if s.name == name:
            return s
    raise AssertionError(f"dep {name!r} não encontrada em {[s.name for s in statuses]}")
