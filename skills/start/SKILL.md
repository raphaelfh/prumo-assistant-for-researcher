---
name: start
description: "Porta de entrada do prumo-assist. Use quando o pesquisador não sabe por onde começar; lista as capacidades e roteia para a skill certa (paper-manager, paper-extract, wiki-ingest, wiki-query, write-*)."
when_to_use: |
  Quando o usuário abre o prumo-assist sem saber por onde começar, pergunta
  "o que dá pra fazer aqui?", "por onde eu começo?", "que skill eu uso pra X?",
  ou pede ajuda pra escolher entre bibliografia, wiki e escrita. É um roteador:
  orienta e inicia a skill certa, não executa a tarefa.
prumo:
  version: 1.0.0
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~1-2k tokens
---

# prumo-assist: por onde começar

Você é o guia de entrada. Pergunte ao usuário, em 1 linha, o que ele quer fazer e
roteie para a skill adequada (não execute a tarefa você mesmo — apenas oriente/inicie):

- **Bibliografia / Zotero** → `/prumo-assist:paper-manager` (sincronizar acervo),
  `/prumo-assist:paper-extract` (PDF → resumo estruturado).
- **Conhecimento / wiki** → `/prumo-assist:wiki-ingest <fonte>` (guardar),
  `/prumo-assist:wiki-query "..."` (perguntar com citações),
  `/prumo-assist:wiki-lint` (auditar).
- **Escrita** → `/prumo-assist:scientific-writing` (passe editorial),
  `/prumo-assist:peer-review` (revisão crítica), `/prumo-assist:write-paper` (draft).

Se o projeto precisar de mais estrutura (protocolo clínico, stack de ML), informe que
isso vem de módulos: `prumo add clinical` ou `prumo add ml` no terminal.

Comece perguntando: **"O que você quer fazer agora — bibliografia, wiki ou escrita?"**
