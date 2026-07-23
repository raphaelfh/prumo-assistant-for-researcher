# Ponte docx↔CriticMarkup — Fase 0: spike do adeu + fix do lua — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Responder a pergunta aberta nº 1 do spec da ponte (o `adeu` preserva `instrText` de campos `ADDIN ZOTERO_ITEM` através da extração com tracked changes?), decidir o backend de extração, e corrigir o bug do filtro lua (`item.id` sempre = citekey).

**Architecture:** Spike com fixtures docx sintéticas construídas por script (pandoc gera o esqueleto válido; Python injeta campo vivo + tracked changes no `word/document.xml`); adeu SEMPRE via `uvx adeu==1.29.0` (isolado — adeu exige Python ≥3.12, prumo é 3.11; nunca importar o SDK). O fix do lua é 1 linha + verificação com pandoc real (spike-grade); a rede de regressão de CI chega na Fase 1 do substrato (citemap golden).

**Tech Stack:** pandoc 3.9 (em `/opt/homebrew/bin/pandoc`), `uvx adeu==1.29.0` (CLI: `extract [--json] [-o]`, `diff`, `markup <input> <edits> [-o -]`, `apply`, `accept-all`), Python stdlib (`zipfile`).

**Spec:** `docs/superpowers/specs/2026-07-05-review-docx-criticmarkup-design.md` (Fase 0 da tabela de fases; status: approved 2026-07-23). Guarda-chuva: `2026-07-22-zero-friction-onboarding-design.md` (Fase 3).

## Global Constraints

- Fronteira de release: **sem release** (spike + fix acumulam em "Não publicado").
- adeu SEMPRE pinado: `uvx adeu==1.29.0` (versão sondada ao vivo em 2026-07-23; era 1.18.4 no início de julho — churn alto é exatamente por que se pina).
- Artefatos do spike ficam no scratchpad da sessão (`/private/tmp/claude-501/...` ou `mktemp -d`), NUNCA no repo; só a EVIDÊNCIA (outputs verbatim) entra no report e a DECISÃO entra neste plano.
- Contagem de conservação sempre pelo NOSSO método (I2): `unzip -p f.docx word/document.xml | grep -c 'ADDIN ZOTERO_ITEM'` — nunca pela saída do adeu.
- Fix do lua conforme spec ("Export instrumentado" item 2): `item.id` SEMPRE carrega o citekey; id numérico migra para `zoteroItemID`; `uris` mantido.
- Qualquer código do repo tocado: `mypy --strict`/`ruff` verdes; mensagens pt-BR; commit convencional com escopo.
- `uv run pytest` completo verde antes de cada commit (441 testes hoje).

---

### Task 1: Spike — o adeu preserva `instrText` com tracked changes?

**Files:**
- Nenhum arquivo do repo. Scripts e fixtures em diretório temporário (`SPIKE=$(mktemp -d)`).
- Report: `.superpowers/sdd/ponte-f0-task-1-report.md` (evidência verbatim).

**Interfaces:**
- Consumes: pandoc real, `uvx adeu==1.29.0`.
- Produces: a resposta A/B/C da matriz de decisão (consumida pela Task 3) + os outputs verbatim dos probes.

- [ ] **Step 1: Construir as fixtures**

```bash
SPIKE=$(mktemp -d) && cd "$SPIKE"
printf 'Primeiro paragrafo de prosa.\n\nAqui vem a citacao CITEPLACEHOLDER e mais prosa.\n\nUltimo paragrafo.\n' > base.md
pandoc base.md -o original.docx
```

Criar `inject.py` no `$SPIKE` (injeta campo vivo no lugar do placeholder e gera as variantes revisadas):

