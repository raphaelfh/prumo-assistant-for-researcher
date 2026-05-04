"""``SessionLog/v1`` — schema do log de sessão de active-learning."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

StepName = Literal["recall", "anchor", "connect", "apply", "reflect"]
SessionStatus = Literal["in-progress", "completed", "abandoned", "partial"]


class StepLog(BaseModel):
    """Log de 1 dos 5 steps da sessão."""

    step_name: StepName
    question: str = Field(..., min_length=1)
    answer: str = ""
    feedback: str = ""
    citations: list[str] = []
    references_missing: list[str] = []


class SessionLog(BaseModel):
    """Log canônico de uma sessão."""

    schema_version: Literal["SessionLog/v1"] = "SessionLog/v1"
    topic: str = Field(..., min_length=1)
    date: str = Field(..., description="ISO YYYY-MM-DD")
    duration_minutes: int = 0
    status: SessionStatus = "in-progress"
    sources_consulted: list[str] = []
    steps: list[StepLog] = []
    references_missing: list[str] = []
    finding_archived: Path | None = None
