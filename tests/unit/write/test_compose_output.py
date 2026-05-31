"""Tests para write_output (3 modos: drafts, into, out)."""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist.domains.write.compose import write_output


def test_write_output_drafts_creates_file(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    (pj / "docs" / "drafts").mkdir(parents=True)
    out = write_output(
        content="# Draft\n\nbody\n",
        pj_path=pj,
        kind="paper",
        mode="drafts",
        date="2026-05-03",
        slug="x",
    )
    assert out.output_path == pj / "docs" / "drafts" / "paper-2026-05-03-x.md"
    assert out.output_path.exists()
    assert out.mode == "drafts"
    assert "body" in out.output_path.read_text()


def test_write_output_into_replaces_block(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    (pj / "docs").mkdir(parents=True)
    target = pj / "docs" / "project_guide.md"
    target.write_text(
        "# Projeto\n\n"
        "<!-- write:begin kind=paper section=intro -->\n"
        "old content\n"
        "<!-- write:end -->\n\n"
        "Footer humano.\n"
    )
    out = write_output(
        content="new content",
        pj_path=pj,
        kind="paper",
        mode="into",
        date="2026-05-03",
        slug="x",
        into=target,
        section="intro",
    )
    text = target.read_text()
    assert "new content" in text
    assert "old content" not in text
    assert "Footer humano." in text  # preservado
    assert out.mode == "into"


def test_write_output_into_inserts_when_block_absent(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    (pj / "docs").mkdir(parents=True)
    target = pj / "docs" / "project_guide.md"
    target.write_text("# Projeto\n\nIntro existente.\n")
    write_output(
        content="generated",
        pj_path=pj,
        kind="paper",
        mode="into",
        date="2026-05-03",
        slug="x",
        into=target,
        section="methods",
    )
    text = target.read_text()
    assert "<!-- write:begin kind=paper section=methods -->" in text
    assert "generated" in text
    assert "Intro existente." in text


def test_write_output_out_writes_to_path(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    target = tmp_path / "anywhere" / "file.md"
    out = write_output(
        content="# X\n",
        pj_path=pj,
        kind="paper",
        mode="out",
        date="2026-05-03",
        slug="x",
        out=target,
    )
    assert target.exists()
    assert out.mode == "out"


def test_write_output_out_refuses_overwrite_without_force(tmp_path: Path) -> None:
    target = tmp_path / "f.md"
    target.write_text("existing")
    with pytest.raises(FileExistsError):
        write_output(
            content="new",
            pj_path=tmp_path,
            kind="paper",
            mode="out",
            date="2026-05-03",
            slug="x",
            out=target,
        )


def test_write_output_out_force_overwrites(tmp_path: Path) -> None:
    target = tmp_path / "f.md"
    target.write_text("existing")
    write_output(
        content="new",
        pj_path=tmp_path,
        kind="paper",
        mode="out",
        date="2026-05-03",
        slug="x",
        out=target,
        force=True,
    )
    assert target.read_text() == "new"
