"""Validação estrutural do docx gerado (Fase 1 do zero-friction onboarding).

Fixtures construídas com zipfile em tmp_path — nenhum pandoc/Zotero real.
``subprocess.run`` é sempre mockado (seam ``_patch_export_seams`` +
``_fake_run_writing_output_flag``/``fake_run`` locais), inclusive na seção
"Task 8": o CI (``ubuntu-latest``) não tem pandoc instalado, então nenhum
teste deste arquivo pode depender do binário real (regra de
``.claude/rules/code.md`` — dependências externas são sempre mockadas nos
seams).
"""

from __future__ import annotations

import hashlib
import html
import subprocess
import zipfile
from pathlib import Path

import pytest

import prumo_assist.domains.write.export as export_mod
from prumo_assist.core.obsidian import SpanFragment, normalize_markdown_with_map, split_frontmatter
from prumo_assist.core.pj_layout import PjRootNotFoundError
from prumo_assist.domains.write.errors import WriteError
from prumo_assist.domains.write.export import (
    CorruptDocxError,
    MissingFieldLockError,
    MissingZoteroPrefsError,
    _assert_fields_locked,
    _assert_zotero_prefs_present,
    _bib_entries_by_key,
    _docx_texts,
    _fingerprint_for,
    _run_and_validate_docx,
    _validate_docx_structure,
)
from prumo_assist.domains.write.schemas.v1 import CiteMapFile, SpanMapFile

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

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        out.parent.mkdir(parents=True, exist_ok=True)
        idx = min(len(calls) - 1, len(payloads) - 1)
        out.write_bytes(payloads[idx])
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

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
    _assert_zotero_prefs_present(*_docx_texts(docx))  # não levanta


def test_prefs_missing_custom_xml_raises(tmp_path: Path) -> None:
    docx = _write_minimal_docx(tmp_path / "sem_custom.docx", items=2, prefs=False)
    with pytest.raises(MissingZoteroPrefsError) as exc:
        _assert_zotero_prefs_present(*_docx_texts(docx))
    assert "ZOTERO_PREF_1" in str(exc.value)
    assert "Document Preferences" in str(exc.value)


def test_prefs_custom_xml_without_pref_raises(tmp_path: Path) -> None:
    docx = tmp_path / "custom_vazio.docx"
    with zipfile.ZipFile(docx, "w") as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES_OK)
        z.writestr("word/document.xml", "<w:document>ZOTERO_ITEM CSL_CITATION</w:document>")
        z.writestr("docProps/custom.xml", "<Properties/>")
    with pytest.raises(MissingZoteroPrefsError):
        _assert_zotero_prefs_present(*_docx_texts(docx))


def test_prefs_not_required_without_citations(tmp_path: Path) -> None:
    docx = _write_minimal_docx(tmp_path / "sem_citacao.docx", items=0, prefs=False)
    _assert_zotero_prefs_present(*_docx_texts(docx))  # não levanta


