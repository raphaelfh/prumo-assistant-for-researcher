---
name: wiki
description: "Wiki do pj_*: ingerir fontes, responder perguntas com citação, auditar a saúde do wiki e conduzir sessões de estudo ancoradas nas fontes."
when_to_use: |
  Modos: ingest, lint, query, study. Frases típicas:
  - ingest: "adiciona esta fonte ao wiki"; "salva este link no wiki"; "registra este tutorial"
  - lint: "audita o wiki"; "encontra páginas órfãs"; "o wiki está consistente?"
  - query: "o que a literatura diz sobre X"; "compara Y e Z"; "quais decisões tomamos sobre W"
  - study: "me ensina X"; "me coloca à prova sobre Y"; "preciso fixar Z"
argument-hint: "[ingest|lint|query|study] [argumentos do modo]"
allowed-tools: Read Write Edit Glob Grep WebFetch Bash(qmd *) mcp__qmd__embed mcp__qmd__query Bash(rg *) Bash(prumo *) Bash(cat *) mcp__qmd__search Bash(echo *)
prumo:
  version: 2.0.0
  agent_compat: [claude-code]
---

# wiki — wiki do projeto

Escolha o modo antes de agir:

1. **Argumento explícito vence.** `/par:wiki query o que a literatura diz sobre X` → modo `query`.
2. **Senão, pela intenção**, usando a tabela abaixo.
3. **Ambíguo entre modos → faça UMA pergunta** listando os candidatos com uma frase de exemplo cada. Na dúvida entre gerar e orientar, oriente.
4. **Leia `modes/<modo>.md` inteiro antes de qualquer operação.** Este arquivo não contém instrução operacional; o preflight e o procedimento de cada modo estão lá.

<!-- prumo:modes-table:begin -->
| Você diz | Modo |
|---|---|
| "adiciona esta fonte ao wiki" | `ingest` |
| "salva este link no wiki" | `ingest` |
| "registra este tutorial" | `ingest` |
| "audita o wiki" | `lint` |
| "encontra páginas órfãs" | `lint` |
| "o wiki está consistente?" | `lint` |
| "o que a literatura diz sobre X" | `query` |
| "compara Y e Z" | `query` |
| "quais decisões tomamos sobre W" | `query` |
| "me ensina X" | `study` |
| "me coloca à prova sobre Y" | `study` |
| "preciso fixar Z" | `study` |
<!-- prumo:modes-table:end -->
