"""Tests pro render e write do callout estruturado em _extract.md."""

from __future__ import annotations

from pathlib import Path

import pytest

from par.core.note_paths import extract_path, meta_path
from par.domains.paper.callout import (
    EXTRACT_BEGIN,
    EXTRACT_END,
    ExtractionSection,
    apply_extraction,
    parse_extract_payload,
    parse_extraction_template,
    render_callout,
)
from par.domains.paper.errors import PaperError
from par.domains.paper.sync import read_nota_yaml


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
    assert (
        "extracted_model: claude-test" in meta_text or "extracted_model: 'claude-test'" in meta_text
    )


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


# ---------------------------------------------------------------------------
# F2 da superfície de skills: validação, locators e proveniência
# ---------------------------------------------------------------------------


def test_apply_extraction_recusa_secao_fora_do_template(tmp_path: Path) -> None:
    _, template = _bootstrap(tmp_path, "smith2024")
    with pytest.raises(PaperError, match="TL;DR"):
        apply_extraction(
            pj_path=tmp_path,
            citekey="smith2024",
            template_path=template,
            content={"TLDR": "resumo"},
            model="m",
            date="2026-09-12",
        )
    assert not extract_path(tmp_path, "smith2024").exists()


def test_apply_extraction_recusa_valor_que_nao_eh_texto(tmp_path: Path) -> None:
    _, template = _bootstrap(tmp_path, "smith2024")
    with pytest.raises(PaperError):
        apply_extraction(
            pj_path=tmp_path,
            citekey="smith2024",
            template_path=template,
            content={"TL;DR": ["lista"]},
            model="m",
            date="2026-09-12",
        )
    assert not extract_path(tmp_path, "smith2024").exists()


def test_apply_extraction_renderiza_locators(tmp_path: Path) -> None:
    _, template = _bootstrap(tmp_path, "smith2024")
    apply_extraction(
        pj_path=tmp_path,
        citekey="smith2024",
        template_path=template,
        content={"TL;DR": "resumo"},
        locators={"TL;DR": [{"page": 3, "quote": "trecho do PDF"}]},
        model="m",
        date="2026-09-12",
    )
    text = extract_path(tmp_path, "smith2024").read_text(encoding="utf-8")
    assert 'p. 3 — "trecho do PDF"' in text


def test_extract_sem_locators_nao_muda_o_render(tmp_path: Path) -> None:
    _, template = _bootstrap(tmp_path, "smith2024")
    apply_extraction(
        pj_path=tmp_path,
        citekey="smith2024",
        template_path=template,
        content={"TL;DR": "resumo"},
        model="m",
        date="2026-09-12",
    )
    assert "**Onde:**" not in extract_path(tmp_path, "smith2024").read_text(encoding="utf-8")


def test_apply_extraction_carimba_meta_de_proveniencia(tmp_path: Path) -> None:
    meta, template = _bootstrap(tmp_path, "smith2024")
    apply_extraction(
        pj_path=tmp_path,
        citekey="smith2024",
        template_path=template,
        content={"TL;DR": "resumo"},
        model="claude-test",
        date="2026-09-12",
    )
    stamped = read_nota_yaml(meta)["_meta"]
    assert stamped["skill"] == "paper/extract"
    assert stamped["schema"] == "PaperCallout/v1"
    assert stamped["model"] == "claude-test"
    assert stamped["input_hash"]
    assert "human_reviewed" not in stamped


def test_parse_extract_payload_aceita_plano_e_estruturado() -> None:
    assert parse_extract_payload({"TL;DR": "a"}) == ({"TL;DR": "a"}, {})
    sections, locators = parse_extract_payload(
        {"sections": {"TL;DR": "a"}, "locators": {"TL;DR": [{"page": 1, "quote": "q"}]}}
    )
    assert sections == {"TL;DR": "a"}
    assert locators == {"TL;DR": [{"page": 1, "quote": "q"}]}
