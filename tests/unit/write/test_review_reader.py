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

import prumo_assist.domains.write.export as export_mod
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
    (todos os runs do campo ganham ancestral ``w:del`` → estado ``deleted``)
    e reproduz o rename Word-fiel de conteúdo textual dentro de uma deleção
    rastreada (ECMA-376 §17.16.14, I2b): ``<w:instrText>``→``<w:delInstrText>``
    e ``<w:t>``→``<w:delText>``. Sem isso a fixture não testaria o que o
    Word realmente grava (achado do review da Fase 2/Task 1 — Finding 1).
    ``touch_ins=True`` acrescenta um run extra embrulhado em ``<w:ins>``
    dentro do campo, sem tocar os demais (só ALGUM run com ancestral →
    estado ``touched``). Mutuamente exclusivos nos testes deste arquivo.
    """
    instr_tag = "delInstrText" if wrap_del else "instrText"
    text_tag = "delText" if wrap_del else "t"

    begin = '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
    instr = (
        f'<w:r><w:{instr_tag} xml:space="preserve"> ADDIN ZOTERO_ITEM CSL_CITATION '
        + html.escape(payload)
        + f" </w:{instr_tag}></w:r>"
    )
    separate = '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
    display = f"<w:r><w:{text_tag}>(Formatted, 2020)</w:{text_tag}></w:r>"
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


def test_read_with_state_deleted_uses_del_instr_text_and_decodes_payload(tmp_path: Path) -> None:
    """Achado do review (Finding 1): Word real renomeia `<w:instrText>` para
    `<w:delInstrText>` quando o campo inteiro é deletado sob Track Changes
    (ECMA-376 §17.16.14, I2b). Sem reconhecer a marca renomeada, a citação
    deletada some da leitura (nem aparece como `deleted`) — este teste
    confere que o payload também decodifica corretamente (occ_id/citekeys/
    formatted) a partir de `w:delInstrText`, não só que o estado bate."""
    payload = _payload(occ_id="00000009", citekeys=["ghi2023"], formatted="(Ghi, 2023)")
    docx = _write_docx_with_fields(
        tmp_path / "deleted_delinstr.docx", [_field_xml(payload, wrap_del=True)]
    )
    with zipfile.ZipFile(docx) as z:
        assert b"w:delInstrText" in z.read("word/document.xml")  # fixture Word-fiel

    citations = read_docx_citations_with_state(docx)

    assert len(citations) == 1
    citation = citations[0]
    assert citation.state == "deleted"
    assert citation.occ_id == "00000009"
    assert citation.citekeys == ("ghi2023",)
    assert citation.formatted == "(Ghi, 2023)"


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


# --- paridade de decode com o leitor stateless (Finding 2 do review) --------


def test_state_reader_and_export_reader_decode_identical_fingerprint_and_formatted(
    tmp_path: Path,
) -> None:
    """Achado do review (Finding 2): `review.py` parseava o texto do
    ElementTree (entidades XML já resolvidas UMA vez pelo parser) e ainda
    aplicava `html.unescape` por cima — um segundo unescape sobre `&para=`
    (já resolvido de `&amp;para=` pelo ET) reinterpreta `&para` como a
    entidade HTML5 sem `;` (¶), corrompendo qualquer fingerprint/formatted
    com esse padrão. Constrói a MESMA fixture docx e compara o decode dos
    dois leitores: `export._read_docx_citations` (stateless, fonte de
    verdade do citemap) e `read_docx_citations_with_state` (stateful)
    precisam concordar byte a byte."""
    formatted = "(Smith, 2020) https://example.com/x?a=1&para=2"
    fingerprint = "sha256:deadbeef?ref=a&para=2"
    payload = (
        '{"citationID":"00000001","prumoOcc":"00000001",'
        '"citationItems":[{"id":"smith2020","prumoFingerprint":"'
        + fingerprint
        + '"}],"properties":{"formattedCitation":"'
        + formatted
        + '"}}'
    )
    docx = _write_docx_with_fields(tmp_path / "paridade.docx", [_field_xml(payload)])

    stateless = export_mod._read_docx_citations(docx)
    stateful = read_docx_citations_with_state(docx)

    assert len(stateless) == 1
    assert len(stateful) == 1
    assert stateful[0].formatted == formatted
    assert stateful[0].fingerprints == {"smith2020": fingerprint}
    assert stateless[0]["formatted"] == stateful[0].formatted
    assert stateless[0]["fingerprints"] == stateful[0].fingerprints
    assert "&para=" in stateful[0].formatted
    assert "¶" not in stateful[0].formatted
    assert "¶" not in stateful[0].fingerprints["smith2020"]
