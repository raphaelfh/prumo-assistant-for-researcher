"""Grafo passivo de citação: citações no corpo → ``cites:`` no YAML.

Reconhece as duas gramáticas via ``core/citations`` (``[@key]``/``@key``
Pandoc e ``[[@key]]`` legado). O filtro por ``known`` descarta qualquer
falso positivo da captura ampla. Migrado de ``cite_graph.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from prumo_assist.core.citations import iter_citekeys
from prumo_assist.core.note_paths import citekey_from_meta_path, iter_note_meta_files
from prumo_assist.domains.paper.sync import FRONTMATTER_RE, read_nota_yaml, write_nota


def extract_citekeys(body: str, known: set[str], self_citekey: str | None = None) -> list[str]:
    """Retorna citekeys referenciados no body.

    - Preserva ordem da 1ª ocorrência; dedup.
    - Filtra os não-existentes em ``known`` e (se fornecido) o próprio
      ``self_citekey``.
    """
    return [key for key in iter_citekeys(body) if key != self_citekey and key in known]


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
        new_cites = extract_citekeys(body, known, self_key)
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
