"""Tests para detecção de dependências externas."""

from __future__ import annotations

import email.message
import http.client
import urllib.error
from unittest.mock import patch

import pytest

from par.core.deps import DepStatus, check_external_deps, zotero_local_api_up


def test_qmd_present_when_on_path() -> None:
    with (
        patch("par.core.deps._binary_on_path", return_value="/usr/local/bin/qmd"),
        patch("par.core.deps._zotero_api_root", return_value=None),
    ):
        statuses = check_external_deps()
    qmd = _by_name(statuses, "qmd")
    assert qmd.present is True
    assert qmd.detail and "qmd" in qmd.detail


def test_qmd_absent_includes_install_hint() -> None:
    with (
        patch("par.core.deps._binary_on_path", return_value=None),
        patch("par.core.deps._zotero_api_root", return_value=None),
    ):
        statuses = check_external_deps()
    qmd = _by_name(statuses, "qmd")
    assert qmd.present is False
    assert "bun install -g @tobilu/qmd" in qmd.hint
    assert "github.com/tobi/qmd" in qmd.hint


def test_zotero_present_when_local_api_answers() -> None:
    with (
        patch("par.core.deps._binary_on_path", return_value=None),
        patch("par.core.deps._zotero_api_root", return_value=200),
    ):
        statuses = check_external_deps()
    zot = _by_name(statuses, "zotero")
    assert zot.present is True


def test_zotero_absent_hint_mentions_port_and_bbt() -> None:
    with (
        patch("par.core.deps._binary_on_path", return_value=None),
        patch("par.core.deps._zotero_api_root", return_value=None),
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
    seen: list[str] = []

    def _spy(url: str, timeout: float = 0.0) -> object:
        seen.append(url)
        raise urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))

    monkeypatch.setattr("par.core.deps.urllib.request.urlopen", _spy)
    monkeypatch.setattr("par.core.deps._binary_on_path", lambda name: None)
    check_external_deps()
    assert seen == ["http://example.test:1234/api/"]


def test_zotero_supported_version_stays_present() -> None:
    with (
        patch("par.core.deps._binary_on_path", return_value=None),
        patch("par.core.deps._zotero_api_root", return_value=200),
        patch("par.core.deps._zotero_version_header", return_value="9.0.6"),
    ):
        zot = _by_name(check_external_deps(), "zotero")
    assert zot.present is True
    assert zot.version == "9.0.6"
    assert "9.0.6" in zot.detail


def test_zotero_below_floor_flags_unsupported() -> None:
    with (
        patch("par.core.deps._binary_on_path", return_value=None),
        patch("par.core.deps._zotero_api_root", return_value=200),
        patch("par.core.deps._zotero_version_header", return_value="8.0.2"),
    ):
        zot = _by_name(check_external_deps(), "zotero")
    assert zot.present is False
    assert zot.version == "8.0.2"
    assert "Zotero 9+" in zot.detail
    assert "zotero.org/download" in zot.hint


def test_zotero_undetectable_version_is_fail_safe() -> None:
    with (
        patch("par.core.deps._binary_on_path", return_value=None),
        patch("par.core.deps._zotero_api_root", return_value=200),
        patch("par.core.deps._zotero_version_header", return_value=None),
    ):
        zot = _by_name(check_external_deps(), "zotero")
    assert zot.present is True
    assert zot.version is None
    assert "versão não detectada" in zot.detail


def test_zotero_version_probe_skipped_when_api_did_not_respond() -> None:
    def _explode(host: str, port: int, timeout: float = 2.0) -> str | None:
        raise AssertionError("probe de versão não deveria rodar sem resposta da API")

    with (
        patch("par.core.deps._binary_on_path", return_value=None),
        patch("par.core.deps._zotero_api_root", return_value=None),
        patch("par.core.deps._zotero_version_header", new=_explode),
    ):
        zot = _by_name(check_external_deps(), "zotero")
    assert zot.present is False
    assert zot.version is None


def test_non_http_service_on_the_port_is_not_a_live_local_api() -> None:
    def _bad_status(*args: object, **kwargs: object) -> object:
        raise http.client.BadStatusLine("lixo nao-http")

    with (
        patch("par.core.deps._binary_on_path", return_value=None),
        patch("par.core.deps.urllib.request.urlopen", _bad_status),
    ):
        zot = _by_name(check_external_deps(), "zotero")
    assert zot.present is False
    assert zot.version is None
    assert "nada escutando" in zot.detail


