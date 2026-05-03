"""Python API pra ``wiki``."""

from __future__ import annotations

from prumo_assist.domains.wiki.index import reindex
from prumo_assist.domains.wiki.lint import lint
from prumo_assist.domains.wiki.stats import stats

__all__ = ["lint", "reindex", "stats"]
