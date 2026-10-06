---
name: export
description: "Gera o docx do manuscrito com citações vivas do Zotero: travado para a rodada de revisão do coautor, ou final para editar no Word com o Zotero."
argument-hint: "<página.md> [revisão|final]"
allowed-tools: Read Bash(prumo write export *)
prumo:
  version: 1.0.0
  determinism: deterministic
  agent_compat: [claude-code]
  cost_estimate: ~1k tokens
  requires: [cli]
  phrases:
    - "exporta o docx para o coautor revisar"
    - "gera a versão final em Word"
    - "quero usar o Zotero no Word"
---

# write export — docx com citações vivas

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

Há dois docx, e trocar um pelo outro estraga o trabalho da pessoa.

1. **Pergunte para que é o docx**, se o pedido não disser: "É para o coautor revisar e voltar para o PAR, ou é a versão final?". Na dúvida, é revisão.
2. Rode o comando da linha escolhida na tabela abaixo na raiz do `pj_*`. Acrescente `--style <estilo>` só se a pessoa pedir outro estilo que não APA.

| Para quê | Comando | O que dá para fazer no Word |
|---|---|---|
| **Revisão** pelo coautor (volta com `prumo write review ingest`) | `prumo write export <página> --to docx` | Comentar e editar o texto. As citações ficam travadas. |
| **Final** (submissão, trocar estilo, editar com o Zotero) | `prumo write export <página> --to docx --final` | Tudo, inclusive Refresh e Add/Edit Citation do Zotero. Esse arquivo nunca vai para a revisão. |

3. Se o comando avisar que citações saíram sem vínculo com o Zotero, repasse o aviso com o comando de refazer que ele traz. O docx é válido do mesmo jeito.
4. Entregue o caminho do docx e uma frase:
   - revisão: "Peça ao coautor para não usar os botões do Zotero (Refresh, Add/Edit Citation) neste arquivo. Quando ele devolver, peça para eu ingerir a revisão.";
   - final: "Pode usar o Zotero no Word à vontade. Para trocar de estilo, use Document Preferences no Zotero ou peça um novo export com o estilo."

## Sinais de alerta

| Pensamento | Realidade |
|---|---|
| "Vou gerar o docx com pandoc direto, é mais rápido" | Nunca gere o docx por outro caminho: as citações saem mortas e a revisão não volta. Sem o `prumo`, pare e roteie para `/par:start`. |
| "O coautor quer só dar uma olhada, mando o final" | Se o arquivo vai voltar com comentários, é revisão. |
| "O Refresh deu erro no docx de revisão" | É a trava funcionando. Para usar o Zotero no Word, exporte o final. |
| "Vou ingerir o docx final" | O final não volta para o PAR: o Zotero reescreve os campos e o ingest recusa. |
