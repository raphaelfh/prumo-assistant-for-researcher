"""Tests pro normalizador Obsidian → Pandoc."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.core.obsidian import normalize_markdown, split_frontmatter


def test_split_frontmatter_extracts_yaml() -> None:
    text = "---\nfoo: bar\n---\n\nbody here\n"
    meta, body = split_frontmatter(text)
    assert meta == {"foo": "bar"}
    assert body == "body here\n"


def test_split_frontmatter_returns_empty_when_absent() -> None:
    text = "no frontmatter here"
    meta, body = split_frontmatter(text)
    assert meta == {}
    assert body == text


def test_citation_with_alias_keeps_only_key() -> None:
    out = normalize_markdown("See [[@smith2024|Smith et al.]] for details.")
    assert out == "See [@smith2024] for details."


def test_wikilink_with_alias_replaces_with_alias() -> None:
    out = normalize_markdown("Refer to [[some-page|that page]].")
    assert out == "Refer to that page."


def test_wikilink_without_alias_keeps_target() -> None:
    out = normalize_markdown("See [[some-page]].")
    assert out == "See some-page."


def test_image_embed_with_missing_file_keeps_path() -> None:
    out = normalize_markdown("![[fig.png]]", page_dir=Path("/no/such/dir"))
    assert out == "![](fig.png)"


def test_image_embed_with_pdf_anchor_drops_silently() -> None:
    out = normalize_markdown("![[paper.pdf#page=3]]")
    assert out == ""


def test_callout_header_becomes_bold_title() -> None:
    text = "> [!note] Important\n> body line\n"
    out = normalize_markdown(text)
    assert "**Important**" in out
    assert "body line" in out


def test_block_id_anchor_is_stripped() -> None:
    out = normalize_markdown("Some claim. ^abc123\nNext line.")
    assert "^abc123" not in out
    assert "Some claim." in out


def test_code_block_is_preserved() -> None:
    text = "Before\n```python\n[[wikilink]]\n```\nAfter"
    out = normalize_markdown(text)
    assert "[[wikilink]]" in out  # within code block
