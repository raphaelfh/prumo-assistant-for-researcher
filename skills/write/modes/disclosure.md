---
name: disclosure
description: "Gera a declaração de uso de IA do projeto a partir da proveniência gravada nos artefatos (determinístico, pt ou en)."
argument-hint: "[--lang pt|en]"
allowed-tools: Read Bash(prumo write disclosure *)
prumo:
  version: 1.0.0
  determinism: deterministic
  agent_compat: [claude-code]
  cost_estimate: ~1k tokens
  requires: [cli]
  phrases:
    - "gera a declaração de uso de IA"
    - "disclosure de IA pro periódico"
---

# write disclosure — declaração de uso de IA

<!-- prumo:preflight:begin -->
> **Preflight — antes de qualquer operação deste modo:**
>
> 1. **Superfície e CLI:** fora do app Claude na aba Code (Mac) ou do Claude Code no terminal
>    (Mac ou Linux), isto é, numa tarefa do Cowork, num chat, numa sessão SSH, no Windows ou no
>    WSL, diga em uma frase que este modo não roda aqui e pare. Senão, rode `prumo --version`
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

1. Rode `prumo write disclosure --lang <pt|en> --json` na raiz do `pj_*`. O idioma segue o pedido da pessoa; sem pedido, use o idioma do manuscrito. Se a pessoa citar o periódico, acrescente `--venue <chave>` (perfis: `icmje`, `jama`, `bmj`); outro nome também vai no `--venue` e devolve o texto genérico com o aviso de conferir a política.
2. Mostre o parágrafo (`statement_pt` ou `statement_en`) e a tabela de `tools`: ferramenta, modelo, tarefa, contagem e se houve revisão humana. Com `venue` preenchido, mostre também `prohibited`, `authorship`, `source_url` e `accessed`; os itens de "Complete antes de submeter" são da pessoa, não seus.
3. Se `tools` vier vazio, diga que nenhum artefato do projeto registra uso de IA. Não invente uso.
4. Nunca edite o parágrafo para acrescentar ferramenta que o comando não listou. Correção de proveniência se faz no artefato, não na declaração.
