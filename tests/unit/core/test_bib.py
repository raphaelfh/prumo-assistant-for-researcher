"""Smoke tests pro parser de _references.bib (BBT)."""

from __future__ import annotations

from prumo_assist.core.bib import extract_field, parse_bib


def test_parses_minimal_entry() -> None:
    text = "@article{smith2024,\n  title = {A title},\n  year = 2024\n}\n"
    entries = parse_bib(text)
    assert len(entries) == 1
    e = entries[0]
    assert e.entry_type == "article"
    assert e.citekey == "smith2024"
    assert "title" in e.body


def test_skips_string_macros_and_comments() -> None:
    text = (
        '@string{j = "Journal Of Things"}\n'
        "@comment{this is a comment}\n"
        "@article{key1, title = {x}}\n"
    )
    entries = parse_bib(text)
    assert len(entries) == 1
    assert entries[0].citekey == "key1"


def test_handles_nested_braces_in_field() -> None:
    text = "@article{key, title = {{Combi-Nado} Fusion}}\n"
    entries = parse_bib(text)
    assert len(entries) == 1
    assert extract_field(entries[0].body, "title") == "{Combi-Nado} Fusion"


def test_extract_field_supports_three_delimiters() -> None:
    body = 'title = {Brace}, author = "Quoted Name", year = 2024'
    assert extract_field(body, "title") == "Brace"
    assert extract_field(body, "author") == "Quoted Name"
    assert extract_field(body, "year") == "2024"


def test_extract_field_returns_none_when_absent() -> None:
    assert extract_field("title = {x}", "doi") is None
