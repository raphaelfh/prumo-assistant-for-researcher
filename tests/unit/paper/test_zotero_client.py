"""Tests diretos das funções de cliente/render do zotero.py (sem rede real)."""

from __future__ import annotations

import email.message
import urllib.error
import urllib.request
from typing import Any
from unittest.mock import patch

import pytest

import par.domains.paper.zotero as zot
from par.domains.paper.zotero import (
    ZoteroRef,
    check_zotero_running,
    fetch_children,
    html_to_markdown,
    render_note,
    resolve_citekey,
    split_children,
)


def test_html_to_markdown_basic_formatting() -> None:
    html = "<p>Olá <strong>mundo</strong> e <em>itálico</em></p>"
    out = html_to_markdown(html)
    assert "**mundo**" in out
    assert "*itálico*" in out
    assert "<p>" not in out


def test_html_to_markdown_headings_and_lists() -> None:
    html = "<h2>Título</h2><ul><li>um</li><li>dois</li></ul>"
    out = html_to_markdown(html)
    assert "## Título" in out
    assert "- um" in out
    assert "- dois" in out


def test_html_to_markdown_unescapes_entities() -> None:
    html = "<p>a &amp; b &lt; c</p>"
    out = html_to_markdown(html)
    assert "a & b < c" in out


def test_html_to_markdown_collapses_blank_lines() -> None:
    html = "<p>a</p><p></p><p></p><p>b</p>"
    out = html_to_markdown(html)
    assert "\n\n\n" not in out


def test_split_children_separates_annotations_and_notes() -> None:
    children = [
        {"itemType": "annotation", "annotationText": "x"},
        {"itemType": "note", "note": "<p>y</p>"},
        {"itemType": "attachment", "filename": "z.pdf"},
    ]
    annotations, notes = split_children(children)
    assert len(annotations) == 1
    assert len(notes) == 1
    # attachment descartado
    assert annotations[0]["annotationText"] == "x"
    assert notes[0]["note"] == "<p>y</p>"


def test_split_children_empty() -> None:
    annotations, notes = split_children([])
    assert annotations == []
    assert notes == []


def test_render_note_extracts_title_from_first_line() -> None:
    note = {"note": "<h1>Minha nota</h1><p>corpo da nota</p>"}
    lines = render_note(note)
    joined = "\n".join(lines)
    assert "Minha nota" in joined
    assert "corpo da nota" in joined


def test_render_note_empty_marks_vazia() -> None:
    note = {"note": ""}
    lines = render_note(note)
    joined = "\n".join(lines)
    assert "vazia" in joined.lower()


def test_resolve_citekey_empty_result_is_none() -> None:
    with patch(
        "par.domains.paper.zotero._http_post_json",
        return_value={"jsonrpc": "2.0", "result": [], "id": 1},
    ):
        assert resolve_citekey("missing") is None


def test_resolve_citekey_network_error_is_none() -> None:
    with patch(
        "par.domains.paper.zotero._http_post_json",
        side_effect=urllib.error.URLError("connection refused"),
    ):
        assert resolve_citekey("smith2024") is None


def test_resolve_citekey_non_dict_response_is_none() -> None:
    with patch("par.domains.paper.zotero._http_post_json", return_value=["unexpected"]):
        assert resolve_citekey("smith2024") is None


# ---------------------------------------------------------------------------
# resolve_citekey contra os shapes REAIS do BBT (medidos em 2026-07-26 contra
# Zotero 9.0.6 + Better BibTeX):
#   - ``item.search`` devolve ``library`` como STRING ('My Library') e NÃO
#     devolve ``itemKey``/``key``;
#   - ``item.pandoc_filter`` devolve ``custom.uri`` =
#     ``http://zotero.org/users/13049353/items/UGJ7VBQ8`` — é dela que saem o
#     caminho de library da API e o itemKey;
#   - erro de aplicação vem com HTTP 200 e ``error`` no corpo (``-32603``).
# ---------------------------------------------------------------------------


