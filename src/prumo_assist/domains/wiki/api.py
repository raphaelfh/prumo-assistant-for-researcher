"""Python API pra ``wiki``."""

from __future__ import annotations

from prumo_assist.domains.wiki.findings import archive_as_finding
from prumo_assist.domains.wiki.index import reindex
from prumo_assist.domains.wiki.lint import lint
from prumo_assist.domains.wiki.schemas.v1 import SessionLog, StepLog
from prumo_assist.domains.wiki.stats import stats
from prumo_assist.domains.wiki.study import (
    append_step,
    create_session_log,
    finalize_session,
    session_log_path,
)

__all__ = [
    "SessionLog",
    "StepLog",
    "append_step",
    "archive_as_finding",
    "create_session_log",
    "finalize_session",
    "lint",
    "reindex",
    "session_log_path",
    "stats",
]
