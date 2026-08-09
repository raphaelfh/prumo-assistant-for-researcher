"""Tests para geração e parsing de ADRs picot-v<N>."""

from __future__ import annotations

import re
from pathlib import Path

from prumo_assist.domains.protocol.adr import (
    SNAPSHOT_BEGIN,
    SNAPSHOT_END,
    compose_adr,
    extract_picot_snapshot,
    find_last_picot_adr,
    next_number,
)
from prumo_assist.domains.protocol.diff import FieldChange, PicotDiff
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
            statement="combinado supera comparador em ≥5 pts",
            rationale="piloto",
            metrics=["AUROC"],
        ),
    )


def test_next_number_starts_at_1(tmp_path: Path) -> None:
    decisions = tmp_path / "decisions"
    decisions.mkdir(parents=True)
    assert next_number(tmp_path) == 1


def test_next_number_increments(tmp_path: Path) -> None:
    decisions = tmp_path / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "adr-0001-foo.md").write_text("# x")
    (decisions / "adr-0003-bar.md").write_text("# x")
    (decisions / "not-an-adr.md").write_text("ignore")
    assert next_number(tmp_path) == 4


def test_numeracao_de_adr_e_por_escopo(tmp_path: Path) -> None:
    from prumo_assist.domains.protocol import adr

    a = tmp_path / "docs" / "studies" / "a" / "decisions"
    b = tmp_path / "docs" / "studies" / "b" / "decisions"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    (a / "adr-0001-x.md").write_text("x", encoding="utf-8")
    (a / "adr-0002-y.md").write_text("y", encoding="utf-8")

    assert adr.next_number(a.parent) == 3
    assert adr.next_number(b.parent) == 1


def test_compose_adr_includes_diff_motivation_and_snapshot(tmp_path: Path) -> None:
    diff = PicotDiff(
        changes=[
            FieldChange(field="population", before="DS_A", after="DS_A+DS_BB", structural=True),
        ]
    )
    spec = _spec(version=2, population="DS_A+DS_BB")
    body = compose_adr(
        adr_number=2,
        spec=spec,
        diff=diff,
        motivation="adicionar coorte externa",
        supersedes_path=None,
        date="2026-05-03",
    )
    assert "ADR-0002" in body
    assert "PICOT v2" in body
    assert "population" in body
    assert "DS_A+DS_BB" in body
    assert "adicionar coorte externa" in body
    assert SNAPSHOT_BEGIN in body
    assert SNAPSHOT_END in body
    assert 'population = "DS_A+DS_BB"' in body


def test_compose_adr_supersedes_link() -> None:
    diff = PicotDiff(changes=[FieldChange("population", "A", "B", True)])
    body = compose_adr(
        adr_number=3,
        spec=_spec(version=3, population="B"),
        diff=diff,
        motivation="motivo",
        supersedes_path=Path("docs/decisions/adr-0002-picot-v2.md"),
        date="2026-05-03",
    )
    assert "supersedes: adr-0002-picot-v2" in body


def test_extract_snapshot_round_trip() -> None:
    diff = PicotDiff(changes=[FieldChange("population", "A", "B", True)])
    body = compose_adr(
        adr_number=1,
        spec=_spec(),
        diff=diff,
        motivation="motivo",
        supersedes_path=None,
        date="2026-05-03",
    )
    extracted = extract_picot_snapshot(body)
    assert extracted is not None
    assert "population" in extracted
    assert 'type = "clinical"' in extracted


def test_extract_snapshot_returns_none_when_absent() -> None:
    body = "ADR sem snapshot"
    assert extract_picot_snapshot(body) is None


def test_find_last_picot_adr(tmp_path: Path) -> None:
    decisions = tmp_path / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "adr-0001-foo.md").write_text("# foo")
    (decisions / "adr-0002-picot-v1-initial.md").write_text("# v1")
    (decisions / "adr-0003-picot-v2-coorte.md").write_text("# v2")
    found = find_last_picot_adr(tmp_path)
    assert found is not None
    assert found.name == "adr-0003-picot-v2-coorte.md"


def test_find_last_picot_adr_none(tmp_path: Path) -> None:
    decisions = tmp_path / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "adr-0001-foo.md").write_text("# foo")
    assert find_last_picot_adr(tmp_path) is None


def test_adr_number_from_filename_works_4_digits() -> None:
    decisions_dir_pat = re.compile(r"adr-(\d{4})-")
    m = decisions_dir_pat.match("adr-0042-picot-v3-foo.md")
    assert m is not None and m.group(1) == "0042"
