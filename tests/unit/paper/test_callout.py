"""Tests pro render e write do callout estruturado."""

from __future__ import annotations

from prumo_assist.domains.paper.callout import (
    EXTRACT_BEGIN,
    EXTRACT_END,
    ExtractionSection,
    parse_extraction_template,
    read_callout,
    render_callout,
    write_callout,
)


def test_parse_template_extracts_section_names_and_instructions() -> None:
    text = "# Header\n\n### TL;DR\n<!-- escreva 2-3 frases -->\n\n### PICOT\n<!-- 5 bullets -->\n"
    sections = parse_extraction_template(text)
    assert [s.name for s in sections] == ["TL;DR", "PICOT"]
    assert "2-3 frases" in sections[0].instruction
    assert "5 bullets" in sections[1].instruction


def test_render_callout_includes_meta_and_sections() -> None:
    sections = [
        ExtractionSection(name="TL;DR", instruction="x"),
        ExtractionSection(name="PICOT", instruction="y"),
    ]
    out = render_callout(
        sections,
        {"TL;DR": "Two-line summary.", "PICOT": "P: ...\nI: ..."},
        model="claude-test",
        date="2026-04-28",
    )
    assert out.startswith(EXTRACT_BEGIN)
    assert out.endswith(EXTRACT_END)
    assert "claude-test" in out
    assert "Two-line summary." in out
    assert "> P: ..." in out
    assert "> I: ..." in out


def test_render_callout_uses_pendente_for_missing_content() -> None:
    sections = [ExtractionSection(name="TL;DR", instruction="x")]
    out = render_callout(sections, {}, model="m", date="2026-04-28")
    assert "_(pendente)_" in out


def test_write_callout_inserts_after_frontmatter() -> None:
    note_text = "---\nid: smith2024\n---\n\nHuman section.\n"
    callout = render_callout([], {}, model="m", date="2026-04-28")
    out = write_callout(note_text, callout)
    assert out.startswith("---\nid: smith2024\n---\n")
    assert callout in out


def test_write_callout_replaces_existing() -> None:
    note_text = (
        f"---\nid: x\n---\n\n{EXTRACT_BEGIN}\n> old content\n{EXTRACT_END}\n\nManual section.\n"
    )
    new_callout = render_callout([], {}, model="newmodel", date="2026-04-28")
    out = write_callout(note_text, new_callout)
    assert "old content" not in out
    assert "newmodel" in out
    assert "Manual section." in out  # manual preservado


def test_read_callout_roundtrip() -> None:
    sections = [ExtractionSection(name="X", instruction="i")]
    callout = render_callout(sections, {"X": "y"}, model="m", date="d")
    note = f"---\nid: a\n---\n\nbefore\n{callout}\nafter\n"
    extracted = read_callout(note)
    assert extracted == callout
