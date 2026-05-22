#!/usr/bin/env python3
"""Gera ADR-N para uma mudança estrutural já capturada em ``picot.toml``.

Pressuposto: a versão em ``.claude/picot.toml`` já foi bumpada (campo
``version`` e ``last_updated``); este script apenas lê o estado atual,
compara contra o último ADR e materializa o novo ADR + propaga blocos.

Uso::

    uv run python ${CLAUDE_SKILL_DIR}/scripts/diff_and_adr.py \\
        --motivation "novo dataset disponível" \\
        --slug novo-dataset \\
        --date 2026-05-19

Saída: JSON em stdout com ``{"adr_path": ..., "propagate": ...}``.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path

from prumo_assist.domains.protocol.adr import (
    compose_adr,
    find_last_picot_adr,
    next_adr_number,
)
from prumo_assist.domains.protocol.api import (
    diff_against_last_adr,
    propagate,
    read_picot,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--motivation", required=True)
    parser.add_argument("--slug", required=True, help="kebab-case curto.")
    parser.add_argument("--date", required=True, help="ISO YYYY-MM-DD.")
    args = parser.parse_args()

    pj = Path(".")
    spec = read_picot(pj)
    diff = diff_against_last_adr(pj)
    last_adr = find_last_picot_adr(pj)
    n = next_adr_number(pj)

    body = compose_adr(
        adr_number=n,
        spec=spec,
        diff=diff,
        motivation=args.motivation,
        supersedes_path=last_adr,
        date=args.date,
    )
    adr_path = (
        pj / "docs" / "decisions"
        / f"adr-{n:04d}-picot-v{spec.version}-{args.slug}.md"
    )
    adr_path.parent.mkdir(parents=True, exist_ok=True)
    adr_path.write_text(body, encoding="utf-8")
    report = propagate(pj)

    out = {
        "adr_path": str(adr_path),
        "propagate": asdict(report) if is_dataclass(report) else report,
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
