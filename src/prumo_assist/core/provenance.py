"""Provenance: bloco ``_meta`` e trace JSONL **local-only**.

Justificativa (clínico/IRB): toda saída de ``prumo`` precisa ser auditável daqui
a 5 anos sem depender de SaaS de terceiros (Langfuse, Logfire). Política default:

- Trace é JSONL append-only em ``<project>/.prumo/traces/YYYY-MM-DD.jsonl``.
- Nunca sai da máquina sem opt-in explícito (flag ``--trace remote`` futura).
- Cada evento carrega ``run_id`` + ``timestamp_utc`` + ``event`` + payload livre.

O ``_meta`` block é o irmão "embutido" do trace: vai dentro de cada artefato
gerado (callout em nota, JSON de export, etc.), pra que o artefato sozinho seja
auto-suficiente pra reproduzir / auditar / citar.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from prumo_assist._version import __version__


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
        extra=extra or {},
    )


class TraceWriter:
    """Append-only JSONL writer em ``<project>/.prumo/traces/YYYY-MM-DD.jsonl``.

    Falhas de IO são swallowed silenciosamente (com fallback pra stderr) — trace
    nunca pode quebrar o comando do usuário. Use ``flush=True`` em testes.
    """

    def __init__(self, project_dir: Path | None = None) -> None:
        base = project_dir or Path.cwd()
        self._dir = base / ".prumo" / "traces"

    def emit(self, event: str, run_id: str, payload: dict[str, Any]) -> None:
        record = {
            "timestamp_utc": now_utc(),
            "run_id": run_id,
            "event": event,
            "prumo_version": __version__,
            **payload,
        }
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            today = datetime.now(UTC).strftime("%Y-%m-%d")
            target = self._dir / f"{today}.jsonl"
            with target.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            # Trace é best-effort. Em CI / sandboxes read-only, ignore.
            print(f"[prumo:trace] ignorado ({exc})", file=_stderr())

    @property
    def directory(self) -> Path:
        return self._dir


def _stderr() -> Any:
    """Lazy import pra evitar overhead em hot paths."""
    import sys

    return sys.stderr


def is_trace_disabled() -> bool:
    """Permite desligar trace via env var (útil em CI puro / sandboxing)."""
    return os.environ.get("PRUMO_NO_TRACE", "").lower() in {"1", "true", "yes"}
