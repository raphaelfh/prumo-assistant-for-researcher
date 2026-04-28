"""Camada transversal: utilitários sem lógica de domínio.

Cada módulo aqui dentro é importável sem efeito colateral e tem um único papel:

- ``config``     — carrega ``pj_*/.claude/pj_config.toml`` com defaults
- ``bib``        — parser tolerante de ``_references.bib`` (Better BibTeX)
- ``csl``        — resolução de estilos CSL a partir de ``~/Zotero/styles/``
- ``obsidian``   — normalizador Obsidian Markdown → Pandoc Markdown
- ``skills``     — parser de ``SKILL.md`` (frontmatter rico) + registry
- ``provenance`` — bloco ``_meta`` + trace JSONL local-only
- ``output``     — console Rich + saída ``--json`` TTY-aware

Nada em ``core`` deve conhecer os domínios (``paper``, ``wiki``, ``write``);
relação é só na direção oposta.
"""

from __future__ import annotations
