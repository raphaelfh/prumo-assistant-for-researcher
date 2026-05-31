"""Unit tests para core/scaffold.py (overlay + descoberta de módulos)."""

from __future__ import annotations

from pathlib import Path

import pytest

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


@pytest.fixture
def fake_modules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Cria templates/modules/<m>/_module.toml fake e aponta scaffold para ele."""
    root = tmp_path / "templates" / "modules"
    clin = root / "clinical"
    clin.mkdir(parents=True)
    (clin / "_module.toml").write_text(
        'description = "Camada clínica"\n'
        'when_to_use = "Estudo clínico"\n'
        'anchor = "docs/protocol.md"\n'
    )
    (clin / "docs").mkdir()
    (clin / "docs" / "protocol.md").write_text("# protocolo")
    bare = root / "bare"  # módulo sem _module.toml
    bare.mkdir()
    monkeypatch.setattr(scaffold, "_modules_root", lambda: root)
    return root


def test_discover_modules_reads_metadata(fake_modules: Path) -> None:
    mods = scaffold.discover_modules()
    names = [m.name for m in mods]
    assert names == ["bare", "clinical"]  # ordenado
    clin = scaffold.get_module("clinical")
    assert clin is not None
    assert clin.description == "Camada clínica"
    assert clin.anchor == "docs/protocol.md"


def test_discover_modules_tolerates_missing_metadata(fake_modules: Path) -> None:
    bare = scaffold.get_module("bare")
    assert bare is not None
    assert bare.description == ""
    assert bare.anchor is None


def test_get_module_unknown_returns_none(fake_modules: Path) -> None:
    assert scaffold.get_module("nope") is None
