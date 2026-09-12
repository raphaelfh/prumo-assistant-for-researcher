"""Domínio ``wiki`` — gestão de conhecimento em ``docs/``.

Cobre o pilar de **conhecimento**:

- ``lint``    — audita ``docs/`` (citekeys quebradas, órfãs, stale, gaps)
- ``index``   — wrapper sobre ``qmd`` (BM25 + vector + rerank)
- ``stats``   — contagem por escopo (notes/writing/decisions) + bibliografia

Os modos agênticos (``wiki ingest``, ``wiki query``) ficam em ``skills/wiki/`` —
chamadas pelo agent-host do usuário, não por este pacote.
"""

from __future__ import annotations
