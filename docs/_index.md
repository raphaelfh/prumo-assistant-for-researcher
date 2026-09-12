---
title: Vault de documentação do prumo-assist
tags: [index]
---

# prumo-assist · vault de documentação

Vault Markdown de orientação de uso do plugin/CLI. Material complementar ao [README](../README.md), [ARCHITECTURE](../ARCHITECTURE.md) e [ROADMAP](../ROADMAP.md) — focado em **didática** e **decisão de uso**, não em referência exaustiva.

## Por onde começar

| Pergunta | Documento |
|---|---|
| Sou pesquisador sem terminal — como começo no Desktop/Cowork? | [[onboarding-pesquisador\|Trilha do pesquisador]] |
| Tenho um gatilho concreto, qual comando usar? | [[actions-by-context\|Contextos → ações]] |
| Como devo estruturar um novo `pj_*`? | [[Research Project Structure\|Estrutura de Projeto de Pesquisa]] |
| Quais são os princípios não-negociáveis do projeto? | [[constitution\|Constitution]] |
| Por que essa decisão estrutural foi tomada? | [[adr/_index\|Índice de ADRs]] |
| Spec da família de skills de escrita (`write-*`) | [[superpowers/specs/2026-05-03-write-family-design]] |
| Spec da integração de notas Zotero (B1 + qmd) | [[superpowers/specs/2026-05-03-zotero-notes-integration-design]] |

## Como o vault está organizado

- `Research Project Structure.md` — modelo "núcleo mínimo + módulos opcionais" pros `pj_*`.
- `actions-by-context.md` — playbook de bolso por gatilho.
- `constitution.md` — rule do projeto (princípios, restrições, governança).
- `superpowers/specs/` — specs vivas de design (não-perecíveis; `status: approved | superseded`).
- `superpowers/plans/` — planos ativos; implementados movem pra `plans/archive/` com `status/verified/release`.
- `adr/` — decisões registradas (MADR minimal, imutáveis). Índice: [[adr/_index]].
- `onboarding-pesquisador.md` — trilha do pesquisador sem terminal (Desktop/Cowork) + kit do piloto da Fase 2.

## Convenções

- Citação interna via wikilink: `[[constitution]]`, `[[constitution#I · Lógica em um lugar só]]`.
- Português técnico no corpo; identificadores e comandos podem permanecer em inglês.
- Documento que não cabe em uma tela é candidato a ser dividido — coerência com o princípio I da [[constitution]].

## Catálogo vivo (gerado — não editar à mão)

<!-- prumo:kb-index:begin -->
**Guias:**

- [[Research Project Structure]] · Estrutura de Projeto de Pesquisa
- [[actions-by-context]] · Contextos de necessidade → ações no prumo-assist
- [[constitution]] · —
- [[onboarding-pesquisador]] · Trilha do pesquisador — prumo-assist sem terminal
- [[positioning]] · Posicionamento e claims do prumo-assist

**Specs** (não-perecíveis):

- [[superpowers/specs/2026-04-29-prumo-scientific-writer-design]] · superseded
- [[superpowers/specs/2026-05-03-active-learning-design]] · approved
- [[superpowers/specs/2026-05-03-formulate-picot-design]] · approved
- [[superpowers/specs/2026-05-03-write-family-design]] · approved
- [[superpowers/specs/2026-05-03-zotero-notes-integration-design]] · approved
- [[superpowers/specs/2026-05-30-pj-base-simplification-design]] · approved
- [[superpowers/specs/2026-06-11-repo-organization-redesign-design]] · approved
- [[superpowers/specs/2026-06-13-researcher-pipeline-design]] · approved
- [[superpowers/specs/2026-07-05-review-docx-criticmarkup-design]] · approved
- [[superpowers/specs/2026-07-22-zero-friction-onboarding-design]] · approved
- [[superpowers/specs/2026-07-22-zettlr-front-design]] · draft
- [[superpowers/specs/2026-07-26-citacao-pandoc-cidada-primeira-classe-design]] · draft
- [[superpowers/specs/2026-07-26-domain-errors-prumoerror-design]] · draft
- [[superpowers/specs/2026-07-26-prosa-idioma-citacao-design]] · approved
- [[superpowers/specs/2026-08-08-layout-por-escopo-design]] · approved
- [[superpowers/specs/2026-08-23-ponte-zotero-auditoria-design]] · approved
- [[superpowers/specs/2026-08-24-pj-instalavel-design]] · approved
- [[superpowers/specs/2026-09-12-superficie-de-skills-design]] · approved

**Plans ativos:**

- (nenhum)

**Plans arquivados:** 33 em `superpowers/plans/archive/`

**ADRs:** ver [[adr/_index|índice de ADRs]]
<!-- prumo:kb-index:end -->
