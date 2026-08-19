"""Tests para helpers de session log."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.wiki.schemas.v1 import StepLog
from prumo_assist.domains.wiki.study import (
    append_step,
    create_session_log,
    finalize_session,
    session_log_path,
)


def _bootstrap(tmp_path: Path) -> Path:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    return pj


def test_session_log_path_no_escopo(tmp_path: Path) -> None:
    scope = _bootstrap(tmp_path)
    out = session_log_path(scope, "curvas-roc", "2026-05-03")
    assert out == scope / "notes" / "session-curvas-roc-2026-05-03.md"


def test_create_session_log_writes_yaml_frontmatter(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    out = create_session_log(
        scope=pj,
        topic="curvas-roc",
        date="2026-05-03",
        sources_consulted=["[@hanley1982roc]", "[[curvas-roc-prediction]]"],
    )
    assert out.exists()
    text = out.read_text()
    assert text.startswith("---\n")
    assert "topic: curvas-roc" in text
    assert "date: '2026-05-03'" in text or 'date: "2026-05-03"' in text
    assert "schema_version: SessionLog/v1" in text
    assert "in-progress" in text
    assert "[@hanley1982roc]" in text


def test_append_step_adds_section(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    log_path = create_session_log(
        scope=pj,
        topic="x",
        date="2026-05-03",
        sources_consulted=[],
    )
    append_step(
        log_path,
        StepLog(
            step_name="recall",
            question="Defina X",
            answer="X é Y",
            feedback="correto",
            citations=["[@a]"],
        ),
    )
    text = log_path.read_text()
    assert "## 1. Recall" in text
    assert "**Pergunta:** Defina X" in text
    assert "**Resposta:** X é Y" in text
    assert "**Feedback:** correto" in text


def test_append_multiple_steps_sequentially_numbered(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    log_path = create_session_log(
        scope=pj,
        topic="x",
        date="2026-05-03",
        sources_consulted=[],
    )
    for name in ("recall", "anchor", "connect"):
        append_step(
            log_path,
            StepLog(step_name=name, question="q", answer="a", feedback="f"),
        )
    text = log_path.read_text()
    assert "## 1. Recall" in text
    assert "## 2. Anchor" in text
    assert "## 3. Connect" in text


def test_finalize_session_updates_yaml(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    log_path = create_session_log(
        scope=pj,
        topic="x",
        date="2026-05-03",
        sources_consulted=[],
    )
    finalize_session(
        log_path,
        duration_minutes=18,
        status="completed",
        references_missing=["ROC multiclasse"],
        finding_archived=Path("docs/studies/principal/notes/x.md"),
    )
    text = log_path.read_text()
    assert "duration_minutes: 18" in text
    assert "status: completed" in text
    assert "ROC multiclasse" in text
    assert "docs/studies/principal/notes/x.md" in text
