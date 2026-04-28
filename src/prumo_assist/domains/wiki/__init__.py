"""Domínio ``wiki`` — gestão de conhecimento em ``docs/``.

Cobre o pilar de **conhecimento**:

- ``lint``    — audita ``docs/`` (citekeys quebradas, órfãs, stale, gaps)
- ``index``   — wrapper sobre ``qmd`` (BM25 + vector + rerank)
- ``stats``   — contagem por tipo (concepts, entities, findings, sources)

As skills agênticas (``wiki-ingest``, ``wiki-query``) ficam em ``skills/`` —
chamadas pelo agent-host do usuário, não por este pacote.
"""

from __future__ import annotations
