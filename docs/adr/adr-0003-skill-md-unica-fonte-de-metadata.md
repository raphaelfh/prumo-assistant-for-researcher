# ADR-0003 — SKILL.md é a única fonte de metadata por skill

- Status: aceito
- Data: 2026-06-11
- Origem: docstring de `core/skills.py` (pré-existente; formalizado nesta data); [[constitution#III · Skills universais]]

## Contexto
Hosts diferentes (Claude Code, Cursor, Codex, Gemini) consomem `name`/`description` do frontmatter. Um manifest paralelo duplicaria metadata e envelheceria em silêncio.

## Decisão
Todo metadata de skill mora no frontmatter do `SKILL.md`: `name`/`description` universais no topo, e o resto sob o namespace `prumo:` (version, schema, determinism, agent_compat, cost_estimate, guidelines_reviewed, inputs). Parser: `core/skills.py:parse_skill_file`, com modo strict (CI) e tolerante (`prumo init`). Campos desconhecidos preservados em `extra` (forward-compat).

## Consequências
Sem `manifest.yaml`. Catálogos (README, router `start`, `_index`) são derivados do registry via `gen_indexes.py` — nunca mantidos à mão (Princípio VII).
