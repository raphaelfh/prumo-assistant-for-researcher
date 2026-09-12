"""Schemas Pydantic versionados pra outputs do domínio paper.

Forward-only: ``v2`` adiciona campos; existentes não mudam de semântica.
``schema_version`` no ``_meta`` permite migração explícita."""

from __future__ import annotations

from par.domains.paper.schemas.v1 import (
    Locator,
    PaperCallout,
    SupportReport,
    SupportVerdict,
)

__all__ = ["Locator", "PaperCallout", "SupportReport", "SupportVerdict"]
