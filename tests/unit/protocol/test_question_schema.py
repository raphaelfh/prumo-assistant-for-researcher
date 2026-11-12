"""Tests para QuestionSpec/v1 (ADR-0041)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from par.domains.protocol.schemas.v1 import (
    FRAMEWORK_ELEMENTS,
    QUESTION_TYPES,
    PicotSpec,
    QuestionSpec,
    question_from_picot,
)

_HYP = {"statement": "s", "rationale": "r", "metrics": ["HR"]}


def _base(type_: str, **extra: Any) -> dict[str, Any]:
    return {
        "type": type_,
        "question": "Pergunta?",
        "created_at": "2026-11-12",
        "last_updated": "2026-11-12",
        "version": 1,
        **extra,
    }


def test_schema_version_default() -> None:
    spec = QuestionSpec.model_validate(_base("observational", objective="o"))
    assert spec.schema_version == "QuestionSpec/v1"


def test_question_is_required() -> None:
    data = _base("observational", objective="o")
    data["question"] = ""
    with pytest.raises(ValidationError, match="question"):
        QuestionSpec.model_validate(data)


@pytest.mark.parametrize("type_", ["clinical", "experimental", "prediction"])
def test_confirmatory_types_require_hypothesis(type_: str) -> None:
    with pytest.raises(ValidationError, match="hypothesis"):
        QuestionSpec.model_validate(_base(type_, objective="o"))
    QuestionSpec.model_validate(_base(type_, hypothesis=_HYP))


@pytest.mark.parametrize("type_", ["qualitative", "case_report"])
def test_descriptive_types_require_objective(type_: str) -> None:
    with pytest.raises(ValidationError, match="objective"):
        QuestionSpec.model_validate(_base(type_, hypothesis=_HYP))
    QuestionSpec.model_validate(_base(type_, objective="o"))


@pytest.mark.parametrize(
    "type_",
    ["observational", "review", "mixed_methods", "economic", "computational", "other"],
)
def test_flexible_types_accept_objective_or_hypothesis(type_: str) -> None:
    QuestionSpec.model_validate(_base(type_, objective="o"))
    QuestionSpec.model_validate(_base(type_, hypothesis=_HYP))
    with pytest.raises(ValidationError, match="objective"):
        QuestionSpec.model_validate(_base(type_))


def test_theoretical_requires_contribution_and_objective() -> None:
    with pytest.raises(ValidationError, match="contribution"):
        QuestionSpec.model_validate(_base("theoretical", objective="o"))
    with pytest.raises(ValidationError, match="objective"):
        QuestionSpec.model_validate(_base("theoretical", contribution="c"))
    QuestionSpec.model_validate(_base("theoretical", contribution="c", objective="o"))


def test_methodological_requires_contribution_condition_hypothesis() -> None:
    with pytest.raises(ValidationError, match="hypothesis_validity_condition"):
        QuestionSpec.model_validate(_base("methodological", contribution="c", hypothesis=_HYP))
    QuestionSpec.model_validate(
        _base(
            "methodological",
            contribution="c",
            hypothesis_validity_condition="v",
            hypothesis=_HYP,
        )
    )


def test_every_type_is_covered_by_rules() -> None:
    assert set(QUESTION_TYPES) == {
        "clinical",
        "experimental",
        "observational",
        "prediction",
        "review",
        "qualitative",
        "mixed_methods",
        "economic",
        "computational",
        "theoretical",
        "methodological",
        "case_report",
        "other",
    }


def test_framework_requires_its_elements() -> None:
    data = _base("review", objective="o", framework="PCC", elements={"population": "p"})
    with pytest.raises(ValidationError) as exc:
        QuestionSpec.model_validate(data)
    assert "concept" in str(exc.value) and "context" in str(exc.value)


def test_framework_rejects_unknown_element() -> None:
    data = _base(
        "review",
        objective="o",
        framework="PCC",
        elements={"population": "p", "concept": "c", "context": "x", "outcome": "?"},
    )
    with pytest.raises(ValidationError, match="outcome"):
        QuestionSpec.model_validate(data)


def test_framework_optional_element() -> None:
    elements = {"population": "p", "exposure": "e", "outcome": "o"}
    spec = QuestionSpec.model_validate(
        _base("observational", objective="o", framework="PECO", elements=elements)
    )
    assert spec.elements == elements
    QuestionSpec.model_validate(
        _base(
            "observational",
            objective="o",
            framework="PECO",
            elements={**elements, "comparison": "c"},
        )
    )


def test_elements_without_framework_rejected() -> None:
    with pytest.raises(ValidationError, match="framework"):
        QuestionSpec.model_validate(_base("observational", objective="o", elements={"x": "y"}))


def test_clinical_picot_requires_comparison() -> None:
    elements = {"population": "p", "intervention": "i", "outcome": "o", "time": "t"}
    with pytest.raises(ValidationError, match="comparison"):
        QuestionSpec.model_validate(
            _base("clinical", hypothesis=_HYP, framework="PICOT", elements=elements)
        )
    QuestionSpec.model_validate(
        _base(
            "clinical",
            hypothesis=_HYP,
            framework="PICOT",
            elements={**elements, "comparison": "c"},
        )
    )


def test_all_frameworks_valid_with_required_elements() -> None:
    for name, (required, _optional) in FRAMEWORK_ELEMENTS.items():
        elements = {k: "x" for k in required}
        QuestionSpec.model_validate(
            _base("other", objective="o", framework=name, elements=elements)
        )


def _picot(**over: Any) -> PicotSpec:
    data: dict[str, Any] = {
        "type": "clinical",
        "created_at": "2026-05-03",
        "last_updated": "2026-05-04",
        "version": 2,
        "population": "P",
        "intervention": "I",
        "comparison": "C",
        "outcome": "O",
        "time": "T",
        "hypothesis": _HYP,
    }
    data.update(over)
    return PicotSpec.model_validate(data)


def test_from_picot_clinical() -> None:
    q = question_from_picot(_picot())
    assert q.type == "clinical"
    assert q.framework == "PICOT"
    assert q.elements == {
        "population": "P",
        "intervention": "I",
        "comparison": "C",
        "outcome": "O",
        "time": "T",
    }
    assert q.version == 2 and q.created_at == "2026-05-03" and q.last_updated == "2026-05-04"
    assert "P" in q.question and q.question.endswith("?")
    assert q.hypothesis is not None and q.hypothesis.statement == "s"


def test_from_picot_prediction_without_comparison() -> None:
    q = question_from_picot(_picot(type="prediction", comparison=None))
    assert q.framework == "PICOT"
    assert "comparison" not in (q.elements or {})


def test_from_picot_methodological() -> None:
    q = question_from_picot(
        _picot(
            type="methodological",
            population=None,
            intervention=None,
            comparison=None,
            outcome=None,
            time=None,
            contribution="Ctb",
            hypothesis_validity_condition="Cond",
        )
    )
    assert q.framework is None and q.elements is None
    assert q.contribution == "Ctb" and q.hypothesis_validity_condition == "Cond"
    assert "Ctb" in q.question
