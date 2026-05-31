#!/usr/bin/env python3
"""Escreve PicotSpec inicial + propaga + cria ADR-0001.

Uso::

    uv run python ${CLAUDE_SKILL_DIR}/scripts/init_picot.py --date YYYY-MM-DD < spec.json

O JSON em stdin é um ``PicotSpec`` serializado (todos os campos exceto
``schema_version`` que tem default). Exemplo mínimo para ``type=clinical``::

    {
      "type": "clinical",
      "created_at": "2026-05-19",
      "last_updated": "2026-05-19",
      "version": 1,
      "population": "...",
      "intervention": "...",
      "comparison": "...",
      "outcome": "...",
      "time": "...",
      "hypothesis": {
        "statement": "...",
        "rationale": "...",
        "metrics": ["AUROC", "ECE"]
      }
    }

Saída: JSON em stdout com ``{"propagate": <report>, "adr_path": <path>}``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path

from prumo_assist.domains.protocol.adr import compose_adr, next_adr_number
from prumo_assist.domains.protocol.api import (
    Hypothesis,
    PicotSpec,
    propagate,
    write_picot,
)
from prumo_assist.domains.protocol.diff import PicotDiff


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--date", required=True, help="ISO date YYYY-MM-DD")
    parser.add_argument(
        "--motivation",
        default="versão inicial — primeira formalização",
        help="Texto da motivação para o ADR-0001.",
    )
    args = parser.parse_args()

    payload = json.load(sys.stdin)
    hypothesis_data = payload.pop("hypothesis")
    spec = PicotSpec(**payload, hypothesis=Hypothesis(**hypothesis_data))

    pj = Path(".")
    write_picot(pj, spec)
    report = propagate(pj)

    n = next_adr_number(pj)
    body = compose_adr(
        adr_number=n,
        spec=spec,
        diff=PicotDiff(changes=[]),
        motivation=args.motivation,
        supersedes_path=None,
        date=args.date,
    )
    adr_path = pj / "docs" / "decisions" / f"adr-{n:04d}-picot-v1-versao-inicial.md"
    adr_path.parent.mkdir(parents=True, exist_ok=True)
    adr_path.write_text(body, encoding="utf-8")

    out = {
        "propagate": asdict(report) if is_dataclass(report) else report,
        "adr_path": str(adr_path),
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
