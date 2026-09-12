"""Gera declaração de uso de IA a partir da proveniência dos artefatos.

Determinístico. Hoje a proveniência é heterogênea (o módulo
``core.provenance`` existe mas ainda não está ligado em todos os produtores):
extrações de paper gravam ``extracted_model``/``extracted_at`` em
``references/notes/<key>/_meta.md``; findings gravam ``generator`` no
frontmatter. Esta op colhe esses sinais (e qualquer bloco ``_meta:`` canônico
futuro), agrega por (skill, modelo) e renderiza o parágrafo de disclosure
exigido por periódicos e pelo EU AI Act.

O nome de skill gravado é canonizado pelo registry de skills antes de agregar:
``generator: wiki-query`` (legado) e ``generator: wiki/query`` (novo) viram a
mesma ferramenta ``par:wiki query``, e a tarefa descrita vem do
``prumo.disclosure_task`` do modo (Princípios I e IV).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from par import PrumoError
from par.core.obsidian import split_frontmatter
from par.core.paths import find_resource
from par.core.provenance import now_utc
from par.core.skills import SkillRegistry, load_skill_registry
from par.domains.write.schemas.v1 import AIDisclosure, AIToolUse

__all__ = ["collect_records", "generate_disclosure"]

_SKIP_PARTS = {".prumo", ".git", "build", "node_modules", ".venv"}

_DEFAULT_TASK = "assistive text generation"


@dataclass(frozen=True)
class ProvRecord:
    skill: str
    model: str | None
    date: str | None
    human_reviewed: bool


def _read_frontmatter(md: Path) -> dict[str, Any] | None:
    fm, _ = split_frontmatter(md.read_text(encoding="utf-8"))
    return fm or None


def _record_from_fm(fm: dict[str, Any]) -> ProvRecord | None:
    _raw_meta = fm.get("_meta")
    meta: dict[str, Any] = _raw_meta if isinstance(_raw_meta, dict) else {}
    reviewed = bool(meta.get("human_reviewed", fm.get("human_reviewed", False)))
    if meta.get("skill") or meta.get("model"):  # future canonical block
        return ProvRecord(
            skill=str(meta.get("skill") or "par"),
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


@dataclass
class _Group:
    count: int = 0
    all_reviewed: bool = True


def _load_registry() -> SkillRegistry | None:
    """Registry do bundle de skills; ``None`` quando o bundle não está resolvível."""
    root = find_resource("skills")
    if root is None:
        return None
    registry, _ = load_skill_registry(root, strict=False)
    return registry


def _canonical(skill: str, registry: SkillRegistry | None) -> tuple[str, str]:
    """(rótulo da ferramenta, tarefa) de um valor de proveniência, legado ou novo.

    Valor que não resolve para um modo existente mantém o comportamento antigo:
    rótulo com prefixo ``par:`` e tarefa genérica.
    """
    ref = registry.resolve(skill) if registry else None
    if registry is None or ref is None:
        tool = skill if skill.startswith("par:") else f"par:{skill}"
        return tool, _DEFAULT_TASK
    mode = registry.find_mode(ref)
    task = mode.disclosure_task if mode and mode.disclosure_task else _DEFAULT_TASK
    return ref.invocation, task


def _aggregate(records: list[ProvRecord], registry: SkillRegistry | None) -> list[AIToolUse]:
    grouped: dict[tuple[str, str, str], _Group] = {}
    for r in records:
        tool, task = _canonical(r.skill, registry)
        slot = grouped.setdefault((tool, r.model or "", task), _Group())
        slot.count += 1
        slot.all_reviewed = slot.all_reviewed and r.human_reviewed
    return [
        AIToolUse(
            tool=tool,
            model=model or None,
            task=task,
            count=slot.count,
            human_reviewed=slot.all_reviewed,
        )
        for (tool, model, task), slot in sorted(grouped.items())
    ]


def _phrase(use: AIToolUse) -> str:
    head = f"{use.tool} ({use.model})" if use.model else use.tool
    return f"{head} for {use.task}"


def _render(uses: list[AIToolUse], lang: str) -> str:
    if not uses:
        if lang == "pt":
            return "Nenhuma ferramenta de IA generativa foi usada na preparação deste trabalho."
        return "No generative AI tools were used in the preparation of this work."
    items = "; ".join(_phrase(u) for u in uses)
    if lang == "pt":
        return (
            f"Durante a preparação deste trabalho, o(s) autor(es) utilizaram {items}. "
            "Após o uso dessas ferramentas, o(s) autor(es) revisaram e editaram o "
            "conteúdo conforme necessário e assumem total responsabilidade pelo "
            "conteúdo da publicação."
        )
    return (
        f"During the preparation of this work, the author(s) used {items}. "
        "After using these tools, the author(s) reviewed and edited the content as "
        "needed and take full responsibility for the content of the publication."
    )


def generate_disclosure(*, root: Path | None = None) -> AIDisclosure:
    """Varre ``root`` (default: cwd) e devolve uma ``AIDisclosure``."""
    root = root or Path.cwd()
    if not root.exists():
        raise PrumoError(f"diretório não encontrado: {root}")
    records = collect_records(root)
    uses = _aggregate(records, _load_registry())
    dates = sorted(r.date for r in records if r.date)
    return AIDisclosure(
        generated_at=now_utc(),
        date_from=dates[0] if dates else None,
        date_to=dates[-1] if dates else None,
        tools=uses,
        statement_pt=_render(uses, "pt"),
        statement_en=_render(uses, "en"),
    )
