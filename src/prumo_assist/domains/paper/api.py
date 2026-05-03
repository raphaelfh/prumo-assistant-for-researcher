"""Python API pra ``paper`` — gateway pra notebooks.

Re-exports puros dos módulos de domínio. Mantém superfície estável (SemVer)
sem boilerplate de wrappers passthrough::

    from prumo_assist import api
    api.paper.sync(pj_path)
    api.paper.find(pj_path, "risk prediction")
"""

from __future__ import annotations

from prumo_assist.domains.paper.find import fuzzy_search as find
from prumo_assist.domains.paper.graph import update_graph
from prumo_assist.domains.paper.lint import lint, set_primary
from prumo_assist.domains.paper.pdfs import sync_pdfs
from prumo_assist.domains.paper.sync import sync
from prumo_assist.domains.paper.zotero import sync_annotations

__all__ = [
    "find",
    "lint",
    "set_primary",
    "sync",
    "sync_annotations",
    "sync_pdfs",
    "update_graph",
]
