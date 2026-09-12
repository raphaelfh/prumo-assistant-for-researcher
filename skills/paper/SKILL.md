---
name: paper
description: "Acervo bibliográfico do pj_*: sincronizar com o Zotero, extrair PDFs em callout estruturado e checar se as citações sustentam as frases."
when_to_use: |
  Modos: extract, library, support. Frases típicas:
  - extract: "resuma o paper X"; "extraia os principais pontos do paper"; "processa todos os papers novos"
  - library: "sincroniza minha bibliografia"; "importa minhas anotações do Zotero"; "encontra paper sobre Y"; "quem cita Z"; "marca o paper principal"; "liga o projeto à coleção do Zotero"
  - support: "as referências batem com o que eu afirmo?"; "checa se as citações sustentam as frases"
argument-hint: "[extract|library|support] [argumentos do modo]"
allowed-tools: Read Write Edit Glob Grep Bash(prumo paper *) Bash(cat *) Agent Bash(rg *) Bash(prumo paper verify-refs *) Bash(prumo validate *)
prumo:
  version: 2.0.0
  agent_compat: [claude-code]
---

# paper — acervo bibliográfico

Escolha o modo antes de agir:

1. **Argumento explícito vence.** `/prumo-assist:paper extract @smith2024` → modo `extract`.
2. **Senão, pela intenção**, usando a tabela abaixo.
3. **Ambíguo entre modos → faça UMA pergunta** listando os candidatos com uma frase de exemplo cada. Na dúvida entre gerar e orientar, oriente.
4. **Leia `modes/<modo>.md` inteiro antes de qualquer operação.** Este arquivo não contém instrução operacional; o preflight e o procedimento de cada modo estão lá.

<!-- prumo:modes-table:begin -->
| Você diz | Modo |
|---|---|
| "resuma o paper X" | `extract` |
| "extraia os principais pontos do paper" | `extract` |
| "processa todos os papers novos" | `extract` |
| "sincroniza minha bibliografia" | `library` |
| "importa minhas anotações do Zotero" | `library` |
| "encontra paper sobre Y" | `library` |
| "quem cita Z" | `library` |
| "marca o paper principal" | `library` |
| "liga o projeto à coleção do Zotero" | `library` |
| "as referências batem com o que eu afirmo?" | `support` |
| "checa se as citações sustentam as frases" | `support` |
<!-- prumo:modes-table:end -->
