"""Leitor OOXML STATEFUL de citações (`read_docx_citations_with_state`, I2b).

Sibling do leitor stateless (`export._read_docx_citations`, I2) testado em
`test_export_docx_validation.py` — mas aqui as fixtures precisam de campo
OOXML REAL (fldChar begin/instrText/separate/display/end) porque o leitor
usa ElementTree para andar pelos ancestrais `w:ins`/`w:del`, não regex sobre
o XML cru. Helper local (não importa de `test_export_docx_validation.py`).
"""

from __future__ import annotations

import html
import zipfile
from pathlib import Path

import pytest

from prumo_assist.domains.write.review import (
    CitationConservationError,
    DocxCitation,
    read_docx_citations_with_state,
)

_W_XMLNS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _payload(*, occ_id: str, citekeys: list[str], formatted: str) -> str:
    """JSON cru do campo ``ADDIN ZOTERO_ITEM CSL_CITATION`` (mesmo formato de
    `zotero_live_docx.lua`/`export._read_docx_citations`)."""
    items = ",".join(f'{{"id":"{key}","prumoFingerprint":"doi:10.1/{key}"}}' for key in citekeys)
    return (
        f'{{"citationID":"{occ_id}","prumoOcc":"{occ_id}",'
        f'"citationItems":[{items}],'
        f'"properties":{{"formattedCitation":"{formatted}"}}}}'
    )


def _field_xml(payload: str, *, wrap_del: bool = False, touch_ins: bool = False) -> str:
    """XML real de UM campo Zotero: fldChar begin/instrText/separate/display/end.

    ``wrap_del=True`` embrulha a sequência INTEIRA do campo em ``<w:del>``
    (todos os runs do campo ganham ancestral ``w:del`` → estado ``deleted``).
    ``touch_ins=True`` acrescenta um run extra embrulhado em ``<w:ins>``
    dentro do campo, sem tocar os demais (só ALGUM run com ancestral →
    estado ``touched``). Mutuamente exclusivos nos testes deste arquivo.
    """
    begin = '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
    instr = (
        '<w:r><w:instrText xml:space="preserve"> ADDIN ZOTERO_ITEM CSL_CITATION '
        + html.escape(payload)
        + " </w:instrText></w:r>"
    )
    separate = '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
    display = "<w:r><w:t>(Formatted, 2020)</w:t></w:r>"
    end = '<w:r><w:fldChar w:fldCharType="end"/></w:r>'

    runs = begin + instr + separate + display
    if touch_ins:
        runs += '<w:ins w:id="9" w:author="Coautor"><w:r><w:t xml:space="preserve"> extra</w:t></w:r></w:ins>'
    runs += end

    if wrap_del:
        return f'<w:del w:id="1" w:author="Coautor">{runs}</w:del>'
    return runs


def _begin_without_end_xml(payload: str) -> str:
    """Campo colapsado: `fldChar begin` + `instrText`, SEM `fldChar end`."""
    return (
        '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        '<w:r><w:instrText xml:space="preserve"> ADDIN ZOTERO_ITEM CSL_CITATION '
        + html.escape(payload)
        + " </w:instrText></w:r>"
    )


def _orphan_end_xml() -> str:
    """Campo colapsado: `fldChar end` sem `begin` correspondente antes."""
    return '<w:r><w:fldChar w:fldCharType="end"/></w:r>'


