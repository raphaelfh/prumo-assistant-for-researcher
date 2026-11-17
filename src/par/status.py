"""``prumo status`` — onde o estudo está e qual a próxima frase dizer (spec 2026-09-12, D5).

Determinístico e só leitura: olha o disco e não grava estado novo (mesma lógica da
ADR-0029 — comparação ao vivo não pode mentir). Vive no topo do pacote, como
``mcp_server.py`` (ADR-0017), porque compõe leituras de vários domínios; ``core/``
continua sem importar ``domains/``.

A ligação com o Zotero (autoexport do BBT) não é sinal daqui: só é observável por
RPC e já é assunto do ``prumo doctor``. O que aparece é o registro que o
``paper connect`` gravou em ``.claude/zotero.toml`` (ADR-0044), lido do disco.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import ValidationError

from par.core import criticmarkup, pj_layout
from par.core.bib import parse_bib
from par.core.note_paths import citekey_from_meta_path, extract_path, iter_note_meta_files
from par.core.pj_layout import PjRootNotFoundError
from par.core.scaffold import is_pristine, module_writing_files
from par.core.skills import SkillRef, SkillRegistry
from par.domains.paper.callout import hash_template
from par.domains.paper.connect import bib_is_placeholder
from par.domains.paper.link import read_link, select_uri
from par.domains.paper.schemas.v1 import ZoteroLink
from par.domains.paper.sync import read_nota_yaml
from par.domains.protocol.question_io import read_question
from par.domains.write.export import EXT_BY_FORMAT, slugify
from par.domains.write.review import (
    EVENT_KIND_AMBIGUOUS_ANCHOR,
    EVENT_KIND_NON_IDENTITY_SPAN,
    EVENT_KIND_UNANCHORED_MARK,
)
from par.domains.write.schemas.v1 import ReviewEventsFile

__all__ = [
    "SCHEMA_VERSION",
    "ExtractStatus",
    "LibraryStatus",
    "NextStep",
    "PicotStatus",
    "ProjectStatus",
    "ReviewSummary",
    "ScopeStatus",
    "Stage",
    "project_status",
    "render_status",
    "status_to_dict",
]

SCHEMA_VERSION = "ProjectStatus/v1"

#: Eventos que o modo ``review reconcile`` resolve — os que bloqueiam o ``apply``.
RECONCILE_KINDS = frozenset(
    {EVENT_KIND_UNANCHORED_MARK, EVENT_KIND_AMBIGUOUS_ANCHOR, EVENT_KIND_NON_IDENTITY_SPAN}
)


@dataclass(frozen=True)
class LibraryStatus:
    entries: int
    placeholder: bool
    synced_at: str | None
    #: Coleção do Zotero gravada pelo ``paper connect`` (ADR-0044); ``None`` sem registro.
    zotero: ZoteroLink | None = None


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
    #: ``type`` e ``framework`` da pergunta fechada (resumo da etapa "Pergunta").
    kind: str | None = None
    framework: str | None = None


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


StageState = Literal["done", "current", "attention", "todo"]

#: Marcador de cada estado no texto do terminal (o painel "Projeto" usa os mesmos).
STAGE_MARKS: dict[str, str] = {"done": "✓", "current": "●", "attention": "!", "todo": "○"}


@dataclass(frozen=True)
class Stage:
    """Uma etapa do estudo, derivada do disco (ADR-0029).

    ``current`` é a primeira etapa não feita; antes dela, ``done`` ou ``attention``
    (pendência que não bloqueia); depois dela, ``todo``. Só ``current`` e
    ``attention`` trazem ``next``.
    """

    id: str
    title: str
    state: StageState
    summary: str
    next: NextStep | None = None
    scope: str | None = None


@dataclass(frozen=True)
class ProjectStatus:
    project: Path
    library: LibraryStatus
    extracts: ExtractStatus
    picot: PicotStatus
    scopes: tuple[ScopeStatus, ...]
    next: NextStep | None
    stages: tuple[Stage, ...] = ()


def _library(pj_root: Path) -> LibraryStatus:
    bib = pj_layout.bib_path(pj_root)
    if not bib.is_file():
        return LibraryStatus(entries=0, placeholder=True, synced_at=None, zotero=read_link(pj_root))
    entries = len(parse_bib(bib.read_text(encoding="utf-8")))
    mtime = datetime.fromtimestamp(bib.stat().st_mtime, tz=UTC)
    return LibraryStatus(
        entries=entries,
        placeholder=bib_is_placeholder(pj_root),
        synced_at=mtime.strftime("%Y-%m-%dT%H:%M:%SZ"),
        zotero=read_link(pj_root),
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
        spec = read_question(pj_root)
    except FileNotFoundError:
        return PicotStatus(closed=False)
    except ValueError as exc:  # ValidationError e TOMLDecodeError são ValueError
        first = str(exc).strip().splitlines()
        return PicotStatus(closed=False, error=first[0] if first else type(exc).__name__)
    return PicotStatus(closed=True, kind=spec.type, framework=spec.framework)


def _drafts(scope: Path, not_drafts: frozenset[str]) -> tuple[str, ...]:
    """Drafts de manuscrito do escopo: ``writing/*.md`` menos os esqueletos de módulo."""
    writing = pj_layout.writing_dir(scope)
    if not writing.is_dir():
        return ()
    return tuple(
        sorted(
            p.name
            for p in writing.glob("*.md")
            if p.name not in not_drafts and not p.name.startswith((".", "_"))
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


@dataclass(frozen=True)
class _Check:
    """Uma etapa antes de ganhar estado: feita ou não, e o passo que a resolve."""

    id: str
    title: str
    done: bool
    summary: str
    step: NextStep
    scope: str | None = None
    attention: NextStep | None = None


def _question_check(picot: PicotStatus, registry: SkillRegistry | None) -> _Check:
    if picot.closed:
        summary = (picot.kind or "fechada") + (f" · {picot.framework}" if picot.framework else "")
        why = "a pergunta do estudo está fechada"
    elif picot.error:
        summary = f"inválida: {picot.error}"
        why = f"a pergunta do estudo não valida ({picot.error})"
    else:
        summary = "ainda aberta"
        why = "a pergunta do estudo ainda não foi fechada"
    step = _step(SkillRef("protocol", "question"), why, registry)
    return _Check("question", "Pergunta", picot.closed, summary, step)


def _library_check(library: LibraryStatus, registry: SkillRegistry | None) -> _Check:
    done = not library.placeholder and library.entries > 0
    if done:
        synced = f" · sync {library.synced_at[:10]}" if library.synced_at else ""
        z = library.zotero
        source = f"{z.library} › {z.collection} · " if z else ""
        summary = f"{source}{library.entries} entrada(s){synced}"
    else:
        summary = "vazia — conecte a coleção do Zotero"
    why = "a bibliografia do projeto está vazia — conecte a coleção do Zotero"
    step = _step(SkillRef("paper", "library"), why, registry)
    return _Check("library", "Bibliografia", done, summary, step)


def _reading_check(extracts: ExtractStatus, registry: SkillRegistry | None) -> _Check:
    if extracts.papers == 0:
        # Sem paper no acervo não há o que ler: a etapa não está feita, e quem a
        # destrava é o sync da bibliografia, não o extract.
        why = "nenhum paper no acervo ainda — sincronize a bibliografia"
        step = _step(SkillRef("paper", "library"), why, registry)
        return _Check("reading", "Leitura", False, "nenhum paper no acervo", step)
    summary = (
        f"{extracts.pending} sem extract · {extracts.without_pdf} sem PDF"
        f" · {extracts.stale} desatualizado(s)"
    )
    ref = SkillRef("paper", "extract")
    step = _step(ref, f"{extracts.pending} paper(s) com PDF e sem extract", registry)
    attention = None
    if extracts.stale:
        why = f"{extracts.stale} extract(s) feitos com um template de extração anterior"
        attention = _step(ref, why, registry)
    return _Check("reading", "Leitura", extracts.pending == 0, summary, step, attention=attention)


#: Esqueletos do módulo ``protocol`` que a etapa acompanha → modo que os preenche.
#: ``protocol.md`` fica de fora: é documento vivo, e o bloco da pergunta já o altera.
_PROTOCOL_STEPS: tuple[tuple[str, SkillRef], ...] = (
    ("statistical_analysis_plan_skeleton.md", SkillRef("protocol", "sap")),
    ("projeto-cep.md", SkillRef("protocol", "cep")),
)


def _protocol_check(pj_root: Path, scope: Path, registry: SkillRegistry | None) -> _Check | None:
    writing = pj_layout.writing_dir(scope)
    if not (writing / "protocol.md").is_file():
        return None
    pending = [
        (name, ref)
        for name, ref in _PROTOCOL_STEPS
        if (writing / name).is_file()
        and is_pristine(pj_root, (writing / name).relative_to(pj_root))
    ]
    names = ", ".join(name for name, _ in pending)
    summary = (
        f"ainda esqueleto: {names}" if pending else "plano de análise e projeto CEP preenchidos"
    )
    ref = pending[0][1] if pending else SkillRef("protocol", "sap")
    why = f"no escopo '{scope.name}', ainda são esqueleto: {names}"
    step = _step(ref, why, registry, scope.name)
    return _Check("protocol", "Protocolo", not pending, summary, step, scope.name)


def _scope_checks(
    pj_root: Path, scope: ScopeStatus, registry: SkillRegistry | None
) -> list[_Check]:
    slug = scope.slug
    n = len(scope.drafts)
    checks = [
        _Check(
            "writing",
            "Escrita",
            n > 0,
            f"{n} draft(s)" if n else "sem draft",
            _step(
                SkillRef("write", "manuscript"),
                f"o escopo '{slug}' ainda não tem draft em writing/",
                registry,
                slug,
            ),
            slug,
        )
    ]
    if scope.reviews:
        eventos = sum(r.reconcile_events for r in scope.reviews)
        marcas = sum(r.pending_marks for r in scope.reviews)
        checks.append(
            _Check(
                "review",
                "Revisão",
                eventos == 0,
                f"{eventos} evento(s) ambíguo(s) · {marcas} marca(s) aguardando apply",
                _step(
                    SkillRef("review", "reconcile"),
                    f"{eventos} evento(s) ambíguo(s) de revisão no escopo '{slug}'",
                    registry,
                    slug,
                ),
                slug,
            )
        )
    if scope.drafts:
        writing = pj_layout.writing_dir(pj_root / pj_layout.STUDIES_RELPATH / slug)
        exports = pj_root / "build" / "exports"
        ext = EXT_BY_FORMAT["docx"]
        docx = [
            exports / f"{slugify(writing.relative_to(pj_root) / d, pj_root)}.{ext}"
            for d in scope.drafts
        ]
        found = sorted((p for p in docx if p.is_file()), key=lambda p: p.stat().st_mtime)
        if found:
            when = datetime.fromtimestamp(found[-1].stat().st_mtime, tz=UTC).strftime("%Y-%m-%d")
            summary = f"{found[-1].name} · {when}"
        else:
            summary = "nenhum docx exportado"
        step = _step(
            SkillRef("write", "export"),
            f"o escopo '{slug}' ainda não tem docx exportado",
            registry,
            slug,
        )
        checks.append(_Check("delivery", "Entrega", bool(found), summary, step, slug))
    return checks


def _stages(checks: list[_Check]) -> tuple[Stage, ...]:
    """Dá estado às etapas: a primeira não feita é ``current`` (spec 2026-11-14).

    Depois da ``current``, cada etapa mostra o próprio estado: feita é ``done`` (a
    pesquisadora pode sincronizar a bibliografia antes de fechar a pergunta), não
    feita é ``todo``.
    """
    out: list[Stage] = []
    seen_current = False
    for c in checks:
        if seen_current and not c.done:
            out.append(Stage(c.id, c.title, "todo", c.summary, None, c.scope))
        elif not c.done:
            out.append(Stage(c.id, c.title, "current", c.summary, c.step, c.scope))
            seen_current = True
        elif c.attention is not None:
            out.append(Stage(c.id, c.title, "attention", c.summary, c.attention, c.scope))
        else:
            out.append(Stage(c.id, c.title, "done", c.summary, None, c.scope))
    return tuple(out)


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
    not_drafts = module_writing_files()
    scope_paths = _scopes(pj_root, scope)
    scopes = tuple(
        ScopeStatus(slug=s.name, drafts=_drafts(s, not_drafts), reviews=_reviews(pj_root, s.name))
        for s in scope_paths
    )
    checks = [
        _question_check(picot, registry),
        _library_check(library, registry),
        _reading_check(extracts, registry),
    ]
    for scope_path, scope_status in zip(scope_paths, scopes, strict=True):
        protocol = _protocol_check(pj_root, scope_path, registry)
        if protocol is not None:
            checks.append(protocol)
        checks.extend(_scope_checks(pj_root, scope_status, registry))
    stages = _stages(checks)
    return ProjectStatus(
        project=pj_root,
        library=library,
        extracts=extracts,
        picot=picot,
        scopes=scopes,
        next=next((st.next for st in stages if st.state == "current"), None),
        stages=stages,
    )


def _zotero_dict(link: ZoteroLink | None) -> dict[str, Any] | None:
    return None if link is None else {**link.model_dump(), "select_uri": select_uri(link)}


def status_to_dict(status: ProjectStatus) -> dict[str, Any]:
    """Payload JSON versionado (``ProjectStatus/v1``) — o que o ``start`` lê."""

    def step(n: NextStep | None) -> dict[str, Any] | None:
        return None if n is None else {**asdict(n), "invocation": n.invocation}

    return {
        "schema_version": SCHEMA_VERSION,
        "project": str(status.project),
        "library": {**asdict(status.library), "zotero": _zotero_dict(status.library.zotero)},
        "extracts": asdict(status.extracts),
        "question": asdict(status.picot),
        # chave anterior à ADR-0041, mantida para quem já lê o JSON
        "picot": asdict(status.picot),
        "scopes": [asdict(s) for s in status.scopes],
        "next": step(status.next),
        "stages": [{**asdict(st), "next": step(st.next)} for st in status.stages],
    }


def render_status(status: ProjectStatus) -> str:
    """Etapas do estudo, uma por linha, terminando na frase do próximo passo."""
    lines = [f"Projeto: {status.project}", ""]
    for st in status.stages:
        where = f" ({st.scope})" if st.scope else ""
        lines.append(f"{STAGE_MARKS[st.state]} {st.title}{where}: {st.summary}")
    lines.append("")
    if status.next is None:
        lines.append("Nada pendente pelos sinais do disco.")
    else:
        n = status.next
        lines.append(f'Próximo passo: diga "{n.say}" ({n.invocation}) — {n.why}.')
    for st in status.stages:
        if st.state == "attention" and st.next is not None:
            lines.append(f'Atenção: {st.next.why} — diga "{st.next.say}" ({st.next.invocation}).')
    return "\n".join(lines)
