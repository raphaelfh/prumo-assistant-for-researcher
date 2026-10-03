"""Tests para detecção de dependências externas."""

from __future__ import annotations

import email.message
import http.client
import subprocess
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest

from par.core import deps
from par.core.deps import (
    DepStatus,
    bbt_rpc_url,
    check_external_deps,
    in_claude_sandbox,
    pandoc_path,
    zotero_base,
    zotero_local_api_up,
)

# A função real, guardada na coleta: a fixture `autouse` `_no_real_pandoc`
# (`tests/unit/conftest.py`) troca `deps._pandoc_version` em todo teste.
_REAL_PANDOC_VERSION = deps._pandoc_version


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
    assert "npm install -g @tobilu/qmd" in qmd.hint
    assert "bun install -g @tobilu/qmd" in qmd.hint
    assert "github.com/tobi/qmd" not in qmd.hint


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


# ---------------------------------------------------------------------------
# Base URL única do Zotero e sandbox do Claude Code (ADR-0037, B6 e B1)
# ---------------------------------------------------------------------------


def test_zotero_base_default_is_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRUMO_ZOTERO_BASE", raising=False)
    assert zotero_base() == "http://127.0.0.1:23119"


def test_zotero_base_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRUMO_ZOTERO_BASE", "http://localhost:9999")
    assert zotero_base() == "http://localhost:9999"


def test_zotero_base_empty_env_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """``PRUMO_ZOTERO_BASE=""`` não vira URL relativa (que derruba export e doctor)."""
    monkeypatch.setenv("PRUMO_ZOTERO_BASE", "")
    assert zotero_base() == "http://127.0.0.1:23119"


def test_bbt_rpc_url_follows_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRUMO_ZOTERO_BASE", "http://example.test:1234")
    assert bbt_rpc_url() == "http://example.test:1234/better-bibtex/json-rpc"


def test_in_claude_sandbox_true_with_runtime_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SANDBOX_RUNTIME", "1")
    assert in_claude_sandbox() is True


def test_in_claude_sandbox_false_without_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SANDBOX_RUNTIME", raising=False)
    assert in_claude_sandbox() is False


@pytest.mark.parametrize("value", ["0", "true"])
def test_in_claude_sandbox_false_with_other_value(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("SANDBOX_RUNTIME", value)
    assert in_claude_sandbox() is False


# ---------------------------------------------------------------------------
# Resolução do pandoc: PATH, senão o do Zettlr.app (ADR-0037, B7)
# ---------------------------------------------------------------------------


def _fake_zettlr_pandoc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: int) -> Path:
    """Arquivo em ``tmp_path`` no papel do pandoc do Zettlr.app, com o modo dado."""
    fake = tmp_path / "Zettlr.app" / "Contents" / "Resources" / "pandoc"
    fake.parent.mkdir(parents=True)
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    fake.chmod(mode)
    monkeypatch.setattr("par.core.deps._ZETTLR_PANDOC", fake)
    return fake


def test_pandoc_path_prefers_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fake_zettlr_pandoc(monkeypatch, tmp_path, 0o755)
    monkeypatch.setattr("par.core.deps._binary_on_path", lambda name: "/opt/bin/pandoc")
    assert pandoc_path() == "/opt/bin/pandoc"


def test_pandoc_path_falls_back_to_zettlr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = _fake_zettlr_pandoc(monkeypatch, tmp_path, 0o755)
    monkeypatch.setattr("par.core.deps._binary_on_path", lambda name: None)
    assert pandoc_path() == str(fake)


def test_pandoc_path_none_without_any(monkeypatch: pytest.MonkeyPatch) -> None:
    # `_ZETTLR_PANDOC` fica no caminho inexistente da fixture do conftest.
    monkeypatch.setattr("par.core.deps._binary_on_path", lambda name: None)
    assert pandoc_path() is None


def test_pandoc_path_ignores_non_executable_zettlr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake_zettlr_pandoc(monkeypatch, tmp_path, 0o644)
    monkeypatch.setattr("par.core.deps._binary_on_path", lambda name: None)
    assert pandoc_path() is None


# ---------------------------------------------------------------------------
# Linha `pandoc` do doctor: piso 3.8.2, fail-safe sem versão (E8 e E9)
# ---------------------------------------------------------------------------


def _pandoc_line(monkeypatch: pytest.MonkeyPatch, version: str | None) -> DepStatus:
    monkeypatch.setattr("par.core.deps._pandoc_version", lambda path, timeout=5.0: version)
    with (
        patch("par.core.deps._binary_on_path", return_value="/opt/bin/pandoc"),
        patch("par.core.deps._zotero_api_root", return_value=None),
    ):
        return _by_name(check_external_deps(), "pandoc")


