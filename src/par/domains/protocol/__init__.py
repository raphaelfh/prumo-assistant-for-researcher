"""Domínio ``protocol`` — a pergunta do estudo (ADR-0041).

Cobre o ciclo de vida da pergunta do estudo do projeto:

- ``schemas.v1.QuestionSpec`` — schema canônico (Pydantic); ``PicotSpec`` é o
  formato anterior, lido e convertido
- ``question_io`` — read/write de ``.claude/question.toml`` (fallback ao
  ``picot.toml`` antigo via ``picot_io``)
- ``render`` — TOML → blocos delimitados em ``protocol.md`` / ``project_guide.md``
- ``diff`` — deep diff entre versões pra detectar mudança estrutural
- ``adr`` — gera ADRs append-only quando versão muda
- ``ops`` — orquestra ``propagate`` e ``diff_against_last_adr``

A parte agêntica (diálogo e ``formalize``) vive na skill
``skills/protocol/modes/question.md``; este pacote é puro Python determinístico.
"""

from __future__ import annotations
