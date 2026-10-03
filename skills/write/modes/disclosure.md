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

1. Rode `prumo write disclosure --lang <pt|en> --json` na raiz do `pj_*`. O idioma segue o pedido da pessoa; sem pedido, use o idioma do manuscrito. Se a pessoa citar o periódico, acrescente `--venue <chave>` (perfis: `icmje`, `jama`, `bmj`); outro nome também vai no `--venue` e devolve o texto genérico com o aviso de conferir a política.
2. Mostre o parágrafo (`statement_pt` ou `statement_en`) e a tabela de `tools`: ferramenta, modelo, tarefa, contagem e se houve revisão humana. Com `venue` preenchido, mostre também `prohibited`, `authorship`, `source_url` e `accessed`; os itens de "Complete antes de submeter" são da pessoa, não seus.
3. Se `tools` vier vazio, diga que nenhum artefato do projeto registra uso de IA. Não invente uso.
4. Nunca edite o parágrafo para acrescentar ferramenta que o comando não listou. Correção de proveniência se faz no artefato, não na declaração.
