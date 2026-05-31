"""Tests para read/write/hash de .claude/picot.toml."""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist.domains.protocol.picot_io import (
    picot_hash,
    picot_path,
    read_picot,
    write_picot,
)
from prumo_assist.domains.protocol.schemas.v1 import Hypothesis, PicotSpec


def _spec() -> PicotSpec:
    return PicotSpec(
        type="clinical",
        created_at="2026-05-03",
        last_updated="2026-05-03",
        version=1,
        population="DS_A + DS_BB",
        intervention="IntervencaoX",
        comparison="melhor comparador",
        outcome="AUROC ≥ 0.85",
        time="retrospectivo",
        hypothesis=Hypothesis(
            statement="combinado supera comparador em ≥5 pontos AUC",
            rationale="efeito piloto",
            metrics=["AUROC", "ECE"],
        ),
    )


def test_picot_path_returns_expected(tmp_path: Path) -> None:
    assert picot_path(tmp_path) == tmp_path / ".claude" / "picot.toml"


def test_write_creates_file(tmp_path: Path) -> None:
    spec = _spec()
    written = write_picot(tmp_path, spec)
    assert written.exists()
    assert written == picot_path(tmp_path)


def test_write_then_read_round_trip(tmp_path: Path) -> None:
    original = _spec()
    write_picot(tmp_path, original)
    loaded = read_picot(tmp_path)
    assert loaded.model_dump() == original.model_dump()


def test_read_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_picot(tmp_path)


def test_read_validates(tmp_path: Path) -> None:
    p = picot_path(tmp_path)
    p.parent.mkdir(parents=True)
    p.write_text(
        "[picot]\n"
        'type = "clinical"\n'
        'created_at = "2026-05-03"\n'
        'last_updated = "2026-05-03"\n'
        "version = 1\n"
        'population = ""\n'  # invalido
        'intervention = "X"\n'
        'comparison = "Y"\n'
        'outcome = "Z"\n'
        'time = "T"\n'
        "[picot.hypothesis]\n"
        'statement = "S"\n'
        'rationale = "R"\n'
        'metrics = ["m"]\n'
    )
    with pytest.raises(ValueError):
        read_picot(tmp_path)


def test_picot_hash_stable(tmp_path: Path) -> None:
    spec = _spec()
    write_picot(tmp_path, spec)
    h1 = picot_hash(tmp_path)
    h2 = picot_hash(tmp_path)
    assert h1 == h2
    assert len(h1) == 8


def test_picot_hash_changes_on_field_change(tmp_path: Path) -> None:
    spec = _spec()
    write_picot(tmp_path, spec)
    h1 = picot_hash(tmp_path)
    spec2 = spec.model_copy(update={"population": "NOVO"})
    write_picot(tmp_path, spec2)
    h2 = picot_hash(tmp_path)
    assert h1 != h2


def test_methodological_omits_picot_fields(tmp_path: Path) -> None:
    spec = PicotSpec(
        type="methodological",
        created_at="2026-05-03",
        last_updated="2026-05-03",
        version=1,
        contribution="X",
        hypothesis_validity_condition="Y",
        hypothesis=Hypothesis(
            statement="S",
            rationale="R",
            metrics=["m"],
        ),
    )
    written = write_picot(tmp_path, spec)
    text = written.read_text()
    # Métodológico não deve emitir population/intervention vazios.
    assert "population" not in text
    assert "intervention" not in text
    assert 'contribution = "X"' in text
