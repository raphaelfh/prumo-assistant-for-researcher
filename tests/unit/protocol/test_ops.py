"""End-to-end tests pros orquestradores `propagate` e `diff_against_last_adr`."""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist.domains.protocol.ops import (
    AdrResult,
    InitResult,
    PropagateReport,
    create_picot_adr,
    detect_mode,
    diff_against_last_adr,
    init_picot_spec,
    propagate,
)
from prumo_assist.domains.protocol.picot_io import picot_path, write_picot
from prumo_assist.domains.protocol.schemas.v1 import Hypothesis, PicotSpec


def _spec(version: int = 1, population: str = "DS_A") -> PicotSpec:
    return PicotSpec(
        type="clinical",
        created_at="2026-05-03",
        last_updated="2026-05-03",
        version=version,
        population=population,
        intervention="IntervencaoX",
        comparison="best baseline",
        outcome="AUROC ≥ 0.85",
        time="retrospectivo",
        hypothesis=Hypothesis(
            statement="combinado supera comparador",
            rationale="piloto",
            metrics=["AUROC"],
        ),
    )


def _bootstrap_pj(tmp_path: Path) -> Path:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    (pj / "docs" / "protocol.md").write_text(
        "# Protocolo do estudo\n\n## Contexto da pesquisa\n\nProse humana inicial.\n"
    )
    (pj / "docs" / "project_guide.md").write_text(
        "---\ntitle: Projeto\n---\n\n# Projeto\n\nIntro.\n"
    )
    (pj / "docs" / "decisions").mkdir()
    return pj


def test_propagate_inserts_blocks_when_absent(tmp_path: Path) -> None:
    pj = _bootstrap_pj(tmp_path)
    write_picot(pj, _spec())
    report = propagate(pj)
    assert isinstance(report, PropagateReport)
    assert report.protocol_status == "inserted"
    assert report.project_status == "inserted"
    protocol_text = (pj / "docs" / "protocol.md").read_text()
    project_text = (pj / "docs" / "project_guide.md").read_text()
    assert "<!-- picot:begin" in protocol_text
    assert "<!-- picot:begin" in project_text
    assert "DS_A" in protocol_text
    assert "Pergunta de pesquisa" in project_text


def test_propagate_replaces_blocks_when_present(tmp_path: Path) -> None:
    pj = _bootstrap_pj(tmp_path)
    write_picot(pj, _spec(population="DS_A"))
    propagate(pj)
    write_picot(pj, _spec(population="DS_A + DS_BB"))
    propagate(pj)
    text = (pj / "docs" / "protocol.md").read_text()
    assert "DS_A + DS_BB" in text
    assert text.count("<!-- picot:begin") == 1


def test_propagate_unchanged_when_hash_matches(tmp_path: Path) -> None:
    pj = _bootstrap_pj(tmp_path)
    write_picot(pj, _spec())
    propagate(pj)
    report = propagate(pj)
    assert report.protocol_status == "unchanged"
    assert report.project_status == "unchanged"


def test_propagate_raises_when_picot_missing(tmp_path: Path) -> None:
    pj = _bootstrap_pj(tmp_path)
    with pytest.raises(FileNotFoundError):
        propagate(pj)


def test_diff_against_last_adr_no_baseline_returns_diff_with_no_changes(
    tmp_path: Path,
) -> None:
    pj = _bootstrap_pj(tmp_path)
    write_picot(pj, _spec())
    out = diff_against_last_adr(pj)
    assert out is not None
    assert out.changes == []
    assert out.has_structural is False


def test_diff_against_last_adr_detects_structural_change(tmp_path: Path) -> None:
    """Após ADR inicial, mudar campo estrutural produz diff structural."""
    from prumo_assist.domains.protocol.adr import compose_adr, next_adr_number
    from prumo_assist.domains.protocol.diff import PicotDiff

    pj = _bootstrap_pj(tmp_path)
    spec_v1 = _spec(version=1, population="DS_A")
    write_picot(pj, spec_v1)
    decisions = pj / "docs" / "decisions"
    body = compose_adr(
        adr_number=next_adr_number(pj),
        spec=spec_v1,
        diff=PicotDiff(changes=[]),
        motivation="versão inicial",
        supersedes_path=None,
        date="2026-05-03",
    )
    (decisions / "adr-0001-picot-v1-versao-inicial.md").write_text(body)

    spec_v2 = _spec(version=2, population="DS_A + DS_BB")
    write_picot(pj, spec_v2)
    diff = diff_against_last_adr(pj)
    assert diff is not None
    assert diff.has_structural is True
    assert any(c.field == "population" for c in diff.changes)


def test_detect_mode_init_when_nothing(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    assert detect_mode(pj) == "init"


def test_detect_mode_formalize_when_protocol_prose(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    (pj / "docs" / "protocol.md").write_text("# Protocolo\n\nprosa humana.\n", encoding="utf-8")
    assert detect_mode(pj) == "formalize"


def test_detect_mode_propagate_when_picot_no_adr(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    write_picot(pj, _spec())
    assert detect_mode(pj) == "propagate"


def test_detect_mode_diff_when_baseline_adr(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs" / "decisions").mkdir(parents=True)
    write_picot(pj, _spec())
    (pj / "docs" / "decisions" / "adr-0001-picot-v1-versao-inicial.md").write_text(
        "# adr\n", encoding="utf-8"
    )
    assert detect_mode(pj) == "diff"


def test_init_picot_spec_writes_toml_and_adr(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    result = init_picot_spec(pj, spec=_spec(), motivation="inicial", date="2026-06-14")
    assert isinstance(result, InitResult)
    assert picot_path(pj).exists()
    assert result.adr_path.exists()
    assert "picot-v1-versao-inicial" in result.adr_path.name
    assert result.report.hash8 != ""


def test_create_picot_adr_writes_and_propagates(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    (pj / "docs" / "protocol.md").write_text("# Protocolo\n", encoding="utf-8")
    (pj / "docs" / "project_guide.md").write_text("---\ntitle: x\n---\n\n# P\n", encoding="utf-8")
    write_picot(pj, _spec(version=2, population="DS_A + DS_BB"))
    result = create_picot_adr(pj, motivation="novo dataset", slug="novo-dataset", date="2026-06-14")
    assert isinstance(result, AdrResult)
    assert result.adr_path.exists()
    assert "picot-v2-novo-dataset" in result.adr_path.name
