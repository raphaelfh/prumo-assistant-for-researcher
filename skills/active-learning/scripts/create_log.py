#!/usr/bin/env python3
"""Cria o skeleton de log de sessão Socrática.

Uso::

    uv run python ${CLAUDE_SKILL_DIR}/scripts/create_log.py \\
        --topic curvas-roc-prediction \\
        --date 2026-05-19 \\
        --sources '["[[concepts/curvas-roc]]", "[[@hanley1982roc]]"]'

Imprime o path do log criado.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from prumo_assist.domains.wiki.study import create_session_log


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True, help="slug do tópico.")
    parser.add_argument("--date", required=True, help="ISO YYYY-MM-DD.")
    parser.add_argument(
        "--sources",
        default="[]",
        help='JSON array de wikilinks: ''[\"[[a]]\", \"[[@k]]\"]''.',
    )
    args = parser.parse_args()

    sources = json.loads(args.sources)
    if not isinstance(sources, list):
        raise SystemExit("--sources deve ser JSON array de strings.")

    path = create_session_log(
        pj_path=Path("."),
        topic=args.topic,
        date=args.date,
        sources_consulted=sources,
    )
    print(path)


if __name__ == "__main__":
    main()
