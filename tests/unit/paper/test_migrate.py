"""Tests para prumo paper migrate-layout."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.core.note_paths import annotations_path, extract_path, meta_path
from prumo_assist.domains.paper.migrate import migrate_pj


def _bootstrap_legacy(tmp_path: Path) -> Path:
    """Cria pj com 1 nota legada incluindo callout extract + bloco zotero annotations."""
    refs = tmp_path / "docs" / "references"
    notes = refs / "papers"
    notes.mkdir(parents=True)
    (refs / "_references.bib").write_text("@article{smith2024, title={X}}\n")
    legacy = notes / "smith2024.md"
    legacy.write_text(
        "---\n"
        "id: smith2024\n"
        "title: Combi-Nado Fusion\n"
        "tldr: User notes\n"
        "---\n\n"
        "<!-- paper-extract:begin -->\n"
        "> ### TL;DR\n"
        "> auto summary\n"
        "<!-- paper-extract:end -->\n\n"
        "## Problema\n\n"
        "human notes here\n\n"
        "## Anotações do Zotero\n\n"
        "<!-- BEGIN ZOTERO ANNOTATIONS -->\n"
        "### 🟡 p. 5 — highlight\n"
        "> highlighted text\n"
        "<!-- END ZOTERO ANNOTATIONS -->\n"
    )
    return tmp_path


def test_migrate_creates_subdir_with_three_files(tmp_path: Path) -> None:
    pj = _bootstrap_legacy(tmp_path)
    report = migrate_pj(pj)
    assert report["migrated"] == ["smith2024"]
    assert meta_path(pj, "smith2024").is_file()
    assert extract_path(pj, "smith2024").is_file()
    assert annotations_path(pj, "smith2024").is_file()


def test_migrate_meta_keeps_yaml_and_human_body(tmp_path: Path) -> None:
    pj = _bootstrap_legacy(tmp_path)
    migrate_pj(pj)
    meta_text = meta_path(pj, "smith2024").read_text()
    assert "id: smith2024" in meta_text
    assert "tldr: User notes" in meta_text
    assert "## Problema" in meta_text
    assert "human notes here" in meta_text
    # callout e bloco zotero NÃO devem estar em _meta.md
    assert "<!-- paper-extract:begin -->" not in meta_text
    assert "<!-- BEGIN ZOTERO ANNOTATIONS -->" not in meta_text


def test_migrate_extract_md_has_callout(tmp_path: Path) -> None:
    pj = _bootstrap_legacy(tmp_path)
    migrate_pj(pj)
    text = extract_path(pj, "smith2024").read_text()
    assert "<!-- paper-extract:begin -->" in text
    assert "auto summary" in text
    assert text.startswith("---\n")
    assert "paper: smith2024" in text


def test_migrate_annotations_md_has_block(tmp_path: Path) -> None:
    pj = _bootstrap_legacy(tmp_path)
    migrate_pj(pj)
    text = annotations_path(pj, "smith2024").read_text()
    assert "<!-- BEGIN ZOTERO ANNOTATIONS -->" in text
    assert "highlighted text" in text
    assert "paper: smith2024" in text


def test_migrate_idempotent_when_already_migrated(tmp_path: Path) -> None:
    pj = _bootstrap_legacy(tmp_path)
    migrate_pj(pj)
    report = migrate_pj(pj)
    assert report["migrated"] == []
    assert report["already_migrated"] == ["smith2024"]


def test_migrate_legacy_without_callout_or_zotero_block(tmp_path: Path) -> None:
    refs = tmp_path / "docs" / "references"
    notes = refs / "papers"
    notes.mkdir(parents=True)
    (refs / "_references.bib").write_text("@article{plain2024, title={Y}}\n")
    (notes / "plain2024.md").write_text(
        "---\nid: plain2024\n---\n\n## Notas\n\nNada de zotero aqui.\n"
    )
    report = migrate_pj(tmp_path)
    assert report["migrated"] == ["plain2024"]
    assert meta_path(tmp_path, "plain2024").is_file()
    # _extract.md e _annotations.md NÃO devem ser criados (não havia conteúdo)
    assert not extract_path(tmp_path, "plain2024").exists()
    assert not annotations_path(tmp_path, "plain2024").exists()
