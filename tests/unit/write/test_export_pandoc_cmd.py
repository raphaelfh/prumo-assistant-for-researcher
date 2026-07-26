"""Tests para o pipeline pandoc de ``prumo_assist.domains.write.export``.

Cobre:

- Roteamento por formato em ``_build_pandoc_cmd`` (docx → filtros Lua do
  Zotero; html/typst → ``--citeproc`` com CSL local).
- Resolução dos filtros vendored.
- Guarda de citekey ausente (``_assert_no_citeproc_missing``) e checagens
  pós-build do docx.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from prumo_assist.core.citations import scan_citekeys
from prumo_assist.domains.write.export import (
    MissingBibliographyPlaceholderError,
    ZoteroCitekeyNotFoundError,
    _assert_bibliography_present,
    _assert_no_citeproc_missing,
    _build_pandoc_cmd,
    _docx_texts,
    _docx_zotero_field_counts,
    _zotero_bibliography_docx_filter,
    _zotero_live_docx_filter,
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


def test_zotero_live_docx_filter_resolves_to_real_file() -> None:
    p = _zotero_live_docx_filter()
    assert p.is_file()
    assert p.name == "zotero_live_docx.lua"


# ---------- _build_pandoc_cmd: docx path ----------


def _cmd(
    to_format: str,
    *,
    style: str = "apa",
    zotero_lookup_file: Path | None = None,
) -> list[str]:
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
        zotero_lookup_file=zotero_lookup_file,
    )


def test_docx_uses_citeproc_plus_live_filter() -> None:
    """Pipeline novo: citeproc pré-renderiza o texto formatado, depois o
    zotero_live_docx.lua embrulha em campos do Word reconhecidos pelo
    plugin Zotero (com display já formatado, sem placeholders)."""
    cmd = _cmd("docx")
    assert "--citeproc" in cmd
    assert "--bibliography=refs.bib" in cmd
    assert "--csl=apa.csl" in cmd
    assert any(a.startswith("--lua-filter=") and a.endswith("zotero_live_docx.lua") for a in cmd)
    assert "--to=docx" in cmd
    assert "--standalone" in cmd


def test_docx_does_not_chain_legacy_bbt_filters() -> None:
    """O pipeline novo substitui completamente os filtros BBT — eles
    seguem disponíveis no pacote como utilitários mas não são usados."""
    cmd = _cmd("docx")
    joined = " ".join(cmd)
    assert "/zotero.lua" not in joined
    assert "/zotero_bibliography_docx.lua" not in joined


def test_docx_propagates_style_via_metadata() -> None:
    cmd = _cmd("docx", style="vancouver")
    assert "--metadata=zotero_csl_style:vancouver" in cmd


def test_docx_propagates_zotero_lookup_file() -> None:
    lookup = Path("/tmp/lookup.json")
    cmd = _cmd("docx", zotero_lookup_file=lookup)
    assert f"--metadata=zotero_lookup_file:{lookup}" in cmd


def test_docx_omits_lookup_metadata_when_no_uris() -> None:
    cmd = _cmd("docx", zotero_lookup_file=None)
    assert not any("zotero_lookup_file" in a for a in cmd)


# ---------- _build_pandoc_cmd: outros formatos preservam citeproc ----------


@pytest.mark.parametrize("fmt", ["html", "typst", "pdf"])
def test_non_docx_formats_keep_citeproc_pipeline(fmt: str) -> None:
    cmd = _cmd(fmt)
    assert "--citeproc" in cmd
    assert "--bibliography=refs.bib" in cmd
    assert "--csl=apa.csl" in cmd
    assert not any("zotero" in a.lower() for a in cmd)


def test_html_uses_html5_standalone_embedded() -> None:
    cmd = _cmd("html")
    assert "--to=html5" in cmd
    assert "--standalone" in cmd
    assert "--embed-resources" in cmd


@pytest.mark.parametrize("fmt", ["typst", "pdf"])
def test_typst_path_uses_typst_writer(fmt: str) -> None:
    cmd = _cmd(fmt)
    assert "--to=typst" in cmd


# ---------- _assert_no_citeproc_missing ----------


def test_citeproc_missing_clean_stderr_passes() -> None:
    _assert_no_citeproc_missing("[INFO] Running filter citeproc\n")


def test_citeproc_missing_raises_with_keys_and_fix() -> None:
    stderr = (
        "[WARNING] Citeproc: citation smith2024 not found\n"
        "[WARNING] Citeproc: citation ghost2020 not found\n"
    )
    with pytest.raises(ZoteroCitekeyNotFoundError) as exc:
        _assert_no_citeproc_missing(stderr)
    msg = str(exc.value)
    assert "smith2024" in msg and "ghost2020" in msg
    # Hint de correção pós-F4: coleção conectada no Zotero (BBT regrava o
    # .bib) — nunca mais `make sync-paper` (alvo exterminado).
    assert "prumo paper connect" in msg
    assert "make sync-paper" not in msg


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
    _assert_bibliography_present(_docx_texts(docx)[0])


def test_assert_bibliography_passes_when_both_present(tmp_path: Path) -> None:
    xml = "ADDIN ZOTERO_ITEM CSL_CITATION ADDIN ZOTERO_BIBL CSL_BIBLIOGRAPHY"
    _assert_bibliography_present(_docx_texts(_fake_docx(tmp_path, xml))[0])


def test_assert_bibliography_raises_when_citations_without_bib(tmp_path: Path) -> None:
    """Reproduz o failure mode que motivou a validação: citações vivas mas
    a página esqueceu o ``::: {#refs} :::``."""
    xml = "ADDIN ZOTERO_ITEM CSL_CITATION foo ADDIN ZOTERO_ITEM CSL_CITATION bar"
    docx = _fake_docx(tmp_path, xml)
    with pytest.raises(MissingBibliographyPlaceholderError) as exc:
        _assert_bibliography_present(_docx_texts(docx)[0])
    msg = str(exc.value)
    assert "2 citação" in msg
    assert "{#refs}" in msg  # mensagem aponta o fix
    assert "Refresh" in msg  # contexto sobre o plugin Word


# ---------- scan_citekeys ----------


def test_scan_citekeys_finds_bracketed_and_bare() -> None:
    md = "Como mostrado em [@foo2023] e também @bar2024."
    assert scan_citekeys(md) == ["bar2024", "foo2023"]


def test_scan_citekeys_supports_kebab_case_and_digits_first() -> None:
    """BBT emite citekeys como `razavi-shearer2023global` (kebab) e
    `2024guidelines` (começa com dígito) — Pandoc aceita ambos."""
    md = "[@razavi-shearer2023global] e [@2024guidelines] no texto."
    assert scan_citekeys(md) == ["2024guidelines", "razavi-shearer2023global"]


def test_scan_citekeys_skips_emails() -> None:
    md = "Contato: foo@bar.com — referência [@real2024key]."
    assert scan_citekeys(md) == ["real2024key"]


def test_scan_citekeys_skips_code_blocks() -> None:
    """Tokens dentro de fenced code blocks (ex: docstrings com `@param`)
    não são citações — não devem entrar no pre-fetch."""
    md = (
        "Citação real: [@bar2024].\n\n"
        "```python\n"
        "@decorator\n"
        "def foo(): pass\n"
        "```\n\n"
        "Outra citação: [@baz2025]."
    )
    assert scan_citekeys(md) == ["bar2024", "baz2025"]


def test_scan_citekeys_dedupes_repeated_keys() -> None:
    md = "[@foo2020] aparece e depois [@foo2020] de novo."
    assert scan_citekeys(md) == ["foo2020"]


def test_scan_citekeys_empty_doc() -> None:
    assert scan_citekeys("texto sem citações") == []
