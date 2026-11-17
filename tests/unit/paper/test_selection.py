"""Testes da coleção selecionada no Zotero (servidor do conector) — emenda da ADR-0044.

Os dois seams (conector e JSON-RPC do Better BibTeX) são 100% mockados; nomes de biblioteca e
coleção são sintéticos.
"""

from __future__ import annotations

import urllib.error
from pathlib import Path
from typing import Any

import pytest

from par.domains.paper import connect, link, selection
from par.domains.paper.schemas.v1 import ZoteroLink

_GROUPS = [
    {
        "id": 1,
        "name": "My Library",
        "collections": [
            {"key": "AAA", "name": "Pesquisa", "parentCollection": False},
            {"key": "BBB", "name": "Item A", "parentCollection": "AAA"},
            {"key": "DDD", "name": "Neta", "parentCollection": "BBB"},
            {"key": "EEE", "name": "Item A", "parentCollection": False},
        ],
    },
    {
        "id": 5,
        "name": "Lab Group",
        "collections": [{"key": "CCC", "name": "Grupo A", "parentCollection": False}],
    },
]

#: Árvore do conector na ordem de profundidade, como o Zotero devolve.
_TARGETS = [
    {"id": "L1", "name": "My Library", "level": 0},
    {"id": "C10", "name": "Pesquisa", "level": 1},
    {"id": "C11", "name": "Item A", "level": 2},
    {"id": "C12", "name": "Neta", "level": 3},
    {"id": "C13", "name": "Item A", "level": 1},
    {"id": "L5", "name": "Lab Group", "level": 0},
    {"id": "C20", "name": "Grupo A", "level": 1},
]

_PLACEHOLDER = "% Bibliografia do projeto — formato Better BibTeX (BBT).\n"
_BIB = "@article{a,\n  title = {T},\n  year = {2024}\n}\n"


def _selected(
    collection_id: int | None, library_id: int = 1, library: str = "My Library"
) -> dict[str, Any]:
    return {
        "libraryID": library_id,
        "libraryName": library,
        "id": collection_id,
        "name": "x",
        "targets": _TARGETS,
        "tags": {},
    }


def _seams(
    monkeypatch: pytest.MonkeyPatch,
    selected: dict[str, Any] | Exception,
    groups: list[Any] | None = None,
) -> list[str]:
    calls: list[str] = []

    def fake_connector(url: str, payload: dict[str, Any], timeout: float = 3.0) -> object:
        calls.append(url.rsplit("/", 1)[-1])
        if isinstance(selected, Exception):
            raise selected
        return selected

    def fake_rpc(url: str, payload: dict[str, Any], timeout: float = 10.0) -> object:
        calls.append(payload["method"])
        if payload["method"] == "user.groups":
            return {"jsonrpc": "2.0", "result": _GROUPS if groups is None else groups}
        return {"jsonrpc": "2.0", "result": {"libraryID": 1, "key": "BBB", "id": 11}}

    monkeypatch.setattr("par.domains.paper.selection._http_post_json", fake_connector)
    monkeypatch.setattr("par.domains.paper.connect._http_post_json", fake_rpc)
    monkeypatch.setattr("par.domains.paper.connect._sleep", lambda _s: None)
    return calls


def _pj(tmp_path: Path, bib_text: str) -> Path:
    refs = tmp_path / "docs" / "references"
    refs.mkdir(parents=True)
    (refs / "_references.bib").write_text(bib_text, encoding="utf-8")
    return tmp_path


# --- selected_collection: caminho pelos targets ---------------------------------------------


@pytest.mark.parametrize(
    ("cid", "lib_id", "lib", "path"),
    [
        (10, 1, "My Library", "Pesquisa"),
        (11, 1, "My Library", "Pesquisa/Item A"),
        (12, 1, "My Library", "Pesquisa/Item A/Neta"),
        (13, 1, "My Library", "Item A"),
        (20, 5, "Lab Group", "Grupo A"),
    ],
)
def test_caminho_vem_dos_targets(
    monkeypatch: pytest.MonkeyPatch, cid: int, lib_id: int, lib: str, path: str
) -> None:
    _seams(monkeypatch, _selected(cid, lib_id, lib))
    sel = selection.selected_collection()
    assert (sel.library_id, sel.library, sel.path) == (lib_id, lib, path)


def test_biblioteca_inteira_selecionada_nao_tem_caminho(monkeypatch: pytest.MonkeyPatch) -> None:
    _seams(monkeypatch, _selected(None))
    assert selection.selected_collection().path is None


def test_zotero_fechado_vira_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    _seams(monkeypatch, urllib.error.URLError("refused"))
    with pytest.raises(connect.ZoteroOfflineError, match="Zotero"):
        selection.selected_collection()


def test_resposta_sem_library_id_vira_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    _seams(monkeypatch, {"name": "x"})
    with pytest.raises(connect.ZoteroOfflineError):
        selection.selected_collection()


# --- resolve_selected: seleção → coleção com chave ------------------------------------------


def test_resolve_casa_pelo_caminho_na_mesma_biblioteca(monkeypatch: pytest.MonkeyPatch) -> None:
    _seams(monkeypatch, _selected(11))
    ref = selection.resolve_selected()
    assert (ref.key, ref.library_id, ref.path) == ("BBB", 1, "Pesquisa/Item A")


