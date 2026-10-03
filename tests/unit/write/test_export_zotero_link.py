"""Vínculo das citações do docx com a biblioteca do Zotero (ADR-0037)."""

from __future__ import annotations

import email.message
import html
import io
import json
import logging
import subprocess
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, cast

import pytest

from par.core.deps import pandoc_path, zotero_base
from par.domains.write import export as export_mod
from par.domains.write.export import (
    BbtLookup,
    _read_docx_citations,
    _redo_command,
    docx_link_warning,
    fetch_bbt_zotero_metadata,
)
from tests.unit.write.test_export_docx_validation import (
    _docx_bytes_for_export_wiring,
    _fake_project,
    _fake_run_writing_output_flag,
    _patch_export_seams,
    _write_minimal_docx_with_payloads,
)

_PANDOC = pandoc_path()

requires_pandoc = pytest.mark.skipif(
    _PANDOC is None, reason="pandoc ausente (nem no PATH nem no Zettlr.app)"
)


def _field_payloads(docx: Path) -> list[dict[str, Any]]:
    """Payloads ``CSL_CITATION`` dos campos ``ZOTERO_ITEM``, na ordem do documento."""
    with zipfile.ZipFile(docx) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    payloads: list[dict[str, Any]] = []
    for match in export_mod._INSTR_TEXT_RE.finditer(xml):
        raw = match.group(1)
        if export_mod._ZOTERO_ITEM_CSL_MARKER not in raw:
            continue
        i = len(payloads) + 1  # 1-based, só campos Zotero (contrato de _parse_csl_payload)
        payloads.append(
            cast(
                dict[str, Any],
                export_mod._parse_csl_payload(
                    html.unescape(raw), i, error_cls=export_mod.CiteMapMismatchError
                ),
            )
        )
    return payloads


# ---------- Lua com pandoc real ----------


