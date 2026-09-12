"""``prumo status`` — onde o estudo está e qual a próxima frase dizer (spec 2026-09-12, D5).

Determinístico e só leitura: olha o disco e não grava estado novo (mesma lógica da
ADR-0029 — comparação ao vivo não pode mentir). Vive no topo do pacote, como
``mcp_server.py`` (ADR-0017), porque compõe leituras de vários domínios; ``core/``
continua sem importar ``domains/``.

A ligação com o Zotero (autoexport do BBT) não é sinal daqui: só é observável por
RPC e já é assunto do ``prumo doctor``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from prumo_assist.core import criticmarkup, pj_layout
from prumo_assist.core.bib import parse_bib
from prumo_assist.core.note_paths import citekey_from_meta_path, extract_path, iter_note_meta_files
from prumo_assist.core.pj_layout import PjRootNotFoundError
from prumo_assist.core.skills import SkillRef, SkillRegistry
from prumo_assist.domains.paper.callout import hash_template
from prumo_assist.domains.paper.connect import bib_is_placeholder
from prumo_assist.domains.paper.sync import read_nota_yaml
from prumo_assist.domains.protocol.picot_io import read_picot
from prumo_assist.domains.write.review import (
    EVENT_KIND_AMBIGUOUS_ANCHOR,
    EVENT_KIND_NON_IDENTITY_SPAN,
    EVENT_KIND_UNANCHORED_MARK,
)
from prumo_assist.domains.write.schemas.v1 import ReviewEventsFile

__all__ = [
    "SCHEMA_VERSION",
    "ExtractStatus",
    "LibraryStatus",
    "NextStep",
    "PicotStatus",
    "ProjectStatus",
    "ReviewSummary",
    "ScopeStatus",
    "project_status",
    "render_status",
    "status_to_dict",
]

SCHEMA_VERSION = "ProjectStatus/v1"

#: Eventos que o modo ``review reconcile`` resolve — os que bloqueiam o ``apply``.
RECONCILE_KINDS = frozenset(
    {EVENT_KIND_UNANCHORED_MARK, EVENT_KIND_AMBIGUOUS_ANCHOR, EVENT_KIND_NON_IDENTITY_SPAN}
)

#: Arquivos de ``writing/`` que não são draft de manuscrito.
_NOT_DRAFTS = frozenset({"protocol.md"})


@dataclass(frozen=True)
class LibraryStatus:
    entries: int
    placeholder: bool
    synced_at: str | None


@dataclass(frozen=True)
class ExtractStatus:
    papers: int
    pending: int
    without_pdf: int
    stale: int


@dataclass(frozen=True)
class PicotStatus:
    closed: bool
    error: str | None = None


@dataclass(frozen=True)
class ReviewSummary:
    review: str
    reconcile_events: int
    pending_marks: int


@dataclass(frozen=True)
class ScopeStatus:
    slug: str
    drafts: tuple[str, ...]
    reviews: tuple[ReviewSummary, ...]


@dataclass(frozen=True)
class NextStep:
    """Próximo passo: o modo, a frase a dizer ao agente e o motivo."""

    skill: str
    mode: str
    say: str
    why: str
    scope: str | None = None

    @property
    def invocation(self) -> str:
        return "/" + SkillRef(self.skill, self.mode).invocation


@dataclass(frozen=True)
class ProjectStatus:
    project: Path
    library: LibraryStatus
    extracts: ExtractStatus
    picot: PicotStatus
    scopes: tuple[ScopeStatus, ...]
    next: NextStep | None


def _library(pj_root: Path) -> LibraryStatus:
    bib = pj_layout.bib_path(pj_root)
    if not bib.is_file():
        return LibraryStatus(entries=0, placeholder=True, synced_at=None)
    entries = len(parse_bib(bib.read_text(encoding="utf-8")))
    mtime = datetime.fromtimestamp(bib.stat().st_mtime, tz=UTC)
    return LibraryStatus(
        entries=entries,
        placeholder=bib_is_placeholder(pj_root),
        synced_at=mtime.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def _extracts(pj_root: Path) -> ExtractStatus:
    template = pj_root / ".claude" / "paper_extraction.md"
    current = hash_template(template) if template.is_file() else None
    metas = iter_note_meta_files(pj_root)
    pending = without_pdf = stale = 0
    for meta in metas:
        key = citekey_from_meta_path(meta)
        if not extract_path(pj_root, key).is_file():
            if (pj_layout.pdfs_dir(pj_root) / f"{key}.pdf").exists():
                pending += 1
            else:
                without_pdf += 1
            continue
        recorded = read_nota_yaml(meta).get("extracted_template_hash")
        if current and recorded and str(recorded) != current:
            stale += 1
    return ExtractStatus(papers=len(metas), pending=pending, without_pdf=without_pdf, stale=stale)


def _picot(pj_root: Path) -> PicotStatus:
    try:
        read_picot(pj_root)
    except FileNotFoundError:
        return PicotStatus(closed=False)
    except ValueError as exc:  # ValidationError e TOMLDecodeError são ValueError
        first = str(exc).strip().splitlines()
        return PicotStatus(closed=False, error=first[0] if first else type(exc).__name__)
    return PicotStatus(closed=True)


def _drafts(scope: Path) -> tuple[str, ...]:
    writing = pj_layout.writing_dir(scope)
    if not writing.is_dir():
        return ()
    return tuple(
        sorted(
            p.name
            for p in writing.glob("*.md")
            if p.name not in _NOT_DRAFTS and not p.name.startswith((".", "_"))
        )
    )


def _reconcile_events(events_yaml: Path) -> int:
    """Eventos que pedem ``review reconcile``. Sidecar ausente ou ilegível conta 0.

    ``status`` é informativo: sidecar corrompido é diagnosticado por
    ``prumo write review events``, que tem a mensagem de correção.
    """
    try:
        raw = yaml.safe_load(events_yaml.read_text(encoding="utf-8"))
        events = ReviewEventsFile.model_validate(raw or {}).events
    except (OSError, yaml.YAMLError, ValidationError):
        return 0
    return sum(1 for event in events if event.kind in RECONCILE_KINDS)


def _pending_marks(review_md: Path) -> int:
    try:
        return len(criticmarkup.parse(review_md.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return 0


def _reviews(pj_root: Path, slug: str) -> tuple[ReviewSummary, ...]:
    root = pj_root / "reviews"
    if not root.is_dir():
        return ()
    return tuple(
        ReviewSummary(
            review=d.name,
            reconcile_events=_reconcile_events(d / "events.yaml"),
            pending_marks=_pending_marks(d / "review.md"),
        )
        for d in sorted(root.glob(f"studies__{slug}__*"))
        if d.is_dir()
    )


def _scopes(pj_root: Path, scope: str | None) -> list[Path]:
    if scope is None:
        return pj_layout.iter_scopes(pj_root)
    target = pj_root / pj_layout.STUDIES_RELPATH / scope
    if not target.is_dir():
        existentes = ", ".join(s.name for s in pj_layout.iter_scopes(pj_root)) or "nenhum"
        raise PjRootNotFoundError(
            f"Escopo '{scope}' não existe em {pj_root} (existentes: {existentes}). "
            f"Crie com `prumo add study {scope}` ou passe um dos existentes em --scope."
        )
    return [target]


def _step(
    ref: SkillRef, why: str, registry: SkillRegistry | None, scope: str | None = None
) -> NextStep:
    mode = registry.find_mode(ref) if registry else None
    say = mode.phrases[0] if mode and mode.phrases else "/" + ref.invocation
    return NextStep(skill=ref.skill, mode=ref.mode, say=say, why=why, scope=scope)


def _next(
    library: LibraryStatus,
    extracts: ExtractStatus,
    picot: PicotStatus,
    scopes: tuple[ScopeStatus, ...],
    registry: SkillRegistry | None,
) -> NextStep | None:
    """Primeiro pendente numa ordem fixa (spec D5)."""
    if library.placeholder or library.entries == 0:
        return _step(
            SkillRef("paper", "library"),
            "a bibliografia do projeto está vazia — conecte a coleção do Zotero",
            registry,
        )
    if extracts.pending:
        return _step(
            SkillRef("paper", "extract"),
            f"{extracts.pending} paper(s) com PDF e sem extract",
            registry,
        )
    if not picot.closed:
        why = (
            f"a PICOT não valida ({picot.error})"
            if picot.error
            else "a PICOT ainda não foi fechada"
        )
        return _step(SkillRef("protocol", "picot"), why, registry)
    for scope in scopes:
        if not scope.drafts:
            return _step(
                SkillRef("write", "manuscript"),
                f"o escopo '{scope.slug}' ainda não tem draft em writing/",
                registry,
                scope.slug,
            )
    for scope in scopes:
        pendentes = sum(r.reconcile_events for r in scope.reviews)
        if pendentes:
            return _step(
                SkillRef("review", "reconcile"),
                f"{pendentes} evento(s) ambíguo(s) de revisão no escopo '{scope.slug}'",
                registry,
                scope.slug,
            )
    return None


def project_status(
    start: Path, *, scope: str | None = None, registry: SkillRegistry | None = None
) -> ProjectStatus:
    """Sinais do projeto que contém ``start`` e o próximo passo.

    ``registry`` dá a frase de cada modo; sem ele, ``say`` cai na própria invocação.

    Raises:
        PjRootNotFoundError: ``start`` fora de um ``pj_*``, ou ``scope`` inexistente.
    """
    pj_root = pj_layout.find_pj_root(start)
    library = _library(pj_root)
    extracts = _extracts(pj_root)
    picot = _picot(pj_root)
    scopes = tuple(
        ScopeStatus(slug=s.name, drafts=_drafts(s), reviews=_reviews(pj_root, s.name))
        for s in _scopes(pj_root, scope)
    )
    return ProjectStatus(
        project=pj_root,
        library=library,
        extracts=extracts,
        picot=picot,
        scopes=scopes,
        next=_next(library, extracts, picot, scopes, registry),
    )


def status_to_dict(status: ProjectStatus) -> dict[str, Any]:
    """Payload JSON versionado (``ProjectStatus/v1``) — o que o ``start`` lê."""
    nxt: dict[str, Any] | None = None
    if status.next is not None:
        nxt = {**asdict(status.next), "invocation": status.next.invocation}
    return {
        "schema_version": SCHEMA_VERSION,
        "project": str(status.project),
        "library": asdict(status.library),
        "extracts": asdict(status.extracts),
        "picot": asdict(status.picot),
        "scopes": [asdict(s) for s in status.scopes],
        "next": nxt,
    }


def render_status(status: ProjectStatus) -> str:
    """Resumo em texto para o terminal, terminando na frase do próximo passo."""
    lib, ex, picot = status.library, status.extracts, status.picot
    if picot.closed:
        picot_txt = "fechada"
    elif picot.error:
        picot_txt = f"inválida ({picot.error})"
    else:
        picot_txt = "aberta"
    lines = [
        f"Projeto: {status.project}",
        f"Bibliografia: {lib.entries} entrada(s)"
        + (" — ainda é o placeholder do scaffold" if lib.placeholder else ""),
        f"Papers: {ex.papers} · sem extract com PDF: {ex.pending} · sem PDF: {ex.without_pdf}"
        f" · extract desatualizado: {ex.stale}",
        f"PICOT: {picot_txt}",
    ]
    for scope in status.scopes:
        eventos = sum(r.reconcile_events for r in scope.reviews)
        marcas = sum(r.pending_marks for r in scope.reviews)
        lines.append(
            f"Escopo {scope.slug}: {len(scope.drafts)} draft(s) · eventos ambíguos: {eventos}"
            f" · marcas aguardando `prumo write review apply`: {marcas}"
        )
    lines.append("")
    if status.next is None:
        lines.append("Nada pendente pelos sinais do disco.")
    else:
        n = status.next
        lines.append(f'Próximo passo: diga "{n.say}" ({n.invocation}) — {n.why}.')
    return "\n".join(lines)
