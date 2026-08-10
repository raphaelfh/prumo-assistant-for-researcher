"""Estatísticas determinísticas do wiki: contagem por escopo + por tipo."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from prumo_assist.core import pj_layout

EXPECTED_DIRS = pj_layout.SCOPE_DIRS


def stats(pj_path: Path) -> dict[str, Any]:
    """Contagem de páginas por escopo (``notes``/``writing``/``decisions``),
    mais ``by_type["references"]`` (bibliografia do projeto) e o total.

    ``by_type["references"]`` continua existindo mesmo com a mudança pro
    layout por escopo — removê-lo violaria forward-only (``constitution.md:63``).
    """
    docs = pj_path / "docs"
    out: dict[str, Any] = {"by_type": {}, "by_scope": {}, "totals": {}}

    if not docs.is_dir():
        out["docs_missing"] = True
        return out

    grand_total = 0
    grand_bytes = 0
    for scope in pj_layout.iter_scopes(pj_path):
        per_scope: dict[str, Any] = {}
        for d in EXPECTED_DIRS:
            target = scope / d
            pages = list(target.rglob("*.md")) if target.is_dir() else []
            size = sum(p.stat().st_size for p in pages)
            per_scope[d] = {"pages": len(pages), "bytes": size}
            grand_total += len(pages)
            grand_bytes += size
        out["by_scope"][scope.name] = per_scope

    papers = pj_layout.papers_dir(pj_path)
    if papers.is_dir():
        rn = list(papers.rglob("*.md"))
        size = sum(p.stat().st_size for p in rn)
        out["by_type"]["references"] = {"pages": len(rn), "bytes": size}
        grand_total += len(rn)
        grand_bytes += size
    else:
        out["by_type"]["references"] = {"pages": 0, "bytes": 0}

    out["totals"] = {"pages": grand_total, "bytes": grand_bytes}
    return out