def _fake_project(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "pj_demo"
    (root / "docs" / "references").mkdir(parents=True)
    (root / "docs" / "references" / "_references.bib").write_text(
        "@article{smith2020, title={X}}\n"
    )
    page = root / "docs" / "page.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("Texto sem citação.\n")
    return root, page


def _patch_export_seams(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    csl = tmp_path / "apa.csl"
    csl.write_text("<style/>")
    monkeypatch.setattr(export_mod, "_check_pandoc", lambda: "pandoc")
    monkeypatch.setattr(export_mod, "_check_bbt_running", lambda timeout=2.0: None)
    monkeypatch.setattr(export_mod, "resolve_csl", lambda style: csl)
    monkeypatch.setattr(export_mod, "fetch_bbt_zotero_metadata", lambda keys, lib: {})


def _fake_run_writing_output_flag(payloads: list[bytes], calls: list[list[str]]) -> object:
    """Substituto de subprocess.run que resolve o alvo pelo --output= do cmd.

    Comandos sem ``--output=`` (ex. ``git rev-parse --short HEAD`` chamado
    por ``_export_git_sha`` dentro de ``_emit_review_sidecars``) são
    simulados como sucesso sem tocar em ``calls``/``payloads`` — só a
    invocação do pandoc participa do protocolo retry/hard-fail.
    """

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        output_flags = [a for a in cmd if a.startswith("--output=")]
        if not output_flags:
            return subprocess.CompletedProcess(cmd, 0, stdout="deadbee\n", stderr="")
        calls.append(list(cmd))
        target = Path(output_flags[0].split("=", 1)[1])
        target.parent.mkdir(parents=True, exist_ok=True)
        idx = min(len(calls) - 1, len(payloads) - 1)
        target.write_bytes(payloads[idx])
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    return fake_run


def test_export_docx_fails_loud_after_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, page = _fake_project(tmp_path)
    _patch_export_seams(monkeypatch, tmp_path)
    calls: list[list[str]] = []
    fake = _fake_run_writing_output_flag([b"lixo 1", b"lixo 2"], calls)
    monkeypatch.setattr("prumo_assist.domains.write.export.subprocess.run", fake)
    with pytest.raises(CorruptDocxError):
        export_mod.export(page=page, to="docx", project_root=root)
    assert len(calls) == 2


def test_export_docx_happy_path_single_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, page = _fake_project(tmp_path)
    _patch_export_seams(monkeypatch, tmp_path)
    calls: list[list[str]] = []
    fake = _fake_run_writing_output_flag([_good_docx_bytes(tmp_path)], calls)
    monkeypatch.setattr("prumo_assist.domains.write.export.subprocess.run", fake)
    result = export_mod.export(page=page, to="docx", project_root=root)
    assert result.suffix == ".docx"
    assert result.is_file()
    assert len(calls) == 1


def test_export_html_does_not_validate_docx(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, page = _fake_project(tmp_path)
    _patch_export_seams(monkeypatch, tmp_path)
    calls: list[list[str]] = []
    fake = _fake_run_writing_output_flag([b"<html>ok</html>"], calls)
    monkeypatch.setattr("prumo_assist.domains.write.export.subprocess.run", fake)
    result = export_mod.export(page=page, to="html", project_root=root)
    assert result.suffix == ".html"
    assert len(calls) == 1  # sem retry, sem validação de zip


def test_compose_docx_goes_through_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _page = _fake_project(tmp_path)
    index = root / "docs" / "index.md"
    index.write_text("---\npages: [docs/page.md]\n---\n")
    _patch_export_seams(monkeypatch, tmp_path)
    calls: list[list[str]] = []
    fake = _fake_run_writing_output_flag([b"lixo 1", b"lixo 2"], calls)
    monkeypatch.setattr("prumo_assist.domains.write.export.subprocess.run", fake)
    with pytest.raises(CorruptDocxError):
        export_mod.compose(index=index, to="docx", project_root=root)
    assert len(calls) == 2


def test_fingerprint_prefers_doi() -> None:
    entry = "@article{k, title={T}, doi={10.1000/xyz}}"
    assert _fingerprint_for(entry, {"itemID": 1, "uri": "u"}) == "doi:10.1000/xyz"


def test_fingerprint_falls_back_to_lookup_hash() -> None:
    fp = _fingerprint_for("@article{k, title={T}}", {"itemID": 7, "uri": "http://z/7"})
    assert fp.startswith("sha256:") and len(fp) == len("sha256:") + 64


def test_fingerprint_offline_uses_bib_entry() -> None:
    fp = _fingerprint_for("@article{k, title={T}}", None)
    assert fp.startswith("bib:")


def test_bib_entries_by_key_present_and_absent() -> None:
    bib_text = "@article{k, title={T}, doi={10.1000/xyz}}\n\n@book{other, title={O}}\n"
    entries = _bib_entries_by_key(bib_text)
    assert "doi={10.1000/xyz}" in entries["k"]
    assert set(entries) == {"k", "other"}
    assert entries.get("nao_existe") is None


# --- Task 7: sidecars citemap/span-map (reviews/<slug>/, I2/I8) -----------------


def _instr_text_run(payload: str) -> str:
    """``<w:r>`` cru do campo Zotero para um payload CSL_CITATION (sem lock)."""
    return (
        '<w:r><w:instrText xml:space="preserve"> ADDIN ZOTERO_ITEM CSL_CITATION '
        + html.escape(payload)
        + "   </w:instrText></w:r>"
    )


def _locked_zotero_field_xml(payload: str) -> str:
    """Campo Zotero embrulhado em content control travado (I4, Task 8).

    Espelha exatamente o que ``wrap_cite_in_field`` produz desde a Task 8:
    ``<w:sdt>`` com ``sdtContentLocked`` envolvendo os runs do campo,
    inalterados.
    """
    return (
        '<w:sdt><w:sdtPr><w:alias w:val="prumo-citation"/>'
        '<w:lock w:val="sdtContentLocked"/></w:sdtPr><w:sdtContent>'
        + _instr_text_run(payload)
        + "</w:sdtContent></w:sdt>"
    )


def _write_minimal_docx_with_payloads(
    path: Path, payloads: list[str], *, locked: bool = True
) -> Path:
    """Zip OOXML mínimo com um campo ``ADDIN ZOTERO_ITEM CSL_CITATION`` por payload.

    Espelha o formato real produzido por ``zotero_live_docx.lua``
    (``wrap_cite_in_field``): JSON escapado com ``html.escape`` dentro de um
    ``<w:instrText>`` — é a fixture de referência do leitor OOXML (MÉTODO I2).

    ``locked=True`` (default, espelha o comportamento pós-Task-8) embrulha
    cada campo num content control ``w:sdt``/``sdtContentLocked`` (I4);
    ``locked=False`` simula uma regressão do filtro (campo sem lock), usado
    pelos testes de ``_assert_fields_locked``.
    """
    field_fn = _locked_zotero_field_xml if locked else _instr_text_run
    fields = "".join(field_fn(payload) for payload in payloads)
    body = "<w:document><w:body>" + fields + "</w:body></w:document>"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES_OK)
        z.writestr("word/document.xml", body)
    return path


def _bib(tmp_path: Path) -> Path:
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{smith2020, title={T}, doi={10.1/x}}\n")
    return bib


def test_read_docx_citations_orders_and_decodes(tmp_path: Path) -> None:
    payload = (
        '{"citationID":"00000001","prumoOcc":"00000001",'
        '"citationItems":[{"id":"smith2020","prumoFingerprint":"doi:10.1/x"}],'
        '"properties":{"formattedCitation":"(Smith, 2020)"}}'
    )
    docx = _write_minimal_docx_with_payloads(tmp_path / "c.docx", [payload])
    occs = export_mod._read_docx_citations(docx)
    assert len(occs) == 1
    assert occs[0]["citekeys"] == ["smith2020"]
    assert occs[0]["occ_id"] == "00000001"


def test_read_docx_citations_preserves_document_order_and_fingerprints(
    tmp_path: Path,
) -> None:
    payload_a = (
        '{"citationID":"00000001","prumoOcc":"00000001",'
        '"citationItems":[{"id":"aaa2020","prumoFingerprint":"doi:10.1/a"}],'
        '"properties":{"formattedCitation":"(Aaa, 2020)"}}'
    )
    payload_b = (
        '{"citationID":"00000002","prumoOcc":"00000002",'
        '"citationItems":['
        '{"id":"bbb2021","prumoFingerprint":"doi:10.1/b"},'
        '{"id":"ccc2022","prumoFingerprint":"doi:10.1/c"}'
        '],"properties":{"formattedCitation":"(Bbb, 2021; Ccc, 2022)"}}'
    )
    docx = _write_minimal_docx_with_payloads(tmp_path / "ord.docx", [payload_a, payload_b])
    occs = export_mod._read_docx_citations(docx)
    assert [o["occ_id"] for o in occs] == ["00000001", "00000002"]
    assert occs[1]["citekeys"] == ["bbb2021", "ccc2022"]
    assert occs[1]["fingerprints"] == {"bbb2021": "doi:10.1/b", "ccc2022": "doi:10.1/c"}
    assert occs[0]["formatted"] == "(Aaa, 2020)"


def test_read_docx_citations_invalid_json_raises_with_field_index(tmp_path: Path) -> None:
    docx = _write_minimal_docx_with_payloads(tmp_path / "bad.docx", ["{isto nao e json"])
    with pytest.raises(export_mod.CiteMapMismatchError) as exc:
        export_mod._read_docx_citations(docx)
    assert "#1" in str(exc.value)


def test_norm_citation_spans_one_per_bracket_group() -> None:
    assert len(export_mod._norm_citation_spans("x [@a] y [@b; @c] z")) == 2


def test_norm_citation_spans_ignores_brackets_without_citekey() -> None:
    assert export_mod._norm_citation_spans("sem citação [nota]") == []


def test_emit_sidecars_mismatch_hard_fails(tmp_path: Path) -> None:
    docx = _write_minimal_docx_with_payloads(tmp_path / "c.docx", [])  # 0 campos
    with pytest.raises(export_mod.CiteMapMismatchError) as exc:
        export_mod._emit_review_sidecars(
            page=tmp_path / "p.md",
            project_root=tmp_path,
            norm_text="texto [@smith2020] aqui",  # 1 citação no norm
            span_frags=[],
            docx_path=docx,
            bib=_bib(tmp_path),
        )
    assert "1" in str(exc.value) and "0" in str(exc.value)
    assert "prumo write export --to docx" in str(exc.value)


def test_emit_sidecars_happy_path_writes_valid_sidecars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Seam própria (não subprocess.run): _export_git_sha roda `git` de verdade
    # se não for mockada — mantém o teste hermético e independente do ambiente.
    monkeypatch.setattr(export_mod, "_export_git_sha", lambda project_root: "deadbee")
    payload = (
        '{"citationID":"00000001","prumoOcc":"00000001",'
        '"citationItems":[{"id":"smith2020","prumoFingerprint":"doi:10.1/x"}],'
        '"properties":{"formattedCitation":"(Smith, 2020)"}}'
    )
    docx = _write_minimal_docx_with_payloads(tmp_path / "c.docx", [payload])
    bib = _bib(tmp_path)
    page = tmp_path / "docs" / "achado.md"
    page.parent.mkdir(parents=True)
    source_text = "Cita [@smith2020] aqui.\n"
    norm_text = "Cita [@smith2020] aqui.\n"
    frag = SpanFragment(0, len(source_text), 0, len(norm_text), "identity")

    out_dir = export_mod._emit_review_sidecars(
        page=page,
        project_root=tmp_path,
        source_text=source_text,
        norm_text=norm_text,
        span_frags=[frag],
        docx_path=docx,
        bib=bib,
    )

    assert out_dir == tmp_path / "reviews" / "achado"
    citemap = CiteMapFile.model_validate_json((out_dir / "citemap.json").read_text())
    span_map = SpanMapFile.model_validate_json((out_dir / "span-map.json").read_text())

    assert citemap.export_git_sha == "deadbee"
    assert citemap.docx_sha256 == hashlib.sha256(docx.read_bytes()).hexdigest()
    assert citemap.bib_sha256 == hashlib.sha256(bib.read_bytes()).hexdigest()
    assert len(citemap.occurrences) == 1
    assert citemap.occurrences[0].citekeys == ["smith2020"]
    assert citemap.occurrences[0].occ_id == "00000001"
    assert len(span_map.fragments) == 1
    assert span_map.source_sha256 == hashlib.sha256(source_text.encode("utf-8")).hexdigest()


def test_emit_sidecars_ignores_citation_like_spans_inside_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Achado do review final: `[@notacite]` num fence e `` `[@outro]` `` inline
    não podem contar como spans de citação — pandoc renderiza código
    verbatim (sem campo OOXML), então ``_norm_citation_spans`` contaria 3
    grupos ``[@...]`` no norm_text contra só 1 campo ZOTERO_ITEM no docx,
    disparando um ``CiteMapMismatchError`` espúrio numa página válida.

    Usa ``normalize_markdown_with_map`` de verdade (em vez de fragments
    montados à mão) para exercitar o span-map tal como o pipeline real o
    produz — os fragments ``kind="code"`` do fence/inline vêm daí.
    """
    monkeypatch.setattr(export_mod, "_export_git_sha", lambda project_root: "deadbee")
    source_text = "Cita [@smith2020].\n\n```\nexemplo: [@notacite]\n```\n\nE `[@outro]` inline.\n"
    norm_text, frags = normalize_markdown_with_map(source_text)

    payload = (
        '{"citationID":"00000001","prumoOcc":"00000001",'
        '"citationItems":[{"id":"smith2020","prumoFingerprint":"doi:10.1/x"}],'
        '"properties":{"formattedCitation":"(Smith, 2020)"}}'
    )
    docx = _write_minimal_docx_with_payloads(tmp_path / "c.docx", [payload])
    bib = _bib(tmp_path)
    page = tmp_path / "docs" / "achado_code.md"
    page.parent.mkdir(parents=True)

    out_dir = export_mod._emit_review_sidecars(
        page=page,
        project_root=tmp_path,
        source_text=source_text,
        norm_text=norm_text,
        span_frags=frags,
        docx_path=docx,
        bib=bib,
    )

    citemap = CiteMapFile.model_validate_json((out_dir / "citemap.json").read_text())
    assert len(citemap.occurrences) == 1
    assert citemap.occurrences[0].citekeys == ["smith2020"]
    assert citemap.occurrences[0].occ_id == "00000001"


def _docx_bytes_for_export_wiring(tmp_path: Path, payloads: list[str]) -> bytes:
    """Fixture completa (payloads + placeholder de bibliografia + prefs).

    Passa pelas 4 validações pós-build de ``export()`` docx (estrutura,
    bibliografia, prefs, locks — Task 8/I4) antes de chegar em
    ``_emit_review_sidecars`` — ``payloads=[]`` simula um docx sem campos
    vivos (caso de mismatch). Cada payload vem embrulhado em content control
    travado (``_locked_zotero_field_xml``), espelhando ``wrap_cite_in_field``
    pós-Task-8.
    """
    path = tmp_path / "_wiring_fixture.docx"
    fields = "".join(_locked_zotero_field_xml(payload) for payload in payloads)
    body = (
        "<w:document><w:body>"
        + fields
        + "<w:p>ZOTERO_BIBL CSL_BIBLIOGRAPHY</w:p>"
        + "</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES_OK)
        z.writestr("word/document.xml", body)
        z.writestr(
            "docProps/custom.xml",
            '<Properties><property name="ZOTERO_PREF_1"/></Properties>',
        )
    return path.read_bytes()


def test_export_docx_emits_review_sidecars(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, page = _fake_project(tmp_path)
    page.write_text("Cita [@smith2020] aqui.\n")
    _patch_export_seams(monkeypatch, tmp_path)
    payload = (
        '{"citationID":"00000001","prumoOcc":"00000001",'
        '"citationItems":[{"id":"smith2020","prumoFingerprint":"doi:10.1/x"}],'
        '"properties":{"formattedCitation":"(Smith, 2020)"}}'
    )
    calls: list[list[str]] = []
    fake = _fake_run_writing_output_flag(
        [_docx_bytes_for_export_wiring(tmp_path, [payload])], calls
    )
    monkeypatch.setattr("prumo_assist.domains.write.export.subprocess.run", fake)

    result = export_mod.export(page=page, to="docx", project_root=root)

    out_dir = root / "reviews" / export_mod.slugify(page, root)
    assert (out_dir / "citemap.json").is_file()
    assert (out_dir / "span-map.json").is_file()
    citemap = CiteMapFile.model_validate_json((out_dir / "citemap.json").read_text())
    assert citemap.docx_sha256 == hashlib.sha256(result.read_bytes()).hexdigest()
    assert citemap.occurrences[0].citekeys == ["smith2020"]

    # Verify source_sha256 in span-map matches the page body (without frontmatter)
    span_map = SpanMapFile.model_validate_json((out_dir / "span-map.json").read_text())
    page_text = page.read_text()
    _, body = split_frontmatter(page_text)
    assert span_map.source_sha256 == hashlib.sha256(body.encode("utf-8")).hexdigest()


def test_export_docx_wiring_mismatch_hard_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, page = _fake_project(tmp_path)
    page.write_text("Cita [@smith2020] aqui.\n")
    _patch_export_seams(monkeypatch, tmp_path)
    calls: list[list[str]] = []
    fake = _fake_run_writing_output_flag(
        [_docx_bytes_for_export_wiring(tmp_path, [])],
        calls,  # 0 campos no docx
    )
    monkeypatch.setattr("prumo_assist.domains.write.export.subprocess.run", fake)

    with pytest.raises(export_mod.CiteMapMismatchError):
        export_mod.export(page=page, to="docx", project_root=root)


# --- Task 8: campos travados (w:sdt/sdtContentLocked, I4) ------------------


def test_fields_locked_with_two_payloads_ok(tmp_path: Path) -> None:
    payload = '{"citationID":"00000001","citationItems":[]}'
    docx = _write_minimal_docx_with_payloads(
        tmp_path / "locked.docx",
        [payload, payload],  # locked=True (default)
    )
    _assert_fields_locked(_docx_texts(docx)[0])  # não levanta


def test_fields_locked_missing_lock_raises(tmp_path: Path) -> None:
    payload = '{"citationID":"00000001","citationItems":[]}'
    docx = _write_minimal_docx_with_payloads(
        tmp_path / "unlocked.docx", [payload, payload], locked=False
    )
    with pytest.raises(MissingFieldLockError) as exc:
        _assert_fields_locked(_docx_texts(docx)[0])
    assert "2" in str(exc.value)  # 2 campos vivos
    assert "0" in str(exc.value)  # 0 locks encontrados
    assert "zotero_live_docx.lua" in str(exc.value)
    assert "prumo write export --to docx" in str(exc.value)


def test_fields_locked_not_required_without_citations(tmp_path: Path) -> None:
    docx = _write_minimal_docx_with_payloads(tmp_path / "sem_campo.docx", [], locked=False)
    _assert_fields_locked(_docx_texts(docx)[0])  # não levanta (0 citações, lock irrelevante)


# --- Task 8: raiz via pj_layout, --resource-path (figuras), guarda de
# sobrescrita ------------------------------------------------------------


def test_detect_project_root_delegates_to_pj_layout(tmp_path: Path) -> None:
    root = tmp_path / "pj_demo"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "pj_config.toml").write_text("")
    page = root / "docs" / "studies" / "estudo1" / "writing" / "pagina.md"
    page.parent.mkdir(parents=True)
    page.write_text("Texto.\n")

    assert export_mod.detect_project_root(page).resolve() == root.resolve()


def test_detect_project_root_raises_pj_root_not_found(tmp_path: Path) -> None:
    page = tmp_path / "solto.md"
    page.write_text("Texto.\n")

    with pytest.raises(PjRootNotFoundError):
        export_mod.detect_project_root(page)


def test_assert_no_missing_resource_raises_with_target() -> None:
    stderr = "[WARNING] Could not fetch resource figures/ausente.png\n"
    with pytest.raises(export_mod.MissingResourceError) as exc:
        export_mod._assert_no_missing_resource(stderr)
    assert "figures/ausente.png" in str(exc.value)


def test_assert_no_missing_resource_silent_when_absent() -> None:
    export_mod._assert_no_missing_resource("[WARNING] Duplicate link reference `foo`.\n")


def test_build_pandoc_cmd_includes_resource_path(tmp_path: Path) -> None:
    page_dir = tmp_path / "docs"
    cmd = export_mod._build_pandoc_cmd(
        pandoc_bin="pandoc",
        input_md=tmp_path / "input.md",
        output=tmp_path / "out.html",
        bib=tmp_path / "refs.bib",
        csl=tmp_path / "apa.csl",
        style="apa",
        metadata_file=None,
        template=None,
        reference_doc=None,
        to_format="html",
        resource_path=page_dir,
    )
    assert "--resource-path" in cmd
    assert cmd[cmd.index("--resource-path") + 1] == str(page_dir)


def test_build_pandoc_cmd_omits_resource_path_by_default(tmp_path: Path) -> None:
    cmd = export_mod._build_pandoc_cmd(
        pandoc_bin="pandoc",
        input_md=tmp_path / "input.md",
        output=tmp_path / "out.html",
        bib=tmp_path / "refs.bib",
        csl=tmp_path / "apa.csl",
        style="apa",
        metadata_file=None,
        template=None,
        reference_doc=None,
        to_format="html",
    )
    assert "--resource-path" not in cmd


def test_export_falha_alto_quando_figura_falta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prova a FIAÇÃO (não repete a prova pura de ``_assert_no_missing_resource``,
    já coberta acima por ``test_assert_no_missing_resource_raises_with_target``):
    quando o pandoc — mockado via ``subprocess.run``, sem depender do binário
    instalado — sai 0 com ``[WARNING] Could not fetch resource`` no stderr,
    ``export()`` propaga ``MissingResourceError`` até o chamador em vez de
    completar em silêncio com a figura ausente."""
    root, page = _fake_project(tmp_path)
    page.write_text("Texto\n\n![Fig](figures/ausente.png)\n")
    _patch_export_seams(monkeypatch, tmp_path)

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout="",
            stderr="[WARNING] Could not fetch resource figures/ausente.png\n",
        )

    monkeypatch.setattr("prumo_assist.domains.write.export.subprocess.run", fake_run)

    with pytest.raises(export_mod.MissingResourceError) as exc:
        export_mod.export(page, to="html", project_root=root)
    assert "figures/ausente.png" in str(exc.value)


def test_export_html_usa_resource_path_do_diretorio_da_pagina(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Prova a FIAÇÃO (complementa, sem repetir, ``test_build_pandoc_cmd_includes_resource_path``
    acima, que testa ``_build_pandoc_cmd`` isolada): o comando que ``export()``
    de fato monta e executa (capturado do ``subprocess.run`` mockado) carrega
    ``--resource-path`` com o VALOR do diretório da página FONTE
    (``page.parent``) — não o tempdir onde o markdown normalizado é gravado.
    Checar só a presença da flag não provaria nada (um valor errado, ex.
    apontando pro tempdir, passaria) — por isso asserta o valor exato."""
    root, page = _fake_project(tmp_path)
    page.write_text("Texto\n\n![Fig](figures/x.png)\n")
    _patch_export_seams(monkeypatch, tmp_path)
    calls: list[list[str]] = []
    fake = _fake_run_writing_output_flag([b"<html>ok</html>"], calls)
    monkeypatch.setattr("prumo_assist.domains.write.export.subprocess.run", fake)

    result = export_mod.export(page, to="html", project_root=root)

    assert result.is_file()
    assert len(calls) == 1
    cmd = calls[0]
    assert "--resource-path" in cmd
    idx = cmd.index("--resource-path")
    assert cmd[idx + 1] == str(page.parent)
    assert cmd[idx + 1] != str(page.parent.parent)  # não aponta pro projeto inteiro


def test_export_recusa_sobrescrever_sem_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A guarda tem que descender de ``WriteError``/``PrumoError`` — não do
    ``FileExistsError`` builtin — senão ``core/cli_op.cli_run`` não a captura
    e o usuário toma traceback cru (regressão de CLI achada na revisão da
    Task 8, corrigida aqui)."""
    root, page = _fake_project(tmp_path)
    _patch_export_seams(monkeypatch, tmp_path)
    out = root / "build" / "exports" / "pagina.docx"
    out.parent.mkdir(parents=True)
    out.write_bytes(b"conteudo do coautor")

    with pytest.raises(export_mod.OutputExistsError) as exc:
        export_mod.export(page, to="docx", out=out, project_root=root)
    assert isinstance(exc.value, WriteError)
    assert "--force" in str(exc.value)
    assert out.read_bytes() == b"conteudo do coautor"  # nao mexeu no arquivo


def test_export_sobrescreve_com_force(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, page = _fake_project(tmp_path)
    _patch_export_seams(monkeypatch, tmp_path)
    out = root / "build" / "exports" / "pagina.docx"
    out.parent.mkdir(parents=True)
    out.write_bytes(b"conteudo antigo")
    calls: list[list[str]] = []
    fake = _fake_run_writing_output_flag([_docx_bytes_for_export_wiring(tmp_path, [])], calls)
    monkeypatch.setattr("prumo_assist.domains.write.export.subprocess.run", fake)

    result = export_mod.export(page, to="docx", out=out, project_root=root, force=True)

    assert result == out
    assert len(calls) == 1


def test_zettlr_export_entry_overwrites_on_second_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``zettlr_export_entry`` (o entrypoint `prumo-zettlr-export` chamado
    pelo Zettlr) sempre passa ``force=True`` — decisão de produto: ali é
    sempre o autor reexportando a própria fonte pra scratch gitignored,
    nunca o docx do coautor com tracked changes. Prova ponta a ponta (export
    real, seams externos mockados) que reexportar o MESMO arquivo pelo
    entrypoint do Zettlr sobrescreve sem levantar ``OutputExistsError``."""
    from prumo_assist.domains.write.cli import zettlr_export_entry

    root, page = _fake_project(tmp_path)
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    _patch_export_seams(monkeypatch, tmp_path)
    calls: list[list[str]] = []
    payload = _docx_bytes_for_export_wiring(tmp_path, [])
    fake = _fake_run_writing_output_flag([payload, payload], calls)
    monkeypatch.setattr("prumo_assist.domains.write.export.subprocess.run", fake)
    monkeypatch.setattr("sys.argv", ["prumo-zettlr-export", str(page)])

    zettlr_export_entry()  # 1a exportação: cria o docx
    zettlr_export_entry()  # 2a exportação do MESMO arquivo: sobrescreve sem erro

    out = root / "build" / "exports" / f"{export_mod.slugify(page, root)}.docx"
    assert out.is_file()
    assert len(calls) == 2


def test_compose_recusa_sobrescrever_sem_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``compose()`` tinha o mesmo buraco: nenhuma guarda de sobrescrita,
    silenciosa (pior que o crash de ``export()`` — nem avisava). Mesma
    exceção/mensagem de ``export()`` por consistência dentro do arquivo."""
    root, _page = _fake_project(tmp_path)
    index = root / "docs" / "index.md"
    index.write_text("---\npages: [docs/page.md]\n---\n")
    _patch_export_seams(monkeypatch, tmp_path)
    out = root / "build" / "exports" / "index.docx"
    out.parent.mkdir(parents=True)
    out.write_bytes(b"conteudo do coautor")

    with pytest.raises(export_mod.OutputExistsError) as exc:
        export_mod.compose(index=index, to="docx", out=out, project_root=root)
    assert isinstance(exc.value, WriteError)
    assert "--force" in str(exc.value)
    assert out.read_bytes() == b"conteudo do coautor"


def test_compose_sobrescreve_com_force(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, _page = _fake_project(tmp_path)
    index = root / "docs" / "index.md"
    index.write_text("---\npages: [docs/page.md]\n---\n")
    _patch_export_seams(monkeypatch, tmp_path)
    out = root / "build" / "exports" / "index.docx"
    out.parent.mkdir(parents=True)
    out.write_bytes(b"conteudo antigo")
    calls: list[list[str]] = []
    fake = _fake_run_writing_output_flag([_docx_bytes_for_export_wiring(tmp_path, [])], calls)
    monkeypatch.setattr("prumo_assist.domains.write.export.subprocess.run", fake)

    result = export_mod.compose(index=index, to="docx", out=out, project_root=root, force=True)

    assert result == out


def test_compose_resource_path_multiplos_diretorios_sem_duplicata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regressão do fix round 1 da Task 8: ``compose()`` nunca recebeu
    ``resource_path`` nenhum, mas ficou sob a mesma checagem
    ``_assert_no_missing_resource`` compartilhada com ``export()`` via
    ``_run_pandoc_checked`` — qualquer figura em página composta passou a
    falhar sempre. Prova o conserto: o comando real carrega
    ``--resource-path`` com o diretório de CADA página combinada (index +
    ``pages:``), sem duplicata (duas páginas no MESMO diretório — A e A2 —
    só contam uma vez), na ordem estável em que entram no ``combined``."""
    root, _page = _fake_project(tmp_path)
    index = root / "docs" / "index.md"
    index.write_text(
        "---\npages: [docs/estudoA/pagA.md, docs/estudoA/pagA2.md, docs/estudoB/pagB.md]\n---\n"
    )

    page_a = root / "docs" / "estudoA" / "pagA.md"
    page_a.parent.mkdir(parents=True)
    (page_a.parent / "figures").mkdir()
    (page_a.parent / "figures" / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    page_a.write_text("Página A\n\n![Fig A](figures/a.png)\n")

    page_a2 = root / "docs" / "estudoA" / "pagA2.md"
    page_a2.write_text("Página A2, mesmo diretório de A.\n")

    page_b = root / "docs" / "estudoB" / "pagB.md"
    page_b.parent.mkdir(parents=True)
    (page_b.parent / "figures").mkdir()
    (page_b.parent / "figures" / "b.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    page_b.write_text("Página B\n\n![Fig B](figures/b.png)\n")

    _patch_export_seams(monkeypatch, tmp_path)
    calls: list[list[str]] = []
    fake = _fake_run_writing_output_flag([b"<html>ok</html>"], calls)
    monkeypatch.setattr("prumo_assist.domains.write.export.subprocess.run", fake)

    export_mod.compose(index=index, to="html", project_root=root)

    assert len(calls) == 1
    cmd = calls[0]
    assert "--resource-path" in cmd
    idx = cmd.index("--resource-path")
    dirs = cmd[idx + 1].split(":")
    assert dirs == [str(index.parent), str(page_a.parent), str(page_b.parent)]
    assert len(calls) == 1
