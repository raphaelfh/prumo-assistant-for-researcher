"""Testes do vínculo com o Zotero gravado no projeto (``ZoteroLink/v1``, ADR-0044).

Seam do Better BibTeX 100% mockado; nomes de biblioteca e coleção são sintéticos.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from par.domains.paper import connect, link
from par.domains.paper.schemas.v1 import ZoteroLink

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
        "collections": [{"key": "CCC", "name": "Grupo A", "parentCollection": False}],
    },
]

_PLACEHOLDER = "% Bibliografia do projeto — formato Better BibTeX (BBT).\n"
_BIB = "@article{a,\n  title = {T},\n  year = {2024}\n}\n"


def _pj(tmp_path: Path, bib_text: str) -> Path:
    refs = tmp_path / "docs" / "references"
    refs.mkdir(parents=True)
    (refs / "_references.bib").write_text(bib_text, encoding="utf-8")
    return tmp_path


def _seam(monkeypatch: pytest.MonkeyPatch, add_result: Any = None) -> list[str]:
    methods: list[str] = []

    def fake(url: str, payload: dict[str, Any], timeout: float = 10.0) -> object:
        methods.append(payload["method"])
        if payload["method"] == "user.groups":
            return {"jsonrpc": "2.0", "result": _GROUPS}
        return {"jsonrpc": "2.0", "result": add_result}

    monkeypatch.setattr("par.domains.paper.connect._http_post_json", fake)
    monkeypatch.setattr("par.domains.paper.connect._sleep", lambda _s: None)
    return methods


def test_find_collection_traz_chave_e_id_da_biblioteca(monkeypatch: pytest.MonkeyPatch) -> None:
    _seam(monkeypatch)
    ref = connect.find_collection("Colecao do estudo piloto1")
    assert (ref.key, ref.library_id) == ("BBB", 1)


def test_sem_arquivo_nao_ha_vinculo(tmp_path: Path) -> None:
    assert link.read_link(tmp_path) is None


def test_arquivo_invalido_conta_como_sem_vinculo(tmp_path: Path) -> None:
    path = link.link_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("isto não é toml [", encoding="utf-8")
    assert link.read_link(tmp_path) is None


def test_write_e_read_fazem_round_trip(tmp_path: Path) -> None:
    saved = ZoteroLink(
        library="My Library",
        library_id=1,
        collection="Pesquisa/Colecao do estudo piloto1",
        collection_key="BBB",
        linked_at="2026-11-16",
        source="connect",
    )
    path = link.write_link(tmp_path, saved)
    assert path == tmp_path / ".claude" / "zotero.toml"
    assert link.read_link(tmp_path) == saved


def test_connect_grava_o_vinculo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pj = _pj(tmp_path, _PLACEHOLDER)
    _seam(monkeypatch, add_result={"libraryID": 1, "key": "BBB", "id": 7})
    connect.connect_collection(pj, "Colecao do estudo piloto1", poll_timeout=0)
    saved = link.read_link(pj)
    assert saved is not None
    assert (saved.library, saved.library_id) == ("My Library", 1)
    assert saved.collection == "Pesquisa/Colecao do estudo piloto1"
    assert (saved.collection_key, saved.source) == ("BBB", "connect")


def test_connect_com_create_usa_a_chave_que_o_bbt_devolve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pj = _pj(tmp_path, _PLACEHOLDER)
    _seam(monkeypatch, add_result={"libraryID": 1, "key": "NOVA", "id": 9})
    connect.connect_collection(pj, "Colecao nova", create=True, poll_timeout=0)
    saved = link.read_link(pj)
    assert saved is not None and saved.collection_key == "NOVA"


def test_connect_recusado_nao_grava_vinculo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pj = _pj(tmp_path, _PLACEHOLDER)
    _seam(monkeypatch)
    with pytest.raises(connect.CollectionNotFoundError):
        connect.connect_collection(pj, "Nao existe", poll_timeout=0)
    assert link.read_link(pj) is None


def test_record_grava_sem_chamar_autoexport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pj = _pj(tmp_path, _BIB)
    methods = _seam(monkeypatch)
    saved = connect.record_collection(pj, "Grupo A")
    assert methods == ["user.groups"]
    assert (saved.library, saved.library_id, saved.collection_key) == ("Lab Group", 5, "CCC")
    assert saved.source == "record"
    assert link.read_link(pj) == saved


def test_record_em_projeto_nao_conectado_manda_conectar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pj = _pj(tmp_path, _PLACEHOLDER)
    methods = _seam(monkeypatch)
    with pytest.raises(connect.NotConnectedError, match="prumo paper connect"):
        connect.record_collection(pj, "Grupo A")
    assert methods == []


def _link(library: str, library_id: int, key: str) -> ZoteroLink:
    return ZoteroLink(
        library=library,
        library_id=library_id,
        collection="X",
        collection_key=key,
        linked_at="2026-11-16",
        source="record",
    )


def test_select_uri_so_para_a_biblioteca_pessoal() -> None:
    personal = _link("My Library", 1, "BBB")
    assert link.select_uri(personal) == "zotero://select/library/collections/BBB"
    # grupo pede o groupID, que o user.groups não devolve (só o libraryID local)
    assert link.select_uri(_link("Lab Group", 5, "CCC")) is None
