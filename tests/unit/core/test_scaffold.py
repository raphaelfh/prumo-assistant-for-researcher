"""Unit tests para core/scaffold.py (overlay + descoberta de módulos)."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.core import scaffold


def test_overlay_copies_into_empty_target(tmp_path: Path) -> None:
    src = tmp_path / "src"
    (src / "docs").mkdir(parents=True)
    (src / "docs" / "a.md").write_text("A")
    (src / "root.txt").write_text("R")
    target = tmp_path / "tgt"
    target.mkdir()

    copied, skipped = scaffold.overlay(src, target)

    assert (target / "docs" / "a.md").read_text() == "A"
    assert (target / "root.txt").read_text() == "R"
    assert sorted(copied) == ["docs/a.md", "root.txt"]
    assert skipped == []


def test_overlay_does_not_clobber_existing(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "keep.txt").write_text("FROM SRC")
    target = tmp_path / "tgt"
    target.mkdir()
    (target / "keep.txt").write_text("USER OWN")

    copied, skipped = scaffold.overlay(src, target)

    assert (target / "keep.txt").read_text() == "USER OWN"
    assert copied == []
    assert skipped == ["keep.txt"]


def test_overlay_is_idempotent(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "x.txt").write_text("X")
    target = tmp_path / "tgt"
    target.mkdir()

    scaffold.overlay(src, target)
    copied, skipped = scaffold.overlay(src, target)  # segunda vez

    assert copied == []
    assert skipped == ["x.txt"]
