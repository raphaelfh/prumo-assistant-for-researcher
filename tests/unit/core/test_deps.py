"""Tests para detecção de dependências externas."""

from __future__ import annotations

import email.message
import http.client
import urllib.error
from unittest.mock import patch

import pytest

from prumo_assist.core.deps import DepStatus, check_external_deps, zotero_local_api_up


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
        "version": None,
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


def test_zotero_supported_version_stays_present() -> None:
    with (
        patch("prumo_assist.core.deps._binary_on_path", return_value=None),
        patch("prumo_assist.core.deps._port_open", return_value=True),
        patch("prumo_assist.core.deps._zotero_version_header", return_value="9.0.6"),
    ):
        zot = _by_name(check_external_deps(), "zotero")
    assert zot.present is True
    assert zot.version == "9.0.6"
    assert "9.0.6" in zot.detail


def test_zotero_below_floor_flags_unsupported() -> None:
    with (
        patch("prumo_assist.core.deps._binary_on_path", return_value=None),
        patch("prumo_assist.core.deps._port_open", return_value=True),
        patch("prumo_assist.core.deps._zotero_version_header", return_value="8.0.2"),
    ):
        zot = _by_name(check_external_deps(), "zotero")
    assert zot.present is False
    assert zot.version == "8.0.2"
    assert "Zotero 9+" in zot.detail
    assert "zotero.org/download" in zot.hint


def test_zotero_undetectable_version_is_fail_safe() -> None:
    with (
        patch("prumo_assist.core.deps._binary_on_path", return_value=None),
        patch("prumo_assist.core.deps._port_open", return_value=True),
        patch("prumo_assist.core.deps._zotero_version_header", return_value=None),
    ):
        zot = _by_name(check_external_deps(), "zotero")
    assert zot.present is True
    assert zot.version is None
    assert "versão não detectada" in zot.detail


def test_zotero_version_probe_skipped_when_port_closed() -> None:
    def _explode(host: str, port: int, timeout: float = 2.0) -> str | None:
        raise AssertionError("probe de versão não deveria rodar com porta fechada")

    with (
        patch("prumo_assist.core.deps._binary_on_path", return_value=None),
        patch("prumo_assist.core.deps._port_open", return_value=False),
        patch("prumo_assist.core.deps._zotero_version_header", new=_explode),
    ):
        zot = _by_name(check_external_deps(), "zotero")
    assert zot.present is False
    assert zot.version is None


def test_zotero_version_probe_never_raises_on_non_http_service() -> None:
    def _bad_status(*args: object, **kwargs: object) -> object:
        raise http.client.BadStatusLine("lixo nao-http")

    with (
        patch("prumo_assist.core.deps._binary_on_path", return_value=None),
        patch("prumo_assist.core.deps._port_open", return_value=True),
        patch("prumo_assist.core.deps.urllib.request.urlopen", _bad_status),
    ):
        zot = _by_name(check_external_deps(), "zotero")
    assert zot.present is True
    assert zot.version is None
    assert "versão não detectada" in zot.detail


# ---------------------------------------------------------------------------
# Sonda "Zotero de pé" — shapes REAIS medidos contra Zotero 9.0.6 + BBT:
# GET /                → 404 (HTTPError, subclasse de URLError/OSError)
# GET /connector/ping  → 200 com header X-Zotero-Version: 9.0.6
# ---------------------------------------------------------------------------


class _FakePingResponse:
    """Resposta mínima do ``urlopen``: context manager com ``headers``."""

    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers

    def __enter__(self) -> _FakePingResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _zotero_running_urlopen(url: str, timeout: float = 0.0) -> _FakePingResponse:
    """Zotero 9.0.6 rodando: só ``/connector/ping`` responde 200; o resto é 404."""
    if url.endswith("/connector/ping"):
        return _FakePingResponse({"X-Zotero-Version": "9.0.6"})
    raise urllib.error.HTTPError(url, 404, "Not Found", email.message.Message(), None)


def test_zotero_local_api_up_probes_connector_ping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRUMO_ZOTERO_BASE", raising=False)
    seen: list[str] = []

    def _spy(url: str, timeout: float = 0.0) -> _FakePingResponse:
        seen.append(url)
        return _zotero_running_urlopen(url, timeout)

    with patch("prumo_assist.core.deps.urllib.request.urlopen", _spy):
        assert zotero_local_api_up() is True
    assert seen == ["http://127.0.0.1:23119/connector/ping"]


def test_zotero_local_api_up_false_when_connection_refused() -> None:
    def _refused(*args: object, **kwargs: object) -> object:
        raise urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))

    with patch("prumo_assist.core.deps.urllib.request.urlopen", _refused):
        assert zotero_local_api_up() is False


def test_zotero_local_api_up_false_on_timeout() -> None:
    def _timeout(*args: object, **kwargs: object) -> object:
        raise TimeoutError

    with patch("prumo_assist.core.deps.urllib.request.urlopen", _timeout):
        assert zotero_local_api_up() is False


def test_zotero_local_api_up_true_on_http_error_status() -> None:
    """Status HTTP de erro ainda é servidor de pé — só há HTTP nessa porta com o app aberto."""

    def _forbidden(url: str, timeout: float = 0.0) -> object:
        raise urllib.error.HTTPError(url, 403, "Forbidden", email.message.Message(), None)

    with patch("prumo_assist.core.deps.urllib.request.urlopen", _forbidden):
        assert zotero_local_api_up() is True


def test_zotero_local_api_up_honors_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRUMO_ZOTERO_BASE", "http://example.test:1234")
    seen: list[str] = []

    def _spy(url: str, timeout: float = 0.0) -> _FakePingResponse:
        seen.append(url)
        return _FakePingResponse({"X-Zotero-Version": "9.0.6"})

    with patch("prumo_assist.core.deps.urllib.request.urlopen", _spy):
        assert zotero_local_api_up() is True
    assert seen == ["http://example.test:1234/connector/ping"]


def _by_name(statuses: list[DepStatus], name: str) -> DepStatus:
    for s in statuses:
        if s.name == name:
            return s
    raise AssertionError(f"dep {name!r} não encontrada em {[s.name for s in statuses]}")
