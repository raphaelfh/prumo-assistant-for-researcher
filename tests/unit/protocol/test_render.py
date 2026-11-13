"""Tests para render QuestionSpec → blocos delimitados em protocol.md / project_guide.md."""

from __future__ import annotations

from par.domains.protocol.render import (
    BLOCK_BEGIN_RE,
    PICOT_BEGIN_PREFIX,
    PICOT_END,
    QUESTION_BEGIN_PREFIX,
    QUESTION_END,
    render_project_block,
    render_protocol_block,
    replace_or_insert_block,
)
from par.domains.protocol.schemas.v1 import Hypothesis, QuestionSpec

_HYP = Hypothesis(
    statement="combinado supera comparador em ≥5 pts AUC",
    rationale="efeito piloto",
    metrics=["AUROC", "ECE"],
)


def _spec() -> QuestionSpec:
    return QuestionSpec(
        type="clinical",
        question="Em DS_A, a fusão combinado supera o melhor comparador?",
        created_at="2026-05-03",
        last_updated="2026-05-03",
        version=2,
        framework="PICOT",
        elements={
            "population": "DS_A + DS_BB",
            "intervention": "fusão combinado",
            "comparison": "melhor comparador",
            "outcome": "AUROC ≥ 0.85",
            "time": "retrospectivo",
        },
        hypothesis=_HYP,
    )


def _scoping_review() -> QuestionSpec:
    return QuestionSpec(
        type="review",
        design="revisão de escopo",
        question="O que se sabe sobre telessaúde na APS rural?",
        objective="Mapear a evidência sobre telessaúde na APS rural.",
        created_at="2026-11-12",
        last_updated="2026-11-12",
        version=1,
        framework="PCC",
        elements={"population": "APS rural", "concept": "telessaúde", "context": "Brasil"},
    )


def test_render_protocol_block_includes_fields() -> None:
    out = render_protocol_block(_spec(), hash8="a1b2c3d4")
    assert out.startswith(f"{QUESTION_BEGIN_PREFIX}v=2 hash=a1b2c3d4 -->")
    assert out.rstrip().endswith(QUESTION_END)
    assert "**Tipo de estudo.** clínico de intervenção" in out
    assert "**Pergunta do estudo.** Em DS_A" in out
    assert "**Estrutura (PICOT).**" in out
    assert "- **Intervenção (sob teste).** fusão combinado" in out
    assert "- **Comparador.** melhor comparador" in out
    assert "combinado supera comparador" in out
    assert "AUROC, ECE" in out


def test_render_project_block_includes_fields() -> None:
    out = render_project_block(_spec(), hash8="a1b2c3d4")
    assert "## Pergunta do estudo" in out
    assert "Em DS_A" in out
    assert "Hipótese central" in out


def test_render_review_without_hypothesis() -> None:
    out = render_protocol_block(_scoping_review(), hash8="00000000")
    assert "revisão (revisão de escopo)" in out
    assert "**Objetivo.** Mapear" in out
    assert "- **Conceito.** telessaúde" in out
    assert "Hipótese" not in out
    project = render_project_block(_scoping_review(), hash8="00000000")
    assert "**Objetivo:** Mapear" in project
    assert "Hipótese central" not in project


def test_render_without_framework_has_no_structure() -> None:
    spec = QuestionSpec(
        type="case_report",
        question="Como se apresentou a síndrome X em uma criança de 4 anos?",
        objective="Descrever apresentação atípica.",
        created_at="2026-11-12",
        last_updated="2026-11-12",
        version=1,
    )
    out = render_protocol_block(spec, hash8="00000000")
    assert "relato de caso" in out
    assert "Estrutura" not in out


def test_render_methodological() -> None:
    spec = QuestionSpec(
        type="methodological",
        question="O método M mantém a propriedade P sob a condição S?",
        created_at="2026-05-03",
        last_updated="2026-05-03",
        version=1,
        contribution="método M",
        hypothesis_validity_condition="a suposição S falha",
        hypothesis=_HYP,
    )
    out = render_project_block(spec, hash8="00000000")
    assert "método M" in out
    assert "suposição S" in out
    assert "População" not in out


def test_render_prediction_uses_predictor_labels() -> None:
    spec = QuestionSpec(
        type="prediction",
        question="A troponina prevê IAM em 30 dias?",
        created_at="2026-11-01",
        last_updated="2026-11-01",
        version=1,
        framework="PICOT",
        elements={
            "population": "dor torácica no PS",
            "intervention": "troponina ultrassensível",
            "outcome": "infarto agudo do miocárdio",
            "time": "30 dias",
        },
        hypothesis=_HYP,
    )
    out = render_protocol_block(spec, hash8="a1b2c3d4")
    assert "- **Preditor (index).** troponina ultrassensível" in out
    assert "- **Desfecho previsto.** infarto agudo do miocárdio" in out
    assert "- **Horizonte temporal.** 30 dias" in out
    assert "Comparador" not in out


def test_replace_or_insert_inserts_when_absent() -> None:
    text = "# Protocolo\n\n## Contexto\n\nProse humana.\n"
    block = render_protocol_block(_spec(), hash8="a1b2c3d4")
    out = replace_or_insert_block(text, block, anchor_pattern=r"^## Contexto.*$")
    assert QUESTION_BEGIN_PREFIX in out
    assert QUESTION_END in out
    assert "Prose humana." in out


def test_replace_or_insert_replaces_existing() -> None:
    block_old = f"{QUESTION_BEGIN_PREFIX}v=1 hash=11111111 -->\nold content\n{QUESTION_END}"
    out = replace_or_insert_block(
        f"# Doc\n\n{block_old}\n\nFooter humano.\n",
        render_protocol_block(_spec(), hash8="a1b2c3d4"),
        anchor_pattern=r"^# Doc.*$",
    )
    assert "old content" not in out
    assert "DS_A" in out
    assert "Footer humano." in out


def test_replace_or_insert_replaces_legacy_picot_block() -> None:
    block_old = f"{PICOT_BEGIN_PREFIX}v=1 hash=11111111 -->\nold content\n{PICOT_END}"
    out = replace_or_insert_block(
        f"# Doc\n\n{block_old}\n",
        render_protocol_block(_spec(), hash8="a1b2c3d4"),
        anchor_pattern=r"^# Doc.*$",
    )
    assert "old content" not in out
    assert "picot:" not in out
    assert out.count(QUESTION_BEGIN_PREFIX) == 1


def test_block_begin_re_extracts_version_and_hash() -> None:
    m = BLOCK_BEGIN_RE.search(render_protocol_block(_spec(), hash8="deadbeef"))
    assert m is not None
    assert m.group("version") == "2"
    assert m.group("hash") == "deadbeef"
    legacy = BLOCK_BEGIN_RE.search(f"{PICOT_BEGIN_PREFIX}v=3 hash=cafebabe -->")
    assert legacy is not None and legacy.group("hash") == "cafebabe"
