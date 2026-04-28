"""Python API pra ``wiki``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from prumo_assist.domains.wiki import index as _index
from prumo_assist.domains.wiki import lint as _lint
from prumo_assist.domains.wiki import stats as _stats


def lint(pj_path: Path) -> dict[str, Any]:
    """Auditoria do wiki."""
    return _lint.lint(pj_path)


def reindex(pj_path: Path, *, name: str | None = None) -> dict[str, Any]:
    """Reindexa o wiki via qmd."""
    return _index.reindex(pj_path, name=name)


def stats(pj_path: Path) -> dict[str, Any]:
    """Contagem por tipo."""
    return _stats.stats(pj_path)
