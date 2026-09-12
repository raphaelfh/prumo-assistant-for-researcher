"""Domínio ``write`` — escrita acadêmica.

Cobre o pilar de **escrita**:

- ``export``   — single-page Markdown → DOCX/Typst/PDF/HTML via Pandoc + CSL
- ``compose``  — multi-page (frontmatter ``pages: [...]``)
- ``comments`` — extrai comentários + revisões de ``.docx`` revisado

O modo agêntico ``review critique`` é instalado no agent-host pelo ``prumo init``
e executada lá. Aqui no Python ficamos com o que dá pra fazer determinístico.
"""

from __future__ import annotations