def _real_search_response(citekey: str, library: str) -> dict[str, object]:
    """Resposta real de ``item.search`` (conjunto de chaves medido ao vivo)."""
    return {
        "jsonrpc": "2.0",
        "result": [
            {
                "DOI": "10.1016/j.ejso.2025.01.001",
                "ISSN": "0748-7983",
                "URL": "https://example.org/artigo",
                "abstract": "…",
                "accessed": {"date-parts": [[2026, 7, 26]]},
                "author": [{"family": "Audisio", "given": "A."}],
                "citation-key": citekey,
                "citekey": citekey,
                "container-title": "European Journal of Surgical Oncology",
                "id": citekey,
                "issue": "3",
                "issued": {"date-parts": [[2025]]},
                "journalAbbreviation": "J Example Stud",
                "language": "en",
                "library": library,
                "page": "1-10",
                "source": "Zotero",
                "title": "Example article title",
                "type": "article-journal",
                "volume": "51",
            }
        ],
        "id": 1,
    }


def _real_pandoc_filter_response(citekey: str, item_id: int, uri: str) -> dict[str, object]:
    """Resposta real de ``item.pandoc_filter`` (``result.items[key].custom``)."""
    return {
        "jsonrpc": "2.0",
        "result": {"items": {citekey: {"custom": {"itemID": item_id, "uri": uri}}}},
        "id": 1,
    }


_RPC_ERROR_BODY: dict[str, object] = {
    "jsonrpc": "2.0",
    "error": {
        "code": -32603,
        "message": 'Error: library.get: {"libraryID":"","group":""} not found',
    },
    "id": 1,
}


def test_resolve_citekey_my_library_uses_uri_user_path() -> None:
    responses = [
        _real_search_response("audisio2025total", "My Library"),
        _real_pandoc_filter_response(
            "audisio2025total", 4712, "http://zotero.org/users/13049353/items/UGJ7VBQ8"
        ),
    ]
    with patch("par.domains.paper.zotero._http_post_json", side_effect=responses):
        ref = resolve_citekey("audisio2025total")
    assert ref == ZoteroRef(library_path="users/13049353", item_key="UGJ7VBQ8")


def test_resolve_citekey_group_library_uses_groups_path() -> None:
    responses = [
        _real_search_response("silva2024llm", "LLM evaluation"),
        _real_pandoc_filter_response(
            "silva2024llm", 8123, "http://zotero.org/groups/5772858/items/ABCD1234"
        ),
    ]
    with patch("par.domains.paper.zotero._http_post_json", side_effect=responses):
        ref = resolve_citekey("silva2024llm")
    assert ref == ZoteroRef(library_path="groups/5772858", item_key="ABCD1234")


def test_resolve_citekey_falls_back_to_library_of_first_result() -> None:
    """Se nenhum item bate exato, a library do primeiro serve de palpite."""
    responses = [
        _real_search_response("other2023", "My Library"),
        _real_pandoc_filter_response(
            "smith2024", 99, "http://zotero.org/users/13049353/items/ZZZZ9999"
        ),
    ]
    with patch("par.domains.paper.zotero._http_post_json", side_effect=responses):
        ref = resolve_citekey("smith2024")
    assert ref == ZoteroRef(library_path="users/13049353", item_key="ZZZZ9999")


def test_resolve_citekey_unknown_key_is_none_without_second_call() -> None:
    calls: list[dict[str, object]] = []

    def fake_post(url: str, payload: dict[str, object], timeout: float = 10.0) -> object:
        calls.append(payload)
        return {"jsonrpc": "2.0", "result": [], "id": 1}

    with patch("par.domains.paper.zotero._http_post_json", fake_post):
        assert resolve_citekey("naoexiste2099") is None
    assert len(calls) == 1


def test_resolve_citekey_none_when_pandoc_filter_omits_key() -> None:
    responses: list[object] = [
        _real_search_response("audisio2025total", "My Library"),
        {"jsonrpc": "2.0", "result": {"items": {}}, "id": 1},
    ]
    with patch("par.domains.paper.zotero._http_post_json", side_effect=responses):
        assert resolve_citekey("audisio2025total") is None


def test_resolve_citekey_jsonrpc_error_body_does_not_raise() -> None:
    responses: list[object] = [
        _real_search_response("audisio2025total", "My Library"),
        _RPC_ERROR_BODY,
    ]
    with patch("par.domains.paper.zotero._http_post_json", side_effect=responses):
        assert resolve_citekey("audisio2025total") is None


