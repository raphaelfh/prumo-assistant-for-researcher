"""Tests para PicotSpec/v1."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from prumo_assist.domains.protocol.schemas.v1 import Hypothesis, PicotSpec


def _valid_clinical() -> dict:
    return {
        "type": "clinical",
        "created_at": "2026-05-03",
        "last_updated": "2026-05-03",
        "version": 1,
        "population": "DS_A + DS_BB",
        "intervention": "intervenção X",
        "comparison": "cuidado usual",
        "outcome": "AUROC ≥ 0.85",
        "time": "retrospectivo, sem janela",
        "hypothesis": {
            "statement": "combinado supera comparador em ≥5 pontos AUC",
            "rationale": "estudos-piloto sugerem efeito relevante",
            "metrics": ["AUROC", "ECE"],
        },
    }


def test_clinical_picot_valid() -> None:
    spec = PicotSpec.model_validate(_valid_clinical())
    assert spec.type == "clinical"
    assert spec.version == 1
    assert spec.hypothesis.statement.startswith("combinado")


def test_clinical_picot_requires_picot_fields() -> None:
    data = _valid_clinical()
    data["population"] = ""
    with pytest.raises(ValidationError) as exc:
        PicotSpec.model_validate(data)
    assert "population" in str(exc.value)


def test_methodological_picot_valid() -> None:
    data = {
        "type": "methodological",
        "created_at": "2026-05-03",
        "last_updated": "2026-05-03",
        "version": 1,
        "contribution": "método estatístico M",
        "hypothesis_validity_condition": "a suposição S falha",
        "hypothesis": {
            "statement": "o método M mantém a propriedade P sob S",
            "rationale": "a correção C compensa o viés",
            "metrics": ["coverage", "set-size"],
        },
    }
    spec = PicotSpec.model_validate(data)
    assert spec.type == "methodological"
    assert spec.population is None
    assert spec.contribution is not None


def test_methodological_picot_requires_contribution() -> None:
    data = {
        "type": "methodological",
        "created_at": "2026-05-03",
        "last_updated": "2026-05-03",
        "version": 1,
        "contribution": "",
        "hypothesis_validity_condition": "X",
        "hypothesis": {
            "statement": "Y",
            "rationale": "Z",
            "metrics": ["m"],
        },
    }
    with pytest.raises(ValidationError) as exc:
        PicotSpec.model_validate(data)
    assert "contribution" in str(exc.value)


def test_hypothesis_metrics_must_be_non_empty() -> None:
    data = _valid_clinical()
    data["hypothesis"]["metrics"] = []
    with pytest.raises(ValidationError):
        PicotSpec.model_validate(data)


def test_version_must_be_positive() -> None:
    data = _valid_clinical()
    data["version"] = 0
    with pytest.raises(ValidationError):
        PicotSpec.model_validate(data)


def test_schema_version_constant() -> None:
    spec = PicotSpec.model_validate(_valid_clinical())
    assert spec.schema_version == "PicotSpec/v1"


def test_hypothesis_statement_required() -> None:
    h = {"statement": "", "rationale": "x", "metrics": ["m"]}
    with pytest.raises(ValidationError):
        Hypothesis.model_validate(h)
