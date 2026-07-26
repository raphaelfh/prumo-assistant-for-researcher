"""Tests para ComposeInputs/v1 + WriteOutput/v1."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from prumo_assist.domains.write.schemas.v1 import (
    CiteMapFile,
    CiteOccurrence,
    ComposeInputs,
    FindingSummary,
    PaperSummary,
    ReviewComment,
    ReviewCommentsFile,
    ReviewEvent,
    ReviewEventsFile,
    SpanFragmentModel,
    SpanMapFile,
    WriteOutput,
)


def test_paper_summary_minimal() -> None:
    p = PaperSummary(citekey="smith2024", title="X", authors="Smith, J.")
    assert p.year is None
    assert p.extract_content is None


def test_paper_summary_requires_citekey() -> None:
    with pytest.raises(ValidationError):
        PaperSummary(citekey="", title="X", authors="Smith")


def test_compose_inputs_default_empty() -> None:
    c = ComposeInputs()
    assert c.picot is None
    assert c.citekeys == []
    assert c.papers == {}
    assert c.protocol is None
    assert c.findings == []
    assert c.schema_version == "ComposeInputs/v1"


def test_compose_inputs_with_data() -> None:
    paper = PaperSummary(citekey="a", title="T", authors="A")
    finding = FindingSummary(path=Path("docs/findings/x.md"), title="F", body="B")
    c = ComposeInputs(
        citekeys=["a"],
        papers={"a": paper},
        protocol="contexto",
        project="proj",
        findings=[finding],
    )
    assert c.papers["a"].citekey == "a"
    assert len(c.findings) == 1


def test_write_output_minimal() -> None:
    out = WriteOutput(
        output_path=Path("docs/drafts/paper-2026-05-03-x.md"),
        mode="drafts",
        kind="paper",
        sections_filled=["Introduction", "Methods"],
        sections_skipped=[],
        citations_used=["smith2024"],
        references_missing=["validação externa"],
        words_generated=1500,
    )
    assert out.schema_version == "WriteOutput/v1"


def test_write_output_invalid_mode() -> None:
    with pytest.raises(ValidationError):
        WriteOutput(
            output_path=Path("x.md"),
            mode="bogus",  # type: ignore[arg-type]
            kind="paper",
            sections_filled=[],
            sections_skipped=[],
            citations_used=[],
            references_missing=[],
            words_generated=0,
        )


def test_write_output_invalid_kind() -> None:
    with pytest.raises(ValidationError):
        WriteOutput(
            output_path=Path("x.md"),
            mode="drafts",
            kind="bogus",  # type: ignore[arg-type]
            sections_filled=[],
            sections_skipped=[],
            citations_used=[],
            references_missing=[],
            words_generated=0,
        )


def test_spanmap_file_roundtrip() -> None:
    f = SpanMapFile(
        page="docs/page.md",
        source_sha256="ab" * 32,
        fragments=[
            SpanFragmentModel(
                source_start=0, source_end=5, norm_start=0, norm_end=5, kind="identity"
            )
        ],
    )
    assert SpanMapFile.model_validate_json(f.model_dump_json()) == f
    assert f.schema_version == "SpanMapFile/v1"


def test_citemap_file_roundtrip() -> None:
    f = CiteMapFile(
        page="docs/page.md",
        export_git_sha="deadbee",
        bib_sha256="cd" * 32,
        docx_sha256="ef" * 32,
        occurrences=[
            CiteOccurrence(
                occ_id="00000001",
                citation_id="00000001",
                citekeys=["smith2020"],
                fingerprints={"smith2020": "doi:10.1000/x"},
                formatted="(Smith, 2020)",
                norm_start=6,
                norm_end=18,
            )
        ],
    )
    assert CiteMapFile.model_validate_json(f.model_dump_json()) == f


def test_review_comment_minimal() -> None:
    """ReviewComment com apenas id, author, text."""
    c = ReviewComment(id="1", author="Alice", text="Sugestão.")
    assert c.date is None
    assert c.anchor_text is None
    assert c.reply_of is None


def test_review_comment_with_date_and_anchor() -> None:
    """ReviewComment com data e texto âncora."""
    c = ReviewComment(
        id="2",
        author="Bob",
        text="Verificar referência.",
        anchor_text="parágrafo introdutório",
        date="2026-07-23T10:30:00Z",
    )
    assert c.reply_of is None


def test_review_comments_file_minimal() -> None:
    """ReviewCommentsFile vazio."""
    f = ReviewCommentsFile(page="docs/page.md")
    assert f.schema_version == "ReviewCommentsFile/v1"
    assert f.page == "docs/page.md"
    assert f.comments == []


def test_review_comments_file_with_comments() -> None:
    """ReviewCommentsFile com comentários."""
    comments = [
        ReviewComment(id="1", author="Alice", text="Revisar."),
        ReviewComment(id="2", author="Bob", text="Adicionar.", anchor_text="seção 2"),
    ]
    f = ReviewCommentsFile(page="docs/page.md", comments=comments)
    assert len(f.comments) == 2
    assert f.comments[0].author == "Alice"
    assert f.comments[1].anchor_text == "seção 2"


def test_review_comments_file_roundtrip() -> None:
    """ReviewCommentsFile roundtrip via JSON."""
    f = ReviewCommentsFile(
        page="docs/page.md",
        comments=[
            ReviewComment(
                id="1",
                author="Revisor",
                text="Ajustar referências.",
                anchor_text="metodologia",
                date="2026-07-23T09:15:00Z",
            )
        ],
    )
    assert ReviewCommentsFile.model_validate_json(f.model_dump_json()) == f


def test_review_event_minimal() -> None:
    """ReviewEvent com apenas kind e detail."""
    e = ReviewEvent(kind="citation-drop", detail="Citação removida.")
    assert e.occ_id is None
    assert e.citekeys == []
    assert e.author is None
    assert e.mark_excerpt is None


def test_review_event_with_context() -> None:
    """ReviewEvent com contexto de citação."""
    e = ReviewEvent(
        kind="citation-drop",
        detail="Citação smith2020 foi deletada.",
        occ_id="00000001",
        citekeys=["smith2020"],
        author="Coautor",
        mark_excerpt="(Smith, 2020)",
    )
    assert e.occ_id == "00000001"
    assert e.citekeys == ["smith2020"]


def test_review_events_file_minimal() -> None:
    """ReviewEventsFile vazio."""
    f = ReviewEventsFile(page="docs/page.md")
    assert f.schema_version == "ReviewEventsFile/v1"
    assert f.page == "docs/page.md"
    assert f.events == []


def test_review_events_file_with_events() -> None:
    """ReviewEventsFile com eventos."""
    events = [
        ReviewEvent(kind="citation-drop", detail="Dropou smith2020."),
        ReviewEvent(
            kind="ambiguous-anchor",
            detail="Âncora não localizada.",
            mark_excerpt="frase comum",
        ),
    ]
    f = ReviewEventsFile(page="docs/page.md", events=events)
    assert len(f.events) == 2
    assert f.events[0].kind == "citation-drop"


def test_review_events_file_roundtrip() -> None:
    """ReviewEventsFile roundtrip via JSON."""
    f = ReviewEventsFile(
        page="docs/page.md",
        events=[
            ReviewEvent(
                kind="unanchored-mark",
                detail="Marca sem posição no texto.",
                author="Coautor",
            )
        ],
    )
    assert ReviewEventsFile.model_validate_json(f.model_dump_json()) == f
