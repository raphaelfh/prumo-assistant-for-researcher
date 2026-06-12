# ADR-0006 — Schemas versionados forward-only

- Status: aceito
- Data: 2026-06-11
- Origem: [[constitution#IV · Forward-only schemas]] (pré-existente; formalizado nesta data)

## Contexto
Outputs gerados (callouts, PICOT, disclosure, session logs) precisam permanecer legíveis por anos — um projeto de pesquisa clínica é auditável muito depois do release que o gerou.

## Decisão
Cada domínio versiona seus contratos em `domains/<X>/schemas/v1.py` (Pydantic, campo `schema_version` Literal). Evolução é aditiva: campos só entram, nunca saem ou mudam de nome entre minors; `vN+1` lê outputs `vN`. Remoção/renome só em major com "⚠ Breaking".

## Consequências
Mudança de schema vem com teste que valida output antigo no parser novo. Schemas são citados por nome/versão (`PaperCallout/v1`) no frontmatter das skills (`prumo.schema`).
