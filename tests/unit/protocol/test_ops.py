"""End-to-end tests pros orquestradores `propagate` e `diff_against_last_adr`."""

from __future__ import annotations

from pathlib import Path

import pytest

from par.domains.protocol.ops import (
    AdrResult,
    InitResult,
    PropagateReport,
    create_question_adr,
    detect_mode,
    diff_against_last_adr,
    init_question_spec,
    propagate,
)
from par.domains.protocol.picot_io import picot_path, write_picot
from par.domains.protocol.question_io import question_path
from par.domains.protocol.schemas.v1 import Hypothesis, PicotSpec, question_from_picot


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


def _mk_project(tmp_path: Path, slug: str = "principal") -> tuple[Path, Path]:
    """Cria a raiz do projeto (marcador ``.claude/pj_config.toml``) e um escopo
    vazio (``notes/``, ``writing/``, ``decisions/``). Devolve ``(pj_root, scope)``.
    """
    pj = tmp_path / "pj_demo"
    (pj / ".claude").mkdir(parents=True)
    (pj / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    scope = pj / "docs" / "studies" / slug
    for sub in ("notes", "writing", "decisions"):
        (scope / sub).mkdir(parents=True)
    return pj, scope


def _bootstrap_pj(tmp_path: Path, slug: str = "principal") -> tuple[Path, Path]:
    """``_mk_project`` + ``protocol.md`` (escopo) e ``project_guide.md`` (projeto)."""
    pj, scope = _mk_project(tmp_path, slug)
    (scope / "writing" / "protocol.md").write_text(
        "# Protocolo do estudo\n\n## Contexto da pesquisa\n\nProse humana inicial.\n"
    )
    (pj / "docs" / "project_guide.md").write_text(
        "---\ntitle: Projeto\n---\n\n# Projeto\n\nIntro.\n"
    )
    return pj, scope


def test_propagate_inserts_blocks_when_absent(tmp_path: Path) -> None:
    pj, scope = _bootstrap_pj(tmp_path)
    write_picot(pj, _spec())
    report = propagate(scope)
    assert isinstance(report, PropagateReport)
    assert report.protocol_status == "inserted"
    assert report.project_status == "inserted"
    protocol_text = (scope / "writing" / "protocol.md").read_text()
    project_text = (pj / "docs" / "project_guide.md").read_text()
    assert "<!-- question:begin" in protocol_text
    assert "<!-- question:begin" in project_text
    assert "DS_A" in protocol_text
    assert "Pergunta do estudo" in project_text


def test_propagate_replaces_blocks_when_present(tmp_path: Path) -> None:
    pj, scope = _bootstrap_pj(tmp_path)
    write_picot(pj, _spec(population="DS_A"))
    propagate(scope)
    write_picot(pj, _spec(population="DS_A + DS_BB"))
    propagate(scope)
    text = (scope / "writing" / "protocol.md").read_text()
    assert "DS_A + DS_BB" in text
    assert text.count("<!-- question:begin") == 1
    assert "<!-- picot:begin" not in text


def test_propagate_unchanged_when_hash_matches(tmp_path: Path) -> None:
    pj, scope = _bootstrap_pj(tmp_path)
    write_picot(pj, _spec())
    propagate(scope)
    report = propagate(scope)
    assert report.protocol_status == "unchanged"
    assert report.project_status == "unchanged"


def test_propagate_raises_when_picot_missing(tmp_path: Path) -> None:
    _pj, scope = _bootstrap_pj(tmp_path)
    with pytest.raises(FileNotFoundError):
        propagate(scope)


def test_diff_against_last_adr_no_baseline_returns_diff_with_no_changes(
    tmp_path: Path,
) -> None:
    pj, scope = _bootstrap_pj(tmp_path)
    write_picot(pj, _spec())
    out = diff_against_last_adr(scope)
    assert out is not None
    assert out.changes == []
    assert out.has_structural is False


def test_diff_against_last_adr_detects_structural_change(tmp_path: Path) -> None:
    """Após ADR inicial, mudar campo estrutural produz diff structural."""
    from par.domains.protocol.adr import compose_adr, next_number
    from par.domains.protocol.diff import QuestionDiff

    pj, scope = _bootstrap_pj(tmp_path)
    spec_v1 = _spec(version=1, population="DS_A")
    write_picot(pj, spec_v1)
    decisions = scope / "decisions"
    body = compose_adr(
        adr_number=next_number(scope),
        spec=question_from_picot(spec_v1),
        diff=QuestionDiff(changes=[]),
        motivation="versão inicial",
        supersedes_path=None,
        date="2026-05-03",
    )
    (decisions / "adr-0001-picot-v1-versao-inicial.md").write_text(body)

    spec_v2 = _spec(version=2, population="DS_A + DS_BB")
    write_picot(pj, spec_v2)
    diff = diff_against_last_adr(scope)
    assert diff is not None
    assert diff.has_structural is True
    assert any(c.field == "elements.population" for c in diff.changes)


def test_detect_mode_init_when_nothing(tmp_path: Path) -> None:
    _pj, scope = _mk_project(tmp_path)
    assert detect_mode(scope) == "init"


def test_detect_mode_formalize_when_protocol_prose(tmp_path: Path) -> None:
    _pj, scope = _mk_project(tmp_path)
    (scope / "writing" / "protocol.md").write_text(
        "# Protocolo\n\nprosa humana.\n", encoding="utf-8"
    )
    assert detect_mode(scope) == "formalize"


def test_detect_mode_propagate_when_picot_no_adr(tmp_path: Path) -> None:
    pj, scope = _mk_project(tmp_path)
    write_picot(pj, _spec())
    assert detect_mode(scope) == "propagate"


def test_detect_mode_diff_when_baseline_adr(tmp_path: Path) -> None:
    pj, scope = _mk_project(tmp_path)
    write_picot(pj, _spec())
    (scope / "decisions" / "adr-0001-picot-v1-versao-inicial.md").write_text(
        "# adr\n", encoding="utf-8"
    )
    assert detect_mode(scope) == "diff"


def test_init_question_spec_writes_toml_and_adr(tmp_path: Path) -> None:
    pj, scope = _mk_project(tmp_path)
    result = init_question_spec(
        scope, spec=question_from_picot(_spec()), motivation="inicial", date="2026-06-14"
    )
    assert isinstance(result, InitResult)
    assert question_path(pj).exists()
    assert not picot_path(pj).exists()
    assert result.adr_path.exists()
    assert "question-v1-versao-inicial" in result.adr_path.name
    assert result.report.hash8 != ""


def test_create_question_adr_writes_and_propagates(tmp_path: Path) -> None:
    pj, scope = _bootstrap_pj(tmp_path)
    write_picot(pj, _spec(version=2, population="DS_A + DS_BB"))
    result = create_question_adr(
        scope, motivation="novo dataset", slug="novo-dataset", date="2026-06-14"
    )
    assert isinstance(result, AdrResult)
    assert result.adr_path.exists()
    assert "question-v2-novo-dataset" in result.adr_path.name
    # a gravação do ADR migra o picot.toml antigo (ADR-0041)
    assert question_path(pj).exists()
    assert not picot_path(pj).exists()


def test_propagate_replaces_legacy_picot_block(tmp_path: Path) -> None:
    pj, scope = _bootstrap_pj(tmp_path)
    protocol = scope / "writing" / "protocol.md"
    protocol.write_text(
        "# P\n\n<!-- picot:begin v=1 hash=deadbeef -->\nvelho\n<!-- picot:end -->\n"
    )
    write_picot(pj, _spec())
    assert propagate(scope).protocol_status == "updated"
    text = protocol.read_text()
    assert "velho" not in text and "<!-- picot:" not in text
    assert text.count("<!-- question:begin") == 1
