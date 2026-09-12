"""Provenance: bloco ``_meta`` embutido em cada artefato gerado.

Justificativa (clínico/IRB): toda saída de ``prumo`` precisa ser auditável daqui
a 5 anos sem depender de SaaS de terceiros. O ``_meta`` vai dentro de cada
artefato (frontmatter de nota, sidecar JSON do export), pra que o artefato
sozinho seja auto-suficiente pra reproduzir / auditar / citar.

Trace JSONL em ``.prumo/traces/`` está adiado até haver consumidor (ADR-0036).
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from par._version import __version__


def now_utc() -> str:
    """Timestamp ISO-8601 em UTC com sufixo ``Z`` (canônico, sem ambiguidade)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run_id() -> str:
    """ID curto (8 chars do uuid4 hex) suficiente pra distinguir runs locais."""
    return uuid.uuid4().hex[:8]


def hash_input(data: bytes | str) -> str:
    """SHA-256 truncado pra 16 hex chars — colisão desprezível no escopo local."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:16]


@dataclass(frozen=True)
class Meta:
    """Bloco ``_meta`` embutido em todo artefato gerado por ``prumo``.

    Forward-only: campos novos podem ser adicionados; existentes não mudam de
    semântica. Outputs antigos com ``Meta`` v1 continuam parseáveis em v2+.
    """

    run_id: str
    timestamp_utc: str
    prumo_version: str
    schema: str  # ex: "PaperCallout/v1"
    skill: str | None = None
    skill_version: str | None = None
    model: str | None = None
    input_hash: str | None = None
    cost_usd: float | None = None
    human_reviewed: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Remove None pra manter JSON enxuto e diff-friendly.
        return {k: v for k, v in d.items() if v not in (None, {}, [])}


def build_meta(
    *,
    schema: str,
    skill: str | None = None,
    skill_version: str | None = None,
    model: str | None = None,
    input_hash: str | None = None,
    cost_usd: float | None = None,
    run_id: str | None = None,
    human_reviewed: bool = False,
    extra: dict[str, Any] | None = None,
) -> Meta:
    """Helper para construir ``Meta`` com defaults sensatos."""
    return Meta(
        run_id=run_id or new_run_id(),
        timestamp_utc=now_utc(),
        prumo_version=__version__,
        schema=schema,
        skill=skill,
        skill_version=skill_version,
        model=model,
        input_hash=input_hash,
        cost_usd=cost_usd,
        human_reviewed=human_reviewed,
        extra=extra or {},
    )
