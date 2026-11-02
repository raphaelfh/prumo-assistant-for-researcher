"""Tests para render TOML → blocos delimitados em protocol.md / project_guide.md."""

from __future__ import annotations

from par.domains.protocol.render import (
    BLOCK_BEGIN_RE,
    PICOT_BEGIN_PREFIX,
    PICOT_END,
    render_project_block,
    render_protocol_block,
    replace_or_insert_block,
)
from par.domains.protocol.schemas.v1 import Hypothesis, PicotSpec


def _spec() -> PicotSpec:
    return PicotSpec(
        type="clinical",
        created_at="2026-05-03",
        last_updated="2026-05-03",
        version=2,
        population="TCGA-BRCA + CPTAC",
        intervention="fusão multimodal",
        comparison="melhor unimodal",
        outcome="AUROC ≥ 0.85",
        time="retrospectivo",
        hypothesis=Hypothesis(
            statement="multimodal supera unimodal em ≥5 pts AUC",
            rationale="PID sinergia",
            metrics=["AUROC", "ECE"],
        ),
    )


def test_render_protocol_block_includes_fields() -> None:
    out = render_protocol_block(_spec(), hash8="a1b2c3d4")
    assert out.startswith(f"{PICOT_BEGIN_PREFIX}v=2 hash=a1b2c3d4 -->")
    assert out.rstrip().endswith(PICOT_END)
    assert "TCGA-BRCA + CPTAC" in out
    assert "fusão multimodal" in out
    assert "melhor unimodal" in out
    assert "AUROC ≥ 0.85" in out
    assert "retrospectivo" in out
    assert "multimodal supera unimodal" in out
    assert "AUROC, ECE" in out


def test_render_project_block_includes_fields() -> None:
    out = render_project_block(_spec(), hash8="a1b2c3d4")
    assert "Pergunta de pesquisa" in out
    assert "Hipótese central" in out
    assert "multimodal supera" in out


def test_render_methodological_omits_picot_fields() -> None:
    spec = PicotSpec(
        type="methodological",
        created_at="2026-05-03",
        last_updated="2026-05-03",
        version=1,
        contribution="conformal MNAR-aware",
        hypothesis_validity_condition="exchangeability quebra sob MNAR",
        hypothesis=Hypothesis(
            statement="cobertura ≈ nominal sob MNAR",
            rationale="IPW corrige",
            metrics=["coverage"],
        ),
    )
    out = render_project_block(spec, hash8="00000000")
    assert "conformal MNAR-aware" in out
    assert "exchangeability" in out
    # campos clínicos não aparecem
    assert "População" not in out


def test_replace_or_insert_inserts_when_absent() -> None:
    text = "# Protocolo\n\n## Contexto\n\nProse humana.\n"
    block = render_protocol_block(_spec(), hash8="a1b2c3d4")
    out = replace_or_insert_block(text, block, anchor_pattern=r"^## Contexto.*$")
    assert PICOT_BEGIN_PREFIX in out
    assert PICOT_END in out
    assert "Prose humana." in out  # preservado


def test_replace_or_insert_replaces_existing() -> None:
    block_old = f"{PICOT_BEGIN_PREFIX}v=1 hash=11111111 -->\nold content\n{PICOT_END}"
    block_new = render_protocol_block(_spec(), hash8="a1b2c3d4")
    text = f"# Doc\n\n{block_old}\n\nFooter humano.\n"
    out = replace_or_insert_block(text, block_new, anchor_pattern=r"^# Doc.*$")
    assert "old content" not in out
    assert "TCGA-BRCA" in out
    assert "Footer humano." in out


def test_block_begin_re_extracts_version_and_hash() -> None:
    block = render_protocol_block(_spec(), hash8="deadbeef")
    m = BLOCK_BEGIN_RE.search(block)
    assert m is not None
    assert m.group("version") == "2"
    assert m.group("hash") == "deadbeef"


def _prediction_spec(comparison: str | None = None) -> PicotSpec:
    return PicotSpec(
        type="prediction",
        created_at="2026-11-01",
        last_updated="2026-11-01",
        version=1,
        population="adultos com dor torácica no pronto-socorro",
        intervention="troponina ultrassensível na admissão",
        comparison=comparison,
        outcome="infarto agudo do miocárdio",
        time="30 dias",
        hypothesis=Hypothesis(
            statement="a troponina discrimina IAM com AUROC ≥ 0.85",
            rationale="derivação prévia",
            metrics=["AUROC"],
        ),
    )


def test_render_prediction_uses_predictor_labels() -> None:
    out = render_protocol_block(_prediction_spec(), hash8="a1b2c3d4")
    assert "**Preditor (index).** troponina ultrassensível na admissão" in out
    assert "**Desfecho previsto.** infarto agudo do miocárdio" in out
    assert "**Horizonte temporal.** 30 dias" in out
    assert "Sem comparador ativo" in out
    assert "Intervenção (sob teste)" not in out


def test_render_prediction_shows_comparison_when_given() -> None:
    out = render_protocol_block(_prediction_spec("escore HEART isolado"), hash8="a1b2c3d4")
    assert "**Comparador.** escore HEART isolado" in out
    project = render_project_block(_prediction_spec("escore HEART isolado"), hash8="a1b2c3d4")
    assert "comparado a **escore HEART isolado**" in project


def test_render_prediction_project_question_without_comparison() -> None:
    out = render_project_block(_prediction_spec(), hash8="a1b2c3d4")
    assert (
        "Em **adultos com dor torácica no pronto-socorro**, **troponina ultrassensível na "
        "admissão** prevê **infarto agudo do miocárdio** no horizonte de **30 dias**?"
    ) in out
    assert "comparado a" not in out
