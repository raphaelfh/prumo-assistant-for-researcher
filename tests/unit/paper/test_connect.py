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
    refs = tmp_path / "docs" / "references"
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
        bib = pj / "docs" / "references" / "_references.bib"

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


_GROUPS_SLASH = [
    {
        "id": 1,
        "name": "My Library",
        "collections": [{"key": "AAA", "name": "Foo/Bar", "parentCollection": False}],
    },
    {
        "id": 7,
        "name": "My/Library",
        "collections": [{"key": "BBB", "name": "Pesquisa", "parentCollection": False}],
    },
]


class TestUnsupportedNames:
    def test_colecao_com_barra_recusa_sem_mutacao(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake, calls = _fake_rpc({"user.groups": {"jsonrpc": "2.0", "result": _GROUPS_SLASH}})
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.UnsupportedCollectionNameError, match="NADA foi criado"):
            connect.find_collection("Bar")  # casa com 'Foo/Bar' pelo último segmento
        assert all(c["method"] == "user.groups" for c in calls)

    def test_library_com_barra_recusa(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake, _ = _fake_rpc({"user.groups": {"jsonrpc": "2.0", "result": _GROUPS_SLASH}})
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.UnsupportedCollectionNameError, match="My/Library"):
            connect.find_collection("Pesquisa", library="My/Library")

    def test_segments_carrega_nomes_crus(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake, _ = _fake_rpc({"user.groups": {"jsonrpc": "2.0", "result": _GROUPS}})
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        ref = connect.find_collection("Colecao do estudo piloto1")
        assert ref.segments == ("My Library", "Pesquisa", "Colecao do estudo piloto1")


class TestHostileChains:
    def test_parent_ausente_pula_colecao(self, monkeypatch: pytest.MonkeyPatch) -> None:
        groups = [
            {
                "id": 1,
                "name": "My Library",
                "collections": [
                    {"key": "CH", "name": "Child", "parentCollection": "GHOST"},
                    {"key": "OK", "name": "Sane", "parentCollection": False},
                ],
            }
        ]
        fake, _ = _fake_rpc({"user.groups": {"jsonrpc": "2.0", "result": groups}})
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        refs = connect.list_collections()
        assert [r.path for r in refs] == ["Sane"]
        with pytest.raises(connect.CollectionNotFoundError):
            connect.find_collection("Child")

    def test_ciclo_de_pais_pula_colecoes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        groups = [
            {
                "id": 1,
                "name": "My Library",
                "collections": [
                    {"key": "A", "name": "Alpha", "parentCollection": "B"},
                    {"key": "B", "name": "Beta", "parentCollection": "A"},
                ],
            }
        ]
        fake, _ = _fake_rpc({"user.groups": {"jsonrpc": "2.0", "result": groups}})
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        assert connect.list_collections() == []

    def test_nome_vazio_pula_colecao(self, monkeypatch: pytest.MonkeyPatch) -> None:
        groups = [
            {
                "id": 1,
                "name": "My Library",
                "collections": [{"key": "E", "name": "  ", "parentCollection": False}],
            }
        ]
        fake, _ = _fake_rpc({"user.groups": {"jsonrpc": "2.0", "result": groups}})
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        assert connect.list_collections() == []


class TestPollZero:
    def test_poll_timeout_zero_ainda_checa_uma_vez(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pj = _pj(tmp_path, bib_text=_PLACEHOLDER)
        bib = pj / "docs" / "references" / "_references.bib"

        def fake(url: str, payload: dict[str, Any], timeout: float = 10.0) -> object:
            if payload["method"] == "user.groups":
                return {"jsonrpc": "2.0", "result": _GROUPS}
            bib.write_text("@article{a2020,\n  title = {A},\n}\n", encoding="utf-8")
            return {"jsonrpc": "2.0", "result": {"status": "ok"}}

        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        result = connect.connect_collection(pj, "Pesquisa", library="Lab Group", poll_timeout=0)
        assert result.exported is True


# ---------------------------------------------------------------------------
# `--create` (ADR-0028): criação opt-in da coleção via efeito colateral de
# `autoexport.add`. Seam segue 100% mockado — nenhum teste toca o Zotero real.
# ---------------------------------------------------------------------------


def _groups_rpc(groups: Any) -> tuple[Callable[..., object], list[dict[str, Any]]]:
    """Seam que responde `user.groups` e aceita `autoexport.add` sem efeito."""
    calls: list[dict[str, Any]] = []

    def fake(url: str, payload: dict[str, Any], timeout: float = 10.0) -> object:
        calls.append(payload)
        if payload["method"] == "user.groups":
            return {"jsonrpc": "2.0", "result": groups}
        return {"jsonrpc": "2.0", "result": {"status": "ok"}}

    return fake, calls


def _mutating(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Só as chamadas que MUTAM o Zotero (tudo que não é leitura)."""
    return [c for c in calls if c["method"] != "user.groups"]


class TestPlanConnection:
    def test_existente_nao_marca_criacao(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake, _ = _groups_rpc(_GROUPS)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        plan = connect.plan_connection("Colecao do estudo piloto1", create=True)
        assert plan.will_create is False
        assert plan.collection.bbt_path == "/My Library/Pesquisa/Colecao do estudo piloto1"
        assert [(s.name, s.exists) for s in plan.segments] == [
            ("My Library", True),
            ("Pesquisa", True),
            ("Colecao do estudo piloto1", True),
        ]

    def test_inexistente_com_create_marca_segmento_novo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake, calls = _groups_rpc(_GROUPS)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        plan = connect.plan_connection("Nova Coleção", create=True)
        assert plan.will_create is True
        assert plan.collection.bbt_path == "/My Library/Nova Coleção"
        assert [(s.name, s.exists) for s in plan.segments] == [
            ("My Library", True),
            ("Nova Coleção", False),
        ]
        assert _mutating(calls) == []  # planejar NUNCA muta

    def test_inexistente_sem_create_continua_erro(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake, calls = _groups_rpc(_GROUPS)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.CollectionNotFoundError, match="NADA foi criado"):
            connect.plan_connection("Nova Coleção", create=False)
        assert _mutating(calls) == []

    def test_library_explicita_direciona_criacao(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake, _ = _groups_rpc(_GROUPS)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        plan = connect.plan_connection("Nova", library="Lab Group", create=True)
        assert plan.collection.bbt_path == "/Lab Group/Nova"

    def test_library_inexistente_recusa(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake, calls = _groups_rpc(_GROUPS)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.LibraryNotFoundError, match="Lab Group"):
            connect.plan_connection("Nova", library="Labb Group", create=True)
        assert _mutating(calls) == []

    def test_biblioteca_sem_colecoes_ainda_e_alvo_valido(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Library vazia não gera CollectionRef, mas continua criável (bug de fetch)."""
        groups = [
            {"id": 1, "name": "My Library", "collections": []},
            {"id": 9, "name": "Vazia", "collections": []},
        ]
        fake, _ = _groups_rpc(groups)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        plan = connect.plan_connection("Nova", library="Vazia", create=True)
        assert plan.collection.bbt_path == "/Vazia/Nova"


class TestCreateGuards:
    def test_barra_no_nome_com_create_recusa_antes_de_mutar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake, calls = _groups_rpc(_GROUPS)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.UnsupportedCollectionNameError, match="NADA foi criado"):
            connect.plan_connection("Pesquisa/Nova", create=True)
        assert _mutating(calls) == []

    def test_nome_vazio_com_create_recusa(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake, calls = _groups_rpc(_GROUPS)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.UnsupportedCollectionNameError):
            connect.plan_connection("   ", create=True)
        assert _mutating(calls) == []

    def test_ambigua_com_create_sem_library_recusa_antes_de_mutar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake, calls = _groups_rpc(_GROUPS)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.AmbiguousCollectionError, match="--library"):
            connect.plan_connection("Pesquisa", create=True)
        assert _mutating(calls) == []

    def test_library_com_barra_recusa_criacao(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake, calls = _groups_rpc(_GROUPS_SLASH)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.UnsupportedCollectionNameError, match="My/Library"):
            connect.plan_connection("Nova", library="My/Library", create=True)
        assert _mutating(calls) == []


class TestConnectCollectionCreate:
    def test_sem_create_inexistente_zero_autoexport_add(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pj = _pj(tmp_path, bib_text=_PLACEHOLDER)
        fake, calls = _groups_rpc(_GROUPS)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.CollectionNotFoundError, match="NADA foi criado"):
            connect.connect_collection(pj, "Nova Coleção")
        assert _mutating(calls) == []

    def test_create_inexistente_chama_add_uma_vez_com_path_novo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pj = _pj(tmp_path, bib_text=_PLACEHOLDER)
        bib = pj / "docs" / "references" / "_references.bib"
        fake, calls = _groups_rpc(_GROUPS)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._sleep", lambda _s: None)
        result = connect.connect_collection(pj, "Nova Coleção", create=True, poll_timeout=0)
        adds = _mutating(calls)
        assert len(adds) == 1
        assert adds[0]["method"] == "autoexport.add"
        assert adds[0]["params"] == [
            "/My Library/Nova Coleção",
            connect.BETTER_BIBLATEX_GUID,
            str(bib.resolve()),
        ]
        assert result.created is True

    def test_create_com_colecao_existente_usa_path_de_hoje(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pj = _pj(tmp_path, bib_text=_PLACEHOLDER)
        fake, calls = _groups_rpc(_GROUPS)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._sleep", lambda _s: None)
        result = connect.connect_collection(
            pj, "Colecao do estudo piloto1", create=True, poll_timeout=0
        )
        adds = _mutating(calls)
        assert len(adds) == 1
        assert adds[0]["params"][0] == "/My Library/Pesquisa/Colecao do estudo piloto1"
        assert result.created is False  # nada foi criado: já existia

    def test_barra_no_nome_com_create_recusa_sem_mutar(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pj = _pj(tmp_path, bib_text=_PLACEHOLDER)
        fake, calls = _groups_rpc(_GROUPS)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.UnsupportedCollectionNameError):
            connect.connect_collection(pj, "Pesquisa/Nova", create=True)
        assert _mutating(calls) == []

    def test_ambigua_com_create_recusa_sem_mutar(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pj = _pj(tmp_path, bib_text=_PLACEHOLDER)
        fake, calls = _groups_rpc(_GROUPS)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.AmbiguousCollectionError, match="--library"):
            connect.connect_collection(pj, "Pesquisa", create=True)
        assert _mutating(calls) == []

    def test_bib_povoado_recusa_antes_de_planejar(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Guarda 1 continua primeira: nem `user.groups` é chamado."""
        pj = _pj(tmp_path, bib_text="@article{x2020,\n  title = {T},\n}\n")
        fake, calls = _groups_rpc(_GROUPS)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        with pytest.raises(connect.AlreadyConnectedError):
            connect.connect_collection(pj, "Nova", create=True)
        assert calls == []


class TestCreationConfirm:
    def test_confirm_recusado_nao_muta(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pj = _pj(tmp_path, bib_text=_PLACEHOLDER)
        fake, calls = _groups_rpc(_GROUPS)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        seen: list[connect.ConnectPlan] = []

        def deny(plan: connect.ConnectPlan) -> bool:
            seen.append(plan)
            return False

        with pytest.raises(connect.CreationDeclinedError, match="NADA foi criado"):
            connect.connect_collection(pj, "Nova", create=True, confirm=deny)
        assert _mutating(calls) == []
        assert seen[0].collection.bbt_path == "/My Library/Nova"

    def test_confirm_nao_e_consultado_quando_colecao_ja_existe(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pj = _pj(tmp_path, bib_text=_PLACEHOLDER)
        fake, calls = _groups_rpc(_GROUPS)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._sleep", lambda _s: None)
        seen: list[connect.ConnectPlan] = []

        def deny(plan: connect.ConnectPlan) -> bool:
            seen.append(plan)
            return False

        connect.connect_collection(
            pj, "Colecao do estudo piloto1", create=True, confirm=deny, poll_timeout=0
        )
        assert seen == []  # nada a confirmar: não há criação
        assert len(_mutating(calls)) == 1

    def test_confirm_aceito_muta(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pj = _pj(tmp_path, bib_text=_PLACEHOLDER)
        fake, calls = _groups_rpc(_GROUPS)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", fake)
        monkeypatch.setattr("prumo_assist.domains.paper.connect._sleep", lambda _s: None)
        result = connect.connect_collection(
            pj, "Nova", create=True, confirm=lambda _p: True, poll_timeout=0
        )
        assert result.created is True
        assert len(_mutating(calls)) == 1
