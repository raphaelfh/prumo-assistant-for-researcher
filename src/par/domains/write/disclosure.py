"""Gera declaração de uso de IA a partir da proveniência dos artefatos.

Determinístico. Lê o bloco ``_meta`` canônico (``core.provenance.build_meta``)
que extract, findings, study e ``write draft`` gravam no frontmatter. Único
fallback legado: ``extracted_model``/``extracted_at`` de ``_meta.md`` extraídos
antes do carimbo (126 arquivos nos pj_* em 2026-09-12). Agrega por (skill,
modelo) e renderiza o parágrafo de disclosure exigido por periódicos e pelo
EU AI Act.

O nome de skill gravado é canonizado pelo registry de skills antes de agregar:
``wiki-query`` (legado) e ``wiki/query`` (novo) viram a mesma ferramenta
``par:wiki query``, e a tarefa descrita vem do
``prumo.disclosure_task`` do modo (Princípios I e IV).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from par import PrumoError
from par.core.obsidian import split_frontmatter
from par.core.paths import find_resource
from par.core.provenance import now_utc
from par.core.skills import SkillRegistry, load_skill_registry
from par.domains.write.schemas.v1 import AIDisclosure, AIToolUse, VenueProfile

__all__ = ["collect_records", "generate_disclosure", "load_venue_profiles"]

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
    # A flag humana mora no frontmatter e prevalece; ``_meta`` só a traz se declarada.
    reviewed = bool(fm.get("human_reviewed", meta.get("human_reviewed")))
    if meta.get("skill") or meta.get("model"):  # bloco canônico
        return ProvRecord(
            skill=str(meta.get("skill") or "par"),
            model=str(meta["model"]) if meta.get("model") else None,
            date=str(meta["timestamp_utc"]) if meta.get("timestamp_utc") else None,
            human_reviewed=reviewed,
        )
    if fm.get("extracted_model"):  # legado: extract anterior ao carimbo
        return ProvRecord(
            skill="paper-extract",
            model=str(fm["extracted_model"]),
            date=str(fm["extracted_at"]) if fm.get("extracted_at") else None,
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


def _render(uses: list[AIToolUse], lang: str, *, dates: str = "") -> str:
    if not uses:
        if lang == "pt":
            return "Nenhuma ferramenta de IA generativa foi usada na preparação deste trabalho."
        return "No generative AI tools were used in the preparation of this work."
    items = "; ".join(_phrase(u) for u in uses) + dates
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


_FILLED = {"tool", "model", "task", "dates", "human_review"}
_MANUAL = {
    "manufacturer": ("fabricante da ferramenta", "tool manufacturer"),
    "prompts": ("prompts usados, quando aplicável", "prompts used, where applicable"),
    "rationale": ("por que a ferramenta foi usada", "why the tool was used"),
}
_PLACEMENT = {
    "methods": ("Métodos", "Methods"),
    "acknowledgments": ("Agradecimentos", "Acknowledgments"),
    "cover_letter": ("carta ao editor", "cover letter"),
    "contributorship": ("declaração de contribuição", "contributorship statement"),
}


def load_venue_profiles(text: str | None = None) -> dict[str, VenueProfile]:
    """Carrega e valida ``venue_policies.toml`` (ou ``text``, nos testes).

    Perfil sem ``source_url``/``accessed`` ou com elemento/local desconhecido é
    defeito do pacote: falha alto em vez de emitir política não conferida.
    """
    if text is None:
        pkg = resources.files("par.domains.write")
        text = pkg.joinpath("venue_policies.toml").read_text(encoding="utf-8")
    data = tomllib.loads(text)
    profiles: dict[str, VenueProfile] = {}
    for key, raw in data.get("venues", {}).items():
        try:
            prof = VenueProfile(key=key, **raw)
        except ValidationError as exc:
            raise PrumoError(
                f"perfil de periódico '{key}' inválido em venue_policies.toml ({exc.error_count()} "
                "erro(s)); todo perfil exige source_url e accessed conferidos na página do "
                "periódico: corrija o arquivo ou remova o perfil."
            ) from exc
        unknown = (set(prof.required) - _FILLED - set(_MANUAL)) | (
            set(prof.placement) - set(_PLACEMENT)
        )
        if unknown:
            raise PrumoError(
                f"perfil '{key}' usa chave(s) desconhecida(s) {sorted(unknown)} em "
                "venue_policies.toml: use só as chaves documentadas no cabeçalho do arquivo."
            )
        profiles[key] = prof
    return profiles


def _dates_clause(date_from: str | None, date_to: str | None, lang: str) -> str:
    if not date_from or not date_to:
        return ""
    a, b = date_from[:10], date_to[:10]
    return f" entre {a} e {b}" if lang == "pt" else f" between {a} and {b}"


def _render_venue(
    uses: list[AIToolUse],
    lang: str,
    prof: VenueProfile,
    date_from: str | None,
    date_to: str | None,
) -> str:
    dates = _dates_clause(date_from, date_to, lang) if "dates" in prof.required else ""
    base = _render(uses, lang, dates=dates)
    idx = 0 if lang == "pt" else 1
    where = " / ".join(_PLACEMENT[p][idx] for p in prof.placement)
    manual = [_MANUAL[e][idx] for e in prof.required if e in _MANUAL]
    lines = [base]
    if uses and manual:
        head = "Complete antes de submeter" if lang == "pt" else "Complete before submitting"
        lines.append(f"{head}: {'; '.join(manual)}.")
    label = "Local" if lang == "pt" else "Placement"
    lines.append(f"{label} ({prof.name}): {where}.")
    return "\n\n".join(lines)


def _unknown_venue_line(venue: str, known: list[str], lang: str) -> str:
    names = ", ".join(known)
    if lang == "pt":
        return (
            f"Sem perfil no prumo para '{venue}' (perfis: {names}); confira a página de "
            "política de IA do periódico antes de submeter."
        )
    return (
        f"No prumo profile for '{venue}' (profiles: {names}); check the journal's AI "
        "policy page before submitting."
    )


def generate_disclosure(*, root: Path | None = None, venue: str | None = None) -> AIDisclosure:
    """Varre ``root`` (default: cwd) e devolve uma ``AIDisclosure``.

    ``venue`` (ex.: ``jama``) aplica o perfil do periódico: preenche os elementos
    exigidos pela proveniência e diz uma vez onde a declaração vai. Periódico sem
    perfil mantém o texto genérico com uma linha pedindo conferir a política.
    """
    root = root or Path.cwd()
    if not root.exists():
        raise PrumoError(f"diretório não encontrado: {root}")
    records = collect_records(root)
    uses = _aggregate(records, _load_registry())
    dates = sorted(r.date for r in records if r.date)
    date_from = dates[0] if dates else None
    date_to = dates[-1] if dates else None
    prof: VenueProfile | None = None
    known: list[str] = []
    if venue:
        profiles = load_venue_profiles()
        prof = profiles.get(venue.strip().lower())
        known = sorted(profiles)

    def render(lang: str) -> str:
        if prof is not None:
            return _render_venue(uses, lang, prof, date_from, date_to)
        text = _render(uses, lang)
        if venue:
            text = f"{text}\n\n{_unknown_venue_line(venue, known, lang)}"
        return text

    statements = {lang: render(lang) for lang in ("pt", "en")}
    return AIDisclosure(
        generated_at=now_utc(),
        date_from=date_from,
        date_to=date_to,
        tools=uses,
        statement_pt=statements["pt"],
        statement_en=statements["en"],
        venue=prof,
    )
