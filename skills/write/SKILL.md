---
name: write
description: "Escrita do manuscrito: draft IMRaD, seção avulsa, convenções editoriais de escrita científica e declaração de uso de IA."
when_to_use: |
  Modos: disclosure, manuscript, section, style. Frases típicas:
  - disclosure: "gera a declaração de uso de IA"; "disclosure de IA pro periódico"
  - manuscript: "escreve um draft do meu paper"; "rascunho IMRaD sobre X"
  - section: "escreve essa seção"; "expande este parágrafo"
  - style: "aplica as convenções de escrita científica"; "tira os travessões"; "passa pro inglês americano"
argument-hint: "[disclosure|manuscript|section|style] [argumentos do modo]"
allowed-tools: Read Bash(prumo write disclosure *) Write Edit Glob Grep Bash(prumo write *) Bash(cat *) Bash(git *) Bash(rg *)
prumo:
  version: 2.0.0
  agent_compat: [claude-code]
---

# write — escrita do manuscrito

Escolha o modo antes de agir:

1. **Argumento explícito vence.** `/par:write style drafts/intro.md` → modo `style`.
2. **Senão, pela intenção**, usando a tabela abaixo.
3. **Ambíguo entre modos → faça UMA pergunta** listando os candidatos com uma frase de exemplo cada. Na dúvida entre gerar e orientar, oriente.
4. **Leia `modes/<modo>.md` inteiro antes de qualquer operação.** Este arquivo não contém instrução operacional; o preflight e o procedimento de cada modo estão lá.

<!-- prumo:modes-table:begin -->
| Você diz | Modo |
|---|---|
| "gera a declaração de uso de IA" | `disclosure` |
| "disclosure de IA pro periódico" | `disclosure` |
| "escreve um draft do meu paper" | `manuscript` |
| "rascunho IMRaD sobre X" | `manuscript` |
| "escreve essa seção" | `section` |
| "expande este parágrafo" | `section` |
| "aplica as convenções de escrita científica" | `style` |
| "tira os travessões" | `style` |
| "passa pro inglês americano" | `style` |
<!-- prumo:modes-table:end -->
