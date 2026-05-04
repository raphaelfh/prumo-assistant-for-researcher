"""Tests para ComposeInputs/v1 + WriteOutput/v1."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from prumo_assist.domains.write.schemas.v1 import (
    ComposeInputs,
    FindingSummary,
    PaperSummary,
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
            output_path=Path("x.md"), mode="bogus", kind="paper",  # type: ignore[arg-type]
            sections_filled=[], sections_skipped=[], citations_used=[],
            references_missing=[], words_generated=0,
        )


def test_write_output_invalid_kind() -> None:
    with pytest.raises(ValidationError):
        WriteOutput(
            output_path=Path("x.md"), mode="drafts", kind="bogus",  # type: ignore[arg-type]
            sections_filled=[], sections_skipped=[], citations_used=[],
            references_missing=[], words_generated=0,
        )
