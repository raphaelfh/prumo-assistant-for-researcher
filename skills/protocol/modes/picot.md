---
name: picot
description: "Apelido de `question` (ADR-0041): a PICOT agora é um dos frameworks opcionais da pergunta do estudo. Leia modes/question.md e siga-o."
argument-hint: "[init | formalize | propagate | diff]"
allowed-tools: Read Write Edit Glob Grep Bash(cat *) Bash(prumo protocol *)
prumo:
  version: 2.0.0
  schema: QuestionSpec/v1
  determinism: hybrid
  agent_compat: [claude-code]
  requires: [cli]
  phrases:
    - "fecha a PICOT"
    - "a PICOT mudou"
---

# PICOT — apelido do modo `question`

<!-- prumo:preflight:begin -->
> **Preflight — antes de qualquer operação deste modo:**
>
> 1. **Superfície e CLI:** fora de um agente com terminal no seu Mac ou Linux (Claude Code
>    no app ou no terminal, Antigravity, Codex no app ChatGPT ou no terminal), isto é, numa
>    tarefa do Cowork, num chat web, numa sessão SSH, no Windows ou no WSL, diga em uma frase
>    que este modo não roda aqui e pare. Senão, rode `prumo --version`
>    (sem `prumo`, a forma `sh … --version` do bloco PAR; cada comando pedirá permissão). O
>    esperado é `prumo <versão do bloco PAR da porta>`.
>    - Linha `PAR:` do sandbox (saída 77): ofereça repetir o comando fora do sandbox, pedindo
>      permissão.
>    - Qualquer outra saída (outra versão, `PAR: falta o uv`, outra linha `PAR:`, nada): roteie
>      para `/par:start`, que resolve, e pare.
>    Nunca simule a operação.
> 2. **Estrutura:** se o diretório não tiver `docs/references/` de um `pj_*`,
>    oriente `prumo init pj_<nome>`; nunca crie o scaffold à mão.
<!-- prumo:preflight:end -->

Este modo existe para quem chega pela PICOT. A pergunta do estudo é o artefato principal
(ADR-0041), e a PICOT é um dos frameworks opcionais dela.

**Leia [`question.md`](question.md) inteiro e siga-o**, com uma diferença: no passo 4 do
`init`, proponha `"framework": "PICOT"` (ou `PICO`, se não houver tempo) sem perguntar se quer
um framework, já que a pesquisadora pediu a PICOT.
