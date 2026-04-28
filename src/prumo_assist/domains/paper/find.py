"""Fuzzy lookup sobre ``_references.bib`` + notas YAML.

Migrado de ``cite_lookup.py``. Comportamento idêntico.
"""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from prumo_assist.core.bib import extract_field, parse_bib
from prumo_assist.domains.paper.sync import read_nota_yaml


def build_index(pj_path: Path) -> dict[str, dict[str, Any]]:
    """Índice ``{citekey: {title, author, year, tldr, role, status}}``."""
    bib = pj_path / "references" / "_references.bib"
    notes_dir = pj_path / "references" / "notes"
    index: dict[str, dict[str, Any]] = {}
    if not bib.exists():
        return index
    for entry in parse_bib(bib.read_text()):
        title = (extract_field(entry.body, "title") or "").strip()
        author = (extract_field(entry.body, "author") or "").strip()
        year = (extract_field(entry.body, "year") or "").strip()
        record: dict[str, Any] = {
            "citekey": entry.citekey,
            "title": title,
            "author": author,
            "year": year,
            "tldr": "",
            "role": "",
            "status": "",
        }
        nota = notes_dir / f"{entry.citekey}.md"
        if nota.exists():
            yaml_dict = read_nota_yaml(nota)
            record["tldr"] = yaml_dict.get("tldr") or ""
            record["role"] = yaml_dict.get("role") or ""
            record["status"] = yaml_dict.get("status") or ""
        index[entry.citekey] = record
    return index


def fuzzy_search(
    pj_path: Path,
    query: str,
    *,
    top_k: int = 5,
    min_ratio: float = 0.25,
) -> list[dict[str, Any]]:
    """Retorna top-k registros por ratio sobre ``"author title year tldr"``.

    Bônus de +0.3 se todos os tokens da query aparecerem como substring,
    favorecendo matches literais sobre ratio-only.
    """
    index = build_index(pj_path)
    q = query.lower()
    scored: list[tuple[float, dict[str, Any]]] = []
    for rec in index.values():
        haystack = " ".join([rec["author"], rec["title"], rec["year"], rec["tldr"]]).lower()
        ratio = difflib.SequenceMatcher(None, q, haystack).ratio()
        tokens = [t for t in q.split() if t]
        if tokens and all(t in haystack for t in tokens):
            ratio += 0.3
        scored.append((ratio, rec))
    scored.sort(key=lambda x: -x[0])
    return [r for ratio, r in scored[:top_k] if ratio >= min_ratio]
