# ADR-0010 — Plugin root = raiz do repo; marketplace self-hosting; schemas vivos do validador

- Status: aceito
- Data: 2026-06-11
- Origem: `.claude-plugin/` + `.github/schemas/` (pré-existente; formalizado nesta data)

## Contexto
O Claude Code descobre skills em `skills/<nome>/SKILL.md`, agents em `agents/*.md` e MCP em `.mcp.json` relativos ao plugin root. O validador oficial de manifests é opaco (a lição da 0.1.1: `repository` deve ser string, não objeto).

## Decisão
O repo é o próprio marketplace (`.claude-plugin/marketplace.json` com `source: "./"`), com plugin root = raiz. Zero overrides de path no `plugin.json`. O conhecimento reverso do validador vive em `.github/schemas/*.schema.json` ("referência viva"), aplicado por `validate_manifests.py` no CI.

## Consequências
`skills/`, `.mcp.json` e `.claude-plugin/` são imóveis — mover quebraria todos os consumidores instalados. Os schemas em `.github/schemas/` devem ser preservados em qualquer reorganização e atualizados quando o validador oficial mudar de comportamento.
