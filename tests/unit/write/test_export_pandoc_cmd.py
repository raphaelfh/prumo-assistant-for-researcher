"""Tests para o pipeline pandoc de ``prumo_assist.domains.write.export``.

Cobre:

- Roteamento por formato em ``_build_pandoc_cmd`` (docx → filtros Lua do
  Zotero; html/typst → ``--citeproc`` com CSL local).
- Resolução dos filtros vendored.
- Detecção das três condições de falha que ``_assert_no_missing_citekeys``
  promove de aviso silencioso a erro acionável.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from prumo_assist.domains.write.export import (
    MissingBibliographyPlaceholderError,
    ZoteroCitekeyNotFoundError,
    _assert_bibliography_present,
    _assert_no_missing_citekeys,
    _build_pandoc_cmd,
    _docx_zotero_field_counts,
    _zotero_bibliography_docx_filter,
    _zotero_lua_filter,
)


# ---------- filter resolution ----------


def test_zotero_lua_filter_resolves_to_real_file() -> None:
    p = _zotero_lua_filter()
    assert p.is_file()
    assert p.name == "zotero.lua"
    assert p.stat().st_size > 10_000  # filtro tem ~54 KB


def test_zotero_bibliography_docx_filter_resolves_to_real_file() -> None:
    p = _zotero_bibliography_docx_filter()
    assert p.is_file()
    assert p.name == "zotero_bibliography_docx.lua"


# ---------- _build_pandoc_cmd: docx path ----------


def _cmd(to_format: str, *, style: str = "apa") -> list[str]:
    return _build_pandoc_cmd(
        pandoc_bin="pandoc",
        input_md=Path("in.md"),
        output=Path(f"out.{to_format}"),
        bib=Path("refs.bib"),
        csl=Path("apa.csl"),
        style=style,
        metadata_file=None,
        template=None,
        reference_doc=None,
        to_format=to_format,
    )


def test_docx_uses_zotero_lua_filter_not_citeproc() -> None:
    cmd = _cmd("docx")
    assert "--citeproc" not in cmd
    assert any(a.startswith("--lua-filter=") and a.endswith("zotero.lua") for a in cmd)
    assert "--to=docx" in cmd
    assert "--standalone" in cmd


def test_docx_also_chains_bibliography_filter_after_zotero_lua() -> None:
    cmd = _cmd("docx")
    filters = [a for a in cmd if a.startswith("--lua-filter=")]
    assert len(filters) == 2
    assert filters[0].endswith("zotero.lua")
    assert filters[1].endswith("zotero_bibliography_docx.lua")


def test_docx_propagates_style_via_metadata() -> None:
    cmd = _cmd("docx", style="vancouver")
    assert "--metadata=zotero_csl_style:vancouver" in cmd


def test_docx_omits_bibliography_and_csl_flags() -> None:
    # zotero.lua busca metadata direto do Zotero — passar --bibliography/--csl
    # é redundante e pode confundir o filtro.
    cmd = _cmd("docx")
    joined = " ".join(cmd)
    assert "--bibliography=" not in joined
    assert "--csl=" not in joined


# ---------- _build_pandoc_cmd: outros formatos preservam citeproc ----------


@pytest.mark.parametrize("fmt", ["html", "typst", "pdf"])
def test_non_docx_formats_keep_citeproc_pipeline(fmt: str) -> None:
    cmd = _cmd(fmt)
    assert "--citeproc" in cmd
    assert "--bibliography=refs.bib" in cmd
    assert "--csl=apa.csl" in cmd
    assert not any("zotero.lua" in a or "zotero_bibliography" in a for a in cmd)


def test_html_uses_html5_standalone_embedded() -> None:
    cmd = _cmd("html")
    assert "--to=html5" in cmd
    assert "--standalone" in cmd
    assert "--embed-resources" in cmd


@pytest.mark.parametrize("fmt", ["typst", "pdf"])
def test_typst_path_uses_typst_writer(fmt: str) -> None:
    cmd = _cmd(fmt)
    assert "--to=typst" in cmd


# ---------- _assert_no_missing_citekeys ----------


def test_assert_passes_on_clean_stdout() -> None:
    _assert_no_missing_citekeys("zotero-live-citations 199d652\nhttp://...\n")


def test_assert_raises_on_not_found_marker() -> None:
    with pytest.raises(ZoteroCitekeyNotFoundError) as exc:
        _assert_no_missing_citekeys("@foo: not found\n@bar: not found")
    msg = str(exc.value)
    assert "foo" in msg and "bar" in msg
    assert "grupo do Zotero" in msg  # sugestão acionável


def test_assert_raises_on_not_in_zotero_marker() -> None:
    """zotero.lua usa duas frases distintas — a regex deve casar ambas."""
    with pytest.raises(ZoteroCitekeyNotFoundError) as exc:
        _assert_no_missing_citekeys("@foo not in Zotero")
    assert "foo" in str(exc.value)


def test_assert_raises_on_duplicates_marker() -> None:
    with pytest.raises(ZoteroCitekeyNotFoundError) as exc:
        _assert_no_missing_citekeys("@foo: duplicates found")
    assert "foo" in str(exc.value)


def test_assert_pane_error_takes_precedence_with_specific_message() -> None:
    """Quando o pane está null, todas as keys retornam not-found em cascata —
    mas a causa raiz é o pane, e a mensagem deve apontar pra isso."""
    stdout = (
        "could not fetch Zotero items: TypeError: ...getActiveZoteroPane() is null\n"
        "@a not in Zotero\n@b not in Zotero"
    )
    with pytest.raises(ZoteroCitekeyNotFoundError) as exc:
        _assert_no_missing_citekeys(stdout)
    assert "JANELA PRINCIPAL" in str(exc.value)
    # Não deve listar as keys individuais nesse caso — a causa é outra.
    assert "biblioteca ativa" not in str(exc.value)


# ---------- _assert_bibliography_present (post-build) ----------


def _fake_docx(tmp_path: Path, document_xml: str) -> Path:
    """Cria um .docx mínimo com o ``word/document.xml`` indicado."""
    p = tmp_path / "out.docx"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", document_xml)
    p.write_bytes(buf.getvalue())
    return p


def test_field_counts_no_zotero_fields(tmp_path: Path) -> None:
    docx = _fake_docx(tmp_path, "<w:document><w:body/></w:document>")
    assert _docx_zotero_field_counts(docx) == (0, 0)


def test_field_counts_full_pipeline(tmp_path: Path) -> None:
    xml = (
        "<w:document>"
        "ADDIN ZOTERO_ITEM CSL_CITATION {a}"
        "ADDIN ZOTERO_ITEM CSL_CITATION {b}"
        "ADDIN ZOTERO_BIBL {} CSL_BIBLIOGRAPHY"
        "</w:document>"
    )
    docx = _fake_docx(tmp_path, xml)
    assert _docx_zotero_field_counts(docx) == (2, 1)


def test_assert_bibliography_passes_when_no_citations(tmp_path: Path) -> None:
    """Página sem citações nem placeholder — nada a verificar, segue o jogo."""
    docx = _fake_docx(tmp_path, "<w:document>texto sem citações</w:document>")
    _assert_bibliography_present(docx)


def test_assert_bibliography_passes_when_both_present(tmp_path: Path) -> None:
    xml = "ADDIN ZOTERO_ITEM CSL_CITATION ADDIN ZOTERO_BIBL CSL_BIBLIOGRAPHY"
    _assert_bibliography_present(_fake_docx(tmp_path, xml))


def test_assert_bibliography_raises_when_citations_without_bib(tmp_path: Path) -> None:
    """Reproduz o failure mode que motivou a validação: citações vivas mas
    a página esqueceu o ``::: {#refs} :::``."""
    xml = "ADDIN ZOTERO_ITEM CSL_CITATION foo ADDIN ZOTERO_ITEM CSL_CITATION bar"
    docx = _fake_docx(tmp_path, xml)
    with pytest.raises(MissingBibliographyPlaceholderError) as exc:
        _assert_bibliography_present(docx)
    msg = str(exc.value)
    assert "2 citação" in msg
    assert "{#refs}" in msg  # mensagem aponta o fix
    assert "Refresh" in msg  # contexto sobre o plugin Word