# ---------------------------------------------------------------------------
# Sonda "API local de pé" — shapes REAIS (Zotero 9.0.6 + BBT):
# GET /                → 404 (HTTPError, subclasse de URLError/OSError)
# GET /connector/ping  → 200 + header X-Zotero-Version, com a API local LIGADA OU NÃO
# GET /api/            → 200 com a API local ligada; 403 "Local API is not enabled" sem
# ---------------------------------------------------------------------------


class _FakePingResponse:
    """Resposta mínima do ``urlopen``: context manager com ``headers``."""

    def __init__(self, headers: dict[str, str], status: int = 200) -> None:
        self.headers = headers
        self.status = status

    def __enter__(self) -> _FakePingResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _zotero_running_urlopen(url: str, timeout: float = 0.0) -> _FakePingResponse:
    """Zotero 9.0.6 rodando: só ``/connector/ping`` responde 200; o resto é 404."""
    if url.endswith("/connector/ping"):
        return _FakePingResponse({"X-Zotero-Version": "9.0.6"})
    raise urllib.error.HTTPError(url, 404, "Not Found", email.message.Message(), None)


def test_zotero_local_api_up_false_when_connection_refused() -> None:
    def _refused(*args: object, **kwargs: object) -> object:
        raise urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))

    with patch("par.core.deps.urllib.request.urlopen", _refused):
        assert zotero_local_api_up() is False


def test_zotero_local_api_up_false_on_timeout() -> None:
    def _timeout(*args: object, **kwargs: object) -> object:
        raise TimeoutError

    with patch("par.core.deps.urllib.request.urlopen", _timeout):
        assert zotero_local_api_up() is False


def test_zotero_local_api_up_honors_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRUMO_ZOTERO_BASE", "http://example.test:1234")
    seen: list[str] = []

    def _spy(url: str, timeout: float = 0.0) -> _FakePingResponse:
        seen.append(url)
        return _FakePingResponse({"X-Zotero-Version": "9.0.6"})

    with patch("par.core.deps.urllib.request.urlopen", _spy):
        assert zotero_local_api_up() is True
    assert seen == ["http://example.test:1234/api/"]


def _by_name(statuses: list[DepStatus], name: str) -> DepStatus:
    for s in statuses:
        if s.name == name:
            return s
    raise AssertionError(f"dep {name!r} não encontrada em {[s.name for s in statuses]}")


# ---------------------------------------------------------------------------
# API local desligada ≠ Zotero fechado (auditoria 2026-08-23, achado A4)
# ---------------------------------------------------------------------------


def test_zotero_local_api_up_probes_the_api_root() -> None:
    """`/api/` é o único endpoint que reprova quando a API local está desligada."""
    seen: list[str] = []

    def _spy(url: str, timeout: float = 0.0) -> _FakePingResponse:
        seen.append(url)
        return _FakePingResponse({})

    with patch("par.core.deps.urllib.request.urlopen", _spy):
        assert zotero_local_api_up() is True
    assert seen == ["http://127.0.0.1:23119/api/"]


def test_zotero_local_api_up_false_when_local_api_is_disabled() -> None:
    """Zotero ABERTO com a API local desligada responde 403 em `/api/`.

    Antes qualquer status HTTP contava como "de pé", então o guard passava e
    os comandos de anotação tomavam 403 em série.
    """

    def _forbidden(url: str, timeout: float = 0.0) -> object:
        raise urllib.error.HTTPError(
            url, 403, "Local API is not enabled", email.message.Message(), None
        )

    with patch("par.core.deps.urllib.request.urlopen", _forbidden):
        assert zotero_local_api_up() is False


def test_doctor_flags_zotero_absent_when_local_api_is_disabled() -> None:
    def _forbidden(url: str, timeout: float = 0.0) -> object:
        raise urllib.error.HTTPError(
            url, 403, "Local API is not enabled", email.message.Message(), None
        )

    with patch("par.core.deps.urllib.request.urlopen", _forbidden):
        zotero = _by_name(check_external_deps(), "zotero")

    assert zotero.present is False
    assert "Allow other applications" in zotero.hint
