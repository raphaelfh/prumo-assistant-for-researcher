"""Tests para SessionLog/v1 + StepLog."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from prumo_assist.domains.wiki.schemas.v1 import SessionLog, StepLog


def test_step_log_minimal() -> None:
    s = StepLog(
        step_name="recall",
        question="Defina X",
        answer="X é Y",
        feedback="correto, mas faltou Z",
    )
    assert s.citations == []
    assert s.references_missing == []


def test_step_log_invalid_step_name() -> None:
    with pytest.raises(ValidationError):
        StepLog(step_name="invented", question="q", answer="a", feedback="f")  # type: ignore[arg-type]


def test_session_log_starts_in_progress() -> None:
    s = SessionLog(topic="x", date="2026-05-03")
    assert s.status == "in-progress"
    assert s.steps == []
    assert s.duration_minutes == 0
    assert s.finding_archived is None


def test_session_log_completed_status() -> None:
    s = SessionLog(topic="x", date="2026-05-03", status="completed")
    assert s.status == "completed"


def test_session_log_invalid_status() -> None:
    with pytest.raises(ValidationError):
        SessionLog(topic="x", date="2026-05-03", status="bogus")  # type: ignore[arg-type]


def test_session_log_schema_version() -> None:
    s = SessionLog(topic="x", date="2026-05-03")
    assert s.schema_version == "SessionLog/v1"
