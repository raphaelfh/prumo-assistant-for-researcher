"""Tests pro resolvedor de estilos CSL."""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist.core.csl import CslNotFoundError, list_zotero_styles, resolve_csl


def test_list_returns_sorted_basenames(tmp_path: Path) -> None:
    (tmp_path / "z-style.csl").write_text("<style/>", encoding="utf-8")
    (tmp_path / "a-style.csl").write_text("<style/>", encoding="utf-8")
    (tmp_path / "ignored.txt").write_text("nope", encoding="utf-8")

    assert list_zotero_styles(tmp_path) == ["a-style", "z-style"]


def test_list_returns_empty_when_dir_missing(tmp_path: Path) -> None:
    assert list_zotero_styles(tmp_path / "no-such-dir") == []


def test_resolve_finds_existing_style(tmp_path: Path) -> None:
    target = tmp_path / "vancouver.csl"
    target.write_text("<style/>", encoding="utf-8")
    assert resolve_csl("vancouver", styles_dir=tmp_path) == target
    assert resolve_csl("vancouver.csl", styles_dir=tmp_path) == target


def test_resolve_raises_with_listing_when_missing(tmp_path: Path) -> None:
    (tmp_path / "apa.csl").write_text("<style/>", encoding="utf-8")
    with pytest.raises(CslNotFoundError) as ei:
        resolve_csl("nonexistent", styles_dir=tmp_path)
    assert "apa" in str(ei.value)
