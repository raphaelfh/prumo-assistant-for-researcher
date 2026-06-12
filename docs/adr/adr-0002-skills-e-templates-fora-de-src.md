# ADR-0002 — `skills/` e `templates/` fora de `src/`, force-included no wheel

- Status: aceito
- Data: 2026-06-11
- Origem: ARCHITECTURE.md ("Por que skills/ está fora de src/", pré-existente; formalizado nesta data)

## Contexto
Skills e templates são conteúdo (Markdown/TOML), não código Python. Contribuir uma skill não deve exigir entender o pacote. Ao mesmo tempo, o wheel precisa carregá-los para `prumo init` funcionar em instalação não-editável.

## Decisão
`skills/` e `templates/` vivem na raiz do repo. O pyproject força a inclusão no wheel (`skills/` → `prumo_assist/_skills`, `templates/` → `prumo_assist/_templates`). `core/paths.resolve_resource` é o único resolvedor, funcionando em modo instalado, editável e worktree.

## Consequências
Mover/renomear qualquer um dos dois diretórios exige atualizar pyproject (force-include) E `core/paths.py` na mesma mudança. PRs de conteúdo não tocam Python.
