"""Guarda A (`assert_no_structural_changes`) — mudança rastreada ou comentário
numa região estrutural que o transplante por âncora de texto (adeu extrai só
prosa linear) não sabe localizar: tabela, nota de rodapé/fim, equação (oMath).

Builder de zip LOCAL, não reusa `test_review_reader.py`: as fixtures aqui
precisam de formas Word-fiéis que o leitor de citações nunca constrói —
célula de tabela (`w:tbl > w:tr > w:tc`), PARTE separada do zip
(`word/footnotes.xml`/`word/endnotes.xml`) e `m:oMath` (namespace math). Um
builder dedicado e pequeno é mais simples que esticar
`_write_docx_with_fields`/`_field_xml` daquele módulo, que são sobre campos
de citação, não sobre essas 3 regiões estruturais.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from prumo_assist.domains.write.review import (
    StructuralChangeError,
    assert_no_structural_changes,
)

_W_XMLNS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
_M_XMLNS = 'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'
_DOC_XMLNS = f"{_W_XMLNS} {_M_XMLNS}"

_FIX_INSTRUCTION = (
    "peça ao coautor para mover a mudança para o corpo do texto ou aplique "
    "manualmente; re-exporte e re-ingira"
)

# Propositalmente > 60 chars, para exercitar o truncamento do trecho na
# mensagem de erro (brief: "primeiros 60 chars do texto da região").
_LONG_TEXT = "Texto de mudanca estrutural bem mais longo que sessenta caracteres para truncar"
assert len(_LONG_TEXT) > 60


def _write_docx(
    path: Path,
    *,
    document_body: str,
    footnotes_body: str | None = None,
    endnotes_body: str | None = None,
) -> Path:
    """Zip OOXML mínimo: `word/document.xml` sempre presente;
    `word/footnotes.xml`/`word/endnotes.xml` só quando o parâmetro
    correspondente é passado — mesmo em docx real essas partes só existem
    quando o documento usa notas."""
    document = (
        f'<?xml version="1.0"?><w:document {_DOC_XMLNS}>'
        f"<w:body>{document_body}</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", document)
        if footnotes_body is not None:
            z.writestr(
                "word/footnotes.xml",
                f'<?xml version="1.0"?><w:footnotes {_W_XMLNS}>{footnotes_body}</w:footnotes>',
            )
        if endnotes_body is not None:
            z.writestr(
                "word/endnotes.xml",
                f'<?xml version="1.0"?><w:endnotes {_W_XMLNS}>{endnotes_body}</w:endnotes>',
            )
    return path


def _table_with_ins(text: str) -> str:
    """`w:tbl > w:tr > w:tc > w:p > w:ins` — forma Word-fiel de inserção
    rastreada dentro de célula de tabela."""
    return (
        "<w:tbl><w:tr><w:tc><w:p>"
        '<w:ins w:id="1" w:author="Coautor">'
        f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r>'
        "</w:ins>"
        "</w:p></w:tc></w:tr></w:tbl>"
    )


def _table_with_comment_range_start(text: str) -> str:
    """`w:tbl > w:tr > w:tc > w:p > w:commentRangeStart` — rule (a) do brief
    cobre comentário dentro de tabela, não só mudança rastreada.
    `w:commentRangeStart` é um marcador VAZIO (sem texto próprio); o trecho
    da mensagem precisa vir do texto da célula em volta."""
    return (
        "<w:tbl><w:tr><w:tc><w:p>"
        '<w:commentRangeStart w:id="7"/>'
        f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r>'
        '<w:commentRangeEnd w:id="7"/>'
        "</w:p></w:tc></w:tr></w:tbl>"
    )


def _table_with_row_level_ins_marker() -> str:
    """`w:tr > w:trPr > w:ins` — marcador de linha INTEIRA inserida sob
    Track Changes (ECMA-376 `CT_TrPrBase`): mesma tag `w:ins` da rule (a),
    mas FORA de qualquer `w:tc` — só dentro de `w:trPr`, irmã da célula, não
    descendente dela. Exercita por que `_first_table_hit` checa ancestral
    `w:tbl` (não `w:tc`): um filtro por `w:tc` deixaria esse marcador passar
    batido."""
    return (
        "<w:tbl><w:tr>"
        '<w:trPr><w:ins w:id="8" w:author="Coautor"/></w:trPr>'
        "<w:tc><w:p><w:r><w:t>celula normal sem marca</w:t></w:r></w:p></w:tc>"
        "</w:tr></w:tbl>"
    )


def _footnote_with_del(text: str) -> str:
    """`w:footnote > w:p > w:del` dentro da PARTE separada `footnotes.xml`."""
    return (
        '<w:footnote w:id="1"><w:p>'
        '<w:del w:id="2" w:author="Coautor">'
        f'<w:r><w:delText xml:space="preserve">{text}</w:delText></w:r>'
        "</w:del>"
        "</w:p></w:footnote>"
    )


def _endnote_with_ins(text: str) -> str:
    """`w:endnote > w:p > w:ins` dentro da PARTE separada `endnotes.xml`."""
    return (
        '<w:endnote w:id="1"><w:p>'
        '<w:ins w:id="3" w:author="Coautor">'
        f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r>'
        "</w:ins>"
        "</w:p></w:endnote>"
    )


def _omath_with_ins(text: str) -> str:
    """`m:oMath > w:ins > m:r > m:t` — inserção rastreada dentro de equação."""
    return (
        "<w:p><m:oMath>"
        '<w:ins w:id="4" w:author="Coautor">'
        f"<m:r><m:t>{text}</m:t></m:r>"
        "</w:ins>"
        "</m:oMath></w:p>"
    )


def _clean_paragraph(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def _body_with_ordinary_tracked_change(text: str) -> str:
    """Mudança rastreada NO CORPO do texto (fora de tabela/nota/equação) — o
    caminho normal do pipeline (adeu extrai, o localizador transplanta);
    NÃO deve disparar a Guarda A."""
    return (
        "<w:p>"
        '<w:ins w:id="5" w:author="Coautor">'
        f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r>'
        "</w:ins>"
        "</w:p>"
    )


def _clean_table(text: str) -> str:
    """`w:tbl > w:tr > w:tc > w:p > w:r > w:t` — tabela limpa sem mudança
    rastreada inside."""
    return (
        "<w:tbl><w:tr><w:tc><w:p>"
        f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r>'
        "</w:p></w:tc></w:tr></w:tbl>"
    )


# --- (a) tabela --------------------------------------------------------


def test_assert_no_structural_changes_table_insertion_raises(tmp_path: Path) -> None:
    docx = _write_docx(tmp_path / "tabela_ins.docx", document_body=_table_with_ins(_LONG_TEXT))

    with pytest.raises(StructuralChangeError) as exc:
        assert_no_structural_changes(docx)

    message = str(exc.value)
    assert "tabela" in message
    assert _LONG_TEXT[:60] in message
    assert _FIX_INSTRUCTION in message


def test_assert_no_structural_changes_table_comment_range_start_raises(
    tmp_path: Path,
) -> None:
    docx = _write_docx(
        tmp_path / "tabela_comentario.docx",
        document_body=_table_with_comment_range_start(_LONG_TEXT),
    )

    with pytest.raises(StructuralChangeError) as exc:
        assert_no_structural_changes(docx)

    message = str(exc.value)
    assert "tabela" in message
    assert _LONG_TEXT[:60] in message
    assert _FIX_INSTRUCTION in message


def test_assert_no_structural_changes_table_row_insert_marker_raises(tmp_path: Path) -> None:
    """Regressão do design: ancestral checado é `w:tbl`, não `w:tc` — o
    marcador de linha inteira inserida vive em `w:trPr`, fora de qualquer
    `w:tc`, e ainda assim precisa disparar a Guarda A."""
    docx = _write_docx(
        tmp_path / "tabela_linha_inserida.docx",
        document_body=_table_with_row_level_ins_marker(),
    )

    with pytest.raises(StructuralChangeError) as exc:
        assert_no_structural_changes(docx)

    assert "tabela" in str(exc.value)


# --- (b) notas (footnotes.xml / endnotes.xml) -------------------------------


def test_assert_no_structural_changes_footnotes_deletion_raises(tmp_path: Path) -> None:
    docx = _write_docx(
        tmp_path / "footnotes_del.docx",
        document_body=_clean_paragraph("Corpo normal, sem mudanca estrutural."),
        footnotes_body=_footnote_with_del(_LONG_TEXT),
    )

    with pytest.raises(StructuralChangeError) as exc:
        assert_no_structural_changes(docx)

    message = str(exc.value)
    assert "nota" in message
    assert _LONG_TEXT[:60] in message
    assert _FIX_INSTRUCTION in message


def test_assert_no_structural_changes_endnotes_insertion_raises(tmp_path: Path) -> None:
    """Rule (b) nomeia `footnotes.xml` E `endnotes.xml` — parte separada,
    checada independentemente (só `endnotes_body` aqui, sem `footnotes.xml`
    no zip)."""
    docx = _write_docx(
        tmp_path / "endnotes_ins.docx",
        document_body=_clean_paragraph("Corpo normal, sem mudanca estrutural."),
        endnotes_body=_endnote_with_ins(_LONG_TEXT),
    )

    with pytest.raises(StructuralChangeError) as exc:
        assert_no_structural_changes(docx)

    message = str(exc.value)
    assert "nota" in message
    assert _LONG_TEXT[:60] in message


# --- (c) equação (oMath) -----------------------------------------------------


def test_assert_no_structural_changes_omath_insertion_raises(tmp_path: Path) -> None:
    docx = _write_docx(tmp_path / "omath_ins.docx", document_body=_omath_with_ins(_LONG_TEXT))

    with pytest.raises(StructuralChangeError) as exc:
        assert_no_structural_changes(docx)

    message = str(exc.value)
    assert "equação" in message
    assert _LONG_TEXT[:60] in message
    assert _FIX_INSTRUCTION in message


# --- limpo → passa; e precisão (não dispara fora das 3 regiões) -------------


def test_assert_no_structural_changes_clean_docx_passes(tmp_path: Path) -> None:
    docx = _write_docx(
        tmp_path / "limpo.docx",
        document_body=_clean_paragraph("Paragrafo comum, sem tabela, nota ou equacao."),
    )

    assert_no_structural_changes(docx)  # não levanta


def test_assert_no_structural_changes_passes_with_ordinary_tracked_change_in_body(
    tmp_path: Path,
) -> None:
    """Mudança rastreada FORA das 3 regiões estruturais é o caminho normal do
    pipeline (adeu extrai, localizador transplanta) — a Guarda A não deve
    disparar aqui; sem essa checagem, uma implementação que procurasse
    `w:ins`/`w:del` em QUALQUER lugar do documento (em vez de restringir ao
    ancestral `w:tc`/`m:oMath`) passaria despercebida nos outros testes."""
    docx = _write_docx(
        tmp_path / "corpo_normal.docx",
        document_body=_body_with_ordinary_tracked_change("texto inserido no corpo, fora de tabela"),
    )

    assert_no_structural_changes(docx)  # não levanta


def test_clean_table_with_sibling_tracked_change_passes(tmp_path: Path) -> None:
    """Regressão: tabela limpa (sem mudança rastreada) + mudança rastreada em
    parágrafo irmão fora da tabela. Uma implementação ingênua (verifica "tabela
    existe EM ALGUM LUGAR" E "mudança rastreada existe EM ALGUM LUGAR") falharia
    aqui. A Guarda A deve verificar que a mudança está DENTRO da estrutura
    (tabela/nota/equação), não apenas que ambas existem."""
    document_body = _clean_table("Célula normal sem mudanca.") + _body_with_ordinary_tracked_change(
        "Paragrafo irmao com mudanca rastreada."
    )
    docx = _write_docx(
        tmp_path / "tabela_limpa_com_irmao_rastreado.docx", document_body=document_body
    )

    assert_no_structural_changes(docx)  # não levanta
