"""Python API pra ``paper`` — gateway pra notebooks.

Cada função CLI tem uma equivalente aqui. Notebooks fazem::

    from prumo_assist import api
    report = api.paper.sync(pj_path)
    df = api.paper.find(pj_path, "risk prediction")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from prumo_assist.domains.paper import (
    find as _find,
)
from prumo_assist.domains.paper import (
    graph as _graph,
)
from prumo_assist.domains.paper import (
    lint as _lint,
)
from prumo_assist.domains.paper import (
    pdfs as _pdfs,
)
from prumo_assist.domains.paper import (
    sync as _sync,
)
from prumo_assist.domains.paper import (
    zotero as _zotero,
)


def sync(pj_path: Path) -> dict[str, Any]:
    """``.bib`` → notas. Mesmo report que ``prumo paper sync``."""
    return _sync.sync(pj_path)


def update_graph(pj_path: Path) -> dict[str, Any]:
    """Grafo passivo de citação."""
    return _graph.update_graph(pj_path)


def find(
    pj_path: Path, query: str, *, top_k: int = 5, min_ratio: float = 0.25
) -> list[dict[str, Any]]:
    """Fuzzy search sobre `.bib` + notas."""
    return _find.fuzzy_search(pj_path, query, top_k=top_k, min_ratio=min_ratio)


def lint(pj_path: Path) -> dict[str, Any]:
    """Auditoria de consistência."""
    return _lint.lint(pj_path)


def set_primary(pj_path: Path, citekey: str) -> dict[str, Any]:
    """Marca um paper como ``role: primary``."""
    return _lint.set_primary(pj_path, citekey)


def sync_pdfs(pj_path: Path) -> dict[str, Any]:
    """Symlinks PDF do Zotero."""
    return _pdfs.sync_pdfs(pj_path)


def sync_annotations(pj_path: Path) -> dict[str, Any]:
    """Annotations + child notes do Zotero (requer Zotero 9 aberto + BBT)."""
    return _zotero.sync_annotations(pj_path)
