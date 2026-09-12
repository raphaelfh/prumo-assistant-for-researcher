"""Tests para refs faltantes e citekeys usados no compose (gramática única)."""

from __future__ import annotations

from pathlib import Path

from par.domains.write.compose import extract_missing_refs, write_output


def test_extract_missing_refs_captures_descriptions() -> None:
    text = "Claim [REF FALTANTE: coorte multicêntrica]. Outra [REF FALTANTE: guideline 2025]."
    assert extract_missing_refs(text) == ["coorte multicêntrica", "guideline 2025"]


def test_extract_missing_refs_empty() -> None:
    assert extract_missing_refs("texto sem pendências") == []


def test_write_output_reports_citations_in_both_flavors(tmp_path: Path) -> None:
    content = "Intro [@smith2024cohort] e bracketed [@jones2023trial] e narrativa @lee2025core.\n"
    result = write_output(
        content=content,
        scope=tmp_path,
        kind="paper",
        mode="drafts",
        date="2026-07-22",
        slug="s1",
    )
    assert result.citations_used == ["jones2023trial", "lee2025core", "smith2024cohort"]


def test_write_output_does_not_truncate_composite_keys(tmp_path: Path) -> None:
    result = write_output(
        content="[@vanDijk2019:pt2]\n",
        scope=tmp_path,
        kind="paper",
        mode="drafts",
        date="2026-07-22",
        slug="s2",
    )
    assert result.citations_used == ["vanDijk2019:pt2"]