def test_resolve_distingue_homonimas_em_pais_diferentes(monkeypatch: pytest.MonkeyPatch) -> None:
    _seams(monkeypatch, _selected(13))
    assert selection.resolve_selected().key == "EEE"


def test_resolve_recusa_biblioteca_inteira(monkeypatch: pytest.MonkeyPatch) -> None:
    _seams(monkeypatch, _selected(None))
    with pytest.raises(selection.NoCollectionSelectedError, match="clique na coleção"):
        selection.resolve_selected()


def test_resolve_sem_match_nao_cria_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _seams(
        monkeypatch, _selected(11), groups=[{"id": 1, "name": "My Library", "collections": []}]
    )
    with pytest.raises(connect.CollectionNotFoundError, match="NADA foi criado"):
        selection.resolve_selected()
    assert "autoexport.add" not in calls


def test_resolve_recusa_irmas_de_mesmo_caminho(monkeypatch: pytest.MonkeyPatch) -> None:
    groups = [
        {
            "id": 1,
            "name": "My Library",
            "collections": [
                {"key": "X1", "name": "Pesquisa", "parentCollection": False},
                {"key": "X2", "name": "Pesquisa", "parentCollection": False},
            ],
        }
    ]
    _seams(monkeypatch, _selected(10), groups=groups)
    with pytest.raises(connect.AmbiguousCollectionError, match="Renomeie"):
        selection.resolve_selected()


# --- connect / record pela seleção -----------------------------------------------------------


def test_connect_selected_liga_a_colecao_selecionada(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pj = _pj(tmp_path, _PLACEHOLDER)
    calls = _seams(monkeypatch, _selected(11))
    r = connect.connect_resolved(pj, selection.resolve_selected, poll_timeout=0)
    assert r.collection.bbt_path == "/My Library/Pesquisa/Item A"
    assert calls == ["getSelectedCollection", "user.groups", "autoexport.add"]
    saved = link.read_link(pj)
    assert saved is not None and saved.collection_key == "BBB"


def test_connect_selected_guarda_1_antes_de_qualquer_rede(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pj = _pj(tmp_path, _BIB)
    calls = _seams(monkeypatch, _selected(11))
    with pytest.raises(connect.AlreadyConnectedError):
        connect.connect_resolved(pj, selection.resolve_selected, poll_timeout=0)
    assert calls == []


def test_connect_resolved_recusa_ref_sem_chave(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pj = _pj(tmp_path, _PLACEHOLDER)
    calls = _seams(monkeypatch, _selected(11))
    planned = connect.CollectionRef(
        library="My Library",
        path="Nova",
        bbt_path="/My Library/Nova",
        segments=("My Library", "Nova"),
    )
    with pytest.raises(connect.CollectionNotFoundError, match="NADA foi criado"):
        connect.connect_resolved(pj, lambda: planned, poll_timeout=0)
    assert "autoexport.add" not in calls


def test_record_selected_nao_chama_autoexport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pj = _pj(tmp_path, _BIB)
    calls = _seams(monkeypatch, _selected(20, 5, "Lab Group"))
    saved = connect.record_resolved(pj, selection.resolve_selected)
    assert (saved.library, saved.collection, saved.source) == ("Lab Group", "Grupo A", "record")
    assert "autoexport.add" not in calls


def test_record_selected_recusa_bib_placeholder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pj = _pj(tmp_path, _PLACEHOLDER)
    calls = _seams(monkeypatch, _selected(11))
    with pytest.raises(connect.NotConnectedError, match="--selected"):
        connect.record_resolved(pj, selection.resolve_selected)
    assert calls == []


# --- selection_mismatch: o Connector vai salvar em outro lugar? -------------------------------


def _link(library_id: int | None = 1, collection: str = "Pesquisa/Item A") -> ZoteroLink:
    return ZoteroLink(
        library="My Library",
        library_id=library_id,
        collection=collection,
        collection_key="BBB",
        linked_at="2026-01-01",
        source="connect",
    )


def test_mismatch_silencioso_quando_bate(monkeypatch: pytest.MonkeyPatch) -> None:
    _seams(monkeypatch, _selected(11))
    assert selection.selection_mismatch(_link()) is None


def test_mismatch_avisa_outra_colecao(monkeypatch: pytest.MonkeyPatch) -> None:
    _seams(monkeypatch, _selected(13))
    msg = selection.selection_mismatch(_link())
    assert msg is not None and "My Library › Item A" in msg and "Connector" in msg


def test_mismatch_avisa_outra_biblioteca_com_mesmo_caminho(monkeypatch: pytest.MonkeyPatch) -> None:
    _seams(monkeypatch, _selected(20, 5, "Lab Group"))
    assert selection.selection_mismatch(_link(collection="Grupo A")) is not None


def test_mismatch_avisa_biblioteca_sem_colecao(monkeypatch: pytest.MonkeyPatch) -> None:
    _seams(monkeypatch, _selected(None))
    msg = selection.selection_mismatch(_link())
    assert msg is not None and "sem coleção" in msg


def test_mismatch_sem_library_id_compara_pelo_nome(monkeypatch: pytest.MonkeyPatch) -> None:
    _seams(monkeypatch, _selected(11))
    assert selection.selection_mismatch(_link(library_id=None)) is None


def test_mismatch_silencioso_com_zotero_fechado(monkeypatch: pytest.MonkeyPatch) -> None:
    _seams(monkeypatch, urllib.error.URLError("refused"))
    assert selection.selection_mismatch(_link()) is None