def _write_docx_with_fields(path: Path, field_bodies: list[str]) -> Path:
    """Zip OOXML com um `<w:p>` por corpo de campo — namespace `w:` declarado
    (ElementTree exige o binding; o leitor stateless usa regex e não precisa)."""
    paragraphs = "".join(f"<w:p>{body}</w:p>" for body in field_bodies)
    document = (
        f'<?xml version="1.0"?><w:document {_W_XMLNS}><w:body>{paragraphs}</w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", document)
    return path


# --- estado: live / deleted / touched --------------------------------------


def test_read_with_state_live_when_untouched(tmp_path: Path) -> None:
    payload = _payload(occ_id="00000001", citekeys=["smith2020"], formatted="(Smith, 2020)")
    docx = _write_docx_with_fields(tmp_path / "live.docx", [_field_xml(payload)])

    citations = read_docx_citations_with_state(docx)

    assert len(citations) == 1
    assert citations[0].state == "live"


def test_read_with_state_deleted_when_all_runs_wrapped_in_del(tmp_path: Path) -> None:
    payload = _payload(occ_id="00000001", citekeys=["smith2020"], formatted="(Smith, 2020)")
    docx = _write_docx_with_fields(tmp_path / "deleted.docx", [_field_xml(payload, wrap_del=True)])

    citations = read_docx_citations_with_state(docx)

    assert len(citations) == 1
    assert citations[0].state == "deleted"


def test_read_with_state_touched_when_some_run_wrapped_in_ins(tmp_path: Path) -> None:
    payload = _payload(occ_id="00000001", citekeys=["smith2020"], formatted="(Smith, 2020)")
    docx = _write_docx_with_fields(tmp_path / "touched.docx", [_field_xml(payload, touch_ins=True)])

    citations = read_docx_citations_with_state(docx)

    assert len(citations) == 1
    assert citations[0].state == "touched"


# --- ordem do documento + decode --------------------------------------------


def test_read_with_state_preserves_document_order(tmp_path: Path) -> None:
    payload_a = _payload(occ_id="00000001", citekeys=["aaa2020"], formatted="(Aaa, 2020)")
    payload_b = _payload(occ_id="00000002", citekeys=["bbb2021"], formatted="(Bbb, 2021)")
    docx = _write_docx_with_fields(
        tmp_path / "ordem.docx", [_field_xml(payload_a), _field_xml(payload_b)]
    )

    citations = read_docx_citations_with_state(docx)

    assert [c.occ_id for c in citations] == ["00000001", "00000002"]


def test_read_with_state_decodes_occ_id_citekeys_and_fingerprints(tmp_path: Path) -> None:
    payload = _payload(
        occ_id="00000007", citekeys=["bbb2021", "ccc2022"], formatted="(Bbb, 2021; Ccc, 2022)"
    )
    docx = _write_docx_with_fields(tmp_path / "decode.docx", [_field_xml(payload)])

    citations = read_docx_citations_with_state(docx)

    assert len(citations) == 1
    citation = citations[0]
    assert isinstance(citation, DocxCitation)
    assert citation.occ_id == "00000007"
    assert citation.citation_id == "00000007"
    assert citation.citekeys == ("bbb2021", "ccc2022")
    assert citation.fingerprints == {
        "bbb2021": "doi:10.1/bbb2021",
        "ccc2022": "doi:10.1/ccc2022",
    }
    assert citation.formatted == "(Bbb, 2021; Ccc, 2022)"


# --- fldChar desbalanceado → CitationConservationError (I2b) ----------------


def test_read_with_state_begin_without_end_raises(tmp_path: Path) -> None:
    payload = _payload(occ_id="00000001", citekeys=["smith2020"], formatted="(Smith, 2020)")
    docx = _write_docx_with_fields(
        tmp_path / "colapsado_begin.docx", [_begin_without_end_xml(payload)]
    )

    with pytest.raises(CitationConservationError) as exc:
        read_docx_citations_with_state(docx)
    assert "colapsado" in str(exc.value)


def test_read_with_state_orphan_end_raises(tmp_path: Path) -> None:
    docx = _write_docx_with_fields(tmp_path / "colapsado_end.docx", [_orphan_end_xml()])

    with pytest.raises(CitationConservationError) as exc:
        read_docx_citations_with_state(docx)
    assert "colapsado" in str(exc.value)


# --- JSON inválido → CitationConservationError com índice -------------------


def test_read_with_state_invalid_json_raises_with_index(tmp_path: Path) -> None:
    docx = _write_docx_with_fields(
        tmp_path / "json_invalido.docx", [_field_xml("{isto nao e json")]
    )

    with pytest.raises(CitationConservationError) as exc:
        read_docx_citations_with_state(docx)
    assert "#1" in str(exc.value)


def test_read_with_state_invalid_json_index_counts_only_zotero_fields(tmp_path: Path) -> None:
    """O índice do erro conta só campos Zotero (marca ADDIN ZOTERO_ITEM), na
    ordem em que aparecem — o 2º campo é o inválido, então "#2"."""
    good_payload = _payload(occ_id="00000001", citekeys=["smith2020"], formatted="(Smith, 2020)")
    docx = _write_docx_with_fields(
        tmp_path / "segundo_invalido.docx",
        [_field_xml(good_payload), _field_xml("{tambem invalido")],
    )

    with pytest.raises(CitationConservationError) as exc:
        read_docx_citations_with_state(docx)
    assert "#2" in str(exc.value)
