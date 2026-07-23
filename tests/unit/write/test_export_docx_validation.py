"""Validação estrutural do docx gerado (Fase 1 do zero-friction onboarding).

Fixtures construídas com zipfile em tmp_path — nenhum pandoc/Zotero real.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from prumo_assist.domains.write.export import (
    CorruptDocxError,
    MissingZoteroPrefsError,
    _assert_zotero_prefs_present,
    _run_and_validate_docx,
    _validate_docx_structure,
)

_CONTENT_TYPES_OK = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="xml" ContentType="application/xml"/>'
    "</Types>"
)


def _write_minimal_docx(
    path: Path,
    *,
    items: int = 0,
    prefs: bool = True,
    include_types: bool = True,
    include_document: bool = True,
    types_xml: str | None = None,
) -> Path:
    """Zip com o esqueleto mínimo que a validação inspeciona."""
    body = "<w:document>" + ("ZOTERO_ITEM CSL_CITATION " * items) + "</w:document>"
    with zipfile.ZipFile(path, "w") as z:
        if include_types:
            z.writestr("[Content_Types].xml", types_xml or _CONTENT_TYPES_OK)
        if include_document:
            z.writestr("word/document.xml", body)
        if prefs:
            z.writestr(
                "docProps/custom.xml",
                '<Properties><property name="ZOTERO_PREF_1"/></Properties>',
            )
    return path


def test_valid_docx_has_no_problems(tmp_path: Path) -> None:
    docx = _write_minimal_docx(tmp_path / "ok.docx")
    assert _validate_docx_structure(docx) == []


def test_missing_file_is_reported(tmp_path: Path) -> None:
    problems = _validate_docx_structure(tmp_path / "nao_existe.docx")
    assert problems and "não foi criado" in problems[0]


def test_non_zip_file_is_reported(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus.docx"
    bogus.write_text("isto não é um zip")
    problems = _validate_docx_structure(bogus)
    assert problems and "zip" in problems[0]


def test_missing_document_xml_is_reported(tmp_path: Path) -> None:
    docx = _write_minimal_docx(tmp_path / "semdoc.docx", include_document=False)
    assert any("word/document.xml" in p for p in _validate_docx_structure(docx))


def test_missing_content_types_is_reported(tmp_path: Path) -> None:
    docx = _write_minimal_docx(tmp_path / "semtypes.docx", include_types=False)
    assert any("[Content_Types].xml" in p for p in _validate_docx_structure(docx))


def test_malformed_content_types_is_reported(tmp_path: Path) -> None:
    docx = _write_minimal_docx(tmp_path / "mal.docx", types_xml="<Types><Default</Types>")
    problems = _validate_docx_structure(docx)
    assert any("[Content_Types].xml" in p and "inválido" in p for p in problems)


def _fake_run_writing(out: Path, payloads: list[bytes], calls: list[list[str]]) -> object:
    """Fabrica um substituto de subprocess.run que escreve payloads[i] em out."""

    def fake_run(cmd: list[str], check: bool, text: bool) -> None:
        calls.append(list(cmd))
        out.parent.mkdir(parents=True, exist_ok=True)
        idx = min(len(calls) - 1, len(payloads) - 1)
        out.write_bytes(payloads[idx])

    return fake_run


def _good_docx_bytes(tmp_path: Path) -> bytes:
    good = _write_minimal_docx(tmp_path / "_good_fixture.docx")
    return good.read_bytes()


def test_run_and_validate_passes_first_try(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "saida.docx"
    calls: list[list[str]] = []
    fake = _fake_run_writing(out, [_good_docx_bytes(tmp_path)], calls)
    monkeypatch.setattr("prumo_assist.domains.write.export.subprocess.run", fake)
    _run_and_validate_docx(["pandoc", f"--output={out}"], out)
    assert len(calls) == 1


def test_run_and_validate_retries_once_on_corrupt_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "saida.docx"
    calls: list[list[str]] = []
    fake = _fake_run_writing(out, [b"lixo nao-zip", _good_docx_bytes(tmp_path)], calls)
    monkeypatch.setattr("prumo_assist.domains.write.export.subprocess.run", fake)
    _run_and_validate_docx(["pandoc", f"--output={out}"], out)
    assert len(calls) == 2


def test_run_and_validate_raises_after_second_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "saida.docx"
    calls: list[list[str]] = []
    fake = _fake_run_writing(out, [b"lixo 1", b"lixo 2"], calls)
    monkeypatch.setattr("prumo_assist.domains.write.export.subprocess.run", fake)
    with pytest.raises(CorruptDocxError) as exc:
        _run_and_validate_docx(["pandoc", f"--output={out}"], out)
    assert len(calls) == 2
    assert "re-executar" in str(exc.value)
    assert str(out) in str(exc.value)


def test_prefs_present_with_citations_ok(tmp_path: Path) -> None:
    docx = _write_minimal_docx(tmp_path / "com_prefs.docx", items=2, prefs=True)
    _assert_zotero_prefs_present(docx)  # não levanta


def test_prefs_missing_custom_xml_raises(tmp_path: Path) -> None:
    docx = _write_minimal_docx(tmp_path / "sem_custom.docx", items=2, prefs=False)
    with pytest.raises(MissingZoteroPrefsError) as exc:
        _assert_zotero_prefs_present(docx)
    assert "ZOTERO_PREF_1" in str(exc.value)
    assert "Document Preferences" in str(exc.value)


def test_prefs_custom_xml_without_pref_raises(tmp_path: Path) -> None:
    docx = tmp_path / "custom_vazio.docx"
    with zipfile.ZipFile(docx, "w") as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES_OK)
        z.writestr("word/document.xml", "<w:document>ZOTERO_ITEM CSL_CITATION</w:document>")
        z.writestr("docProps/custom.xml", "<Properties/>")
    with pytest.raises(MissingZoteroPrefsError):
        _assert_zotero_prefs_present(docx)


def test_prefs_not_required_without_citations(tmp_path: Path) -> None:
    docx = _write_minimal_docx(tmp_path / "sem_citacao.docx", items=0, prefs=False)
    _assert_zotero_prefs_present(docx)  # não levanta
