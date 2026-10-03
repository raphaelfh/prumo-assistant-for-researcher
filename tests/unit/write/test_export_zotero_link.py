"""Vínculo das citações do docx com a biblioteca do Zotero (ADR-0037)."""

from __future__ import annotations

import html
import json
import subprocess
import zipfile
from pathlib import Path
from typing import Any, cast

import pytest

from par.core.deps import pandoc_path
from par.domains.write import export as export_mod

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