def test_fetch_children_extracts_data_field() -> None:
    api_response = [
        {"key": "C1", "data": {"itemType": "annotation", "annotationText": "x"}},
        {"key": "C2", "data": {"itemType": "note", "note": "<p>y</p>"}},
        {"key": "C3", "no_data_here": True},  # ignorado
    ]
    with patch("par.domains.paper.zotero._http_get_json", return_value=api_response):
        out = fetch_children(ZoteroRef("users/13049353", "PARENT01"))
    assert len(out) == 2
    assert out[0]["itemType"] == "annotation"
    assert out[1]["itemType"] == "note"


def test_fetch_children_non_list_response_is_empty() -> None:
    with patch("par.domains.paper.zotero._http_get_json", return_value={"error": "x"}):
        assert fetch_children(ZoteroRef("users/13049353", "PARENT01")) == []


def test_fetch_children_network_error_is_empty() -> None:
    with patch(
        "par.domains.paper.zotero._http_get_json",
        side_effect=urllib.error.URLError("refused"),
    ):
        assert fetch_children(ZoteroRef("users/13049353", "PARENT01")) == []


# ---------------------------------------------------------------------------
# Annotations são NETAS do item top-level (top → attachment → annotation).
# Medido em 2026-07-26 contra Zotero 9.0.6 + Better BibTeX:
#   /items/5MSIQBA3/children            → n=2, ambos 'attachment' (0 annotation)
#   /items/9JUI5P4Q/children            → n=0, embora o anexo tenha 8 annotations
#   /items/9JUI5P4Q/annotations         → 404
#   /items?itemType=annotation&limit=100 → n=83   ← única via
#   o filtro ?parentItem=<key> é IGNORADO pela Local API (devolve tudo)
# ---------------------------------------------------------------------------


def _annotation_entry(
    key: str, parent: str, page: str, text: str, sort_index: str
) -> dict[str, Any]:
    """Envelope real de ``/items?itemType=annotation`` (chaves de ``data`` medidas)."""
    return {
        "key": key,
        "version": 4711,
        "library": {"type": "user", "id": 13049353, "name": "raphael"},
        "data": {
            "key": key,
            "version": 4711,
            "parentItem": parent,
            "itemType": "annotation",
            "annotationType": "highlight",
            "annotationAuthorName": "",
            "annotationText": text,
            "annotationComment": "",
            "annotationColor": "#ffd400",
            "annotationPageLabel": page,
            "annotationSortIndex": sort_index,
            "annotationPosition": '{"pageIndex":3,"rects":[[70.9,516.5,525.3,527.6]]}',
            "tags": [],
            "relations": {},
            "dateAdded": "2026-05-11T18:22:41Z",
            "dateModified": "2026-05-11T18:22:41Z",
        },
    }


def _attachment_entry(key: str, parent: str, title: str) -> dict[str, Any]:
    """Envelope real de ``/items/<top>/children`` para um anexo PDF."""
    return {
        "key": key,
        "version": 3300,
        "data": {
            "key": key,
            "version": 3300,
            "parentItem": parent,
            "itemType": "attachment",
            "linkMode": "imported_url",
            "title": title,
            "contentType": "application/pdf",
            "filename": f"{key}.pdf",
            "tags": [],
            "relations": {},
        },
    }


def _http_error(url: str, code: int, reason: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, reason, email.message.Message(), None)


def test_fetch_annotations_index_groups_by_parent_item() -> None:
    """Uma chamada por biblioteca; o cliente indexa por ``parentItem``."""
    page = [
        _annotation_entry("AN000001", "9JUI5P4Q", "12", "MMR deficiency", "00003|000100|00010"),
        _annotation_entry("AN000002", "9JUI5P4Q", "13", "microsatellite", "00004|000100|00010"),
        _annotation_entry("AN000003", "OUTROANX", "2", "outro paper", "00001|000100|00010"),
    ]
    calls: list[str] = []

    def fake_get(url: str, timeout: float = 10.0) -> object:
        calls.append(url)
        return page if "start=0" in url or "start" not in url else []

    with patch("par.domains.paper.zotero._http_get_json", fake_get):
        index = zot.fetch_annotations_index("users/13049353")

    assert set(index) == {"9JUI5P4Q", "OUTROANX"}
    assert [a["key"] for a in index["9JUI5P4Q"]] == ["AN000001", "AN000002"]
    assert index["9JUI5P4Q"][0]["annotationText"] == "MMR deficiency"
    assert "itemType=annotation" in calls[0]
    # NÃO usa ?parentItem= — a Local API ignora esse filtro
    assert "parentItem=" not in calls[0]


