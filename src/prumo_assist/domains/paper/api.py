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
from prumo_assist.domains.paper.migrate import migrate_pj as migrate_layout
from prumo_assist.domains.paper.pdfs import sync_pdfs
from prumo_assist.domains.paper.sync import sync
from prumo_assist.domains.paper.sync_all import sync_all
from prumo_assist.domains.paper.zotero import sync_annotations, sync_notes

__all__ = [
    "find",
    "lint",
    "migrate_layout",
    "set_primary",
    "sync",
    "sync_all",
    "sync_annotations",
    "sync_notes",
    "sync_pdfs",
    "update_graph",
]
