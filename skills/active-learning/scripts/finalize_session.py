#!/usr/bin/env python3
"""Atualiza frontmatter do log com fechamento da sessão.

Uso::

    uv run python ${CLAUDE_SKILL_DIR}/scripts/finalize_session.py \\
        --log-path docs/wiki/study-sessions/curvas-roc-2026-05-19.md \\
        --duration 22 \\
        --status completed \\
        --missing '["paper-X-sobre-Y"]' \\
        --finding docs/wiki/findings/curvas-roc-coverage-mnar.md
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from prumo_assist.domains.wiki.study import finalize_session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-path", required=True)
    parser.add_argument("--duration", type=int, required=True)
    parser.add_argument(
        "--status",
        required=True,
        choices=("completed", "abandoned", "partial"),
    )
    parser.add_argument("--missing", default="[]")
    parser.add_argument("--finding", default="", help="path ou string vazia.")
    args = parser.parse_args()

    missing = json.loads(args.missing)
    finding = Path(args.finding) if args.finding else None

    finalize_session(
        Path(args.log_path),
        duration_minutes=args.duration,
        status=args.status,
        references_missing=missing,
        finding_archived=finding,
    )
    print("ok")


if __name__ == "__main__":
    main()
