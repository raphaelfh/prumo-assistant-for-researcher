"""Seam do adeu pinado (`_run_adeu_extract`) + parser de marcas com autoria
(`parse_adeu_markdown`) — Task 4 da ponte Fase 2.

`_run_adeu_extract` roda `uvx adeu==1.29.0 extract --json <docx> -o -`;
subprocess SEMPRE mockado aqui (regra deste repo — `.claude/rules/code.md`)
via `patch("prumo_assist.domains.write.review.subprocess.run")`.
`parse_adeu_markdown` é parse puro de string sobre o markdown já devolvido
pelo seam — não precisa mockar nada.

Golden fixture literal do spike (per brief da Task 4): trava o formato real
de saída do adeu (marca de conteúdo + anotação `{>>[Chg:<id> tipo]
<Autor><<}` colada em seguida, rodapé `\n---\n## Footnotes`) sem rodar o
adeu no CI.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from prumo_assist.core import criticmarkup
from prumo_assist.domains.write.review import (
    AdeuUnavailableError,
    ReviewMark,
    _run_adeu_extract,
    parse_adeu_markdown,
)

ADEU_GOLDEN = (
    "Primeiro paragrafo de prosa.\n\n"
    "Aqui vem a citacao (Smith, 2020){++ TEXTO INSERIDO PELO COAUTOR++}"
    "{>>[Chg:901 insert] Coautor<<} e mais prosa.\n\n"
    "{--Ultimo paragrafo.--}{>>[Chg:902 delete] Coautor<<}\n\n---\n## Footnotes"
)


# --- golden: marcas pareadas com autoria -------------------------------------


def test_parse_adeu_markdown_golden_yields_two_marks_with_authorship() -> None:
    _clean_text, marks = parse_adeu_markdown(ADEU_GOLDEN)

    assert len(marks) == 2
    ins_mark, del_mark = marks
    assert isinstance(ins_mark, ReviewMark)
    assert ins_mark.kind == "ins"
    assert ins_mark.b == " TEXTO INSERIDO PELO COAUTOR"
    assert ins_mark.author == "Coautor"
    assert ins_mark.chg_id == "901"
    assert del_mark.kind == "del"
    assert del_mark.a == "Ultimo paragrafo."
    assert del_mark.author == "Coautor"
    assert del_mark.chg_id == "902"


def test_parse_adeu_markdown_golden_clean_text_strips_annotations_and_footer() -> None:
    clean_text, _marks = parse_adeu_markdown(ADEU_GOLDEN)

    assert "Chg:" not in clean_text
    assert "Coautor" not in clean_text
    assert "Footnotes" not in clean_text
    assert "---" not in clean_text
    assert "Primeiro paragrafo de prosa." in clean_text
    assert "{++ TEXTO INSERIDO PELO COAUTOR++}" in clean_text
    assert "e mais prosa." in clean_text
    assert "{--Ultimo paragrafo.--}" in clean_text


def test_parse_adeu_markdown_golden_offsets_index_into_clean_text() -> None:
    """DECISÃO da Task 4: offsets de `ReviewMark` são no `clean_text` (pós
    remoção de anotações/rodapé) — reconstruir cada marca via
    `criticmarkup.emit` a partir de `clean_text[start:end]` precisa bater
    exatamente com a marca original (mesmo kind/a/b)."""
    clean_text, marks = parse_adeu_markdown(ADEU_GOLDEN)

    for mark in marks:
        assert clean_text[mark.start : mark.end] == criticmarkup.emit(mark.kind, mark.a, mark.b)


# --- marca de conteúdo sem anotação ------------------------------------------


def test_content_mark_without_trailing_annotation_has_unknown_author() -> None:
    markdown = "Texto normal {++inserido sem anotacao++} fim."

    clean_text, marks = parse_adeu_markdown(markdown)

    assert len(marks) == 1
    mark = marks[0]
    assert mark.kind == "ins"
    assert mark.author == "(desconhecido)"
    assert mark.chg_id is None
    assert clean_text == markdown  # nada pareado para remover — texto intacto


# --- anotação órfã (comment sem marca de conteúdo imediatamente antes) -----


def test_orphan_comment_without_preceding_mark_stays_as_comment_with_unknown_author() -> None:
    markdown = "Frase comum. {>>Isto e um comentario solto<<} mais texto."

    clean_text, marks = parse_adeu_markdown(markdown)

    assert len(marks) == 1
    mark = marks[0]
    assert mark.kind == "comment"
    assert mark.b == "Isto e um comentario solto"
    assert mark.author == "(desconhecido)"
    assert mark.chg_id is None
    # órfã NÃO é removida do texto — só anotações PAREADAS somem.
    assert clean_text == markdown


def test_orphan_comment_matching_chg_pattern_extracts_author_and_id_anyway() -> None:
    """Mesma extração `[Chg:...]` vale para o corpo de uma comment órfã — não
    precisa estar pareada com marca de conteúdo para a autoria ser lida."""
    markdown = "Frase solta. {>>[Chg:777 insert] Revisor Solto<<} resto."

    _clean_text, marks = parse_adeu_markdown(markdown)

    assert len(marks) == 1
    mark = marks[0]
    assert mark.kind == "comment"
    assert mark.chg_id == "777"
    assert mark.author == "Revisor Solto"


# --- formato markup-path do adeu: {>>Diff: ...<<} ---------------------------


def test_diff_format_annotation_pairs_and_defaults_to_unknown_author() -> None:
    """`{>>Diff: ...<<}` pareia com a marca de conteúdo anterior igual a
    `[Chg:...]` (mesma regra de adjacência), mas como o corpo não casa o
    padrão, autor fica desconhecido e chg_id None."""
    markdown = "Prosa {++novo trecho++}{>>Diff: alguma descricao do path<<} fim."

    clean_text, marks = parse_adeu_markdown(markdown)

    assert len(marks) == 1
    mark = marks[0]
    assert mark.kind == "ins"
    assert mark.b == "novo trecho"
    assert mark.author == "(desconhecido)"
    assert mark.chg_id is None
    assert "Diff:" not in clean_text
    assert "novo trecho" in clean_text


# --- seam: _run_adeu_extract (subprocess sempre mockado) --------------------


def _completed(
    *, returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["uvx", "adeu==1.29.0"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_run_adeu_extract_invokes_pinned_uvx_command(tmp_path: Path) -> None:
    docx = tmp_path / "revisado.docx"

    with patch(
        "prumo_assist.domains.write.review.subprocess.run",
        return_value=_completed(returncode=0, stdout='{"markdown": "ok"}'),
    ) as mock_run:
        _run_adeu_extract(docx)

    mock_run.assert_called_once_with(
        ["uvx", "adeu==1.29.0", "extract", "--json", str(docx), "-o", "-"],
        capture_output=True,
        text=True,
    )


def test_run_adeu_extract_parses_markdown_field_from_stdout_json(tmp_path: Path) -> None:
    docx = tmp_path / "revisado.docx"
    stdout = json.dumps({"markdown": "# titulo\n\ncorpo com {++marca++}", "other": 123})

    with patch(
        "prumo_assist.domains.write.review.subprocess.run",
        return_value=_completed(returncode=0, stdout=stdout),
    ):
        markdown = _run_adeu_extract(docx)

    assert markdown == "# titulo\n\ncorpo com {++marca++}"


def test_run_adeu_extract_nonzero_exit_raises_adeu_unavailable(tmp_path: Path) -> None:
    docx = tmp_path / "revisado.docx"

    with (
        patch(
            "prumo_assist.domains.write.review.subprocess.run",
            return_value=_completed(returncode=1, stderr="erro fatal do adeu"),
        ),
        pytest.raises(AdeuUnavailableError) as exc,
    ):
        _run_adeu_extract(docx)

    message = str(exc.value)
    assert "uv --version" in message
    assert "uvx adeu==1.29.0 --version" in message
    assert "backend de PROSA" in message


def test_run_adeu_extract_uvx_not_found_raises_adeu_unavailable(tmp_path: Path) -> None:
    docx = tmp_path / "revisado.docx"

    with (
        patch(
            "prumo_assist.domains.write.review.subprocess.run",
            side_effect=FileNotFoundError("uvx não encontrado"),
        ),
        pytest.raises(AdeuUnavailableError) as exc,
    ):
        _run_adeu_extract(docx)

    message = str(exc.value)
    assert "uv --version" in message
    assert "uvx adeu==1.29.0 --version" in message
