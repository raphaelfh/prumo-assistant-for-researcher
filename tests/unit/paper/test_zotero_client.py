"""Tests diretos das funções de cliente/render do zotero.py (sem rede real)."""

from __future__ import annotations

import urllib.error
from unittest.mock import patch

from prumo_assist.domains.paper.zotero import (
    html_to_markdown,
    render_note,
    resolve_citekey,
    split_children,
)


def test_html_to_markdown_basic_formatting() -> None:
    html = "<p>Olá <strong>mundo</strong> e <em>itálico</em></p>"
    out = html_to_markdown(html)
    assert "**mundo**" in out
    assert "*itálico*" in out
    assert "<p>" not in out


def test_html_to_markdown_headings_and_lists() -> None:
    html = "<h2>Título</h2><ul><li>um</li><li>dois</li></ul>"
    out = html_to_markdown(html)
    assert "## Título" in out
    assert "- um" in out
    assert "- dois" in out


def test_html_to_markdown_unescapes_entities() -> None:
    html = "<p>a &amp; b &lt; c</p>"
    out = html_to_markdown(html)
    assert "a & b < c" in out


def test_html_to_markdown_collapses_blank_lines() -> None:
    html = "<p>a</p><p></p><p></p><p>b</p>"
    out = html_to_markdown(html)
    assert "\n\n\n" not in out


def test_split_children_separates_annotations_and_notes() -> None:
    children = [
        {"itemType": "annotation", "annotationText": "x"},
        {"itemType": "note", "note": "<p>y</p>"},
        {"itemType": "attachment", "filename": "z.pdf"},
    ]
    annotations, notes = split_children(children)
    assert len(annotations) == 1
    assert len(notes) == 1
    # attachment descartado
    assert annotations[0]["annotationText"] == "x"
    assert notes[0]["note"] == "<p>y</p>"


def test_split_children_empty() -> None:
    annotations, notes = split_children([])
    assert annotations == []
    assert notes == []


def test_render_note_extracts_title_from_first_line() -> None:
    note = {"note": "<h1>Minha nota</h1><p>corpo da nota</p>"}
    lines = render_note(note)
    joined = "\n".join(lines)
    assert "Minha nota" in joined
    assert "corpo da nota" in joined


def test_render_note_empty_marks_vazia() -> None:
    note = {"note": ""}
    lines = render_note(note)
    joined = "\n".join(lines)
    assert "vazia" in joined.lower()


def test_resolve_citekey_exact_match() -> None:
    rpc_response = {
        "jsonrpc": "2.0",
        "result": [
            {"citationKey": "smith2024", "itemKey": "ABCD1234", "library": {"id": 1}},
        ],
        "id": 1,
    }
    with patch("prumo_assist.domains.paper.zotero._http_post_json", return_value=rpc_response):
        result = resolve_citekey("smith2024")
    assert result == (1, "ABCD1234")


def test_resolve_citekey_falls_back_to_first_result() -> None:
    rpc_response = {
        "jsonrpc": "2.0",
        "result": [
            {"citationKey": "other2023", "itemKey": "ZZZZ9999", "library": {"id": 3}},
        ],
        "id": 1,
    }
    with patch("prumo_assist.domains.paper.zotero._http_post_json", return_value=rpc_response):
        result = resolve_citekey("smith2024")
    assert result == (3, "ZZZZ9999")


def test_resolve_citekey_empty_result_is_none() -> None:
    with patch(
        "prumo_assist.domains.paper.zotero._http_post_json",
        return_value={"jsonrpc": "2.0", "result": [], "id": 1},
    ):
        assert resolve_citekey("missing") is None


def test_resolve_citekey_network_error_is_none() -> None:
    with patch(
        "prumo_assist.domains.paper.zotero._http_post_json",
        side_effect=urllib.error.URLError("connection refused"),
    ):
        assert resolve_citekey("smith2024") is None


def test_resolve_citekey_non_dict_response_is_none() -> None:
    with patch("prumo_assist.domains.paper.zotero._http_post_json", return_value=["unexpected"]):
        assert resolve_citekey("smith2024") is None