def test_annotations_for_item_matches_attachments_of_children() -> None:
    """``/children`` traz só attachments; as annotations casam por ``parentItem``."""
    children = [
        _attachment_entry("9JUI5P4Q", "5MSIQBA3", "Full Text PDF")["data"],
        _attachment_entry("SNAPSHOT1", "5MSIQBA3", "Snapshot")["data"],
        {"itemType": "note", "key": "NOTE0001", "note": "<p>minha nota</p>"},
    ]
    index = {
        "9JUI5P4Q": [_annotation_entry("AN1", "9JUI5P4Q", "12", "MMR", "a")["data"]],
        "NAOMEU01": [_annotation_entry("AN9", "NAOMEU01", "1", "outro", "b")["data"]],
    }
    out = zot.annotations_for_item(children, index)
    assert [a["key"] for a in out] == ["AN1"]


def test_fetch_children_http_403_explains_how_to_enable_local_api() -> None:
    """403 = Local API desligada: erro acionável, nunca lista vazia."""
    from par.domains.paper.errors import PaperError

    with (
        patch(
            "par.domains.paper.zotero._http_get_json",
            side_effect=_http_error(
                "http://127.0.0.1:23119/api/users/0/items/X/children",
                403,
                "Local API is not enabled",
            ),
        ),
        pytest.raises(PaperError) as exc,
    ):
        fetch_children(ZoteroRef("users/13049353", "PARENT01"))
    msg = str(exc.value)
    assert "403" in msg
    assert "Settings" in msg and "Advanced" in msg
    assert "Allow other applications on this computer to communicate with Zotero" in msg


def test_fetch_children_http_400_raises_instead_of_empty_list() -> None:
    from par.domains.paper.errors import PaperError

    with (
        patch(
            "par.domains.paper.zotero._http_get_json",
            side_effect=_http_error(
                "http://127.0.0.1:23119/api/users/1/items/X/children", 400, "Bad Request"
            ),
        ),
        pytest.raises(PaperError) as exc,
    ):
        fetch_children(ZoteroRef("users/1", "PARENT01"))
    assert "400" in str(exc.value)


def test_fetch_annotations_index_http_403_raises() -> None:
    from par.domains.paper.errors import PaperError

    with (
        patch(
            "par.domains.paper.zotero._http_get_json",
            side_effect=_http_error(
                "http://127.0.0.1:23119/api/users/0/items", 403, "Local API is not enabled"
            ),
        ),
        pytest.raises(PaperError),
    ):
        zot.fetch_annotations_index("users/13049353")


def test_fetch_annotations_index_paginates_until_short_page() -> None:
    """Biblioteca com mais annotations que uma página: paginação por ``start``."""
    first = [
        _annotation_entry(f"AN{i:06d}", "9JUI5P4Q", "1", f"t{i}", f"{i:05d}")
        for i in range(zot._ANNOTATIONS_PAGE_SIZE)
    ]
    second = [_annotation_entry("ANLAST", "OUTROANX", "9", "última", "99999")]
    pages = {0: first, zot._ANNOTATIONS_PAGE_SIZE: second}

    def fake_get(url: str, timeout: float = 10.0) -> object:
        start = int(url.split("start=")[1].split("&")[0])
        return pages.get(start, [])

    with patch("par.domains.paper.zotero._http_get_json", fake_get):
        index = zot.fetch_annotations_index("users/13049353")

    assert len(index["9JUI5P4Q"]) == zot._ANNOTATIONS_PAGE_SIZE
    assert [a["key"] for a in index["OUTROANX"]] == ["ANLAST"]


