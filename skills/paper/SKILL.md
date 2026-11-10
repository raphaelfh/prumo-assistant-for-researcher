---
name: paper
description: "Acervo bibliográfico do pj_*: sincronizar com o Zotero, extrair PDFs em callout estruturado e checar se as citações sustentam as frases."
when_to_use: |
  Modos: extract, library, support. Frases típicas:
  - extract: "resuma o paper X"; "extraia os principais pontos do paper"; "processa todos os papers novos"
  - library: "sincroniza minha bibliografia"; "o que eu anotei no Zotero sobre este paper"; "encontra paper sobre Y"; "quem cita Z"; "marca o paper principal"; "liga o projeto à coleção do Zotero"
  - support: "as referências batem com o que eu afirmo?"; "checa se as citações sustentam as frases"
argument-hint: "[extract|library|support] [argumentos do modo]"
allowed-tools: Read Write Edit Glob Grep Bash(prumo paper extract-prep *) Bash(prumo paper extract *) Bash(prumo paper sync-pdfs *) Bash(cat *) Agent Bash(prumo paper sync *) Bash(prumo paper graph *) Bash(prumo paper find *) Bash(prumo paper lint *) Bash(prumo paper set-primary *) Bash(prumo paper migrate-layout *) Bash(rg *) Bash(prumo paper verify-refs *) Bash(prumo validate *) Bash(prumo --version)
prumo:
  version: 2.0.0
  agent_compat: [claude-code]
---

# paper — acervo bibliográfico

<!-- prumo:runtime:begin -->
**PAR 0.71.3** · raiz do plugin: `${CLAUDE_PLUGIN_ROOT}` (se ali aparecer a variável `CLAUDE_PLUGIN_ROOT` em vez de um caminho, você está no Antigravity ou no Codex: a raiz é a pasta que contém o `skills/` ou o `agents/` deste arquivo)
- CLI: `prumo`. Se `prumo` não existir nesta sessão (fora do Claude, ou hooks bloqueados pela organização), use `sh "${CLAUDE_PLUGIN_ROOT}/shims/prumo"` com a raiz acima: funciona igual, mas cada comando pode pedir permissão.
- Tools MCP do PAR (servidor `prumo`): `mcp__plugin_par_prumo__*` no Claude, `mcp__prumo__*` no Codex, servidor `<pasta do plugin>_prumo` no Antigravity.
- Invocação: o texto escreve `/par:<skill>` (Claude); no Codex e no app ChatGPT é `$par:<skill>`, no Antigravity `/<skill>`.
- Agents: `${CLAUDE_PLUGIN_ROOT}/agents/`. Sem tool de subagent no host, leia o agent e siga-o você mesmo.
<!-- prumo:runtime:end -->

Escolha o modo antes de agir:

1. **Argumento explícito vence.** `/par:paper extract @smith2024` → modo `extract`.
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
| "o que eu anotei no Zotero sobre este paper" | `library` |
| "encontra paper sobre Y" | `library` |
| "quem cita Z" | `library` |
| "marca o paper principal" | `library` |
| "liga o projeto à coleção do Zotero" | `library` |
| "as referências batem com o que eu afirmo?" | `support` |
| "checa se as citações sustentam as frases" | `support` |
<!-- prumo:modes-table:end -->