```python
"""Injeta campo ADDIN ZOTERO_ITEM + tracked changes em um docx gerado por pandoc."""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

FIELD = (
    '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
    '<w:r><w:instrText xml:space="preserve"> ADDIN ZOTERO_ITEM CSL_CITATION '
    '{&quot;citationID&quot;:&quot;00000001&quot;,'
    '&quot;citationItems&quot;:[{&quot;id&quot;:&quot;smith2020&quot;}],'
    '&quot;properties&quot;:{&quot;formattedCitation&quot;:&quot;(Smith, 2020)&quot;}}'
    ' </w:instrText></w:r>'
    '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
    '<w:r><w:t>(Smith, 2020)</w:t></w:r>'
    '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
)

INS = (
    '<w:ins w:id="901" w:author="Coautor" w:date="2026-07-23T12:00:00Z">'
    "<w:r><w:t xml:space=\"preserve\"> TEXTO INSERIDO PELO COAUTOR</w:t></w:r></w:ins>"
)

def rewrite(src: str, dst: str, transform) -> None:
    shutil.copy(src, dst)
    with zipfile.ZipFile(src) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    xml = transform(xml)
    tmp = Path(dst + ".tmp")
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(tmp, "w") as zout:
        for item in zin.infolist():
            data = xml.encode("utf-8") if item.filename == "word/document.xml" else zin.read(item)
            zout.writestr(item, data)
    tmp.replace(dst)

def put_field(xml: str) -> str:
    # pandoc emite o placeholder como run próprio: <w:r><w:t ...>CITEPLACEHOLDER</w:t></w:r>
    return re.sub(r"<w:r>(?:(?!</w:r>).)*?CITEPLACEHOLDER(?:(?!</w:r>).)*?</w:r>", FIELD, xml, count=1, flags=re.S)

def add_prose_changes(xml: str) -> str:
    # inserção rastreada após o campo + deleção rastreada da palavra 'Ultimo'
    xml = xml.replace('<w:fldChar w:fldCharType="end"/></w:r>', '<w:fldChar w:fldCharType="end"/></w:r>' + INS, 1)
    return re.sub(
        r"<w:r>((?:(?!</w:r>).)*?)<w:t([^>]*)>Ultimo([^<]*)</w:t></w:r>",
        '<w:del w:id="902" w:author="Coautor" w:date="2026-07-23T12:00:00Z">'
        r"<w:r>\1<w:delText\2>Ultimo\3</w:delText></w:r></w:del>",
        xml, count=1, flags=re.S,
    )

def delete_field(xml: str) -> str:
    # embrulha TODOS os runs do campo num w:del e troca w:t por w:delText (coautor deletou a citação)
    start = xml.index('<w:r><w:fldChar w:fldCharType="begin"/>')
    end_marker = '<w:fldChar w:fldCharType="end"/></w:r>'
    end = xml.index(end_marker, start) + len(end_marker)
    field = xml[start:end].replace("<w:t>", "<w:delText>").replace("</w:t>", "</w:delText>")
    wrapped = '<w:del w:id="903" w:author="Coautor" w:date="2026-07-23T12:00:00Z">' + field + "</w:del>"
    return xml[:start] + wrapped + xml[end:]

rewrite("original.docx", "com_campo.docx", put_field)
rewrite("com_campo.docx", "reviewed_prosa.docx", add_prose_changes)
rewrite("com_campo.docx", "reviewed_campo.docx", delete_field)
print("fixtures ok")
```

Run: `cd "$SPIKE" && python3 inject.py`
Expected: `fixtures ok`. Sanity: `unzip -p com_campo.docx word/document.xml | grep -c 'ADDIN ZOTERO_ITEM'` → `1`. Se o Word/pandoc mudou a forma do run do placeholder e o `put_field` não casar, inspecionar `unzip -p original.docx word/document.xml | grep -o '.\{40\}CITEPLACEHOLDER.\{40\}'` e ajustar o regex — registrar o ajuste no report.

- [ ] **Step 2: Probe A — extração**

