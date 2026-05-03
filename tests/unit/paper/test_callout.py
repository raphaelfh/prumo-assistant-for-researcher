"""Tests pro render e write do callout estruturado em _extract.md."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.core.note_paths import extract_path, meta_path
from prumo_assist.domains.paper.callout import (
    EXTRACT_BEGIN,
    EXTRACT_END,
    ExtractionSection,
    apply_extraction,
    parse_extraction_template,
    render_callout,
)


def test_parse_template_extracts_section_names_and_instructions() -> None:
    text = "# Header\n\n### TL;DR\n<!-- escreva 2-3 frases -->\n\n### PICOT\n<!-- 5 bullets -->\n"
    sections = parse_extraction_template(text)
    assert [s.name for s in sections] == ["TL;DR", "PICOT"]


def test_render_callout_includes_meta_and_sections() -> None:
    sections = [
        ExtractionSection(name="TL;DR", instruction="x"),
        ExtractionSection(name="PICOT", instruction="y"),
    ]
    out = render_callout(
        sections,
        {"TL;DR": "Two-line summary.", "PICOT": "P: ..."},
        model="claude-test",
        date="2026-04-28",
    )
    assert out.startswith(EXTRACT_BEGIN)
    assert out.endswith(EXTRACT_END)
    assert "claude-test" in out
    assert "Two-line summary." in out


def _bootstrap(tmp_path: Path, citekey: str) -> tuple[Path, Path]:
    """Cria pj_*/references/notes/<key>/_meta.md mínimo + paper_extraction template."""
    meta = meta_path(tmp_path, citekey)
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(f"---\nid: {citekey}\nextracted_at: null\n---\n\n## Notas humanas\n")
    template = tmp_path / ".claude" / "paper_extraction.md"
    template.parent.mkdir(parents=True, exist_ok=True)
    template.write_text("### TL;DR\n<!-- 2 linhas -->\n\n### PICOT\n<!-- 5 bullets -->\n")
    return meta, template


def test_apply_extraction_creates_extract_md(tmp_path: Path) -> None:
    citekey = "smith2024"
    _meta, template = _bootstrap(tmp_path, citekey)
    changed = apply_extraction(
        pj_path=tmp_path,
        citekey=citekey,
        template_path=template,
        content={"TL;DR": "summary", "PICOT": "p: x"},
        model="claude-test",
        date="2026-05-03",
    )
    assert changed is True
    extract = extract_path(tmp_path, citekey)
    assert extract.exists()
    text = extract.read_text()
    assert "summary" in text
    assert EXTRACT_BEGIN in text
    assert EXTRACT_END in text
    # frontmatter mínimo
    assert text.startswith("---\n")
    assert "paper: smith2024" in text
    assert "source: prumo-paper-extract" in text


def test_apply_extraction_updates_meta_yaml_extracted_fields(tmp_path: Path) -> None:
    citekey = "smith2024"
    meta, template = _bootstrap(tmp_path, citekey)
    apply_extraction(
        pj_path=tmp_path,
        citekey=citekey,
        template_path=template,
        content={"TL;DR": "x"},
        model="claude-test",
        date="2026-05-03",
    )
    meta_text = meta.read_text()
    assert "extracted_at: '2026-05-03'" in meta_text or 'extracted_at: "2026-05-03"' in meta_text
    assert "extracted_model: claude-test" in meta_text or "extracted_model: 'claude-test'" in meta_text


def test_apply_extraction_idempotent_when_content_unchanged(tmp_path: Path) -> None:
    citekey = "smith2024"
    _, template = _bootstrap(tmp_path, citekey)
    apply_extraction(
        pj_path=tmp_path,
        citekey=citekey,
        template_path=template,
        content={"TL;DR": "x"},
        model="m",
        date="2026-05-03",
    )
    changed = apply_extraction(
        pj_path=tmp_path,
        citekey=citekey,
        template_path=template,
        content={"TL;DR": "x"},
        model="m",
        date="2026-05-04",  # data muda mas conteúdo não
    )
    assert changed is False
