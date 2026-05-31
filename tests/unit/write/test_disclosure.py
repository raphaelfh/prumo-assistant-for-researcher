"""Testes do gerador de declaração de uso de IA."""

from __future__ import annotations

from pathlib import Path  # noqa: F401  # used by later tasks

from prumo_assist.domains.write.schemas.v1 import AIDisclosure, AIToolUse


def test_aitooluse_defaults() -> None:
    u = AIToolUse(tool="prumo-assist:paper-extract", task="t")
    assert u.count == 1
    assert u.human_reviewed is False
    assert u.model is None


def test_aidisclosure_schema_version() -> None:
    d = AIDisclosure(generated_at="t", statement_pt="p", statement_en="e")
    assert d.schema_version == "AIDisclosure/v1"
    assert d.tools == []
