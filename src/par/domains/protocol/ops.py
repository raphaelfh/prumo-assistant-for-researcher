"""Orquestradores determinísticos de ``protocol``, expostos como ``prumo protocol *``.

Lado determinístico Python das operações: ``detect_mode`` (estado → modo),
``init_question_spec`` (escreve QuestionSpec + propaga + ADR-0001), ``create_question_adr``
(ADR-N + propaga), ``propagate`` (regenera blocos) e ``diff_against_last_adr``.
O modo ``protocol question`` chama estas funções via CLI (``prumo protocol …``),
não por import.

O julgamento agêntico (diálogo Socrático, ``formalize`` de prosa → QuestionSpec)
fica no ``SKILL.md``; aqui mora só o que é exato/auditável.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from par.core import pj_layout
from par.core.pj_layout import find_pj_root
from par.domains.protocol.adr import (
    compose_adr,
    extract_snapshot,
    find_last_question_adr,
    next_number,
    parse_snapshot,
)
from par.domains.protocol.diff import QuestionDiff, diff_question
from par.domains.protocol.drift import Drift, SourceText, collect, find_drift, merge_drift
from par.domains.protocol.question_io import (
    current_question_file,
    question_hash,
    read_question,
    write_question,
)
from par.domains.protocol.render import (
    BLOCK_BEGIN_RE,
    render_project_block,
    render_protocol_block,
    replace_or_insert_block,
)
from par.domains.protocol.schemas.v1 import QuestionSpec

PropagateStatus = Literal["inserted", "updated", "unchanged", "missing"]


@dataclass(frozen=True)
class PropagateReport:
    """Resultado de ``propagate``: status por destino."""

    protocol_status: PropagateStatus
    project_status: PropagateStatus
    hash8: str


def propagate(scope: Path) -> PropagateReport:
    """Lê ``question.toml`` (do projeto), regenera blocos delimitados em
    ``protocol.md`` (do escopo) e ``project_guide.md`` (do projeto).

    Status por destino:

    - ``missing``: arquivo destino não existe (humano precisa criar)
    - ``inserted``: bloco não existia, foi inserido após anchor
    - ``updated``: bloco existia, foi substituído (hash mudou)
    - ``unchanged``: bloco já tem o hash atual, nada a fazer
    """
    pj_root = find_pj_root(scope)
    spec = read_question(pj_root)
    h = question_hash(pj_root)

    protocol_status = _propagate_one(
        target=pj_layout.writing_dir(scope) / "protocol.md",
        block=render_protocol_block(spec, hash8=h),
        anchor=r"^# .+$",
        new_hash8=h,
    )
    project_status = _propagate_one(
        target=pj_root / "docs" / "project_guide.md",
        block=render_project_block(spec, hash8=h),
        anchor=r"^---\n.*?\n---",
        new_hash8=h,
    )
    return PropagateReport(
        protocol_status=protocol_status,
        project_status=project_status,
        hash8=h,
    )


def _propagate_one(
    *,
    target: Path,
    block: str,
    anchor: str,
    new_hash8: str,
) -> PropagateStatus:
    if not target.exists():
        return "missing"
    text = target.read_text(encoding="utf-8")
    existing = BLOCK_BEGIN_RE.search(text)
    if existing and existing.group("hash") == new_hash8:
        return "unchanged"
    new_text = replace_or_insert_block(text, block, anchor_pattern=anchor)
    target.write_text(new_text, encoding="utf-8")
    return "updated" if existing else "inserted"


def detect_mode(scope: Path) -> str:
    """Detecta a operação do modo ``protocol question`` pelo estado do escopo/projeto.

    Retorna ``init`` | ``formalize`` | ``propagate`` | ``diff``.
    """
    protocol_md = pj_layout.writing_dir(scope) / "protocol.md"
    pj_root = find_pj_root(scope)
    if current_question_file(pj_root) is None:
        has_prose = protocol_md.exists() and protocol_md.read_text(errors="ignore").strip() != ""
        return "formalize" if has_prose else "init"
    if find_last_question_adr(scope) is None:
        return "propagate"
    return "diff"


@dataclass(frozen=True)
class InitResult:
    """Resultado de ``init_question_spec``: relatório de propagação + caminho do ADR-0001."""

    report: PropagateReport
    adr_path: Path


def init_question_spec(
    scope: Path, *, spec: QuestionSpec, motivation: str, date: str
) -> InitResult:
    """Escreve o ``QuestionSpec`` inicial (no projeto), propaga os blocos e cria o
    ADR-0001 (no escopo)."""
    pj_root = find_pj_root(scope)
    write_question(pj_root, spec)
    report = propagate(scope)
    n = next_number(scope)
    body = compose_adr(
        adr_number=n,
        spec=spec,
        diff=QuestionDiff(changes=[]),
        motivation=motivation,
        supersedes_path=None,
        date=date,
    )
    adr_path = pj_layout.decisions_dir(scope) / f"adr-{n:04d}-question-v1-versao-inicial.md"
    adr_path.parent.mkdir(parents=True, exist_ok=True)
    adr_path.write_text(body, encoding="utf-8")
    return InitResult(report=report, adr_path=adr_path)


@dataclass(frozen=True)
class AdrResult:
    """Resultado de ``create_question_adr``: relatório de propagação + caminho do ADR."""

    report: PropagateReport
    adr_path: Path


def create_question_adr(scope: Path, *, motivation: str, slug: str, date: str) -> AdrResult:
    """Grava o ADR-N (no escopo) para a versão atual do ``question.toml`` (após bump)
    e propaga."""
    pj_root = find_pj_root(scope)
    spec = read_question(pj_root)
    # read_question acima já garante que a pergunta existe, então diff_against_last_adr
    # nunca retorna None aqui; o ``or`` só estreita o tipo p/ mypy.
    diff = diff_against_last_adr(scope) or QuestionDiff(changes=[])
    last_adr = find_last_question_adr(scope)
    # A gravação migra o question.toml antigo para question.toml (ADR-0041).
    write_question(pj_root, spec)
    n = next_number(scope)
    body = compose_adr(
        adr_number=n,
        spec=spec,
        diff=diff,
        motivation=motivation,
        supersedes_path=last_adr,
        date=date,
    )
    adr_path = pj_layout.decisions_dir(scope) / f"adr-{n:04d}-question-v{spec.version}-{slug}.md"
    adr_path.parent.mkdir(parents=True, exist_ok=True)
    adr_path.write_text(body, encoding="utf-8")
    report = propagate(scope)
    return AdrResult(report=report, adr_path=adr_path)


def diff_against_last_adr(scope: Path) -> QuestionDiff | None:
    """Compara ``question.toml`` atual (do projeto) contra snapshot do último ADR
    ``question-v<N>`` (do escopo).

    Retorna ``None`` se ``question.toml`` ausente. Retorna ``QuestionDiff`` com
    ``changes=[]`` quando não há ADR baseline (caller decide criar v1).
    """
    pj_root = find_pj_root(scope)
    if current_question_file(pj_root) is None:
        return None
    current = read_question(pj_root)
    last_adr = find_last_question_adr(scope)
    if last_adr is None:
        return QuestionDiff(changes=[])
    snapshot_text = extract_snapshot(last_adr.read_text(encoding="utf-8"))
    if snapshot_text is None:
        return QuestionDiff(changes=[])
    return diff_question(parse_snapshot(snapshot_text), current)


def manuscript_drift(scope: Path, draft: Path | None = None) -> list[Drift]:
    """Drift entre drafts do escopo e o lado protocolo (``protocol.md`` + ``question.toml``).

    ``draft`` restringe a um arquivo; sem ele, todo ``writing/*.md`` exceto
    ``protocol.md``. Só lê — nunca edita o manuscrito.
    """
    pj_root = find_pj_root(scope)
    protocol_md = pj_layout.writing_dir(scope) / "protocol.md"
    question_file = current_question_file(pj_root)
    candidates = (protocol_md, question_file) if question_file else (protocol_md,)
    protocol_side = [_source(p, pj_root) for p in candidates if p.is_file()]
    if not protocol_side:
        return []
    if draft is not None:
        drafts = [draft] if draft.resolve() != protocol_md.resolve() else []
    else:
        drafts = sorted(
            p for p in pj_layout.writing_dir(scope).glob("*.md") if p.name != "protocol.md"
        )
    protocol_facts = collect(protocol_side)
    return merge_drift(
        d for path in drafts for d in find_drift(protocol_facts, _source(path, pj_root))
    )


def _source(path: Path, pj_root: Path) -> SourceText:
    resolved = path.resolve()
    try:
        label = resolved.relative_to(pj_root.resolve()).as_posix()
    except ValueError:
        label = str(resolved)
    lines = tuple(resolved.read_text(encoding="utf-8", errors="ignore").splitlines())
    return SourceText(label=label, lines=lines)
