---
title: Vault de documentação do prumo-assist
tags: [index]
---

# prumo-assist · vault de documentação

Vault Obsidian de orientação de uso do plugin/CLI. Material complementar ao [README](../README.md), [ARCHITECTURE](../ARCHITECTURE.md) e [ROADMAP](../ROADMAP.md) — focado em **didática** e **decisão de uso**, não em referência exaustiva.

## Por onde começar

| Pergunta | Documento |
|---|---|
| O que o pesquisador faz vs. o que o prumo-assist resolve? | [[journey\|Canvas de jornada]] *(abrir como canvas)* |
| Tenho um gatilho concreto, qual comando usar? | [[actions-by-context\|Contextos → ações]] |
| Como devo estruturar um novo `pj_*`? | [[Research Project Structure\|Estrutura de Projeto de Pesquisa]] |
| Visualização da estrutura por composição (L0–L3) | [[canvas/project-structure\|Canvas estrutural]] |
| Como uma ideia ou citação atravessa o repo? | [[canvas/project-flow\|Canvas de fluxo]] |
| Como ficam as notas Zotero ↔ repo (B1)? | [[canvas/zotero-notes-architecture\|Canvas de arquitetura Zotero-notas]] |
| Quais são os princípios não-negociáveis do projeto? | [[constitution\|Constitution]] |
| Spec da skill `scientific-writing` | [[superpowers/specs/2026-04-29-prumo-scientific-writer-design]] |
| Spec da integração de notas Zotero (B1 + qmd) | [[superpowers/specs/2026-05-03-zotero-notes-integration-design]] |

## Como o vault está organizado

- `journey.canvas` — fluxo da jornada do pesquisador (Double Diamond × JTBD).
- `Research Project Structure.md` — modelo "núcleo mínimo + módulos opcionais" pros `pj_*`.
- `canvas/project-structure.canvas` — visualização da estrutura por composição.
- `canvas/project-flow.canvas` — fluxo de informação (ideia + citação) atravessando o repo.
- `actions-by-context.md` — playbook de bolso por gatilho.
- `constitution.md` — rule do projeto (princípios, restrições, governança).
- `superpowers/specs/` — specs vivas de design de skills (não-perecíveis).

## Convenções

- Citação interna via wikilink: `[[constitution]]`, `[[constitution#I · Lógica em um lugar só]]`.
- Português técnico no corpo; identificadores e comandos podem permanecer em inglês.
- Documento que não cabe em uma tela é candidato a ser dividido — coerência com o princípio I da [[constitution]].
