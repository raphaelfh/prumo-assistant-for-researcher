"""Orquestradores determinísticos de ``protocol``, expostos como ``prumo protocol *``.

Lado determinístico Python das operações: ``detect_mode`` (estado → modo),
``init_picot_spec`` (escreve PicotSpec + propaga + ADR-0001), ``create_picot_adr``
(ADR-N + propaga), ``propagate`` (regenera blocos) e ``diff_against_last_adr``.
O modo ``protocol picot`` chama estas funções via CLI (``prumo protocol …``),
não por import.

O julgamento agêntico (diálogo Socrático, ``formalize`` de prosa → PicotSpec)
fica no ``SKILL.md``; aqui mora só o que é exato/auditável.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from prumo_assist.core import pj_layout
from prumo_assist.core.pj_layout import find_pj_root
from prumo_assist.domains.protocol.adr import (
    compose_adr,
    extract_picot_snapshot,
    find_last_picot_adr,
    next_number,
)
from prumo_assist.domains.protocol.diff import PicotDiff, diff_picot
from prumo_assist.domains.protocol.picot_io import (
    picot_hash,
    picot_path,
    read_picot,
    write_picot,
)
from prumo_assist.domains.protocol.render import (
    BLOCK_BEGIN_RE,
    render_project_block,
    render_protocol_block,
    replace_or_insert_block,
)
from prumo_assist.domains.protocol.schemas.v1 import PicotSpec

PropagateStatus = Literal["inserted", "updated", "unchanged", "missing"]


@dataclass(frozen=True)
class PropagateReport:
    """Resultado de ``propagate``: status por destino."""

    protocol_status: PropagateStatus
    project_status: PropagateStatus
    hash8: str


def propagate(scope: Path) -> PropagateReport:
    """Lê ``picot.toml`` (do projeto), regenera blocos delimitados em
    ``protocol.md`` (do escopo) e ``project_guide.md`` (do projeto).

    Status por destino:

    - ``missing``: arquivo destino não existe (humano precisa criar)
    - ``inserted``: bloco não existia, foi inserido após anchor
    - ``updated``: bloco existia, foi substituído (hash mudou)
    - ``unchanged``: bloco já tem o hash atual, nada a fazer
    """
    pj_root = find_pj_root(scope)
    spec = read_picot(pj_root)
    h = picot_hash(pj_root)

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
    """Detecta a operação do modo ``protocol picot`` pelo estado do escopo/projeto.

    Retorna ``init`` | ``formalize`` | ``propagate`` | ``diff``.
    """
    protocol_md = pj_layout.writing_dir(scope) / "protocol.md"
    pj_root = find_pj_root(scope)
    if not picot_path(pj_root).exists():
        has_prose = protocol_md.exists() and protocol_md.read_text(errors="ignore").strip() != ""
        return "formalize" if has_prose else "init"
    if find_last_picot_adr(scope) is None:
        return "propagate"
    return "diff"


@dataclass(frozen=True)
class InitResult:
    """Resultado de ``init_picot_spec``: relatório de propagação + caminho do ADR-0001."""

    report: PropagateReport
    adr_path: Path


def init_picot_spec(scope: Path, *, spec: PicotSpec, motivation: str, date: str) -> InitResult:
    """Escreve o ``PicotSpec`` inicial (no projeto), propaga os blocos e cria o
    ADR-0001 (no escopo)."""
    pj_root = find_pj_root(scope)
    write_picot(pj_root, spec)
    report = propagate(scope)
    n = next_number(scope)
    body = compose_adr(
        adr_number=n,
        spec=spec,
        diff=PicotDiff(changes=[]),
        motivation=motivation,
        supersedes_path=None,
        date=date,
    )
    adr_path = pj_layout.decisions_dir(scope) / f"adr-{n:04d}-picot-v1-versao-inicial.md"
    adr_path.parent.mkdir(parents=True, exist_ok=True)
    adr_path.write_text(body, encoding="utf-8")
    return InitResult(report=report, adr_path=adr_path)


@dataclass(frozen=True)
class AdrResult:
    """Resultado de ``create_picot_adr``: relatório de propagação + caminho do ADR."""

    report: PropagateReport
    adr_path: Path


def create_picot_adr(scope: Path, *, motivation: str, slug: str, date: str) -> AdrResult:
    """Grava o ADR-N (no escopo) para a versão atual do ``picot.toml`` (após bump)
    e propaga."""
    pj_root = find_pj_root(scope)
    spec = read_picot(pj_root)
    # read_picot acima já garante que o picot.toml existe, então diff_against_last_adr
    # nunca retorna None aqui; o ``or`` apenas estreita PicotDiff | None -> PicotDiff p/ mypy.
    diff = diff_against_last_adr(scope) or PicotDiff(changes=[])
    last_adr = find_last_picot_adr(scope)
    n = next_number(scope)
    body = compose_adr(
        adr_number=n,
        spec=spec,
        diff=diff,
        motivation=motivation,
        supersedes_path=last_adr,
        date=date,
    )
    adr_path = pj_layout.decisions_dir(scope) / f"adr-{n:04d}-picot-v{spec.version}-{slug}.md"
    adr_path.parent.mkdir(parents=True, exist_ok=True)
    adr_path.write_text(body, encoding="utf-8")
    report = propagate(scope)
    return AdrResult(report=report, adr_path=adr_path)


def diff_against_last_adr(scope: Path) -> PicotDiff | None:
    """Compara ``picot.toml`` atual (do projeto) contra snapshot do último ADR
    ``picot-v<N>`` (do escopo).

    Retorna ``None`` se ``picot.toml`` ausente. Retorna ``PicotDiff`` com
    ``changes=[]`` quando não há ADR baseline (caller decide criar v1).
    """
    pj_root = find_pj_root(scope)
    if not picot_path(pj_root).exists():
        return None
    current = read_picot(pj_root)
    last_adr = find_last_picot_adr(scope)
    if last_adr is None:
        return PicotDiff(changes=[])
    snapshot_text = extract_picot_snapshot(last_adr.read_text(encoding="utf-8"))
    if snapshot_text is None:
        return PicotDiff(changes=[])
    parsed = tomllib.loads(snapshot_text)
    baseline = PicotSpec.model_validate(parsed["picot"])
    return diff_picot(baseline, current)
