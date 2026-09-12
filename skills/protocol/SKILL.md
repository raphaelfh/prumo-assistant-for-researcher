---
name: protocol
description: "Protocolo do estudo: fechar e versionar a PICOT, gerar o plano de análise estatística e o projeto para CEP/Plataforma Brasil."
when_to_use: |
  Modos: cep, picot, sap. Frases típicas:
  - cep: "gera o projeto CEP"; "preciso submeter pra Plataforma Brasil"
  - picot: "fecha a PICOT"; "formaliza a pergunta de pesquisa"; "a PICOT mudou"
  - sap: "gera o plano de análise estatística"; "justifica o tamanho amostral"; "planeja as análises de sensibilidade"
argument-hint: "[cep|picot|sap] [argumentos do modo]"
allowed-tools: Read Write Edit Glob Grep Bash(prumo write *) Bash(cat *) Bash(prumo protocol *)
prumo:
  version: 2.0.0
  agent_compat: [claude-code]
---

# protocol — protocolo do estudo

Escolha o modo antes de agir:

1. **Argumento explícito vence.** `/par:protocol picot formalize` → modo `picot`.
2. **Senão, pela intenção**, usando a tabela abaixo.
3. **Ambíguo entre modos → faça UMA pergunta** listando os candidatos com uma frase de exemplo cada. Na dúvida entre gerar e orientar, oriente.
4. **Leia `modes/<modo>.md` inteiro antes de qualquer operação.** Este arquivo não contém instrução operacional; o preflight e o procedimento de cada modo estão lá.

<!-- prumo:modes-table:begin -->
| Você diz | Modo |
|---|---|
| "gera o projeto CEP" | `cep` |
| "preciso submeter pra Plataforma Brasil" | `cep` |
| "fecha a PICOT" | `picot` |
| "formaliza a pergunta de pesquisa" | `picot` |
| "a PICOT mudou" | `picot` |
| "gera o plano de análise estatística" | `sap` |
| "justifica o tamanho amostral" | `sap` |
| "planeja as análises de sensibilidade" | `sap` |
<!-- prumo:modes-table:end -->