def test_fetch_annotations_index_survives_ignored_start_param() -> None:
    """Se a API ignorasse ``start`` (como ignora ``parentItem``), não duplicamos."""
    page = [
        _annotation_entry(f"AN{i:06d}", "9JUI5P4Q", "1", f"t{i}", f"{i:05d}")
        for i in range(zot._ANNOTATIONS_PAGE_SIZE)
    ]
    calls: list[str] = []

    def fake_get(url: str, timeout: float = 10.0) -> object:
        calls.append(url)
        return page  # sempre a mesma página, `start` ignorado

    with patch("par.domains.paper.zotero._http_get_json", fake_get):
        index = zot.fetch_annotations_index("users/13049353")

    assert len(index["9JUI5P4Q"]) == zot._ANNOTATIONS_PAGE_SIZE
    assert len(calls) == 2  # para na primeira página sem novidade


# ---------------------------------------------------------------------------
# check_zotero_running — mapa de endpoints REAL do Zotero 9.0.6 + BBT:
# GET /               → 404 (HTTPError, subclasse de URLError)
# GET /connector/ping → 200 com header X-Zotero-Version: 9.0.6
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


def _zotero_running_urlopen(url: object, timeout: float = 0.0) -> _FakePingResponse:
    """Zotero rodando com a API local LIGADA: ``/api/`` e ``/connector/ping`` respondem."""
    target = url.full_url if isinstance(url, urllib.request.Request) else str(url)
    if target.endswith("/connector/ping"):
        return _FakePingResponse({"X-Zotero-Version": "9.0.6"})
    if target.endswith("/api/"):
        return _FakePingResponse({})
    raise urllib.error.HTTPError(target, 404, "Not Found", email.message.Message(), None)


def test_check_zotero_running_true_when_local_api_answers() -> None:
    with patch("urllib.request.urlopen", _zotero_running_urlopen):
        assert check_zotero_running() is True


def test_check_zotero_running_false_when_app_open_but_local_api_disabled() -> None:
    """Regressão: o app aberto responde ``/connector/ping``, mas ``/api/`` dá 403.

    Antes isso contava como "rodando" e o guard deixava o comando seguir pra
    tomar 403 em série na primeira chamada de verdade.
    """

    def _api_disabled(url: object, timeout: float = 0.0) -> _FakePingResponse:
        target = url.full_url if isinstance(url, urllib.request.Request) else str(url)
        if target.endswith("/connector/ping"):
            return _FakePingResponse({"X-Zotero-Version": "9.0.6"})
        raise urllib.error.HTTPError(
            target, 403, "Local API is not enabled", email.message.Message(), None
        )

    with patch("urllib.request.urlopen", _api_disabled):
        assert check_zotero_running() is False


def test_check_zotero_running_false_on_connection_refused() -> None:
    def _refused(*args: object, **kwargs: object) -> object:
        raise urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))

    with patch("urllib.request.urlopen", _refused):
        assert check_zotero_running() is False


def test_check_zotero_running_false_on_timeout() -> None:
    def _timeout(*args: object, **kwargs: object) -> object:
        raise TimeoutError

    with patch("urllib.request.urlopen", _timeout):
        assert check_zotero_running() is False


# ---------------------------------------------------------------------------
# Host configurável via PRUMO_ZOTERO_BASE
# ---------------------------------------------------------------------------


def test_zotero_base_default_is_loopback_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRUMO_ZOTERO_BASE", raising=False)
    assert zot._zotero_base() == "http://127.0.0.1:23119"


def test_zotero_base_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRUMO_ZOTERO_BASE", "http://localhost:9999")
    assert zot._zotero_base() == "http://localhost:9999"


def test_bbt_rpc_and_api_follow_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRUMO_ZOTERO_BASE", "http://example.test:1234")
    assert zot._bbt_rpc() == "http://example.test:1234/better-bibtex/json-rpc"
    assert zot._zotero_api() == "http://example.test:1234/api"


def test_fetch_children_uses_overridden_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRUMO_ZOTERO_BASE", "http://example.test:1234")
    captured: dict[str, str] = {}

    def fake_get(url: str, timeout: float = 10.0) -> object:
        captured["url"] = url
        return []

    monkeypatch.setattr(zot, "_http_get_json", fake_get)
    zot.fetch_children(ZoteroRef("users/13049353", "PARENT01"))
    assert captured["url"].startswith("http://example.test:1234/api/users/13049353/items/PARENT01")
