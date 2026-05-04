"""Tests para read_inputs (carrega ComposeInputs do pj_*)."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.write.compose import read_inputs


def _bootstrap(tmp_path: Path) -> Path:
    pj = tmp_path / "pj_demo"
    refs = pj / "references"
    refs.mkdir(parents=True)
    (refs / "_references.bib").write_text(
        "@article{smith2024,\n  title = {Combinado Fusion},\n"
        "  author = \"Smith, J.\",\n  year = 2024\n}\n"
        "@article{doe2025,\n  title = {Other},\n"
        "  author = \"Doe, A.\",\n  year = 2025\n}\n"
    )
    (refs / "notes" / "smith2024").mkdir(parents=True)
    (refs / "notes" / "smith2024" / "_meta.md").write_text(
        "---\nid: smith2024\ntitle: Combinado Fusion\nauthor:\n"
        "  - { family: Smith, given: J. }\nissued: { date-parts: [[2024]] }\n---\n\n"
        "## Notas\n"
    )
    (refs / "notes" / "smith2024" / "_extract.md").write_text(
        "---\npaper: smith2024\nsource: prumo-paper-extract\n---\n\n"
        "<!-- paper-extract:begin -->\n"
        "> ### TL;DR\n> resumo bom\n"
        "<!-- paper-extract:end -->\n"
    )
    docs = pj / "docs"
    docs.mkdir()
    (docs / "protocol.md").write_text("# Protocolo\n\nContexto operacional.\n")
    (docs / "project.md").write_text("# Projeto\n\nProse formal.\n")
    return pj


def test_read_inputs_minimal_pj(tmp_path: Path) -> None:
    pj = tmp_path / "pj_empty"
    pj.mkdir()
    out = read_inputs(pj)
    assert out.picot is None
    assert out.citekeys == []
    assert out.papers == {}
    assert out.protocol is None
    assert out.findings == []


def test_read_inputs_picot_loaded_when_exists(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    (pj / ".claude").mkdir()
    (pj / ".claude" / "picot.toml").write_text(
        '[picot]\n'
        'type = "clinical"\n'
        'created_at = "2026-05-03"\n'
        'last_updated = "2026-05-03"\n'
        'version = 1\n'
        'population = "DS_A"\n'
        'intervention = "IntervencaoX"\n'
        'comparison = "best baseline"\n'
        'outcome = "AUROC ≥ 0.85"\n'
        'time = "retrospectivo"\n'
        '[picot.hypothesis]\n'
        'statement = "combinado supera comparador"\n'
        'rationale = "piloto"\n'
        'metrics = ["AUROC"]\n'
    )
    out = read_inputs(pj)
    assert out.picot is not None
    assert out.picot.population == "DS_A"


def test_read_inputs_citekeys_and_papers(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    out = read_inputs(pj)
    assert "smith2024" in out.citekeys
    assert "doe2025" in out.citekeys
    assert "smith2024" in out.papers
    smith = out.papers["smith2024"]
    assert smith.title == "Combinado Fusion"
    assert smith.year == 2024
    assert "resumo bom" in (smith.extract_content or "")


def test_read_inputs_paper_without_extract(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    # doe2025 não tem _meta.md/_extract.md
    out = read_inputs(pj)
    assert "doe2025" in out.citekeys
    # PaperSummary deve existir mesmo sem _meta.md (vem do .bib direto)
    assert "doe2025" in out.papers
    assert out.papers["doe2025"].extract_content is None


def test_read_inputs_protocol_and_project(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    out = read_inputs(pj)
    assert out.protocol is not None
    assert "Contexto operacional" in out.protocol
    assert out.project is not None
    assert "Prose formal" in out.project


def test_read_inputs_findings_extended_wiki(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    findings_dir = pj / "docs" / "wiki" / "findings"
    findings_dir.mkdir(parents=True)
    (findings_dir / "calibration.md").write_text(
        "---\nid: calibration\ntitle: Calibration matters\n---\n\nConclusion.\n"
    )
    out = read_inputs(pj)
    assert len(out.findings) == 1
    assert out.findings[0].title == "Calibration matters"


def test_read_inputs_findings_fallback(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    findings_dir = pj / "docs" / "findings"
    findings_dir.mkdir(parents=True)
    (findings_dir / "calibration.md").write_text(
        "---\nid: calibration\ntitle: Calibration matters\n---\n\nC.\n"
    )
    out = read_inputs(pj)
    assert len(out.findings) == 1
