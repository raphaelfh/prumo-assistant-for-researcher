#!/usr/bin/env python3
"""Anexa um step ao log de sessão Socrática.

Uso::

    uv run python ${CLAUDE_SKILL_DIR}/scripts/append_step.py \\
        --log-path docs/wiki/study-sessions/curvas-roc-2026-05-19.md \\
        --step recall < step.json

``step.json`` em stdin é um ``StepLog`` parcial::

    {
      "question": "...",
      "answer": "...",
      "feedback": "...",
      "citations": ["[[@key]]"],
      "references_missing": ["..."]
    }

(``step_name`` vem de ``--step``, sobrescreve o JSON.)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from prumo_assist.domains.wiki.schemas.v1 import StepLog
from prumo_assist.domains.wiki.study import append_step


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-path", required=True)
    parser.add_argument(
        "--step",
        required=True,
        choices=("recall", "anchor", "connect", "apply", "reflect"),
    )
    args = parser.parse_args()

    payload = json.load(sys.stdin)
    payload["step_name"] = args.step
    step = StepLog(**payload)
    append_step(Path(args.log_path), step)
    print("ok")


if __name__ == "__main__":
    main()
