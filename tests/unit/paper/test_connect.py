"""Testes do prumo paper connect (Fase 4 do zero-friction) — seam 100% mockado."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from prumo_assist.domains.paper import connect

_GROUPS = [
    {
        "id": 1,
        "name": "My Library",
        "collections": [
            {"key": "AAA", "name": "Pesquisa", "parentCollection": False},
            {"key": "BBB", "name": "Colecao do estudo piloto1", "parentCollection": "AAA"},
        ],
    },
    {
        "id": 5,
        "name": "Lab Group",
        "collections": [{"key": "CCC", "name": "Pesquisa", "parentCollection": False}],
    },
]


def _fake_rpc(
    responses: dict[str, Any],
) -> tuple[Callable[..., object], list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []

    def fake(url: str, payload: dict[str, Any], timeout: float = 10.0) -> object:
        calls.append(payload)
        method = payload["method"]
        if method in responses:
            value = responses[method]
            if isinstance(value, Exception):
                raise value
            return value
        raise AssertionError(f"método inesperado: {method}")

    return fake, calls


def _pj(tmp_path: Path, *, bib_text: str | None) -> Path:
    refs = tmp_path / "references"
    refs.mkdir(parents=True)
    if bib_text is not None:
        (refs / "_references.bib").write_text(bib_text, encoding="utf-8")
    return tmp_path


_PLACEHOLDER = "% Bibliografia do projeto — formato Better BibTeX (BBT).\n%\n% Fluxo...\n"


class TestFindCollection:
    def test_resolve_com_cadeia_de_pais(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake, _ = _fake_rpc({"user.groups": {"jsonrpc": "2.0", "result": _GROUPS}})
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        ref = connect.find_collection("Colecao do estudo piloto1")
        assert ref.bbt_path == "/My Library/Pesquisa/Colecao do estudo piloto1"
        assert ref.library == "My Library"

    def test_ambigua_sem_library_lista_candidatos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake, _ = _fake_rpc({"user.groups": {"jsonrpc": "2.0", "result": _GROUPS}})
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.AmbiguousCollectionError, match="--library"):
            connect.find_collection("Pesquisa")

    def test_ambigua_resolve_com_library(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake, _ = _fake_rpc({"user.groups": {"jsonrpc": "2.0", "result": _GROUPS}})
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        ref = connect.find_collection("Pesquisa", library="Lab Group")
        assert ref.bbt_path == "/Lab Group/Pesquisa"

    def test_inexistente_sugere_e_garante_nada_criado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake, calls = _fake_rpc({"user.groups": {"jsonrpc": "2.0", "result": _GROUPS}})
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.CollectionNotFoundError, match="NADA foi criado"):
            connect.find_collection("Pesquisa Typo")
        assert all(c["method"] == "user.groups" for c in calls)  # nenhum autoexport.add

    def test_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake, _ = _fake_rpc({"user.groups": {"jsonrpc": "2.0", "result": _GROUPS}})
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        assert connect.find_collection("Colecao do estudo piloto1").library == "My Library"


class TestBibPlaceholder:
    def test_placeholder_do_scaffold(self, tmp_path: Path) -> None:
        pj = _pj(tmp_path, bib_text=_PLACEHOLDER)
        assert connect.bib_is_placeholder(pj) is True

    def test_bib_com_entrada_real(self, tmp_path: Path) -> None:
        pj = _pj(tmp_path, bib_text="@article{x2020,\n  title = {T},\n}\n")
        assert connect.bib_is_placeholder(pj) is False

    def test_ausente_e_vazio_sao_placeholder(self, tmp_path: Path) -> None:
        assert connect.bib_is_placeholder(_pj(tmp_path, bib_text=None)) is True
        assert connect.bib_is_placeholder(_pj(tmp_path / "b", bib_text="")) is True


class TestConnectCollection:
    def test_happy_path_add_e_export(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pj = _pj(tmp_path, bib_text=_PLACEHOLDER)
        bib = pj / "references" / "_references.bib"

        def fake(url: str, payload: dict[str, Any], timeout: float = 10.0) -> object:
            if payload["method"] == "user.groups":
                return {"jsonrpc": "2.0", "result": _GROUPS}
            if payload["method"] == "autoexport.add":
                assert payload["params"] == [
                    "/My Library/Pesquisa/Colecao do estudo piloto1",
                    connect.BETTER_BIBLATEX_GUID,
                    str(bib.resolve()),
                ]
                bib.write_text("@article{a2020,\n  title = {A},\n}\n", encoding="utf-8")
                return {"jsonrpc": "2.0", "result": {"status": "ok"}}
            raise AssertionError(payload["method"])

        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        result = connect.connect_collection(pj, "Colecao do estudo piloto1")
        assert result.exported is True
        assert result.collection.bbt_path.endswith("Colecao do estudo piloto1")

    def test_bib_povoado_recusa_sem_mutacao(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pj = _pj(tmp_path, bib_text="@article{x2020,\n  title = {T},\n}\n")
        fake, calls = _fake_rpc({})  # NENHUM método deveria ser chamado
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.AlreadyConnectedError, match="Automatic export"):
            connect.connect_collection(pj, "Pesquisa")
        assert calls == []

    def test_poll_timeout_vira_exported_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pj = _pj(tmp_path, bib_text=_PLACEHOLDER)

        def fake(url: str, payload: dict[str, Any], timeout: float = 10.0) -> object:
            if payload["method"] == "user.groups":
                return {"jsonrpc": "2.0", "result": _GROUPS}
            return {"jsonrpc": "2.0", "result": {"status": "ok"}}  # add ok, mas bib nunca muda

        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._sleep", lambda _s: None)
        result = connect.connect_collection(pj, "Pesquisa", library="Lab Group", poll_timeout=0.1)
        assert result.exported is False

    def test_erro_jsonrpc_no_add_vira_offline_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pj = _pj(tmp_path, bib_text=_PLACEHOLDER)

        def fake(url: str, payload: dict[str, Any], timeout: float = 10.0) -> object:
            if payload["method"] == "user.groups":
                return {"jsonrpc": "2.0", "result": _GROUPS}
            return {"jsonrpc": "2.0", "error": {"code": -32000, "message": "boom"}}

        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.ZoteroOfflineError, match="boom"):
            connect.connect_collection(pj, "Pesquisa", library="My Library")

    def test_zotero_fechado(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import urllib.error

        pj = _pj(tmp_path, bib_text=_PLACEHOLDER)
        fake, _ = _fake_rpc({"user.groups": urllib.error.URLError("refused")})
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.ZoteroOfflineError, match="abra o Zotero"):
            connect.connect_collection(pj, "Pesquisa")
