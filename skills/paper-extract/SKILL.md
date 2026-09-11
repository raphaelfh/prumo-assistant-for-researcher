---
name: paper-extract
description: "Extrai conteúdo estruturado do PDF de um paper (TL;DR, Problema com PICOT, Método, Resultados, Limitações) e escreve em callout delimitado em docs/references/papers/<citekey>/_extract.md. Pressupõe /prumo-assist:paper-manager sync executado + symlinks via prumo paper sync-pdfs."
when_to_use: |
  Quando o usuário pedir "resuma o paper X", "extraia os principais pontos",
  "processa todos os papers novos", ou quando um pj_* acabou de sincronizar
  papers do Zotero e o usuário quer alimentar o callout automaticamente.
argument-hint: "[citekey] | --all [--limit N] [--stale-only]"
allowed-tools: Read Write Edit Glob Grep Bash(prumo paper *) Bash(cat *) Agent
prumo:
  version: 1.0.0
  schema: PaperExtract/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~2-5k tokens (single) | ~20-80k (batch)
  inputs:
    citekey: optional (single mode)
    limit: optional (batch mode)
    stale_only: optional (batch mode)
  requires: [cli]
---

# Paper Extract — extração estruturada de PDF → callout da nota

<!-- prumo:preflight:begin -->
> **Preflight (contrato ADR-0019) — execute ANTES de qualquer operação desta skill:**
>
> 1. **CLI:** rode `prumo --version`. Se o comando NÃO existir: não simule NENHUMA
>    operação desta skill; roteie para `/prumo-assist:start` (instalação guiada com
>    consentimento) e pare aqui.
> 2. **Drift CLI×plugin (evidência da Fase 0):** se `$CLAUDE_PLUGIN_ROOT` estiver
>    definido, compare a versão do CLI com o campo `version` de
>    `$CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json`. CLI mais antigo → avise
>    ("CLI X < plugin Y — comandos novos podem não existir") e ofereça
>    `uv tool upgrade prumo-assist` (rode SÓ com consentimento). Sem a variável,
>    pule este passo em silêncio.
> 3. **Estrutura:** se o diretório não tiver `docs/references/` de um `pj_*`,
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
- O CLI `prumo` precisa estar no PATH (rode `prumo doctor`; se ausente:
  `uv tool install git+https://github.com/raphaelfh/prumo-assist`).

## Operações

### 1. `/prumo-assist:paper-extract <citekey>` — single

Interativo, 1 paper.

Passos:

1. **Validar pré-requisitos + ler config** via `Bash`:
   ```bash
   prumo paper extract-prep <citekey> --json
   ```
   Capture `language`, `template_path`, `pdf_path` e `meta_path` do JSON. Se falhar (exit ≠ 0), aborte mostrando a mensagem (ela já traz o comando de correção).

2. **Despachar 1 subagent** via tool `Agent` com `subagent_type="general-purpose"`:
   - Prompt:
     ```
     Leia o PDF em <absolute_path_to_pdf> com a tool Read (lê PDF nativamente;
     leia em blocos de páginas se o PDF tiver >10 páginas).
     Para cada seção do template em <absolute_path_to_paper_extraction.md>,
     preencha APENAS com conteúdo do PDF. Grounding rigoroso: sem opinião,
     sem inferência fora do texto. Cite página quando souber: (p.5).

     Idioma do output: <language da config>.
     Citações literais (quotes) preservar no idioma original do PDF.

     Se >50% de alguma página parece OCR corrompido (texto ilegível),
     abortar retornando {"error": "OCR ruim", "citekey": "<citekey>"}.

     Retornar EXATAMENTE JSON puro, sem markdown cercado:
     {"TL;DR": "...", "Problema": "...", "Método": "...",
      "Resultados": "...", "Limitações": "..."}
     ```

3. **Receber JSON** do subagent. Se `error`, abortar mostrando motivo.

4. **Aplicar extração** via `Bash` (escreve o callout em `docs/references/papers/<citekey>/_extract.md` e atualiza `_meta.md`):
   ```bash
   cat <<'JSON' | prumo paper extract <citekey> --model "<modelo_atual>" --date "<hoje>" --json
   { "TL;DR": "<conteúdo extraído>", "Problema": "...", "Método": "...", "Resultados": "...", "Limitações": "..." }
   JSON
   ```
   Emite `{"changed": true}` (MUDOU) ou `{"changed": false}` (IDÊNTICO).

5. **Mostrar diff** do callout ao usuário e perguntar: "Arquivar TL;DR como finding (`type: finding`) em `docs/studies/<slug>/notes/`?". Se sim, delegar a `/prumo-assist:wiki-query` ou criar finding direto.

### 2. `/prumo-assist:paper-extract-all [--limit N] [--stale-only]` — batch

Non-interactive em modo headless (via `claude -p`) ou interactive.

Passos:

1. **Ler config:** leia `.claude/pj_config.toml` (via `Read`) e pegue `paper_extract.batch.default_limit` (default 20) e `paper_extract.batch.subagents_per_wave` (default 8); se o arquivo ou as chaves não existirem, use os defaults.

2. **Elegíveis:**
   - Todas as notas em `docs/references/papers/*/_meta.md` com:
     - `docs/references/pdfs/<citekey>.pdf` symlink existe e aponta para arquivo real (validado via `prumo paper extract-prep <citekey>` — reporta symlink quebrado ou PDF ausente);
     - `extracted_at: null` **OU** (`--stale-only` AND hash atual do template != `extracted_template_hash`) — verificado lendo cada `_meta.md` com `Read`.
   - Aplicar `--limit` (default: `config.paper_extract.batch.default_limit`).

3. **Despachar em ondas de `subagents_per_wave` (default 8)**:
   - Cada onda = 1 message com N tool calls em paralelo para `Agent(subagent_type="general-purpose", ...)`.
   - Cada subagent recebe prompt idêntico ao single, escreve DIRETO no disco (chama `prumo paper extract` via `Bash`, dict via stdin, idêntico ao single), retorna apenas `{citekey, status, error?}`.

4. **Coletar** status de todas as ondas em uma lista.

5. **Imprimir tabela final**:
   ```
   citekey                   status   erro
   smith2024combinado       ok       —
   jones2023trial           erro     PDF symlink quebrado
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
- Subagent retorna JSON malformado → retry 1x com prompt "corrija o JSON anterior"; depois skip com erro "JSON malformado após 2 tentativas".
- Callout com delimitadores corrompidos (usuário mexeu dentro) → abortar com "Restaure ou delete as linhas entre `<!-- paper-extract:begin -->` e `<!-- paper-extract:end -->` em docs/references/papers/<citekey>/_extract.md."
