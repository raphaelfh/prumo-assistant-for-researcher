---
name: review
description: "Revisão: crítica substantiva do draft por seção e reconciliação dos eventos ambíguos do round-trip docx↔CriticMarkup."
when_to_use: |
  Modos: critique, reconcile. Frases típicas:
  - critique: "revisa este draft"; "me dá um peer review"; "quais buracos no meu argumento"; "seja o advogado do diabo"; "seja duro"; "revisa antes de submeter"
  - reconcile: "reconcilia os eventos ambíguos da revisão"; "resolve as marcas sem âncora do docx"
argument-hint: "[critique|reconcile] [argumentos do modo]"
allowed-tools: Read Glob Grep Bash(prumo validate *) Agent Bash(prumo write review events *) Bash(prumo doctor *) mcp__prumo__review_status mcp__prumo__review_events mcp__prumo__review_worklist mcp__prumo__propose_prose_edit
prumo:
  version: 2.0.0
  agent_compat: [claude-code]
---

# review — revisão

Escolha o modo antes de agir:

1. **Argumento explícito vence.** `/par:review critique drafts/paper.md` → modo `critique`.
2. **Senão, pela intenção**, usando a tabela abaixo.
3. **Ambíguo entre modos → faça UMA pergunta** listando os candidatos com uma frase de exemplo cada. Na dúvida entre gerar e orientar, oriente.
4. **Leia `modes/<modo>.md` inteiro antes de qualquer operação.** Este arquivo não contém instrução operacional; o preflight e o procedimento de cada modo estão lá.

<!-- prumo:modes-table:begin -->
| Você diz | Modo |
|---|---|
| "revisa este draft" | `critique` |
| "me dá um peer review" | `critique` |
| "quais buracos no meu argumento" | `critique` |
| "seja o advogado do diabo" | `critique` |
| "seja duro" | `critique` |
| "revisa antes de submeter" | `critique` |
| "reconcilia os eventos ambíguos da revisão" | `reconcile` |
| "resolve as marcas sem âncora do docx" | `reconcile` |
<!-- prumo:modes-table:end -->
