"""Orquestradores para ``propagate`` e ``diff_against_last_adr``.

Lado determinístico Python das operações. A skill ``formulate-picot`` usa
estas funções via Python -c após coletar inputs do usuário.

``init`` e ``formalize`` (modos agênticos) ficam no SKILL.md — escrevem
``.claude/picot.toml`` via ``write_picot`` e chamam ``propagate``.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from prumo_assist.domains.protocol.adr import (
    extract_picot_snapshot,
    find_last_picot_adr,
)
from prumo_assist.domains.protocol.diff import PicotDiff, diff_picot
from prumo_assist.domains.protocol.picot_io import (
    picot_hash,
    picot_path,
    read_picot,
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


def propagate(pj_path: Path) -> PropagateReport:
    """Lê ``picot.toml``, regenera blocos delimitados em protocol.md e project_guide.md.

    Status por destino:

    - ``missing``: arquivo destino não existe (humano precisa criar)
    - ``inserted``: bloco não existia, foi inserido após anchor
    - ``updated``: bloco existia, foi substituído (hash mudou)
    - ``unchanged``: bloco já tem o hash atual, nada a fazer
    """
    spec = read_picot(pj_path)
    h = picot_hash(pj_path)

    protocol_status = _propagate_one(
        target=pj_path / "docs" / "protocol.md",
        block=render_protocol_block(spec, hash8=h),
        anchor=r"^# .+$",
        new_hash8=h,
    )
    project_status = _propagate_one(
        target=pj_path / "docs" / "project_guide.md",
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


def diff_against_last_adr(pj_path: Path) -> PicotDiff | None:
    """Compara ``picot.toml`` atual contra snapshot do último ADR ``picot-v<N>``.

    Retorna ``None`` se ``picot.toml`` ausente. Retorna ``PicotDiff`` com
    ``changes=[]`` quando não há ADR baseline (caller decide criar v1).
    """
    if not picot_path(pj_path).exists():
        return None
    current = read_picot(pj_path)
    last_adr = find_last_picot_adr(pj_path)
    if last_adr is None:
        return PicotDiff(changes=[])
    snapshot_text = extract_picot_snapshot(last_adr.read_text(encoding="utf-8"))
    if snapshot_text is None:
        return PicotDiff(changes=[])
    parsed = tomllib.loads(snapshot_text)
    baseline = PicotSpec.model_validate(parsed["picot"])
    return diff_picot(baseline, current)
