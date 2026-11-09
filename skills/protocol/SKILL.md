---
name: protocol
description: "Protocolo do estudo: fechar e versionar a PICOT, gerar o plano de análise estatística e o projeto para CEP/Plataforma Brasil."
when_to_use: |
  Modos: cep, picot, sap. Frases típicas:
  - cep: "gera o projeto CEP"; "preciso submeter pra Plataforma Brasil"
  - picot: "fecha a PICOT"; "formaliza a pergunta de pesquisa"; "a PICOT mudou"
  - sap: "gera o plano de análise estatística"; "justifica o tamanho amostral"; "planeja as análises de sensibilidade"
argument-hint: "[cep|picot|sap] [argumentos do modo]"
allowed-tools: Read Write Edit Glob Grep Bash(prumo write *) Bash(cat *) Bash(prumo protocol *) Bash(prumo --version)
prumo:
  version: 2.0.0
  agent_compat: [claude-code]
---

# protocol — protocolo do estudo

<!-- prumo:runtime:begin -->
**PAR 0.71.3** · raiz do plugin: `${CLAUDE_PLUGIN_ROOT}` (se ali aparecer a variável `CLAUDE_PLUGIN_ROOT` em vez de um caminho, você está no Antigravity ou no Codex: a raiz é a pasta que contém o `skills/` ou o `agents/` deste arquivo)
- CLI: `prumo`. Se `prumo` não existir nesta sessão (fora do Claude, ou hooks bloqueados pela organização), use `sh "${CLAUDE_PLUGIN_ROOT}/shims/prumo"` com a raiz acima: funciona igual, mas cada comando pode pedir permissão.
- Tools MCP do PAR (servidor `prumo`): `mcp__plugin_par_prumo__*` no Claude, `mcp__prumo__*` no Codex, servidor `par_prumo` no Antigravity.
- Invocação: o texto escreve `/par:<skill>` (Claude); no Codex e no app ChatGPT é `$par:<skill>`, no Antigravity `/<skill>`.
- Agents: `${CLAUDE_PLUGIN_ROOT}/agents/`. Sem tool de subagent no host, leia o agent e siga-o você mesmo.
<!-- prumo:runtime:end -->

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
