---
name: paper-extract
description: "Extrai conteúdo estruturado do PDF de um paper (TL;DR, Problema com PICOT, Método, Resultados, Limitações) e escreve em um callout delimitado acima das seções humanas da nota. Invocar quando o usuário pedir \"resuma o paper X\", \"extraia os principais pontos\", \"processa todos os papers novos\", \"/paper-extract\", \"/paper-extract-all\", ou quando um `pj_*` acabou de sincronizar papers do Zotero e o usuário quer alimentar o callout automaticamente. Pressuposto: `/paper-manager sync` já criou as notas e `make sync-pdfs` criou os symlinks."
---

# Paper Extract — extração estruturada de PDF → callout da nota

Skill que lê o PDF (via symlink em `references/pdfs/<citekey>.pdf`), gera conteúdo para 5 seções estruturadas e escreve em `references/notes/<citekey>/_extract.md` (arquivo dedicado, layout α). O usuário edita/refina as seções humanas em `_meta.md`; o `_extract.md` é 100% auto.

## Pressupostos

- cwd é um `pj_*` com `.claude/paper_extraction.md` e `.claude/pj_config.toml` presentes (scaffold default atende).
- `_references.bib` exportado pelo BBT.
- `references/pdfs/<citekey>.pdf` é symlink válido (rode `make sync-pdfs` primeiro).
- `references/notes/<citekey>/_meta.md` já existe (rode `/paper-manager sync` ou `make sync-paper` primeiro).

Se qualquer pré-requisito falha, abortar com mensagem clara.

## Operações

### 1. `/paper-extract <citekey>` — single

Interativo, 1 paper.

Passos:

1. **Validar** via `Bash`:
   - `test -f "references/notes/<citekey>/_meta.md" && test -L "references/pdfs/<citekey>.pdf" && test -f "$(readlink references/pdfs/<citekey>.pdf)"`
   - `test -f ".claude/paper_extraction.md"` (config opcional: ausente → usa DEFAULTS)
   - Qualquer falha → abortar com mensagem de qual pré-requisito falta e o que rodar.

2. **Ler config:**
   ```bash
   python3 -c "import sys, json; sys.path.insert(0, '../.claude/scripts'); from _project_config import load_config; print(json.dumps(load_config(__import__('pathlib').Path('.'))))"
   ```
   Extrair `paper_extract.language`.

3. **Despachar 1 subagent** via tool `Agent` com `subagent_type="general-purpose"`:
   - Prompt:
     ```
     Leia o PDF em <absolute_path_to_pdf> usando mcp__pdf-reader__read_pdf.
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

4. **Receber JSON** do subagent. Se `error`, abortar mostrando motivo.

5. **Aplicar extração** via `Bash`:
   ```bash
   python3 -c '
   import sys; sys.path.insert(0, "../.claude/scripts")
   from pathlib import Path
   from paper_extract import apply_extraction
   import json
   content = json.loads("""<JSON_AQUI>""")
   changed = apply_extraction(
       nota_path=Path("references/notes/<citekey>/_extract.md"),
       template_path=Path(".claude/paper_extraction.md"),
       content=content,
       model="<modelo_atual>",
       date="<hoje>",
   )
   print("MUDOU" if changed else "IDÊNTICO")
   '
   ```

6. **Mostrar diff** do callout ao usuário e perguntar: "Arquivar TL;DR como finding em `docs/findings/`?". Se sim, delegar a `/wiki-query` ou criar finding direto.

### 2. `/paper-extract-all [--limit N] [--stale-only]` — batch

Non-interactive em modo headless (via `make extract-paper-all`) ou interactive.

Passos:

1. **Ler config** → `default_limit` e `subagents_per_wave`.

2. **Elegíveis:**
   - Todas as notas em `references/notes/*/_meta.md` com:
     - `references/pdfs/<citekey>.pdf` symlink existe e aponta para arquivo real;
     - `extracted_at: null` **OU** (`--stale-only` AND hash atual do template != `extracted_template_hash`).
   - Aplicar `--limit` (default: `config.paper_extract.batch.default_limit`).

3. **Despachar em ondas de `subagents_per_wave` (default 8)**:
   - Cada onda = 1 message com N tool calls em paralelo para `Agent(subagent_type="general-purpose", ...)`.
   - Cada subagent recebe prompt idêntico ao single, escreve DIRETO no disco (chama `apply_extraction` via `Bash`), retorna apenas `{citekey, status, error?}`.

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

- `paper_extraction.md` ausente → "Restaure do scaffold: `cp ../.claude/templates/pj_projeto/.claude/paper_extraction.md .claude/`"
- `pj_config.toml` ausente → usa DEFAULTS (não é erro fatal).
- Subagent retorna JSON malformado → retry 1x com prompt "corrija o JSON anterior"; depois skip com erro "JSON malformado após 2 tentativas".
- Callout com delimitadores corrompidos (usuário mexeu dentro) → abortar com "Restaure ou delete as linhas entre `<!-- paper-extract:begin -->` e `<!-- paper-extract:end -->` em references/notes/<citekey>/_extract.md."
