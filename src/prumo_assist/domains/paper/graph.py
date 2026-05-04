"""Grafo passivo de citação: ``[[@citekey]]`` no corpo → ``cites:`` no YAML.

Migrado de ``cite_graph.py``. Comportamento idêntico.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from prumo_assist.core.note_paths import citekey_from_meta_path, iter_note_meta_files
from prumo_assist.domains.paper.sync import FRONTMATTER_RE, read_nota_yaml, write_nota

WIKILINK_RE = re.compile(r"\[\[@([A-Za-z0-9_-]+)\]\]")


def extract_wikilinks(body: str, known: set[str], self_citekey: str | None = None) -> list[str]:
    """Retorna citekeys referenciados no body.

    - Preserva ordem da 1ª ocorrência.
    - Dedup.
    - Filtra os não-existentes em ``known`` e (se fornecido) o próprio ``self_citekey``.
    """
    seen: list[str] = []
    for m in WIKILINK_RE.finditer(body):
        key = m.group(1)
        if key == self_citekey:
            continue
        if key not in known:
            continue
        if key not in seen:
            seen.append(key)
    return seen


def update_graph(pj_path: Path) -> dict[str, Any]:
    """Varre todas as notas, popula ``cites`` a partir de wikilinks no body.

    Retorna ``{"edges_added": N, "edges_removed": M}``.
    """
    meta_files = iter_note_meta_files(pj_path)
    known = {citekey_from_meta_path(p) for p in meta_files}

    edges_added, edges_removed = 0, 0

    for nota in meta_files:
        text = nota.read_text()
        m = FRONTMATTER_RE.match(text)
        if not m:
            continue
        body = text[m.end() :]
        yaml_dict = read_nota_yaml(nota)
        self_key = yaml_dict.get("id") or citekey_from_meta_path(nota)
        new_cites = extract_wikilinks(body, known, self_key)
        old_cites = yaml_dict.get("cites") or []
        if new_cites == old_cites:
            continue
        added = set(new_cites) - set(old_cites)
        removed = set(old_cites) - set(new_cites)
        edges_added += len(added)
        edges_removed += len(removed)
        yaml_dict["cites"] = new_cites
        write_nota(nota, yaml_dict, body)

    return {"edges_added": edges_added, "edges_removed": edges_removed}
