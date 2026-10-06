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
> **Preflight (contrato ADR-0019) — execute ANTES de qualquer operação desta skill:**
>
> 1. **Superfície e CLI:** este modo precisa do app Claude na aba Code (Mac) ou do Claude Code
>    no terminal (Mac ou Linux). Se esta conversa for uma tarefa do Cowork, um chat, uma sessão
>    SSH ou rodar no Windows ou no WSL, diga em uma frase que este modo não é suportado aqui e
>    que a pessoa deve abrir o app Claude na aba Code (Mac) ou o Claude Code no terminal (Mac ou
>    Linux), e pare. Senão, rode `prumo --version`; o esperado é
>    `prumo <versão do bloco PAR da porta>`.
>    (a) `prumo` não existe: rode a forma `sh … --version` do bloco PAR e aplique (b)–(d) à
>    saída dela; avise uma vez que cada comando vai pedir permissão. Só se a saída não trouxer
>    nem a versão nem uma linha `PAR:`, diga "abra uma sessão nova" e pare.
>    (b) Outra versão: rode `command -v prumo`. Caminho terminado em `/shims/prumo`: é outra
>    versão do plugin; diga "este `prumo` é de outra versão do plugin — abra uma sessão nova".
>    Qualquer outro caminho (por exemplo `~/.local/bin/prumo`): é o CLI antigo, instalado à
>    parte; ofereça UMA vez, com consentimento, `uv tool uninstall prumo-assistant-for-researcher`
>    (se a pessoa usa o Zettlr, antes peça "regenera o perfil do Zettlr" e a reimportação do
>    perfil, que ainda aponta para dentro desse CLI). Nos dois casos, use a forma `sh …` nesta
>    sessão.
>    (c) A saída contém `PAR: falta o uv`: roteie para `/par:start` (que instala o uv com
>    consentimento) e pare.
>    (d) Qualquer outra linha que comece com `PAR:`: repasse-a (ela traz o comando de correção).
>    Se for a do sandbox (saída 77), ofereça repetir o mesmo comando fora do sandbox, pedindo
>    permissão; nos outros casos, pare.
>    Nunca simule a operação.
> 2. **Estrutura:** se o diretório não tiver `docs/references/` de um `pj_*`,
>    oriente `prumo init pj_<nome>` — NUNCA crie o scaffold manualmente (o agente
>    não simula trabalho do CLI) e NUNCA cite tooling do monorepo do autor.
>
> Recusar-se a operar sem dependência NÃO é falha — é o contrato fail-closed (D1):
> operação exata nunca é simulada.
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
