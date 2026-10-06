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
> 1. **CLI:** rode `prumo --version`. Se o comando NÃO existir: não simule NENHUMA
>    operação desta skill; roteie para `/par:start` (instalação guiada com
>    consentimento) e pare aqui.
> 2. **Drift CLI×plugin (evidência da Fase 0):** se `$CLAUDE_PLUGIN_ROOT` estiver
>    definido, compare a versão do CLI com o campo `version` de
>    `$CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json`. CLI mais antigo → avise
>    ("CLI X < plugin Y — comandos novos podem não existir") e ofereça
>    `uv tool upgrade prumo-assistant-for-researcher` (rode SÓ com consentimento). Sem a variável,
>    pule este passo em silêncio.
> 3. **Estrutura:** se o diretório não tiver `docs/references/` de um `pj_*`,
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
