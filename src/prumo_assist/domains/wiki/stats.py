"""Estatísticas determinísticas do wiki: contagem por tipo + tamanhos."""

from __future__ import annotations

from pathlib import Path
from typing import Any

EXPECTED_DIRS = ("concepts", "entities", "findings", "sources", "decisions")


def stats(pj_path: Path) -> dict[str, Any]:
    """Retorna contagem de páginas por categoria e total de bytes."""
    docs = pj_path / "docs"
    refs_notes = pj_path / "references" / "notes"
    out: dict[str, Any] = {"by_type": {}, "totals": {}}

    if not docs.is_dir():
        out["docs_missing"] = True
        return out

    grand_total = 0
    grand_bytes = 0
    for d in EXPECTED_DIRS:
        target = docs / d
        if not target.is_dir():
            out["by_type"][d] = {"pages": 0, "bytes": 0}
            continue
        pages = list(target.glob("*.md"))
        size = sum(p.stat().st_size for p in pages)
        out["by_type"][d] = {"pages": len(pages), "bytes": size}
        grand_total += len(pages)
        grand_bytes += size

    if refs_notes.is_dir():
        rn = list(refs_notes.glob("*.md"))
        out["by_type"]["references"] = {
            "pages": len(rn),
            "bytes": sum(p.stat().st_size for p in rn),
        }
        grand_total += len(rn)
        grand_bytes += sum(p.stat().st_size for p in rn)

    out["totals"] = {"pages": grand_total, "bytes": grand_bytes}
    return out