```bash
cd "$SPIKE"
uvx adeu==1.29.0 extract reviewed_prosa.docx -o - | head -40
uvx adeu==1.29.0 extract --json reviewed_prosa.docx -o - | head -60
```
Registrar verbatim: o campo aparece? Como (texto display `(Smith, 2020)`? marcador de campo? instrText?) As tracked changes aparecem (ins/del)?

- [ ] **Step 3: Probe B — diff→markup (caminho CriticMarkup)**

```bash
cd "$SPIKE"
uvx adeu==1.29.0 help diff
uvx adeu==1.29.0 diff com_campo.docx reviewed_prosa.docx > edits.json 2>&1 || true; head -60 edits.json
uvx adeu==1.29.0 markup com_campo.docx edits.json -o - 2>&1 | head -60 || true
```
(Se `diff` emitir outro formato/uso, seguir o help e registrar o fluxo real.) Registrar: o CriticMarkup de saída contém `{++...++}`/`{--...--}` da prosa? A citação sobrevive intacta (display e/ou campo), foi achatada para texto puro, ou sumiu?

- [ ] **Step 4: Probe C — deleção do campo inteiro**

```bash
cd "$SPIKE"
uvx adeu==1.29.0 extract --json reviewed_campo.docx -o - | head -60
uvx adeu==1.29.0 accept-all reviewed_campo.docx -o campo_aceito.docx 2>&1 | tail -3 || true
unzip -p campo_aceito.docx word/document.xml 2>/dev/null | grep -c 'ADDIN ZOTERO_ITEM' || echo "0 (campo removido após accept-all — esperado)"
unzip -p reviewed_campo.docx word/document.xml | grep -c 'ADDIN ZOTERO_ITEM'
```
Registrar: a deleção do campo é visível como evento? O instrText segue presente no docx revisado (nossa contagem I2 = 1) mesmo que o adeu não o mostre?

- [ ] **Step 5: Preencher a matriz de decisão no report**

| Resultado observado | Backend decidido |
|---|---|
| adeu expõe/preserva o campo (instrText ou display estável) nos probes A–C | **(a)** adeu pinado para marcas E campos |
| adeu achata/perde o campo mas trata bem a prosa | **(b)** adeu só para prosa; extração de CITAÇÃO 100% OOXML própria (`zipfile`, método I2) |
| adeu falha/inadequado também para prosa | **(c)** `pandoc --track-changes=all` para prosa + OOXML próprio para citação |

Report completo em `.superpowers/sdd/ponte-f0-task-1-report.md` com os outputs verbatim de cada probe e a linha da matriz escolhida com justificativa de 2–3 frases. Sem commit (nada do repo mudou).

---

### Task 2: Fix do lua — `item.id` sempre carrega o citekey

**Files:**
- Modify: `src/prumo_assist/_filters/zotero_live_docx.lua:94` (função `build_csl_citation`)
- Modify: `CHANGELOG.md` (item em "Não publicado" → "### Corrigido")

**Interfaces:**
- Consumes: comportamento atual (linha 93–95: `local lookup = zotero_lookup[key] or {}` / `local item = { id = lookup.itemID or key }` / `if lookup.uri ...`).
- Produces: payload de campo com `id` = citekey SEMPRE e `zoteroItemID` = id numérico quando o lookup popula. Pré-condição da I1/I2b (citação como átomo chaveado por citekey) das fases seguintes.

- [ ] **Step 1: Aplicar o fix**

Em `zotero_live_docx.lua`, substituir:

```lua
    local lookup = zotero_lookup[key] or {}
    local item = { id = lookup.itemID or key }
    if lookup.uri then item.uris = { lookup.uri } end
```

por:

```lua
    local lookup = zotero_lookup[key] or {}
    -- I1/I2b (spec da ponte): id SEMPRE = citekey (átomo opaco chaveado);
    -- o id numérico do Zotero viaja em zoteroItemID.
    local item = { id = key }
    if lookup.itemID then item.zoteroItemID = lookup.itemID end
    if lookup.uri then item.uris = { lookup.uri } end
```

