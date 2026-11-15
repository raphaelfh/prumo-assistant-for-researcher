"""Deep diff entre dois ``QuestionSpec`` (atual vs snapshot do último ADR).

Detecta quais campos mudaram e quais são "estruturais" (mudança = bump de
versão + ADR novo). Campos não-estruturais (``last_updated``, ``rationale``)
podem mudar livremente sem bump.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from par.domains.protocol.schemas.v1 import QuestionSpec

STRUCTURAL_FIELDS: frozenset[str] = frozenset(
    {
        "type",
        "question",
        "design",
        "framework",
        "population",
        "intervention",
        "comparison",
        "outcome",
        "time",
        "contribution",
        "hypothesis_validity_condition",
        "hypothesis.statement",
        "hypothesis.metrics",
    }
)


def is_structural_field(field: str) -> bool:
    """``True`` se a mudança nesse campo deve gerar bump + ADR.

    Todo elemento do framework (``elements.<chave>``) é estrutural.
    """
    return field in STRUCTURAL_FIELDS or field.startswith("elements.")


@dataclass(frozen=True)
class FieldChange:
    """Mudança em 1 campo do ``QuestionSpec``."""

    field: str
    before: Any
    after: Any
    structural: bool


@dataclass(frozen=True)
class QuestionDiff:
    """Resultado de ``diff_question``: lista de mudanças + flag de structural."""

    changes: list[FieldChange]

    @property
    def has_structural(self) -> bool:
        return any(c.structural for c in self.changes)


def diff_question(before: QuestionSpec, after: QuestionSpec) -> QuestionDiff:
    """Compara campo-a-campo. Retorna ``QuestionDiff`` com lista de mudanças."""
    changes: list[FieldChange] = []
    flat_before = _flatten(before.model_dump(mode="python"))
    flat_after = _flatten(after.model_dump(mode="python"))
    all_keys = set(flat_before) | set(flat_after)
    for key in sorted(all_keys):
        if key == "schema_version":
            continue
        b = flat_before.get(key)
        a = flat_after.get(key)
        if b == a:
            continue
        changes.append(
            FieldChange(
                field=key,
                before=b,
                after=a,
                structural=is_structural_field(key),
            )
        )
    return QuestionDiff(changes=changes)


def _flatten(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Achata 1 nível de nested (``hypothesis.statement`` etc.)."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        full = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, prefix=f"{full}."))
        else:
            out[full] = v
    return out
