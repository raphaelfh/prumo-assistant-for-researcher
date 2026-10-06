---
name: support
description: "Classifica se cada citação de uma página sustenta a frase que a cita (Fully/Partially/Unsubstantiated/No-source) com o subagent verifier lendo o PDF — SINALIZA apenas, nunca edita nem bloqueia. Roda `prumo paper verify-refs` antes (base determinística: existência/retração/título)."
argument-hint: "--page <page.md>"
allowed-tools: Read Glob Grep Bash(prumo paper verify-refs *) Bash(prumo validate *) Agent
prumo:
  version: 1.0.0
  determinism: hybrid
  agent_compat: [claude-code]
  cost_estimate: ~3-8k tokens (depende do nº de citações na página)
  inputs:
    page: required
  requires: [cli]
  phrases:
    - "as referências batem com o que eu afirmo?"
    - "checa se as citações sustentam as frases"
  legacy: [citation-support]
---

# paper support — a citação sustenta a frase?

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

Ataca o residual que nenhuma camada determinística alcança: **referência real
que não sustenta a afirmação**.

Regra de ouro: **este protocolo SINALIZA e para.** Nunca edita página, bib, notas ou worklist, nunca
propõe marca, nunca bloqueia export/apply. Se algo precisar mudar no texto, o
caminho é humano (ou o fluxo `review reconcile` → `prumo write review apply`).

## Protocolo

1. **Base determinística primeiro**: rode
   `prumo paper verify-refs <pj> --page <page.md> --json`.
   - `retracted`/`doi-not-found` (errors): reporte no topo. Citekey retratada
     segue para o verifier marcada `retracted: true`.
2. **Inventário**: extraia da página cada par (frase → citekeys marcadas
   `[@key]`). Frase = sentença completa que contém a(s) marca(s).
3. **Montar os pares**: para cada citekey, `pdf_path` =
   `docs/references/pdfs/<citekey>.pdf` absoluto (`null` se não existir) e
   `locators` = os trechos da linha `**Onde:**` da seção pertinente em
   `docs/references/papers/<citekey>/_extract.md`, quando houver. Extract sem
   locators não impede nada: o verifier procura no PDF inteiro.
4. **Despachar o subagent `verifier`** (tool `Agent`, `subagent_type: "verifier"`; se o plugin registrar com prefixo, `par:verifier`). Se nenhum dos dois tipos existir nesta sessão, leia o prompt canônico `agents/verifier.md` (na pasta da linha *Agents* do bloco PAR da porta) e despache `subagent_type: "general-purpose"` com o corpo do arquivo como prompt.
   Envie `page` e `pairs`. Ele lê o PDF e devolve `SupportReport/v1` com quatro
   vias: `fully`, `partially`, `unsubstantiated`, `no-source`.
5. **Validar o contrato**:
   `cat <<'JSON' | prumo validate SupportReport/v1 --json` com o JSON devolvido.
   Inválido → devolva a mensagem ao verifier UMA vez; na segunda falha, mostre o
   erro ao pesquisador sem completar vereditos por conta própria.
6. **Relatório final** (tabela): frase (recorte) | citekey | veredito | página |
   trecho | justificativa. Feche com a lista de ações sugeridas AO HUMANO
   (ex.: "reescrever a frase X", "trocar a citação Y", "rodar
   `/par:paper extract Z`") — sem executar nenhuma.

## Limites duros

- NUNCA conclua veredito sem o PDF lido pelo verifier.
- Citação retratada NUNCA vira "Fully supported" — erro determinístico
  primeiro, sempre.
