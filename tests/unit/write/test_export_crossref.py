"""Figuras e tabelas numeradas no export (ADR-0035).

Testes do builder rodam sempre. Os de pipeline completo usam o pandoc real
(filtro Lua não tem como ser mockado de forma útil) e são pulados sem pandoc
no PATH — o CI (``ubuntu-latest``) não o instala.
"""

from __future__ import annotations

import base64
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from par.domains.write import export as export_mod
from par.domains.write.export import (
    PandocFailedError,
    _assert_no_citeproc_missing,
    _build_pandoc_cmd,
    _crossref_filter,
)

_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

requires_pandoc = pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc ausente")


def _cmd(
    to_format: str, tmp: Path, *, lang: str | None = None, csl: Path | None = None
) -> list[str]:
    return _build_pandoc_cmd(
        pandoc_bin="pandoc",
        input_md=tmp / "in.md",
        output=tmp / f"out.{to_format}",
        bib=tmp / "refs.bib",
        csl=csl or tmp / "style.csl",
        style="apa",
        metadata_file=None,
        template=None,
        reference_doc=None,
        to_format=to_format,
        resource_path=tmp,
        lang=lang,
    )


def test_crossref_filter_resolves_to_real_file() -> None:
    assert _crossref_filter().is_file()
    assert _crossref_filter().name == "crossref.lua"


@pytest.mark.parametrize("fmt", ["docx", "html", "typst", "pdf"])
def test_crossref_filter_runs_before_citeproc(fmt: str, tmp_path: Path) -> None:
    """Antes do citeproc, ``@fig:x`` nunca chega a ser tratado como citekey."""
    cmd = _cmd(fmt, tmp_path)
    crossref_idx = cmd.index(f"--lua-filter={_crossref_filter()}")
    assert crossref_idx < cmd.index("--citeproc")


def test_lang_vira_metadata_prumo_lang(tmp_path: Path) -> None:
    assert "--metadata=prumo_lang:pt-BR" in _cmd("docx", tmp_path, lang="pt-BR")
    assert not any("prumo_lang" in a for a in _cmd("docx", tmp_path))


def test_export_passa_writing_language_ao_pandoc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fiação: ``[writing].language`` do projeto chega ao comando do pandoc."""
    root = tmp_path / "pj_demo"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "pj_config.toml").write_text('[writing]\nlanguage = "pt-BR"\n')
    (root / "docs" / "references").mkdir(parents=True)
    (root / "docs" / "references" / "_references.bib").write_text("@article{a, title={X}}\n")
    page = root / "docs" / "page.md"
    page.write_text("Texto.\n")
    csl = tmp_path / "apa.csl"
    csl.write_text("<style/>")
    monkeypatch.setattr(export_mod, "_check_pandoc", lambda: "pandoc")
    monkeypatch.setattr(export_mod, "resolve_csl", lambda style: csl)
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        out = Path(next(a for a in cmd if a.startswith("--output=")).split("=", 1)[1])
        out.write_text("<html/>")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("par.domains.write.export.subprocess.run", fake_run)
    export_mod.export(page, to="html", project_root=root)
    assert "--metadata=prumo_lang:pt-BR" in calls[0]


# ---------- pipeline real ----------


def _run_docx(tmp: Path, body: str, *, lang: str = "en-US") -> tuple[str, str]:
    """Roda a cadeia docx real (crossref → citeproc → zotero_live) e devolve (xml, stderr)."""
    (tmp / "x.png").write_bytes(_PNG_1PX)
    (tmp / "refs.bib").write_text(
        "@article{silva2020, author={Silva, Ana}, title={T}, journal={J}, year={2020}}\n"
    )
    csl = tmp / "style.csl"
    csl.write_text(
        subprocess.run(
            ["pandoc", "--print-default-data-file", "default.csl"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    (tmp / "in.md").write_text(body)
    cmd = _cmd("docx", tmp, lang=lang, csl=csl)
    proc = export_mod._run_pandoc_checked(cmd)
    _assert_no_citeproc_missing(proc.stderr)
    with zipfile.ZipFile(tmp / "out.docx") as z:
        return z.read("word/document.xml").decode("utf-8"), proc.stderr


_DOC = (
    "Ver @tbl:base e @fig:fluxo [@silva2020].\n\n"
    "![Fluxo de participantes](x.png){#fig:fluxo}\n\n"
    "| A | B |\n|---|---|\n| 1 | 2 |\n\n: Características {#tbl:base}\n"
)


@requires_pandoc
def test_docx_numera_legendas_resolve_refs_e_preserva_citacao_viva(tmp_path: Path) -> None:
    xml, _stderr = _run_docx(tmp_path, _DOC)
    assert "SEQ Figure" in xml
    assert "SEQ Table" in xml
    assert "Table 1" in xml
    assert "Figure 1" in xml
    assert "@tbl:base" not in xml
    assert "ADDIN ZOTERO_ITEM CSL_CITATION" in xml


@requires_pandoc
def test_docx_rotulo_em_pt_br(tmp_path: Path) -> None:
    xml, _stderr = _run_docx(tmp_path, _DOC, lang="pt-BR")
    assert "Tabela 1" in xml
    assert "Figura 1" in xml


@requires_pandoc
def test_referencia_entre_colchetes_falha_com_correcao(tmp_path: Path) -> None:
    with pytest.raises(PandocFailedError, match="fora de colchetes"):
        _run_docx(tmp_path, "Ver [@fig:fluxo].\n\n![Fluxo](x.png){#fig:fluxo}\n")


@requires_pandoc
def test_referencia_sem_alvo_falha_com_correcao(tmp_path: Path) -> None:
    with pytest.raises(PandocFailedError, match=r"\{#fig:nada\}"):
        _run_docx(tmp_path, "Ver @fig:nada.\n")
