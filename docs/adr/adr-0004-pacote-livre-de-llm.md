# ADR-0004 — O pacote Python é 100% livre de LLM

- Status: aceito
- Data: 2026-06-11
- Origem: [[constitution#II · Determinístico antes de agêntico]] (pré-existente; formalizado nesta data)

## Contexto
Reprodutibilidade e auditoria de pesquisa clínica exigem que operações repetíveis não dependam de um modelo. Custo e latência de LLM são desperdício quando regex/AST/subprocess resolvem.

## Decisão
`src/prumo_assist/` nunca chama um LLM. A metade agêntica vive nos skills (`skills/*/SKILL.md`), que delegam todo trabalho determinístico de volta ao pacote (CLI `prumo` ou `uv run python -c` importando `prumo_assist.domains.*`). Cada domínio documenta no docstring qual skill é seu par agêntico.

## Consequências
Skill agêntica que poderia ser determinística é candidata a refator para `domains/`. Os contratos entre as duas metades (YAML de notas, blocos delimitados, schemas) são load-bearing e mudam só de forma coordenada.
