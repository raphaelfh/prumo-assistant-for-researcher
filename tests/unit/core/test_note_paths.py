"""Tests para helpers de path do layout α."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.core.note_paths import (
    annotations_path,
    child_note_path,
    extract_path,
    meta_path,
    note_dir,
    slugify,
)


def test_note_dir_returns_subdir(tmp_path: Path) -> None:
    out = note_dir(tmp_path, "smith2024")
    assert out == tmp_path / "references" / "notes" / "smith2024"


def test_meta_path(tmp_path: Path) -> None:
    out = meta_path(tmp_path, "smith2024")
    assert out == tmp_path / "references" / "notes" / "smith2024" / "_meta.md"


def test_extract_path(tmp_path: Path) -> None:
    out = extract_path(tmp_path, "smith2024")
    assert out == tmp_path / "references" / "notes" / "smith2024" / "_extract.md"


def test_annotations_path(tmp_path: Path) -> None:
    out = annotations_path(tmp_path, "smith2024")
    assert out == tmp_path / "references" / "notes" / "smith2024" / "_annotations.md"


def test_child_note_path_with_itemkey_and_slug(tmp_path: Path) -> None:
    out = child_note_path(tmp_path, "smith2024", "ABCD1234", "ideias-da-introducao")
    assert (
        out
        == tmp_path
        / "references"
        / "notes"
        / "smith2024"
        / "note__ABCD1234__ideias-da-introducao.md"
    )


def test_slugify_converts_to_kebab() -> None:
    assert slugify("Ideias da Introdução") == "ideias-da-introducao"


def test_slugify_strips_punctuation() -> None:
    assert slugify("Crítica Metodológica: parte 2!") == "critica-metodologica-parte-2"


def test_slugify_truncates_to_30_chars() -> None:
    long = "uma frase muito longa que ultrapassa trinta caracteres facilmente"
    out = slugify(long)
    assert len(out) <= 30
    assert not out.endswith("-")  # sem hífen pendurado


def test_slugify_handles_empty() -> None:
    assert slugify("") == "untitled"
    assert slugify("   ") == "untitled"


def test_iter_note_meta_files_includes_alpha(tmp_path: Path) -> None:
    from prumo_assist.core.note_paths import iter_note_meta_files

    notes = tmp_path / "references" / "notes"
    (notes / "smith2024").mkdir(parents=True)
    (notes / "smith2024" / "_meta.md").write_text("---\nid: smith2024\n---\n")
    (notes / "doe2025").mkdir()
    (notes / "doe2025" / "_meta.md").write_text("---\nid: doe2025\n---\n")
    out = iter_note_meta_files(tmp_path)
    assert [p.parent.name for p in out] == ["doe2025", "smith2024"]


def test_iter_note_meta_files_includes_legacy_during_transition(tmp_path: Path) -> None:
    from prumo_assist.core.note_paths import citekey_from_meta_path, iter_note_meta_files

    notes = tmp_path / "references" / "notes"
    notes.mkdir(parents=True)
    (notes / "legacy_one.md").write_text("---\nid: legacy_one\n---\n")
    (notes / "alpha_one").mkdir()
    (notes / "alpha_one" / "_meta.md").write_text("---\nid: alpha_one\n---\n")
    out = iter_note_meta_files(tmp_path)
    assert len(out) == 2
    keys = {citekey_from_meta_path(p) for p in out}
    assert keys == {"alpha_one", "legacy_one"}


def test_iter_note_meta_files_prefers_alpha_when_both_exist(tmp_path: Path) -> None:
    from prumo_assist.core.note_paths import iter_note_meta_files

    notes = tmp_path / "references" / "notes"
    notes.mkdir(parents=True)
    (notes / "smith2024.md").write_text("---\nid: smith2024\n---\n")
    (notes / "smith2024").mkdir()
    (notes / "smith2024" / "_meta.md").write_text("---\nid: smith2024\n---\nALPHA\n")
    out = iter_note_meta_files(tmp_path)
    assert len(out) == 1
    assert "ALPHA" in out[0].read_text()
