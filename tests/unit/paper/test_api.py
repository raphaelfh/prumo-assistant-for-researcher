"""Superfície pública de ``par.domains.paper`` sem o pipeline de anotações.

ADR-0037 (B9): ``sync-annotations``, ``sync-notes``, ``sync-all`` e a tool
MCP ``paper_sync_all`` saíram do PAR; estes guardas impedem a volta silenciosa.
"""

from __future__ import annotations

import importlib.util

import pytest

from par.domains.paper import api as paper_api
from par.domains.paper import errors


@pytest.mark.parametrize("nome", ["sync_all", "sync_annotations", "sync_notes"])
def test_api_nao_reexporta_o_pipeline_de_anotacoes(nome: str) -> None:
    assert nome not in paper_api.__all__
    assert not hasattr(paper_api, nome)


@pytest.mark.parametrize("mod", ["par.domains.paper.zotero", "par.domains.paper.sync_all"])
def test_modulos_aposentados_nao_existem(mod: str) -> None:
    assert importlib.util.find_spec(mod) is None


def test_zotero_api_error_saiu() -> None:
    assert not hasattr(errors, "ZoteroApiError")
