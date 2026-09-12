"""Tests para read_inputs (carrega ComposeInputs a partir de um ESCOPO)."""

from __future__ import annotations

from pathlib import Path

from par.core import pj_layout
from par.domains.write import compose
from par.domains.write.compose import read_inputs


def _project(root: Path) -> Path:
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    return root


def _scope(root: Path, slug: str) -> Path:
    s = root / "docs" / "studies" / slug
    for sub in ("notes", "writing", "decisions"):
        (s / sub).mkdir(parents=True, exist_ok=True)
    return s


def _bootstrap(tmp_path: Path) -> Path:
    """Projeto com bib + paper completos; devolve o ESCOPO ``a`` (não a raiz)."""
    root = _project(tmp_path / "pj_demo")
    scope = _scope(root, "a")
    refs = root / "docs" / "references"
    refs.mkdir(parents=True, exist_ok=True)
    (refs / "_references.bib").write_text(
        "@article{smith2024,\n  title = {Combinado Fusion},\n"
        '  author = "Smith, J.",\n  year = 2024\n}\n'
        "@article{doe2025,\n  title = {Other},\n"
        '  author = "Doe, A.",\n  year = 2025\n}\n',
        encoding="utf-8",
    )
    (refs / "papers" / "smith2024").mkdir(parents=True)
    (refs / "papers" / "smith2024" / "_meta.md").write_text(
        "---\nid: smith2024\ntitle: Combinado Fusion\nauthor:\n"
        "  - { family: Smith, given: J. }\nissued: { date-parts: [[2024]] }\n---\n\n"
        "## Notas\n",
        encoding="utf-8",
    )
    (refs / "papers" / "smith2024" / "_extract.md").write_text(
        "---\npaper: smith2024\nsource: prumo-paper-extract\n---\n\n"
        "<!-- paper-extract:begin -->\n"
        "> ### TL;DR\n> resumo bom\n"
        "<!-- paper-extract:end -->\n",
        encoding="utf-8",
    )
    (scope / "writing" / "protocol.md").write_text(
        "# Protocolo\n\nContexto operacional.\n", encoding="utf-8"
    )
    (root / "docs" / "project_guide.md").write_text(
        "# Projeto\n\nProse formal.\n", encoding="utf-8"
    )
    return scope


def test_read_inputs_minimal_pj(tmp_path: Path) -> None:
    root = _project(tmp_path / "pj_empty")
    out = read_inputs(root)
    assert out.picot is None
    assert out.citekeys == []
    assert out.papers == {}
    assert out.protocol is None
    assert out.findings == []


def test_read_inputs_picot_loaded_when_exists(tmp_path: Path) -> None:
    scope = _bootstrap(tmp_path)
    root = pj_layout.find_pj_root(scope)
    (root / ".claude" / "picot.toml").write_text(
        "[picot]\n"
        'type = "clinical"\n'
        'created_at = "2026-05-03"\n'
        'last_updated = "2026-05-03"\n'
        "version = 1\n"
        'population = "DS_A"\n'
        'intervention = "IntervencaoX"\n'
        'comparison = "best baseline"\n'
        'outcome = "AUROC ≥ 0.85"\n'
        'time = "retrospectivo"\n'
        "[picot.hypothesis]\n"
        'statement = "combinado supera comparador"\n'
        'rationale = "piloto"\n'
        'metrics = ["AUROC"]\n',
        encoding="utf-8",
    )
    out = read_inputs(scope)
    assert out.picot is not None
    assert out.picot.population == "DS_A"


def test_read_inputs_citekeys_and_papers(tmp_path: Path) -> None:
    scope = _bootstrap(tmp_path)
    out = read_inputs(scope)
    assert "smith2024" in out.citekeys
    assert "doe2025" in out.citekeys
    assert "smith2024" in out.papers
    smith = out.papers["smith2024"]
    assert smith.title == "Combinado Fusion"
    assert smith.year == 2024
    assert "resumo bom" in (smith.extract_content or "")


def test_read_inputs_year_from_biblatex_date(tmp_path: Path) -> None:
    """Better BibLaTeX (o que ``prumo paper connect`` gera) não emite ``year``:
    o ano do ``PaperSummary`` tem de vir do ``date``."""
    root = _project(tmp_path / "pj_biblatex")
    refs = root / "docs" / "references"
    refs.mkdir(parents=True, exist_ok=True)
    (refs / "_references.bib").write_text(
        "@article{audisio2025total,\n"
        "  title = {Total {{Neoadjuvant Therapy}}},\n"
        "  author = {Audisio, Alessandro},\n"
        "  date = {2025-09-01},\n"
        "  journaltitle = {JAMA Oncology},\n"
        "  urldate = {2026-07-23}\n"
        "}\n",
        encoding="utf-8",
    )
    out = read_inputs(root)
    assert out.papers["audisio2025total"].year == 2025


def test_read_inputs_paper_without_extract(tmp_path: Path) -> None:
    scope = _bootstrap(tmp_path)
    # doe2025 não tem _meta.md/_extract.md
    out = read_inputs(scope)
    assert "doe2025" in out.citekeys
    # PaperSummary deve existir mesmo sem _meta.md (vem do .bib direto)
    assert "doe2025" in out.papers
    assert out.papers["doe2025"].extract_content is None


def test_read_inputs_protocol_and_project(tmp_path: Path) -> None:
    scope = _bootstrap(tmp_path)
    out = read_inputs(scope)
    assert out.protocol is not None
    assert "Contexto operacional" in out.protocol
    assert out.project is not None
    assert "Prose formal" in out.project


def test_read_inputs_findings_por_type(tmp_path: Path) -> None:
    scope = _bootstrap(tmp_path)
    (scope / "notes" / "calibration.md").write_text(
        "---\ntype: finding\ntitle: Calibration matters\n---\n\nConclusion.\n",
        encoding="utf-8",
    )
    (scope / "notes" / "n.md").write_text("---\ntype: note\n---\n\noutro\n", encoding="utf-8")
    out = read_inputs(scope)
    assert len(out.findings) == 1
    assert out.findings[0].title == "Calibration matters"


def test_compose_acha_finding_por_type(tmp_path: Path) -> None:
    root = _project(tmp_path)
    scope = _scope(root, "a")
    (scope / "notes" / "f.md").write_text(
        "---\ntype: finding\ntitle: F\n---\ncorpo", encoding="utf-8"
    )
    (scope / "notes" / "n.md").write_text("---\ntype: note\n---\noutro", encoding="utf-8")

    achados = compose._read_findings(scope)
    assert len(achados) == 1
