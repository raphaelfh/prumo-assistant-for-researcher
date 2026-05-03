"""Tests pro sync_annotations escrevendo arquivo dedicado _annotations.md."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from prumo_assist.core.note_paths import annotations_path, meta_path
from prumo_assist.domains.paper.zotero import compose_annotations_file, render_annotation


def test_render_annotation_yellow_highlight() -> None:
    data = {
        "annotationColor": "#ffd400",
        "annotationPageLabel": "5",
        "annotationType": "highlight",
        "annotationText": "Combinado fusion improves...",
        "annotationComment": "verificar",
    }
    lines = render_annotation(data)
    assert any("🟡" in line for line in lines)
    assert any("p. 5" in line for line in lines)
    assert any("> Combinado fusion improves..." in line for line in lines)
    assert any("verificar" in line for line in lines)


def test_compose_annotations_file_has_yaml_and_block() -> None:
    text = compose_annotations_file(
        citekey="smith2024",
        annotations=[{
            "annotationColor": "#ffd400",
            "annotationPageLabel": "1",
            "annotationType": "highlight",
            "annotationText": "Hello",
            "annotationSortIndex": "00001",
        }],
        notes=[],
    )
    assert text.startswith("---\n")
    assert "paper: smith2024" in text
    assert "source: prumo-zotero-annotations" in text
    assert "<!-- BEGIN ZOTERO ANNOTATIONS -->" in text
    assert "<!-- END ZOTERO ANNOTATIONS -->" in text
    assert "Hello" in text


def test_sync_annotations_writes_dedicated_file(tmp_path: Path) -> None:
    from prumo_assist.domains.paper.zotero import sync_annotations

    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "_references.bib").write_text("@article{smith2024, title={X}}\n")
    meta_p = meta_path(tmp_path, "smith2024")
    meta_p.parent.mkdir(parents=True, exist_ok=True)
    meta_p.write_text("---\nid: smith2024\n---\n\nbody\n")

    fake_children = [
        {
            "itemType": "annotation",
            "annotationType": "highlight",
            "annotationColor": "#ffd400",
            "annotationPageLabel": "5",
            "annotationText": "Hello",
            "annotationSortIndex": "001",
        }
    ]

    with (
        patch("prumo_assist.domains.paper.zotero.check_zotero_running", return_value=True),
        patch("prumo_assist.domains.paper.zotero.resolve_citekey", return_value=(1, "ABCD1234")),
        patch("prumo_assist.domains.paper.zotero.fetch_children", return_value=fake_children),
    ):
        report = sync_annotations(tmp_path)

    annot = annotations_path(tmp_path, "smith2024")
    assert annot.exists()
    assert "Hello" in annot.read_text()
    assert report["inserted"] == 1
    # _meta.md NÃO mexido
    assert "Hello" not in meta_p.read_text()
