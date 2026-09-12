"""Contratos do domínio paper: locators do extract e veredito de suporte (spec D3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from prumo_assist.domains.paper.schemas.v1 import (
    Locator,
    PaperCallout,
    SupportReport,
    SupportVerdict,
)


def _callout(**extra: object) -> PaperCallout:
    return PaperCallout.model_validate(
        {
            "citekey": "smith2024",
            "sections": {"TL;DR": "resumo"},
            "model": "m",
            "extracted_at": "2026-09-12",
            "template_hash": "abc123",
            **extra,
        }
    )


def test_locators_sao_opcionais() -> None:
    assert _callout().locators == {}


def test_locators_validam_pagina_e_trecho() -> None:
    c = _callout(locators={"TL;DR": [{"page": 5, "quote": "trecho literal"}]})
    assert c.locators["TL;DR"] == [Locator(page=5, quote="trecho literal")]
    with pytest.raises(ValidationError):
        _callout(locators={"TL;DR": [{"page": 0, "quote": "x"}]})
    with pytest.raises(ValidationError):
        _callout(locators={"TL;DR": [{"page": 2, "quote": ""}]})


def test_veredito_que_sustenta_exige_trecho() -> None:
    base = {"sentence": "A reduz B.", "citekey": "k", "justification": "j"}
    with pytest.raises(ValidationError, match="quote"):
        SupportVerdict.model_validate({**base, "verdict": "fully"})
    ok = SupportVerdict.model_validate({**base, "verdict": "partially", "quote": "q", "page": 3})
    assert ok.page == 3
    assert SupportVerdict.model_validate({**base, "verdict": "unsubstantiated"}).quote is None
    assert SupportVerdict.model_validate({**base, "verdict": "no-source"}).verdict == "no-source"


def test_veredito_fora_das_opcoes_eh_recusado() -> None:
    with pytest.raises(ValidationError):
        SupportVerdict.model_validate(
            {"sentence": "s", "citekey": "k", "justification": "j", "verdict": "talvez"}
        )


def test_support_report_tem_schema_version() -> None:
    report = SupportReport(page="docs/x.md")
    assert report.schema_version == "SupportReport/v1"
    assert report.verdicts == []
