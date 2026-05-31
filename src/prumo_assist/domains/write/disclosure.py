"""Gera declaração de uso de IA a partir da proveniência dos artefatos.

Determinístico. Hoje a proveniência é heterogênea (o módulo
``core.provenance`` existe mas ainda não está ligado em todos os produtores):
extrações de paper gravam ``extracted_model``/``extracted_at`` em
``references/notes/<key>/_meta.md``; findings gravam ``generator`` no
frontmatter. Esta op colhe esses sinais (e qualquer bloco ``_meta:`` canônico
futuro), agrega por (skill, modelo) e renderiza o parágrafo de disclosure
exigido por periódicos e pelo EU AI Act.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from prumo_assist import PrumoError  # noqa: F401  # used by generate_disclosure (Task 5)
from prumo_assist.core.provenance import (
    now_utc,  # noqa: F401  # used by generate_disclosure (Task 5)
)
from prumo_assist.domains.write.schemas.v1 import (  # noqa: F401  # used by generate_disclosure (Task 5)
    AIDisclosure,
    AIToolUse,
)

__all__ = ["collect_records", "generate_disclosure"]  # noqa: F822  # generate_disclosure added by Task 5

_SKIP_PARTS = {".prumo", ".git", "build", "node_modules", ".venv"}

_TASK_BY_SKILL = {
    "paper-extract": "structured extraction of key information from source documents",
    "wiki-query": "synthesis of answers grounded in the project knowledge base",
    "active-learning": "synthesis of study-session findings",
    "peer-review": "critical review of draft sections",
    "write-paper": "drafting of manuscript sections",
    "write-scientific": "drafting of prose sections",
    "write-statistics": "drafting of the statistical analysis plan",
    "write-projeto-cep": "drafting of the research ethics submission",
}
_DEFAULT_TASK = "assistive text generation"


@dataclass(frozen=True)
class ProvRecord:
    skill: str
    model: str | None
    date: str | None
    human_reviewed: bool


def _read_frontmatter(md: Path) -> dict[str, Any] | None:
    text = md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        fm = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None
    return fm if isinstance(fm, dict) else None


def _record_from_fm(fm: dict[str, Any]) -> ProvRecord | None:
    _raw_meta = fm.get("_meta")
    meta: dict[str, Any] = _raw_meta if isinstance(_raw_meta, dict) else {}
    reviewed = bool(meta.get("human_reviewed", fm.get("human_reviewed", False)))
    if meta.get("skill") or meta.get("model"):  # future canonical block
        return ProvRecord(
            skill=str(meta.get("skill") or "prumo-assist"),
            model=str(meta["model"]) if meta.get("model") else None,
            date=str(meta["timestamp_utc"]) if meta.get("timestamp_utc") else None,
            human_reviewed=reviewed,
        )
    if fm.get("extracted_model"):  # paper-extract note metadata
        return ProvRecord(
            skill="paper-extract",
            model=str(fm["extracted_model"]),
            date=str(fm["extracted_at"]) if fm.get("extracted_at") else None,
            human_reviewed=reviewed,
        )
    if fm.get("generator"):  # finding frontmatter
        return ProvRecord(
            skill=str(fm["generator"]),
            model=str(fm["model"]) if fm.get("model") else None,
            date=str(fm["added"]) if fm.get("added") else None,
            human_reviewed=reviewed,
        )
    return None


def collect_records(root: Path) -> list[ProvRecord]:
    records: list[ProvRecord] = []
    for md in sorted(root.rglob("*.md")):
        if _SKIP_PARTS & set(md.parts):
            continue
        fm = _read_frontmatter(md)
        if fm is None:
            continue
        rec = _record_from_fm(fm)
        if rec is not None:
            records.append(rec)
    return records
