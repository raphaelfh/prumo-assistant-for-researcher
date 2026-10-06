"""Python API pra ``paper`` — gateway pra notebooks.

Re-exports puros dos módulos de domínio. Mantém superfície estável (SemVer)
sem boilerplate de wrappers passthrough::

    from par import api
    api.paper.sync(pj_path)
    api.paper.find(pj_path, "multimodal fusion")
"""

from __future__ import annotations

from par.domains.paper.callout import apply_extraction, parse_extract_payload
from par.domains.paper.connect import connect_collection
from par.domains.paper.errors import PaperError
from par.domains.paper.find import fuzzy_search as find
from par.domains.paper.graph import update_graph
from par.domains.paper.lint import lint, set_primary
from par.domains.paper.migrate import migrate_pj as migrate_layout
from par.domains.paper.pdfs import sync_pdfs
from par.domains.paper.prep import ExtractPrep, extract_prep
from par.domains.paper.sync import sync
from par.domains.paper.verify import verify_refs

__all__ = [
    "ExtractPrep",
    "PaperError",
    "apply_extraction",
    "connect_collection",
    "extract_prep",
    "find",
    "lint",
    "migrate_layout",
    "parse_extract_payload",
    "set_primary",
    "sync",
    "sync_pdfs",
    "update_graph",
    "verify_refs",
]