def test_pandoc_line_present_with_3_10_1(monkeypatch: pytest.MonkeyPatch) -> None:
    line = _pandoc_line(monkeypatch, "3.10.1")
    assert line.present is True
    assert line.version == "3.10.1"
    assert line.detail == "pandoc 3.10.1 em /opt/bin/pandoc"
    assert line.required_by == ["write export", "write compose"]


def test_pandoc_line_is_last(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("par.core.deps._pandoc_version", lambda path, timeout=5.0: "3.10.1")
    with (
        patch("par.core.deps._binary_on_path", return_value="/opt/bin/pandoc"),
        patch("par.core.deps._zotero_api_root", return_value=None),
    ):
        names = [s.name for s in check_external_deps()]
    assert names == ["qmd", "zotero", "pandoc"]


def test_pandoc_line_rejects_3_1_2(monkeypatch: pytest.MonkeyPatch) -> None:
    line = _pandoc_line(monkeypatch, "3.1.2")
    assert line.present is False
    assert line.version == "3.1.2"
    assert line.detail == "pandoc 3.1.2 em /opt/bin/pandoc"
    assert "3.8.2" in line.hint
    assert "brew upgrade pandoc" in line.hint
    assert "prumo doctor" in line.hint
    assert "{#tbl:…}" in line.hint


def test_pandoc_line_accepts_floor_3_8_2(monkeypatch: pytest.MonkeyPatch) -> None:
    line = _pandoc_line(monkeypatch, "3.8.2")
    assert line.present is True
    assert line.hint == ""


def test_pandoc_line_fail_safe_without_version(monkeypatch: pytest.MonkeyPatch) -> None:
    line = _pandoc_line(monkeypatch, None)
    assert line.present is True
    assert line.version is None
    assert "versão não detectada" in line.detail


def test_pandoc_line_absent_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    # `_ZETTLR_PANDOC` fica no caminho inexistente da fixture do conftest.
    with (
        patch("par.core.deps._binary_on_path", return_value=None),
        patch("par.core.deps._zotero_api_root", return_value=None),
    ):
        line = _by_name(check_external_deps(), "pandoc")
    assert line.present is False
    assert line.version is None
    assert line.detail == "pandoc não encontrado (nem no PATH nem no Zettlr.app)"
    assert "brew install pandoc" in line.hint
    assert "github.com/jgm/pandoc/releases" in line.hint
    assert "3.8.2" in line.hint


def test_pandoc_line_names_zettlr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fake_zettlr_pandoc(monkeypatch, tmp_path, 0o755)
    monkeypatch.setattr("par.core.deps._pandoc_version", lambda path, timeout=5.0: "3.10.1")
    with (
        patch("par.core.deps._binary_on_path", return_value=None),
        patch("par.core.deps._zotero_api_root", return_value=None),
    ):
        line = _by_name(check_external_deps(), "pandoc")
    assert line.present is True
    assert line.detail == "pandoc 3.10.1 do Zettlr.app"


# ---------------------------------------------------------------------------
# `_pandoc_version` real, com `subprocess.run` mockado
# ---------------------------------------------------------------------------


def _fake_run(stdout: str) -> object:
    def _run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")

    return _run


def test_pandoc_version_parses_first_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "par.core.deps.subprocess.run", _fake_run("pandoc 3.10.1\nFeatures: +server\n")
    )
    assert _REAL_PANDOC_VERSION("/opt/bin/pandoc") == "3.10.1"


def test_pandoc_version_none_on_missing_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    def _missing(cmd: list[str], **kwargs: object) -> object:
        raise FileNotFoundError(2, "No such file or directory", cmd[0])

    monkeypatch.setattr("par.core.deps.subprocess.run", _missing)
    assert _REAL_PANDOC_VERSION("/nao/existe/pandoc") is None


def test_pandoc_version_none_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _slow(cmd: list[str], **kwargs: object) -> object:
        raise subprocess.TimeoutExpired(cmd, 5.0)

    monkeypatch.setattr("par.core.deps.subprocess.run", _slow)
    assert _REAL_PANDOC_VERSION("/opt/bin/pandoc") is None


def test_pandoc_version_none_on_garbage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("par.core.deps.subprocess.run", _fake_run("oops"))
    assert _REAL_PANDOC_VERSION("/opt/bin/pandoc") is None
