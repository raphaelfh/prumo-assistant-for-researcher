"""Deep diff entre dois ``PicotSpec`` (atual vs snapshot do último ADR).

Detecta quais campos mudaram e quais são "estruturais" (mudança = bump de
versão + ADR novo). Campos não-estruturais (``last_updated``, ``rationale``)
podem mudar livremente sem bump.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from prumo_assist.domains.protocol.schemas.v1 import PicotSpec

STRUCTURAL_FIELDS: frozenset[str] = frozenset(
    {
        "type",
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
    """``True`` se a mudança nesse campo deve gerar bump + ADR."""
    return field in STRUCTURAL_FIELDS


@dataclass(frozen=True)
class FieldChange:
    """Mudança em 1 campo do ``PicotSpec``."""

    field: str
    before: Any
    after: Any
    structural: bool


@dataclass(frozen=True)
class PicotDiff:
    """Resultado de ``diff_picot``: lista de mudanças + flag de structural."""

    changes: list[FieldChange]

    @property
    def has_structural(self) -> bool:
        return any(c.structural for c in self.changes)


def diff_picot(before: PicotSpec, after: PicotSpec) -> PicotDiff:
    """Compara campo-a-campo. Retorna ``PicotDiff`` com lista de mudanças."""
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
    return PicotDiff(changes=changes)


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