- [ ] **Step 2: Verificação spike-grade com pandoc real (com e sem lookup)**

```bash
SPIKE2=$(mktemp -d) && cd "$SPIKE2"
printf -- '---\nnocite: []\n---\nTexto com [@smith2020].\n\n::: {#refs}\n:::\n' > page.md
printf '@article{smith2020, title={Title}, author={Smith, A.}, year={2020}}\n' > refs.bib
printf '{"smith2020": {"itemID": 123, "uri": "http://zotero.org/users/1/items/ABC"}}\n' > lookup.json
cat > mini.csl <<'CSL'
<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0">
  <info><title>mini</title><id>mini</id><updated>2026-01-01T00:00:00+00:00</updated></info>
  <citation><layout><text variable="title"/></layout></citation>
  <bibliography><layout><text variable="title"/></layout></bibliography>
</style>
CSL
LUA=<repo>/.claude/worktrees/open-source-software-engineering-market-40b0b6/src/prumo_assist/_filters/zotero_live_docx.lua
pandoc page.md --citeproc --bibliography=refs.bib --csl=mini.csl --to=docx --standalone \
  --lua-filter="$LUA" --metadata=zotero_csl_style:apa --metadata=zotero_lookup_file:lookup.json -o com_lookup.docx
pandoc page.md --citeproc --bibliography=refs.bib --csl=mini.csl --to=docx --standalone \
  --lua-filter="$LUA" --metadata=zotero_csl_style:apa -o sem_lookup.docx
unzip -p com_lookup.docx word/document.xml | grep -o '"id":"smith2020"' && unzip -p com_lookup.docx word/document.xml | grep -o '"zoteroItemID":123'
unzip -p sem_lookup.docx word/document.xml | grep -o '"id":"smith2020"'
```
Expected: `"id":"smith2020"` nos DOIS docx; `"zoteroItemID":123` só no `com_lookup.docx`. Colar os outputs no report. (Nota: o JSON dentro de `instrText` sai XML-escaped; se o grep literal não casar, usar `grep -o 'id[^,]*smith2020'` e registrar a forma exata observada.)

- [ ] **Step 3: Suíte completa + lint**

Run: `uv run pytest` → 441 passed (o filtro não tem teste unitário próprio hoje; nada deve quebrar). `uv run ruff check . && uv run ruff format --check .` e `uv run mypy` → verdes (lua não é analisado; a checagem protege qualquer toque acidental).

- [ ] **Step 4: CHANGELOG**

Em `CHANGELOG.md`, adicionar ao bloco `### Corrigido` existente de "Não publicado":

```markdown
- Filtro `zotero_live_docx.lua`: `item.id` do campo `CSL_CITATION` agora carrega
  SEMPRE o citekey (o id numérico do Zotero migra para `zoteroItemID`) —
  pré-condição do átomo de citação da ponte docx↔CriticMarkup (spec 2026-07-05,
  invariantes I1/I2b).
```

- [ ] **Step 5: Registrar dívida de regressão + commit**

Anotar no report: teste de regressão CI-safe do payload chega na Fase 1 do substrato (citemap golden fixtures) — o spike acima é a evidência desta fase.

```bash
git add src/prumo_assist/_filters/zotero_live_docx.lua CHANGELOG.md
git commit -m "fix(filters): item.id do campo Zotero sempre carrega o citekey (zoteroItemID separado)"
```

Report: `.superpowers/sdd/ponte-f0-task-2-report.md`.

---

### Task 3 (controller): registrar decisão e arquivar

- [ ] **Step 1:** Colar neste plano (seção abaixo) a linha da matriz de decisão escolhida na Task 1 com a justificativa.
- [ ] **Step 2:** Frontmatter `status: implemented` + `verified: <data>` + `release: null` + `spec`/`phase`; mover para `docs/superpowers/plans/archive/`; `gen_indexes`; commit + push.

## Decisão de backend (preenchida na Task 3)

*(pendente da Task 1)*
