"""Tests do orquestrador prumo paper sync-all."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from prumo_assist.domains.paper.sync_all import sync_all


def _bootstrap(tmp_path: Path) -> Path:
    refs = tmp_path / "references"
    (refs / "notes").mkdir(parents=True)
    (refs / "_references.bib").write_text("@article{smith2024, title={X}}\n")
    return tmp_path


def test_sync_all_runs_three_phases(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    with (
        patch(
            "prumo_assist.domains.paper.sync_all.sync",
            return_value={"created": 1, "updated": 0, "orphans": []},
        ) as m_sync,
        patch(
            "prumo_assist.domains.paper.sync_all.sync_annotations",
            return_value={"inserted": 2, "updated": 0, "unchanged": 0,
                          "no_meta": [], "no_resolve": [], "no_children": [], "errors": []},
        ) as m_annot,
        patch(
            "prumo_assist.domains.paper.sync_all.sync_notes",
            return_value={"inserted": 3, "updated": 0, "unchanged": 0,
                          "no_meta": [], "no_resolve": [], "errors": []},
        ) as m_notes,
    ):
        report = sync_all(pj)
    m_sync.assert_called_once_with(pj)
    m_annot.assert_called_once_with(pj)
    m_notes.assert_called_once_with(pj)
    assert report["sync"]["created"] == 1
    assert report["annotations"]["inserted"] == 2
    assert report["notes"]["inserted"] == 3


def test_sync_all_reports_zotero_offline_without_crashing(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    with (
        patch(
            "prumo_assist.domains.paper.sync_all.sync",
            return_value={"created": 1, "updated": 0, "orphans": []},
        ),
        patch(
            "prumo_assist.domains.paper.sync_all.sync_annotations",
            side_effect=ConnectionError("Zotero offline"),
        ),
        patch(
            "prumo_assist.domains.paper.sync_all.sync_notes",
            side_effect=ConnectionError("Zotero offline"),
        ),
    ):
        report = sync_all(pj)
    assert report["sync"]["created"] == 1
    assert report["annotations"] is None
    assert report["notes"] is None
    assert any("Zotero offline" in w for w in report["warnings"])
