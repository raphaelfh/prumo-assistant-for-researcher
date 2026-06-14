"""Testa `paper.prep.extract_prep` (validação de pré-req + leitura de config)."""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist import ConfigError
from prumo_assist.domains.paper.prep import ExtractPrep, extract_prep


def _bootstrap(tmp_path: Path, citekey: str = "smith2020") -> Path:
    pj = tmp_path / "pj_demo"
    (pj / ".claude").mkdir(parents=True)
    (pj / ".claude" / "paper_extraction.md").write_text("# Template\n", encoding="utf-8")
    refs = pj / "references"
    (refs / "pdfs").mkdir(parents=True)
    (refs / "_references.bib").write_text("@article{smith2020,}\n", encoding="utf-8")
    (refs / "pdfs" / f"{citekey}.pdf").write_text("%PDF-1.4\n", encoding="utf-8")
    notes = refs / "notes" / citekey
    notes.mkdir(parents=True)
    (notes / "_meta.md").write_text("---\nid: smith2020\n---\n", encoding="utf-8")
    return pj


def test_extract_prep_returns_language_and_paths(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    prep = extract_prep(pj, "smith2020")
    assert isinstance(prep, ExtractPrep)
    assert prep.language == "pt-BR"  # default em DEFAULTS
    assert prep.template_path.name == "paper_extraction.md"
    assert prep.pdf_path.exists()
    assert prep.meta_path.exists()


def test_extract_prep_missing_meta_raises(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    (pj / "references" / "notes" / "smith2020" / "_meta.md").unlink()
    with pytest.raises(FileNotFoundError, match=r"_meta\.md"):
        extract_prep(pj, "smith2020")


def test_extract_prep_missing_template_raises(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    (pj / ".claude" / "paper_extraction.md").unlink()
    with pytest.raises(FileNotFoundError, match="paper_extraction"):
        extract_prep(pj, "smith2020")


def test_extract_prep_invalid_language_raises_configerror(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    (pj / ".claude" / "pj_config.toml").write_text(
        '[paper_extract]\nlanguage = "fr"\n', encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="language"):
        extract_prep(pj, "smith2020")
