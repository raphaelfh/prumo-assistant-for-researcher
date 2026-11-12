"""Tests para deep diff entre PicotSpec atual e snapshot do último ADR."""

from __future__ import annotations

from par.domains.protocol.diff import (
    QuestionDiff,
    diff_question,
    is_structural_field,
)
from par.domains.protocol.schemas.v1 import (
    Hypothesis,
    PicotSpec,
    QuestionSpec,
    question_from_picot,
)


def _spec(**overrides: object) -> QuestionSpec:
    base = dict(
        type="clinical",
        created_at="2026-05-03",
        last_updated="2026-05-03",
        version=1,
        population="DS_A",
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
    base.update(overrides)
    return question_from_picot(PicotSpec(**base))  # type: ignore[arg-type]


def test_diff_no_changes() -> None:
    a, b = _spec(), _spec()
    out = diff_question(a, b)
    assert isinstance(out, QuestionDiff)
    assert out.changes == []
    assert out.has_structural is False


def test_diff_structural_field_change() -> None:
    a = _spec()
    b = _spec(population="DS_A + DS_BB")
    out = diff_question(a, b)
    # o question derivado da PICOT também muda; o elemento é o que interessa aqui
    change = next(c for c in out.changes if c.field == "elements.population")
    assert change.before == "DS_A"
    assert change.after == "DS_A + DS_BB"
    assert change.structural is True
    assert out.has_structural is True


def test_diff_non_structural_field_change_does_not_flag() -> None:
    a = _spec()
    b = _spec(last_updated="2026-06-01")
    out = diff_question(a, b)
    assert any(c.field == "last_updated" for c in out.changes)
    assert out.has_structural is False


def test_diff_hypothesis_statement() -> None:
    a = _spec()
    b = _spec(
        hypothesis=Hypothesis(
            statement="combinado supera comparador em ≥7 pts",
            rationale="piloto",
            metrics=["AUROC"],
        )
    )
    out = diff_question(a, b)
    fields = [c.field for c in out.changes]
    assert "hypothesis.statement" in fields
    statement_change = next(c for c in out.changes if c.field == "hypothesis.statement")
    assert statement_change.structural is True


def test_diff_hypothesis_rationale_not_structural() -> None:
    a = _spec()
    assert a.hypothesis is not None
    b = _spec(
        hypothesis=Hypothesis(
            statement=a.hypothesis.statement,
            rationale="motivo refinado",
            metrics=a.hypothesis.metrics,
        )
    )
    out = diff_question(a, b)
    rationale_changes = [c for c in out.changes if c.field == "hypothesis.rationale"]
    assert len(rationale_changes) == 1
    assert rationale_changes[0].structural is False
    assert out.has_structural is False


def test_diff_metrics_change_is_structural() -> None:
    a = _spec()
    assert a.hypothesis is not None
    b = _spec(
        hypothesis=Hypothesis(
            statement=a.hypothesis.statement,
            rationale=a.hypothesis.rationale,
            metrics=["AUROC", "ECE"],
        )
    )
    out = diff_question(a, b)
    metrics_change = next(c for c in out.changes if c.field == "hypothesis.metrics")
    assert metrics_change.structural is True


def test_is_structural_field() -> None:
    assert is_structural_field("population") is True
    assert is_structural_field("elements.concept") is True
    assert is_structural_field("question") is True
    assert is_structural_field("objective") is False
    assert is_structural_field("hypothesis.statement") is True
    assert is_structural_field("hypothesis.metrics") is True
    assert is_structural_field("last_updated") is False
    assert is_structural_field("hypothesis.rationale") is False
    assert is_structural_field("version") is False  # bump é consequência, não sinal
