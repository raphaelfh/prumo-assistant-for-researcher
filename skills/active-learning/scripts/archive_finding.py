#!/usr/bin/env python3
"""Arquiva insight como finding em ``docs/wiki/findings/<slug>.md``.

Uso::

    uv run python ${CLAUDE_SKILL_DIR}/scripts/archive_finding.py \\
        --slug curvas-roc-coverage-mnar \\
        --title "Curvas ROC e escolha de limiar" \\
        --date 2026-05-19 \\
        --tags '["curvas-roc", "mnar"]' \\
        --sources '["[[concepts/curvas-roc]]", "[[@hanley1982roc]]"]' \\
        --generator active-learning < body.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from prumo_assist.domains.wiki.findings import archive_as_finding


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--tags", default="[]")
    parser.add_argument("--sources", default="[]")
    parser.add_argument("--generator", default="active-learning")
    args = parser.parse_args()

    body = sys.stdin.read()
    tags = json.loads(args.tags)
    sources = json.loads(args.sources)

    out = archive_as_finding(
        pj_path=Path("."),
        slug=args.slug,
        title=args.title,
        body=body,
        sources=sources,
        date=args.date,
        tags=tags,
        generator=args.generator,
    )
    print(out)


if __name__ == "__main__":
    main()
