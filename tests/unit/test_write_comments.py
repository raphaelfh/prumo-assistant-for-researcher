"""Tests pro extrator de comentários de .docx."""

from __future__ import annotations

import zipfile
from pathlib import Path

from prumo_assist.domains.write.comments import (
    Comment,
    Revision,
    render_checklist,
)


def test_render_checklist_with_no_items() -> None:
    md = render_checklist(comments=[], revisions=[], source="x.docx")
    assert "## Comentários" in md
    assert "## Track changes" in md
    assert md.count("(nenhum)") == 2


def test_render_checklist_includes_comments_and_revisions() -> None:
    comments = [
        Comment(
            id="0", author="Alice", text="Sugestão de revisão.", anchor_text="frase X", date=None
        ),
    ]
    revisions = [
        Revision(kind="insertion", author="Bob", text="texto novo", date=None),
        Revision(kind="deletion", author="Bob", text="velho", date=None),
    ]
    md = render_checklist(comments=comments, revisions=revisions, source="paper.docx")
    assert "**Alice**" in md
    assert "frase X" in md
    assert "Inserção" in md
    assert "Deleção" in md


def test_extract_from_docx_handles_minimal_file(tmp_path: Path) -> None:
    """Smoke test: cria docx mínimo (sem comments) e verifica que não crasha."""
    docx = tmp_path / "minimal.docx"
    minimal_doc = (
        '<?xml version="1.0"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>Hello</w:t></w:r></w:p></w:body>"
        "</w:document>"
    )
    with zipfile.ZipFile(docx, "w") as z:
        z.writestr("word/document.xml", minimal_doc)
    from prumo_assist.domains.write.comments import extract_from_docx

    result = extract_from_docx(docx)
    assert result.comments == []
    assert result.revisions == []
