"""Tests pro sync_annotations escrevendo arquivo dedicado _annotations.md."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from par.core.note_paths import annotations_path, meta_path
from par.domains.paper.zotero import (
    ZoteroRef,
    compose_annotations_file,
    render_annotation,
)


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
        annotations=[
            {
                "annotationColor": "#ffd400",
                "annotationPageLabel": "1",
                "annotationType": "highlight",
                "annotationText": "Hello",
                "annotationSortIndex": "00001",
            }
        ],
        notes=[],
    )
    assert text.startswith("---\n")
    assert "paper: smith2024" in text
    assert "source: prumo-zotero-annotations" in text
    assert "<!-- BEGIN ZOTERO ANNOTATIONS -->" in text
    assert "<!-- END ZOTERO ANNOTATIONS -->" in text
    assert "Hello" in text


def test_sync_annotations_writes_dedicated_file(tmp_path: Path) -> None:
    from par.domains.paper.zotero import sync_annotations

    refs = tmp_path / "docs" / "references"
    refs.mkdir(parents=True)
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
        patch("par.domains.paper.zotero.check_zotero_running", return_value=True),
        patch(
            "par.domains.paper.zotero.resolve_citekey",
            return_value=ZoteroRef("users/13049353", "ABCD1234"),
        ),
        patch("par.domains.paper.zotero.fetch_children", return_value=fake_children),
        patch("par.domains.paper.zotero.fetch_annotations_index", return_value={}),
    ):
        report = sync_annotations(tmp_path)

    annot = annotations_path(tmp_path, "smith2024")
    assert annot.exists()
    assert "Hello" in annot.read_text()
    assert report["inserted"] == 1
    # _meta.md NÃO mexido
    assert "Hello" not in meta_p.read_text()


def test_sync_annotations_unchanged_when_content_identical(tmp_path: Path) -> None:
    """Re-sync com mesmo conteúdo do Zotero conta como `unchanged`, não `updated`."""
    from par.domains.paper.zotero import sync_annotations

    refs = tmp_path / "docs" / "references"
    refs.mkdir(parents=True)
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
        patch("par.domains.paper.zotero.check_zotero_running", return_value=True),
        patch(
            "par.domains.paper.zotero.resolve_citekey",
            return_value=ZoteroRef("users/13049353", "ABCD1234"),
        ),
        patch("par.domains.paper.zotero.fetch_children", return_value=fake_children),
        patch("par.domains.paper.zotero.fetch_annotations_index", return_value={}),
    ):
        sync_annotations(tmp_path)  # primeira chamada: inserted
        report = sync_annotations(tmp_path)  # segunda: idêntica

    assert report["unchanged"] == 1
    assert report["inserted"] == 0
    assert report["updated"] == 0


def test_sync_annotations_updated_when_content_changes(tmp_path: Path) -> None:
    """Re-sync com conteúdo diferente do Zotero conta como `updated`."""
    from par.domains.paper.zotero import sync_annotations

    refs = tmp_path / "docs" / "references"
    refs.mkdir(parents=True)
    (refs / "_references.bib").write_text("@article{smith2024, title={X}}\n")
    meta_p = meta_path(tmp_path, "smith2024")
    meta_p.parent.mkdir(parents=True, exist_ok=True)
    meta_p.write_text("---\nid: smith2024\n---\n\nbody\n")

    first = [
        {
            "itemType": "annotation",
            "annotationType": "highlight",
            "annotationColor": "#ffd400",
            "annotationPageLabel": "5",
            "annotationText": "First",
            "annotationSortIndex": "001",
        }
    ]
    second = [
        {
            "itemType": "annotation",
            "annotationType": "highlight",
            "annotationColor": "#ffd400",
            "annotationPageLabel": "5",
            "annotationText": "Second",
            "annotationSortIndex": "001",
        }
    ]

    with (
        patch("par.domains.paper.zotero.check_zotero_running", return_value=True),
        patch(
            "par.domains.paper.zotero.resolve_citekey",
            return_value=ZoteroRef("users/13049353", "ABCD1234"),
        ),
        patch("par.domains.paper.zotero.fetch_annotations_index", return_value={}),
    ):
        with patch("par.domains.paper.zotero.fetch_children", return_value=first):
            sync_annotations(tmp_path)
        with patch("par.domains.paper.zotero.fetch_children", return_value=second):
            report = sync_annotations(tmp_path)

    assert report["updated"] == 1
    assert report["inserted"] == 0
    assert "Second" in annotations_path(tmp_path, "smith2024").read_text()


# ---------------------------------------------------------------------------
# Caminho REAL: annotations são netas (top → attachment → annotation).
# `/children` do top-level devolve APENAS attachments/notes; as annotations vêm
# de `/items?itemType=annotation` e casam por `parentItem`. Medido em 2026-07-26
# (Zotero 9.0.6 + BBT): anexo 9JUI5P4Q tem 8 annotations e
# `/items/9JUI5P4Q/children` devolve n=0.
# ---------------------------------------------------------------------------


def _bootstrap(tmp_path: Path, *citekeys: str) -> None:
    refs = tmp_path / "docs" / "references"
    refs.mkdir(parents=True)
    (refs / "_references.bib").write_text(
        "".join(f"@article{{{ck}, title={{X}}}}\n" for ck in citekeys)
    )
    for ck in citekeys:
        meta_p = meta_path(tmp_path, ck)
        meta_p.parent.mkdir(parents=True, exist_ok=True)
        meta_p.write_text(f"---\nid: {ck}\n---\n\nbody\n")


def _attachment(key: str, parent: str) -> dict[str, Any]:
    return {
        "key": key,
        "version": 3300,
        "parentItem": parent,
        "itemType": "attachment",
        "linkMode": "imported_url",
        "title": "Full Text PDF",
        "contentType": "application/pdf",
        "filename": f"{key}.pdf",
        "tags": [],
        "relations": {},
    }


def _annotation(key: str, parent: str, text: str, sort_index: str) -> dict[str, Any]:
    return {
        "key": key,
        "version": 4711,
        "parentItem": parent,
        "itemType": "annotation",
        "annotationType": "highlight",
        "annotationAuthorName": "",
        "annotationText": text,
        "annotationComment": "",
        "annotationColor": "#ffd400",
        "annotationPageLabel": "12",
        "annotationSortIndex": sort_index,
        "annotationPosition": '{"pageIndex":3,"rects":[[70.9,516.5,525.3,527.6]]}',
        "tags": [],
        "relations": {},
        "dateAdded": "2026-05-11T18:22:41Z",
        "dateModified": "2026-05-11T18:22:41Z",
    }


def test_sync_annotations_collects_grandchild_annotations(tmp_path: Path) -> None:
    """`/children` só traz attachments — as annotations vêm do índice por parentItem."""
    from par.domains.paper.zotero import sync_annotations

    _bootstrap(tmp_path, "peng2024mismatch")
    children = [_attachment("9JUI5P4Q", "5MSIQBA3"), _attachment("SNAPSHOT1", "5MSIQBA3")]
    index = {
        "9JUI5P4Q": [
            _annotation("AN000001", "9JUI5P4Q", "MMR deficiency", "00003|000100|00010"),
            _annotation("AN000002", "9JUI5P4Q", "microsatellite instability", "00004|000100|0001"),
        ],
        "NAOMEU01": [_annotation("AN000009", "NAOMEU01", "de outro paper", "00001|000100|00010")],
    }

    with (
        patch("par.domains.paper.zotero.check_zotero_running", return_value=True),
        patch(
            "par.domains.paper.zotero.resolve_citekey",
            return_value=ZoteroRef("users/13049353", "5MSIQBA3"),
        ),
        patch("par.domains.paper.zotero.fetch_children", return_value=children),
        patch(
            "par.domains.paper.zotero.fetch_annotations_index",
            return_value=index,
        ),
    ):
        report = sync_annotations(tmp_path)

    text = annotations_path(tmp_path, "peng2024mismatch").read_text()
    assert "MMR deficiency" in text
    assert "microsatellite instability" in text
    assert "de outro paper" not in text
    assert report["inserted"] == 1
    assert report["no_children"] == []


def test_sync_annotations_fetches_index_once_per_library(tmp_path: Path) -> None:
    """Uma chamada a /items?itemType=annotation resolve a biblioteca inteira."""
    from par.domains.paper.zotero import sync_annotations

    _bootstrap(tmp_path, "a2024", "b2024", "c2024")
    children = [_attachment("ANEXO001", "TOP00001")]
    calls: list[str] = []

    def fake_index(library_path: str) -> dict[str, list[dict[str, Any]]]:
        calls.append(library_path)
        return {"ANEXO001": [_annotation("AN1", "ANEXO001", "Hello", "001")]}

    with (
        patch("par.domains.paper.zotero.check_zotero_running", return_value=True),
        patch(
            "par.domains.paper.zotero.resolve_citekey",
            return_value=ZoteroRef("users/13049353", "TOP00001"),
        ),
        patch("par.domains.paper.zotero.fetch_children", return_value=children),
        patch("par.domains.paper.zotero.fetch_annotations_index", fake_index),
    ):
        report = sync_annotations(tmp_path)

    assert calls == ["users/13049353"]
    assert report["inserted"] == 3


def test_sync_annotations_without_any_annotation_is_no_children(tmp_path: Path) -> None:
    """Item sem annotation nenhuma continua sendo 'sem anotações' — não é erro."""
    from par.domains.paper.zotero import sync_annotations

    _bootstrap(tmp_path, "smith2024")
    children = [_attachment("ANEXO001", "TOP00001")]

    with (
        patch("par.domains.paper.zotero.check_zotero_running", return_value=True),
        patch(
            "par.domains.paper.zotero.resolve_citekey",
            return_value=ZoteroRef("users/13049353", "TOP00001"),
        ),
        patch("par.domains.paper.zotero.fetch_children", return_value=children),
        patch("par.domains.paper.zotero.fetch_annotations_index", return_value={}),
    ):
        report = sync_annotations(tmp_path)

    assert report["no_children"] == ["smith2024"]
    assert report["errors"] == []
    assert report["inserted"] == 0
    assert not annotations_path(tmp_path, "smith2024").exists()


def test_sync_annotations_propagates_local_api_disabled(tmp_path: Path) -> None:
    """403 na Local API vira erro acionável — não some como 'sem anotações'."""
    import pytest

    from par.domains.paper.errors import PaperError
    from par.domains.paper.zotero import sync_annotations

    _bootstrap(tmp_path, "smith2024")

    with (
        patch("par.domains.paper.zotero.check_zotero_running", return_value=True),
        patch(
            "par.domains.paper.zotero.resolve_citekey",
            return_value=ZoteroRef("users/13049353", "TOP00001"),
        ),
        patch(
            "par.domains.paper.zotero.fetch_children",
            side_effect=PaperError("A API local do Zotero está desligada (HTTP 403)"),
        ),
        pytest.raises(PaperError),
    ):
        sync_annotations(tmp_path)
