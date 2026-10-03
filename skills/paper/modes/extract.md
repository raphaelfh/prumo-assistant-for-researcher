---
name: extract
description: "Extrai conteúdo estruturado do PDF de um paper (TL;DR, Problema com PICOT, Método, Resultados, Limitações) e escreve em callout delimitado em docs/references/papers/<citekey>/_extract.md. Pressupõe /par:paper library sync executado + symlinks via prumo paper sync-pdfs."
argument-hint: "[citekey] | --all [--limit N] [--stale-only]"
allowed-tools: Read Write Edit Glob Grep Bash(prumo paper extract-prep *) Bash(prumo paper extract *) Bash(prumo paper sync-pdfs *) Bash(cat *) Agent
prumo:
  version: 1.0.0
  schema: PaperCallout/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~2-5k tokens (single) | ~20-80k (batch)
  inputs:
    citekey: optional (single mode)
    limit: optional (batch mode)
    stale_only: optional (batch mode)
  requires: [cli]
  phrases:
    - "resuma o paper X"
    - "extraia os principais pontos do paper"
    - "processa todos os papers novos"
  legacy: [paper-extract, paper-extract-all]
  disclosure_task: "structured extraction of key information from source documents"
---

# Paper Extract — extração estruturada de PDF → callout da nota

<!-- prumo:preflight:begin -->
> **Preflight (contrato ADR-0019) — execute ANTES de qualquer operação desta skill:**
>
> 1. **CLI:** rode `prumo --version`. Se o comando NÃO existir: não simule NENHUMA
>    operação desta skill; roteie para `/par:start` (instalação guiada com
>    consentimento) e pare aqui.
> 2. **Estrutura:** se o diretório não tiver `docs/references/` de um `pj_*`,
>    oriente `prumo init pj_<nome>` — NUNCA crie o scaffold manualmente (o agente
>    não simula trabalho do CLI) e NUNCA cite tooling do monorepo do autor.
>
> Recusar-se a operar sem dependência NÃO é falha — é o contrato fail-closed (D1):
> operação exata nunca é simulada.
<!-- prumo:preflight:end -->

Skill que lê o PDF (via symlink em `docs/references/pdfs/<citekey>.pdf`), gera conteúdo para 5 seções estruturadas e escreve em `docs/references/papers/<citekey>/_extract.md` (arquivo dedicado, layout α). O usuário edita/refina as seções humanas em `_meta.md`; o `_extract.md` é 100% auto.

## Pressupostos

- cwd é um `pj_*` (scaffold default atende). A skill lê o PDF e escreve o callout em `_extract.md`.
- A validação de pré-requisitos (template, `.bib`, PDF, `_meta.md`) e a leitura de
  config são feitas por `prumo paper extract-prep <citekey>` (aborta com o comando de correção).

## Operações

### 1. `/par:paper extract <citekey>` — single

Interativo, 1 paper.

Passos:

1. **Validar pré-requisitos + ler config** via `Bash`:
   ```bash
   prumo paper extract-prep <citekey> --json
   ```
   Capture `language`, `template_path`, `pdf_path` e `meta_path` do JSON. Se falhar (exit ≠ 0), aborte mostrando a mensagem (ela já traz o comando de correção).

2. **Despachar o subagent `reader`** (tool `Agent`, `subagent_type: "reader"`; se o plugin registrar com prefixo, `par:reader`). Se nenhum dos dois tipos existir nesta sessão, leia o prompt canônico `agents/reader.md` (em `$CLAUDE_PLUGIN_ROOT/agents/` ou `.claude/agents/`) e despache `subagent_type: "general-purpose"` com o corpo do arquivo como prompt.
   Preencha: `citekey`, `pdf_path`, `template_path` e `language` (do passo 1), `pj_path` (absoluto),
   `model` (o modelo desta sessão) e `date` (hoje, YYYY-MM-DD).

3. **Receber o status** do reader: `{"citekey", "status", "error"?}`. O reader grava sozinho via
   `prumo paper extract`, com locators por seção; o comando valida o JSON por `PaperCallout/v1` e
   carimba a proveniência no `_meta.md`. Se `status` for `error`, aborte mostrando o motivo.

4. **Não grave o extract pelo thread principal.** O PDF e o JSON ficam no contexto do reader; aqui
   só chega o status.

5. **Mostrar o callout** gravado ao usuário e perguntar: "Arquivar TL;DR como finding (`type: finding`) em `docs/studies/<slug>/notes/`?". Se sim, delegar a `/par:wiki query` ou criar finding direto.

### 2. `/par:paper extract [--limit N] [--stale-only]` — batch

Non-interactive em modo headless (via `claude -p`) ou interactive.

Passos:

1. **Ler config:** leia `.claude/pj_config.toml` (via `Read`) e pegue `paper_extract.batch.default_limit` (default 20) e `paper_extract.batch.subagents_per_wave` (default 8); se o arquivo ou as chaves não existirem, use os defaults.

2. **Elegíveis:**
   - Todas as notas em `docs/references/papers/*/_meta.md` com:
     - `docs/references/pdfs/<citekey>.pdf` symlink existe e aponta para arquivo real (validado via `prumo paper extract-prep <citekey>` — reporta symlink quebrado ou PDF ausente);
     - `extracted_at: null` **OU** (`--stale-only` AND hash atual do template != `extracted_template_hash`) — verificado lendo cada `_meta.md` com `Read`.
   - Aplicar `--limit` (default: `config.paper_extract.batch.default_limit`).

3. **Despachar em ondas de `subagents_per_wave` (default 8)**:
   - Cada onda = 1 message com N chamadas `Agent` em paralelo, uma por paper, despachando o `reader`
     exatamente como no single (mesmo fallback para `general-purpose` com `agents/reader.md`).
   - Cada reader grava direto via `prumo paper extract` e devolve só `{citekey, status, error?}`.

4. **Coletar** status de todas as ondas em uma lista.

5. **Imprimir tabela final**:
   ```
   citekey                   status   erro
   smith2024multimodal       ok       —
   jones2023fusion           erro     PDF symlink quebrado
   ...
   ✓ N ok · M erro · K skipped (já extraídos ou sem PDF).
   ```

## Boundaries

- **Nunca** tocar seções `##` (Problema, Método, …) da nota — só o callout delimitado.
- **Nunca** tocar `_references.bib` (BBT é dono).
- **Nunca** baixar PDF — respeita copyright; Zotero cuida.
- **Paper sem PDF no Zotero** → skip, reportar, não abortar o batch.
- **PDF sem OCR decente** → subagent aborta o paper individual, batch continua.

## Erros comuns

- `paper_extraction.md` ausente → "Restaure rodando `prumo init . --merge` no diretório do projeto (recoloca arquivos ausentes do template sem sobrescrever os existentes)."
- `pj_config.toml` ausente → usa DEFAULTS (não é erro fatal).
- `prumo paper extract` recusa o JSON do reader (seção fora do template, tipo errado) → o reader corrige 1 vez pela mensagem; na segunda recusa devolve `error` e o batch segue.
- Callout com delimitadores corrompidos (usuário mexeu dentro) → abortar com "Restaure ou delete as linhas entre `<!-- paper-extract:begin -->` e `<!-- paper-extract:end -->` em docs/references/papers/<citekey>/_extract.md."
