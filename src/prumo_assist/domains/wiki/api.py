"""Python API pra ``wiki``."""

from __future__ import annotations

from prumo_assist.domains.wiki.findings import archive_as_finding
from prumo_assist.domains.wiki.index import reindex
from prumo_assist.domains.wiki.lint import lint
from prumo_assist.domains.wiki.stats import stats

__all__ = ["archive_as_finding", "lint", "reindex", "stats"]