@requires_pandoc
def test_lua_uris_is_always_a_json_array(tmp_path: Path) -> None:
    """``uris`` sai sempre como array: ``[URI]`` com vínculo, ``[]`` sem (B2)."""
    assert _PANDOC is not None
    (tmp_path / "refs.bib").write_text(
        "@article{linked2020, author={Silva, Ana}, title={T1}, journal={J}, year={2020}}\n"
        "@article{unlinked2021, author={Souza, Bia}, title={T2}, journal={J}, year={2021}}\n"
    )
    (tmp_path / "style.csl").write_text(
        subprocess.run(
            [_PANDOC, "--print-default-data-file", "default.csl"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    (tmp_path / "zotero_lookup.json").write_text(
        json.dumps(
            {
                "linked2020": {
                    "itemID": 42,
                    "uri": "http://zotero.org/users/local/abcd/items/ABCD1234",
                    "fingerprint": "sha256:x",
                }
            }
        )
    )
    (tmp_path / "in.md").write_text("Cita [@linked2020] e [@unlinked2021].\n\n::: {#refs}\n:::\n")
    cmd = export_mod._build_pandoc_cmd(
        pandoc_bin=_PANDOC,
        input_md=tmp_path / "in.md",
        output=tmp_path / "out.docx",
        bib=tmp_path / "refs.bib",
        csl=tmp_path / "style.csl",
        style="apa",
        metadata_file=None,
        template=None,
        reference_doc=None,
        to_format="docx",
        zotero_lookup_file=tmp_path / "zotero_lookup.json",
        resource_path=tmp_path,
    )
    export_mod._run_pandoc_checked(cmd)
    uris = {
        item["id"]: item.get("uris", "<ausente>")
        for p in _field_payloads(tmp_path / "out.docx")
        for item in p["citationItems"]
    }
    assert uris == {
        "linked2020": ["http://zotero.org/users/local/abcd/items/ABCD1234"],
        "unlinked2021": [],
    }


@requires_pandoc
def test_lua_uris_ignores_non_string_uri(tmp_path: Path) -> None:
    """Lookup com ``"uri": null`` (lookup antigo/fora do contrato) sai ``uris: []``,
    e ``zoteroItemID`` só aparece quando é número."""
    assert _PANDOC is not None
    (tmp_path / "refs.bib").write_text(
        "@article{k2020, author={Silva, Ana}, title={T1}, journal={J}, year={2020}}\n"
    )
    (tmp_path / "style.csl").write_text(
        subprocess.run(
            [_PANDOC, "--print-default-data-file", "default.csl"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    (tmp_path / "zotero_lookup.json").write_text(
        json.dumps({"k2020": {"itemID": None, "uri": None, "fingerprint": "x"}})
    )
    (tmp_path / "in.md").write_text("Cita [@k2020].\n\n::: {#refs}\n:::\n")
    cmd = export_mod._build_pandoc_cmd(
        pandoc_bin=_PANDOC,
        input_md=tmp_path / "in.md",
        output=tmp_path / "out.docx",
        bib=tmp_path / "refs.bib",
        csl=tmp_path / "style.csl",
        style="apa",
        metadata_file=None,
        template=None,
        reference_doc=None,
        to_format="docx",
        zotero_lookup_file=tmp_path / "zotero_lookup.json",
        resource_path=tmp_path,
    )
    export_mod._run_pandoc_checked(cmd)
    (item,) = [i for p in _field_payloads(tmp_path / "out.docx") for i in p["citationItems"]]
    assert item["uris"] == []
    assert "zoteroItemID" not in item
    assert _read_docx_citations(tmp_path / "out.docx")[0]["unlinked"] == ["k2020"]


# ---------- fetch_bbt_zotero_metadata: lookup melhor-esforço (B1, B3) ----------

_RPC_URL = "http://127.0.0.1:23119/better-bibtex/json-rpc"
_OK_BODY: dict[str, object] = {"jsonrpc": "2.0", "result": {"items": {}}}


def _install_urlopen_spy(
    monkeypatch: pytest.MonkeyPatch,
    *,
    body: object = None,
    exc: BaseException | None = None,
) -> list[tuple[urllib.request.Request, float]]:
    """Troca o ``urlopen`` do export por um espião; devolve as chamadas ``(req, timeout)``."""
    calls: list[tuple[urllib.request.Request, float]] = []

    def spy(req: urllib.request.Request, timeout: float) -> io.BytesIO:
        calls.append((req, timeout))
        if exc is not None:
            raise exc
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr("par.domains.write.export.urllib.request.urlopen", spy)
    return calls


def _params(req: urllib.request.Request) -> object:
    return json.loads(cast(bytes, req.data))["params"]


def test_fetch_unreachable_on_url_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_urlopen_spy(monkeypatch, exc=urllib.error.URLError(ConnectionRefusedError()))
    lookup = fetch_bbt_zotero_metadata(["k"], None)
    assert lookup.failure == "unreachable"
    assert lookup.items == {}


def test_fetch_unreachable_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_urlopen_spy(monkeypatch, exc=TimeoutError())
    lookup = fetch_bbt_zotero_metadata(["k"], None)
    assert lookup.failure == "unreachable"
    assert lookup.items == {}


def test_fetch_unreachable_on_http_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """404: Zotero aberto sem o Better BibTeX (ou o BBT ainda iniciando)."""
    err = urllib.error.HTTPError(_RPC_URL, 404, "Not Found", hdrs=email.message.Message(), fp=None)
    _install_urlopen_spy(monkeypatch, exc=err)
    lookup = fetch_bbt_zotero_metadata(["k"], None)
    assert lookup.failure == "unreachable"
    assert lookup.items == {}


def test_fetch_rpc_error_on_jsonrpc_error_body(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"jsonrpc": "2.0", "error": {"code": -32603, "message": "could not find library"}}
    _install_urlopen_spy(monkeypatch, body=body)
    lookup = fetch_bbt_zotero_metadata(["k"], "Lab")
    assert lookup.failure == "rpc_error"
    assert "could not find library" in lookup.detail
    assert lookup.items == {}


def test_fetch_rpc_error_on_http_500(monkeypatch: pytest.MonkeyPatch) -> None:
    err = urllib.error.HTTPError(
        _RPC_URL, 500, "Internal Server Error", hdrs=email.message.Message(), fp=None
    )
    _install_urlopen_spy(monkeypatch, exc=err)
    lookup = fetch_bbt_zotero_metadata(["k"], None)
    assert lookup.failure == "rpc_error"
    assert "500" in lookup.detail


def test_fetch_rpc_error_on_malformed_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """Corpo fora do contrato não vira exceção: a função nunca levanta (ADR-0037)."""
    _install_urlopen_spy(monkeypatch, body={"result": []})
    lookup = fetch_bbt_zotero_metadata(["k"], None)
    assert lookup.failure == "rpc_error"
    assert lookup.detail == "resposta JSON-RPC inesperada"
    assert lookup.items == {}


def test_fetch_success_returns_items(monkeypatch: pytest.MonkeyPatch) -> None:
    uri = "http://zotero.org/users/local/k/items/AB"
    body = {
        "jsonrpc": "2.0",
        "result": {
            "items": {
                "smith2020": {"custom": {"itemID": 7, "uri": uri}},
                "ghost2020": None,
            }
        },
    }
    _install_urlopen_spy(monkeypatch, body=body)
    lookup = fetch_bbt_zotero_metadata(["smith2020", "ghost2020"], None)
    assert lookup.items == {"smith2020": {"itemID": 7, "uri": uri}}
    assert lookup.failure == ""


def test_fetch_keeps_only_well_typed_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """``uri`` ausente/vazio/não-str não vira ``null`` no lookup: o Lua o emitiria como
    ``"uris":[null]`` e a citação passaria por vinculada sem aviso (ADR-0037)."""
    uri = "http://zotero.org/users/local/k/items/AB"
    body = {
        "jsonrpc": "2.0",
        "result": {
            "items": {
                "id_only2020": {"custom": {"itemID": 7}},
                "uri_only2020": {"custom": {"uri": uri}},
                "empty_uri2020": {"custom": {"itemID": 8, "uri": ""}},
                "bad_types2020": {"custom": {"itemID": "x", "uri": 5}},
            }
        },
    }
    _install_urlopen_spy(monkeypatch, body=body)
    lookup = fetch_bbt_zotero_metadata(list(body["result"]["items"]), None)  # type: ignore[index]
    assert lookup.items == {
        "id_only2020": {"itemID": 7},
        "uri_only2020": {"uri": uri},
        "empty_uri2020": {"itemID": 8},
    }


def test_fetch_never_raises_on_empty_zotero_base(monkeypatch: pytest.MonkeyPatch) -> None:
    """``PRUMO_ZOTERO_BASE=""`` cai no padrão; base malformada vira ``unreachable``."""
    monkeypatch.setenv("PRUMO_ZOTERO_BASE", "")
    calls = _install_urlopen_spy(monkeypatch, body=_OK_BODY)
    fetch_bbt_zotero_metadata(["k"], None)
    assert calls[0][0].full_url == _RPC_URL


def test_fetch_unreachable_on_malformed_zotero_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRUMO_ZOTERO_BASE", "http://[::1")
    lookup = fetch_bbt_zotero_metadata(["k"], None)
    assert lookup.failure == "unreachable"
    assert lookup.items == {}


@pytest.mark.parametrize("raw", [b"", b"<html>No endpoint found</html>", b'{"result": {'])
def test_fetch_rpc_error_on_non_json_body(monkeypatch: pytest.MonkeyPatch, raw: bytes) -> None:
    """Algo respondeu 200 com corpo que não é JSON: E3, não E1/E2."""

    def spy(req: urllib.request.Request, timeout: float) -> io.BytesIO:
        return io.BytesIO(raw)

    monkeypatch.setattr("par.domains.write.export.urllib.request.urlopen", spy)
    lookup = fetch_bbt_zotero_metadata(["k"], None)
    assert lookup.failure == "rpc_error"
    assert lookup.detail == "resposta JSON-RPC inesperada"


def test_fetch_rpc_error_when_result_has_no_items(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_urlopen_spy(monkeypatch, body={"jsonrpc": "2.0", "result": {}})
    lookup = fetch_bbt_zotero_metadata(["k"], None)
    assert lookup.failure == "rpc_error"


def test_fetch_records_duplicate_citekeys(monkeypatch: pytest.MonkeyPatch) -> None:
    """``errors[citekey]`` do BBT: 0 = não achada, n>0 = citekey duplicada."""
    body = {
        "jsonrpc": "2.0",
        "result": {"items": {}, "errors": {"dup2020": 2, "ghost2020": 0, "odd2020": "x"}},
    }
    _install_urlopen_spy(monkeypatch, body=body)
    lookup = fetch_bbt_zotero_metadata(["dup2020", "ghost2020"], None)
    assert lookup.failure == ""
    assert lookup.duplicates == ("dup2020",)


def test_fetch_params_omit_library_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem ``zotero.library``, o 3º parâmetro sai (B3): ``""`` faz o BBT recusar."""
    calls = _install_urlopen_spy(monkeypatch, body=_OK_BODY)
    fetch_bbt_zotero_metadata(["k"], None)
    assert _params(calls[0][0]) == [["k"], True]


def test_fetch_params_include_library(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_urlopen_spy(monkeypatch, body=_OK_BODY)
    lookup = fetch_bbt_zotero_metadata(["k"], "Lab")
    assert _params(calls[0][0]) == [["k"], True, "Lab"]
    assert lookup.library == "Lab"


def test_fetch_timeout_is_two_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_urlopen_spy(monkeypatch, body=_OK_BODY)
    fetch_bbt_zotero_metadata(["k"], None)
    assert calls[0][1] == 2.0


def test_fetch_url_follows_prumo_zotero_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRUMO_ZOTERO_BASE", "http://example.test:1234")
    calls = _install_urlopen_spy(monkeypatch, body=_OK_BODY)
    fetch_bbt_zotero_metadata(["k"], None)
    assert calls[0][0].full_url == "http://example.test:1234/better-bibtex/json-rpc"


def test_fetch_without_citekeys_does_not_call(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_urlopen_spy(monkeypatch, body=_OK_BODY)
    assert fetch_bbt_zotero_metadata([], None) == BbtLookup({})
    assert calls == []


# ---------- _read_docx_citations: chave "unlinked" por ocorrência ----------


def _payload(items: list[dict[str, object]], occ: str = "00000001") -> str:
    """JSON ``CSL_CITATION`` mínimo, no formato do ``zotero_live_docx.lua``."""
    return json.dumps(
        {
            "citationID": occ,
            "prumoOcc": occ,
            "citationItems": items,
            "properties": {"formattedCitation": "(X)"},
        }
    )


def test_read_docx_citations_marks_unlinked(tmp_path: Path) -> None:
    first = _payload([{"id": "a2020", "uris": ["u"]}, {"id": "b2021", "uris": []}])
    second = _payload([{"id": "c2022"}], occ="00000002")
    docx = _write_minimal_docx_with_payloads(tmp_path / "u.docx", [first, second])
    occs = _read_docx_citations(docx)
    assert [o["unlinked"] for o in occs] == [["b2021"], ["c2022"]]


# ---------- docx_link_warning: um aviso por causa (E1–E4) ----------

_REDO = "prumo write export docs/p.md --to docx --force"
_LINKED_ENTRY: dict[str, object] = {"itemID": 1, "uri": "u"}


def _docx_with(tmp_path: Path, items: list[dict[str, object]]) -> Path:
    """Docx mínimo com uma ocorrência por item, na ordem dada."""
    payloads = [_payload([item], occ=f"{i:08d}") for i, item in enumerate(items, start=1)]
    return _write_minimal_docx_with_payloads(tmp_path / "w.docx", payloads)


def test_warning_none_when_all_linked(tmp_path: Path) -> None:
    docx = _docx_with(tmp_path, [{"id": "a2020", "uris": ["u"]}])
    assert docx_link_warning(docx, BbtLookup({"a2020": _LINKED_ENTRY}), _REDO) is None


def test_warning_unreachable_e1(tmp_path: Path) -> None:
    docx = _docx_with(tmp_path, [{"id": "a2020", "uris": []}])
    msg = docx_link_warning(docx, BbtLookup({}, failure="unreachable"), _REDO)
    assert msg is not None
    assert msg.startswith("Não consegui falar com o Better BibTeX")
    assert _REDO in msg


def test_warning_sandbox_e2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SANDBOX_RUNTIME", "1")
    docx = _docx_with(tmp_path, [{"id": "a2020", "uris": []}])
    msg = docx_link_warning(docx, BbtLookup({}, failure="unreachable"), _REDO)
    assert msg is not None
    assert "sandbox do Claude Code" in msg
    assert "sandbox.excludedCommands" in msg
    assert zotero_base() in msg
    assert _REDO in msg


def test_warning_rpc_error_e3(tmp_path: Path) -> None:
    docx = _docx_with(tmp_path, [{"id": "a2020", "uris": []}])
    lookup = BbtLookup({}, failure="rpc_error", detail="could not find library")
    msg = docx_link_warning(docx, lookup, _REDO)
    assert msg is not None
    assert "could not find library" in msg
    assert "9.0.65" in msg
    assert "zotero.library" in msg
    assert _REDO in msg


def test_warning_not_found_e4_lists_keys_and_library(tmp_path: Path) -> None:
    docx = _docx_with(tmp_path, [{"id": "a2020", "uris": ["u"]}, {"id": "b2021", "uris": []}])
    msg = docx_link_warning(docx, BbtLookup({"a2020": _LINKED_ENTRY}, library="Lab"), _REDO)
    assert msg is not None
    assert "b2021" in msg
    assert "(Lab)" in msg
    assert _REDO in msg
    default = docx_link_warning(docx, BbtLookup({"a2020": _LINKED_ENTRY}), _REDO)
    assert default is not None
    assert "(My Library, a padrão)" in default


def test_read_docx_citations_null_uri_is_unlinked(tmp_path: Path) -> None:
    """``uris`` sem nenhuma string não vazia (``[null]``, ``[""]``) conta como sem vínculo."""
    payload = _payload([{"id": "a2020", "uris": [None]}, {"id": "b2021", "uris": [""]}])
    docx = _write_minimal_docx_with_payloads(tmp_path / "n.docx", [payload])
    assert _read_docx_citations(docx)[0]["unlinked"] == ["a2020", "b2021"]


def test_warning_duplicates_get_own_sentence(tmp_path: Path) -> None:
    """Citekey duplicada no Zotero não entra no E4 ("não achada"): tem frase própria."""
    docx = _docx_with(tmp_path, [{"id": "dup2020", "uris": []}, {"id": "ghost2021", "uris": []}])
    msg = docx_link_warning(docx, BbtLookup({}, duplicates=("dup2020",)), _REDO)
    assert msg is not None
    not_found, duplicated = msg.split("\n")
    assert not_found.startswith("1 citekey(s) não foram achadas")
    assert "ghost2021" in not_found
    assert "dup2020" not in not_found
    assert "duplicada" in duplicated
    assert "dup2020" in duplicated
    assert _REDO in duplicated


def test_warning_only_duplicates(tmp_path: Path) -> None:
    docx = _docx_with(tmp_path, [{"id": "dup2020", "uris": []}])
    msg = docx_link_warning(docx, BbtLookup({}, duplicates=("dup2020",)), _REDO)
    assert msg is not None
    assert "não foram achadas" not in msg
    assert "dup2020" in msg


def test_warning_e4_truncates_after_five_keys(tmp_path: Path) -> None:
    keys = ["aaa2001", "bbb2002", "ccc2003", "ddd2004", "eee2005", "fff2006", "ggg2007"]
    docx = _docx_with(tmp_path, [{"id": k, "uris": []} for k in keys])
    msg = docx_link_warning(docx, BbtLookup({}), _REDO)
    assert msg is not None
    assert "7 citekey(s)" in msg
    assert "aaa2001, bbb2002, ccc2003, ddd2004, eee2005, …" in msg
    assert "fff2006" not in msg


def test_warning_counts_distinct_citekeys(tmp_path: Path) -> None:
    """Uma chave sem vínculo citada duas vezes conta uma vez (B1)."""
    docx = _docx_with(tmp_path, [{"id": "a2020", "uris": []}, {"id": "a2020", "uris": []}])
    msg = docx_link_warning(docx, BbtLookup({}, failure="unreachable"), _REDO)
    assert msg is not None
    assert "1 citekey(s)" in msg


# ---------- _redo_command: o comando de refazer reproduz a chamada (B1) ----------


def test_redo_export_defaults() -> None:
    assert (
        _redo_command("export", Path("/tmp/p.md"))
        == "prumo write export /tmp/p.md --to docx --force"
    )


def test_redo_quotes_paths_with_spaces() -> None:
    assert "'/tmp/meu draft.md'" in _redo_command("export", Path("/tmp/meu draft.md"))


def test_redo_compose_with_all_options() -> None:
    redo = _redo_command(
        "compose",
        Path("/tmp/i.md"),
        style="vancouver",
        bib=Path("/tmp/r.bib"),
        out_dir=Path("/tmp/out"),
        reference_doc=Path("/tmp/rev.docx"),
    )
    assert redo == (
        "prumo write compose --index /tmp/i.md --to docx --force --style vancouver "
        "--bib /tmp/r.bib --out-dir /tmp/out --reference-doc /tmp/rev.docx"
    )


# ---------- fiação: export()/compose() sem gate, aviso por on_warning ----------

_WIRING_PAYLOAD = (
    '{"citationID":"00000001","prumoOcc":"00000001",'
    '"citationItems":[{"id":"smith2020","uris":[],"prumoFingerprint":"doi:10.1/x"}],'
    '"properties":{"formattedCitation":"(Smith, 2020)"}}'
)


def _wire_unreachable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Projeto falso com ``[@smith2020]``, pandoc mockado e BBT inalcançável."""
    root, page = _fake_project(tmp_path)
    page.write_text("Cita [@smith2020] aqui.\n")
    _patch_export_seams(monkeypatch, tmp_path)
    monkeypatch.setattr(
        export_mod,
        "fetch_bbt_zotero_metadata",
        lambda keys, lib, **kw: BbtLookup({}, failure="unreachable"),
    )
    calls: list[list[str]] = []
    fake = _fake_run_writing_output_flag(
        [_docx_bytes_for_export_wiring(tmp_path, [_WIRING_PAYLOAD])], calls
    )
    monkeypatch.setattr("par.domains.write.export.subprocess.run", fake)
    return root, page


def test_export_unreachable_does_not_raise_and_warns_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, page = _wire_unreachable(tmp_path, monkeypatch)
    avisos: list[str] = []
    out = export_mod.export(page=page, to="docx", project_root=root, on_warning=avisos.append)
    assert out.is_file()
    assert len(avisos) == 1
    assert "prumo write export" in avisos[0]
    assert "--style" not in avisos[0]


def test_export_redo_carries_style_and_reference_doc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, page = _wire_unreachable(tmp_path, monkeypatch)
    reference_doc = tmp_path / "revista.docx"
    reference_doc.write_bytes(b"ref")
    avisos: list[str] = []
    export_mod.export(
        page=page,
        to="docx",
        style="vancouver",
        reference_doc=reference_doc,
        project_root=root,
        on_warning=avisos.append,
    )
    assert len(avisos) == 1
    assert "--style vancouver" in avisos[0]
    assert "--reference-doc" in avisos[0]


def test_compose_unreachable_does_not_raise_and_warns_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _page = _wire_unreachable(tmp_path, monkeypatch)
    index = root / "docs" / "index.md"
    index.write_text("---\npages: [docs/page.md]\n---\n")
    avisos: list[str] = []
    out = export_mod.compose(index=index, to="docx", project_root=root, on_warning=avisos.append)
    assert out.is_file()
    assert len(avisos) == 1
    assert "prumo write compose --index" in avisos[0]


def test_export_default_on_warning_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    root, page = _wire_unreachable(tmp_path, monkeypatch)
    with caplog.at_level(logging.WARNING, logger="par.domains.write.export"):
        export_mod.export(page=page, to="docx", project_root=root)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "Não consegui falar" in warnings[0].getMessage()


# ---------- _check_pandoc: PATH ou Zettlr.app, e o E7 ----------


def test_check_pandoc_e7_without_pandoc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("par.core.deps._binary_on_path", lambda name: None)
    with pytest.raises(export_mod.ToolNotFoundError) as exc:
        export_mod._check_pandoc()
    assert "3.8.2" in str(exc.value)
    assert "prumo doctor" in str(exc.value)


def test_check_pandoc_uses_zettlr_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = tmp_path / "Zettlr.app" / "pandoc"
    fake.parent.mkdir(parents=True)
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setattr("par.core.deps._binary_on_path", lambda name: None)
    monkeypatch.setattr("par.core.deps._ZETTLR_PANDOC", fake)
    assert export_mod._check_pandoc() == str(fake)
