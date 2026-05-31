"""Tests para sync-notes: child notes do Zotero → note__<itemKey>__<slug>.md."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml

from prumo_assist.core.note_paths import child_note_path, meta_path
from prumo_assist.domains.paper.zotero import (
    _replace_note_block,
    compose_child_note_file,
    note_title_from_html,
    render_child_note,
    sync_notes,
)


def test_note_title_from_html_uses_first_heading() -> None:
    html = "<h1>Ideias da Introdução</h1><p>corpo</p>"
    assert note_title_from_html(html) == "Ideias da Introdução"


def test_note_title_from_html_uses_first_line_when_no_heading() -> None:
    html = "<p>Crítica metodológica importante</p><p>resto</p>"
    assert note_title_from_html(html) == "Crítica metodológica importante"


def test_note_title_from_html_empty_is_untitled() -> None:
    assert note_title_from_html("") == "(sem título)"
    assert note_title_from_html("<p></p>") == "(sem título)"


def _sample_note() -> dict[str, object]:
    return {
        "itemType": "note",
        "key": "ABCD1234",
        "note": "<h1>Ideias da Introdução</h1><p>risk prediction ajuda</p>",
        "dateAdded": "2026-04-30T14:23:00Z",
        "dateModified": "2026-05-02T09:11:00Z",
        "tags": [{"tag": "hipoteses"}, {"tag": "datasets"}],
    }


def test_render_child_note_has_begin_end_block() -> None:
    out = render_child_note(_sample_note())
    assert out.startswith("<!-- BEGIN ZOTERO -->")
    assert out.endswith("<!-- END ZOTERO -->")
    assert "risk prediction ajuda" in out


def test_compose_child_note_file_has_stable_yaml() -> None:
    text = compose_child_note_file("smith2024", _sample_note())
    assert text.startswith("---\n")
    fm = yaml.safe_load(text.split("---", 2)[1])
    assert fm["paper"] == "smith2024"
    assert fm["zotero_item_key"] == "ABCD1234"
    assert fm["source"] == "zotero-child-note"
    assert fm["date_added"] == "2026-04-30T14:23:00Z"
    assert fm["date_modified"] == "2026-05-02T09:11:00Z"
    assert fm["title"] == "Ideias da Introdução"
    assert fm["tags"] == ["hipoteses", "datasets"]
    assert "<!-- BEGIN ZOTERO -->" in text
    assert "<!-- END ZOTERO -->" in text


def test_compose_child_note_file_escapes_title_with_colon() -> None:
    note: dict[str, Any] = {
        "itemType": "note",
        "key": "ABCD1234",
        "note": "<h1>Método: uma revisão</h1><p>x</p>",
    }
    text = compose_child_note_file("smith2024", note)
    fm = yaml.safe_load(text.split("---", 2)[1])
    assert fm["title"] == "Método: uma revisão"
    assert fm["zotero_item_key"] == "ABCD1234"


def test_compose_child_note_file_escapes_tag_specials() -> None:
    note: dict[str, Any] = {
        "itemType": "note",
        "key": "EFGH5678",
        "note": "<p>corpo</p>",
        "tags": [{"tag": "a, b"}, {"tag": "c: d"}],
    }
    text = compose_child_note_file("doe2025", note)
    fm = yaml.safe_load(text.split("---", 2)[1])
    assert fm["tags"] == ["a, b", "c: d"]


def test_compose_child_note_file_handles_missing_optional_fields() -> None:
    note = {"itemType": "note", "key": "EFGH5678", "note": "<p>corpo</p>"}
    text = compose_child_note_file("doe2025", note)
    assert "zotero_item_key: EFGH5678" in text
    assert "date_added: ''" in text
    assert "tags: []" in text


def _bootstrap_pj(tmp_path: Path, citekey: str = "smith2024") -> Path:
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "_references.bib").write_text(f"@article{{{citekey}, title={{X}}}}\n")
    meta_p = meta_path(tmp_path, citekey)
    meta_p.parent.mkdir(parents=True, exist_ok=True)
    meta_p.write_text(f"---\nid: {citekey}\n---\n\nbody\n")
    return tmp_path


def test_sync_notes_writes_one_file_per_child_note(tmp_path: Path) -> None:
    pj = _bootstrap_pj(tmp_path)
    children = [_sample_note()]
    with (
        patch("prumo_assist.domains.paper.zotero.check_zotero_running", return_value=True),
        patch("prumo_assist.domains.paper.zotero.resolve_citekey", return_value=(1, "PARENT01")),
        patch("prumo_assist.domains.paper.zotero.fetch_children", return_value=children),
    ):
        report = sync_notes(pj)
    out = child_note_path(pj, "smith2024", "ABCD1234", "ideias-da-introducao")
    assert out.exists()
    assert "risk prediction ajuda" in out.read_text()
    assert report["inserted"] == 1


def test_sync_notes_idempotent_second_run(tmp_path: Path) -> None:
    pj = _bootstrap_pj(tmp_path)
    children = [_sample_note()]
    with (
        patch("prumo_assist.domains.paper.zotero.check_zotero_running", return_value=True),
        patch("prumo_assist.domains.paper.zotero.resolve_citekey", return_value=(1, "PARENT01")),
        patch("prumo_assist.domains.paper.zotero.fetch_children", return_value=children),
    ):
        sync_notes(pj)
        report = sync_notes(pj)
    assert report["inserted"] == 0
    assert report["unchanged"] == 1


def test_sync_notes_preserves_human_text_outside_block(tmp_path: Path) -> None:
    pj = _bootstrap_pj(tmp_path)
    children = [_sample_note()]
    with (
        patch("prumo_assist.domains.paper.zotero.check_zotero_running", return_value=True),
        patch("prumo_assist.domains.paper.zotero.resolve_citekey", return_value=(1, "PARENT01")),
        patch("prumo_assist.domains.paper.zotero.fetch_children", return_value=children),
    ):
        sync_notes(pj)
        out = child_note_path(pj, "smith2024", "ABCD1234", "ideias-da-introducao")
        original = out.read_text()
        out.write_text(original + "\n## Minha anotação humana\n\ntexto meu\n")
        updated = [dict(_sample_note(), note="<h1>Ideias da Introdução</h1><p>NOVO corpo</p>")]
        with patch("prumo_assist.domains.paper.zotero.fetch_children", return_value=updated):
            sync_notes(pj)
    final = out.read_text()
    assert "NOVO corpo" in final
    assert "Minha anotação humana" in final  # texto humano preservado


def test_replace_note_block_without_end_marker_regenerates() -> None:
    existing = "conteúdo sem marcador algum\n"
    new = "---\npaper: x\n---\n\n<!-- BEGIN ZOTERO -->\ncorpo\n<!-- END ZOTERO -->\n"
    out = _replace_note_block(existing, new)
    assert out == new  # regenera integralmente quando não há END


def test_sync_notes_raises_when_zotero_offline(tmp_path: Path) -> None:
    import pytest

    pj = _bootstrap_pj(tmp_path)
    with (
        patch("prumo_assist.domains.paper.zotero.check_zotero_running", return_value=False),
        pytest.raises(ConnectionError),
    ):
        sync_notes(pj)


def test_api_reexports_sync_notes_and_sync_all() -> None:
    from prumo_assist.domains.paper import api

    assert hasattr(api, "sync_notes")
    assert hasattr(api, "sync_all")
