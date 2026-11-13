"""Tests para question_io (ADR-0041): leitura, fallback ao picot.toml e escrita."""

from __future__ import annotations

from pathlib import Path

import pytest

from par.domains.protocol.picot_io import picot_path, write_picot
from par.domains.protocol.question_io import (
    current_question_file,
    question_hash,
    question_path,
    read_question,
    write_question,
)
from par.domains.protocol.schemas.v1 import Hypothesis, PicotSpec, QuestionSpec


def _question() -> QuestionSpec:
    return QuestionSpec(
        type="review",
        question="O que se sabe sobre telessaúde na APS rural?",
        design="revisão de escopo",
        objective="Mapear a evidência.",
        created_at="2026-11-12",
        last_updated="2026-11-12",
        version=1,
        framework="PCC",
        elements={"population": "APS rural", "concept": "telessaúde", "context": "Brasil"},
    )


def _picot() -> PicotSpec:
    return PicotSpec(
        type="clinical",
        created_at="2026-05-03",
        last_updated="2026-05-03",
        version=1,
        population="P",
        intervention="I",
        comparison="C",
        outcome="O",
        time="T",
        hypothesis=Hypothesis(statement="s", rationale="r", metrics=["m"]),
    )


def test_roundtrip(tmp_path: Path) -> None:
    write_question(tmp_path, _question())
    assert read_question(tmp_path) == _question()
    text = question_path(tmp_path).read_text(encoding="utf-8")
    assert "[question.elements]" in text
    assert "None" not in text


def test_missing_raises_with_command(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="protocol question"):
        read_question(tmp_path)
    assert current_question_file(tmp_path) is None


def test_fallback_reads_legacy_picot(tmp_path: Path) -> None:
    write_picot(tmp_path, _picot())
    spec = read_question(tmp_path)
    assert spec.framework == "PICOT"
    assert spec.elements is not None and spec.elements["comparison"] == "C"
    assert current_question_file(tmp_path) == picot_path(tmp_path)
    assert len(question_hash(tmp_path)) == 8


def test_write_removes_legacy_picot(tmp_path: Path) -> None:
    write_picot(tmp_path, _picot())
    write_question(tmp_path, read_question(tmp_path))
    assert not picot_path(tmp_path).exists()
    assert question_path(tmp_path).exists()
    assert read_question(tmp_path).elements == {
        "population": "P",
        "intervention": "I",
        "comparison": "C",
        "outcome": "O",
        "time": "T",
    }


def test_invalid_table_points_to_git_diff(tmp_path: Path) -> None:
    question_path(tmp_path).parent.mkdir(parents=True)
    question_path(tmp_path).write_text('x = "y"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="git diff"):
        read_question(tmp_path)
