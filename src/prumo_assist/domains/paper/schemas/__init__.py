"""Schemas Pydantic versionados pra outputs do domínio paper.

Forward-only: ``v2`` adiciona campos; existentes não mudam de semântica.
``schema_version`` no ``_meta`` permite migração explícita."""

from __future__ import annotations

from prumo_assist.domains.paper.schemas.v1 import PaperCallout

__all__ = ["PaperCallout"]
