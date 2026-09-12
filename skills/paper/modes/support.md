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

Ataca o residual que nenhuma camada determinística alcança: **referência real
que não sustenta a afirmação** (buraco semântico da autoria original — spec da
ponte, §Camada de verificação de referências, item 4).

Regra de ouro: **este protocolo SINALIZA e para.** Nunca edita a página, nunca
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
4. **Despachar o subagent `verifier`** (tool `Agent`, `subagent_type: "verifier"`; se o plugin registrar com prefixo, `par:verifier`). Se nenhum dos dois tipos existir nesta sessão, leia o prompt canônico `agents/verifier.md` (em `$CLAUDE_PLUGIN_ROOT/agents/` ou `.claude/agents/`) e despache `subagent_type: "general-purpose"` com o corpo do arquivo como prompt.
   Envie `page` e `pairs`. Ele lê o PDF e devolve `SupportReport/v1` com quatro
   vias: `fully`, `partially`, `unsubstantiated`, `no-source`.
5. **Validar o contrato**:
   `cat <<'JSON' | prumo validate SupportReport/v1 --json` com o JSON devolvido.
   Inválido → devolva a mensagem ao verifier UMA vez; na segunda falha, mostre o
   erro ao pesquisador sem completar vereditos por conta própria.
   Subcomando ausente (`No such command 'validate'`, exit 2 — o CLI instalado é
   mais antigo que o plugin, mesmo com `prumo --version` e `verify-refs`
   respondendo) → confira à mão: `schema_version` = `SupportReport/v1`; `page`
   não vazio; em cada item de `verdicts`, `sentence`, `citekey` e `justification`
   não vazios, `verdict` ∈ `fully|partially|unsubstantiated|no-source`, `quote`
   presente quando `fully`/`partially` e `page` ≥ 1 quando houver. Falhou → mesma
   regra acima. Diga ao pesquisador UMA vez que `uv tool upgrade prumo-assistant-for-researcher`
   traz a validação e rode SÓ com consentimento.
6. **Relatório final** (tabela): frase (recorte) | citekey | veredito | página |
   trecho | justificativa. Feche com a lista de ações sugeridas AO HUMANO
   (ex.: "reescrever a frase X", "trocar a citação Y", "rodar
   `/par:paper extract Z`") — sem executar nenhuma.

## Limites duros

- NUNCA edite página, bib, notas ou worklist — nem "só uma vírgula".
- NUNCA conclua veredito sem o PDF lido pelo verifier. O `_extract.md` é
  resumo de LLM e só serve para achar a página; na dúvida entre Partially e
  Unsubstantiated, o verifier escolhe Unsubstantiated (falso-negativo é mais
  barato que falso-conforto — mesmo racional fail-closed do repo).
- Citação retratada NUNCA vira "Fully supported" — erro determinístico
  primeiro, sempre.
