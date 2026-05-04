"""Domínio ``protocol`` — formalização de PICOT.

Cobre o ciclo de vida da PICOT do projeto:

- ``schemas.v1.PicotSpec`` — schema canônico (Pydantic)
- ``picot_io`` — read/write de ``.claude/picot.toml``
- ``render`` — TOML → blocos delimitados em ``protocol.md`` / ``project.md``
- ``diff`` — deep diff entre versões pra detectar mudança estrutural
- ``adr`` — gera ADRs append-only quando versão muda
- ``ops`` — orquestra ``propagate`` e ``diff_against_last_adr``

A parte agêntica (modos Socrático e Formalize) vive na skill
``skills/formulate-picot/SKILL.md``; este pacote é puro Python determinístico.
"""

from __future__ import annotations
