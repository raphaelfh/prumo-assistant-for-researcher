# ADR-0012 — Remoção dos agents ML pré-pivot

- Status: aceito
- Data: 2026-06-11
- Origem: [[2026-06-11-repo-organization-redesign-design]] (D8)

## Contexto
`agents/ml-theory-expert.md` e `agents/stack-docs-researcher.md` vêm do monorepo de ML anterior ao pivot clínico. O primeiro depende de `./theory/knowledge/` que não existe em nenhum lugar (quebrado como distribuído); o segundo allowlista tools host-específicas ausentes do Claude Code puro. A descrição do marketplace promete "agents para pesquisa clínica" — nenhum dos dois é isso, e nenhum dos 14 skills os usa.

## Decisão
Remover ambos no release v0.62.0 (MINOR com "⚠ Breaking"). Conteúdo preservado no histórico git (mesmo precedente das skills removidas na 0.3.0). O diretório `agents/` deixa de existir até haver agents alinhados ao propósito clínico.

## Consequências
Consumidores perdem dois agents que provavelmente nunca funcionaram como distribuídos. Agent futuro deve: servir o fluxo clínico, funcionar standalone (sem diretórios externos fantasma) e allowlistar apenas tools universais.
