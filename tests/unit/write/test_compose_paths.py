"""Tests para resolve_template + compose_path."""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist.domains.write.compose import compose_path, resolve_template


def test_resolve_template_default_from_skill_bundle(tmp_path: Path) -> None:
    """Plugin ships skills/write-<kind>/template.md; deve ser default."""
    out = resolve_template(pj_path=tmp_path, kind="paper")
    assert out is not None
    assert out.name == "template.md"
    assert "skills/write-paper" in str(out) or "_skills/write-paper" in str(out)


def test_resolve_template_project_override(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    over = pj / ".claude" / "writing_templates"
    over.mkdir(parents=True)
    (over / "paper.md").write_text("# Project Paper\n")
    out = resolve_template(pj_path=pj, kind="paper")
    assert out == over / "paper.md"


def test_resolve_template_explicit_override(tmp_path: Path) -> None:
    custom = tmp_path / "custom.md"
    custom.write_text("# Custom\n")
    out = resolve_template(
        pj_path=tmp_path, kind="paper", explicit=custom,
    )
    assert out == custom


def test_resolve_template_explicit_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_template(
            pj_path=tmp_path, kind="paper", explicit=tmp_path / "nope.md",
        )


def test_resolve_template_invalid_kind(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="kind"):
        resolve_template(pj_path=tmp_path, kind="bogus")  # type: ignore[arg-type]


def test_compose_path_drafts_default(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    (pj / "docs").mkdir(parents=True)
    out = compose_path(
        pj_path=pj, kind="paper", date="2026-05-03", slug="combinado",
    )
    assert out == pj / "docs" / "drafts" / "paper-2026-05-03-combinado.md"


def test_compose_path_into_uses_path_arg(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    (pj / "docs").mkdir(parents=True)
    target = pj / "docs" / "project_guide.md"
    target.write_text("# Projeto\n")
    out = compose_path(
        pj_path=pj, kind="paper", date="2026-05-03", slug="x", into=target,
    )
    assert out == target


def test_compose_path_out_uses_path_arg(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    target = tmp_path / "any" / "place.md"
    out = compose_path(
        pj_path=pj, kind="paper", date="2026-05-03", slug="x", out=target,
    )
    assert out == target


def test_compose_path_into_and_out_conflict(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        compose_path(
            pj_path=tmp_path, kind="paper", date="2026-05-03", slug="x",
            into=tmp_path / "a.md", out=tmp_path / "b.md",
        )
