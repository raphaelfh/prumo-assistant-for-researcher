---
title: Integração de Notas Zotero ↔ Repo (B1 + qmd)
date: 2026-05-03
status: superseded
superseded-by: "[[2026-10-02-ponte-zotero-minima-design]]"
tags: [zotero, notes, retrieval, architecture, knowledge-base]
---

# Integração de Notas Zotero ↔ Repo

> Aposentado pela ADR-0037 (0.71.0): `sync-notes` e as notas-filhas saem do PAR.

## Resumo executivo

Estendemos o `prumo paper sync-*` com um novo comando `sync-notes` que projeta cada **child note do Zotero** num arquivo Markdown próprio sob `references/notes/<citekey>/`. Direção é **read-only Zotero → repo**, multi-nota é preservado, identificadores estáveis (Zotero `itemKey`) garantem reconciliação. Wiki retrieval continua a cargo do MCP `qmd`. Nenhum banco intermediário é introduzido — princípios I (Lógica em um lugar só) e VI (YAGNI militante) da [`constitution`](../../constitution.md) são respeitados.

## Contexto e problema

A pesquisa clínica deste projeto envolve:
- Anotação no PDF do Zotero (highlights, comments) durante leitura.
- **Child notes** livres no Zotero como rascunhos de leitura ("ideias da intro", "crítica metodológica").
- Texto formal estruturado em Markdown no Obsidian (`<key>.md` com Problema/Método/Resultados/...).

O `prumo paper sync-annotations` já cobre highlights via API local. Mas **child notes** ficam isoladas no Zotero, perdidas pro grafo do projeto e pro retrieval do agente. O resultado é que ideias de leitura nunca encontram o argumento na escrita formal — fricção de centralização.

## AS-IS

```
┌──────────────────┐
│ Zotero (SQLite)  │
│  parent items    │
│  attachments     │
│   ├ annotations  │ ──── prumo paper sync-annotations ──→  bloco em <key>.md
│   ├ child notes  │ ──── (nenhum sync hoje)
│  standalone notes│ ──── (idem)
└──────────────────┘

references/notes/<key>.md  ← arquivo único; YAML CSL-JSON + callout extract +
                             seções humanas + bloco annotations
```

Limitações:
- Múltiplas child notes do Zotero **não chegam** ao repo.
- Quando chegariam (via `mgmeyers Zotero Integration` ad-hoc), todas iam pra mesma pasta `references/notes/`, conflitando com o `<key>.md` produzido pelo `prumo paper sync`.
- Granularidade ruim pra retrieval: arquivo único de 2-5 mil tokens dilui sinal BM25/vector.
- Identificação frágil: nada no Markdown rastreia o `itemKey` da fonte.

## Decisões arquiteturais

### D1 — Adotar B1 (read-only granular)

Cada child note Zotero vira **um arquivo Markdown próprio**. Direção: Zotero → repo. Edição da child note acontece no Zotero (com PDF aberto ao lado, contexto certo). Repo é espelho navegável + retrieval-friendly + versionado em git.

**Por que não bidirecional**: conflict resolution é dor real, conversão HTML↔Markdown é lossy nas duas direções, e a separação "rascunho de leitura no Zotero / argumento formal no Markdown" é coerente com o fluxo cognitivo do pesquisador.

### D2 — Pasta-por-paper, layout α

Em vez de pasta plana com prefixos, cada citekey ganha um diretório:

```
references/notes/<citekey>/
├── _meta.md                          ← gerado por `prumo paper sync`
├── _extract.md                       ← gerado por `/prumo-assist:paper-extract`
├── _annotations.md                   ← gerado por `prumo paper sync-annotations`
└── note__<itemKey>__<slug>.md        ← gerado por `prumo paper sync-notes` (NOVO)
```

Convenções:
- Arquivos com prefixo `_` são "infraestrutura do paper" (gerados pelo prumo).
- `note__*.md` é espelho de child notes do Zotero (1:1).
- `<itemKey>` no nome é o identificador estável (8 caracteres alfanuméricos do Zotero); `<slug>` é cosmético, derivado do título da nota.
- Pasta isola o domínio do paper: navegação no Obsidian fica clara, retrieval pode filtrar por path.

### D3 — qmd permanece único motor de retrieval

O MCP `qmd` indexa `references/notes/**/*.md` diretamente (BM25 + vector + rerank). Ele *é* o "NoSQL embedded" do retrieval. Não introduzimos banco intermediário.

### D4 — Sem banco canônico (SQLite, NoSQL, ou outro)

Análise comparativa registrada na própria sessão de brainstorming:

- **SQLite canônico**: redundância — Zotero já é SQLite, qmd já é índice especializado.
- **Document store / search engine embedded**: substituiria parcial ou totalmente o qmd; sem ganho.
- **Vector DB embedded**: redundância TOTAL — qmd cobre.
- **Graph DB embedded** (Kuzu): única vantagem genuinamente nova (path queries N-hop sobre citações). **Não introduzido hoje** — mantido como candidato a cache regenerável quando triggers acontecerem (ver §"Quando re-avaliar").

Filesystem como canônico ganha em: versionamento git, edição humana direta, compatibilidade Obsidian, portabilidade, simplicidade.

### D5 — Convivência com `mgmeyers Zotero Integration`

O plugin `obsidian-zotero-desktop-connector` (mgmeyers) está instalado em alguns `pj_*`. Ele permanece, mas com papel **redefinido**:

- **Mantido**: comandos ad-hoc na escrita ("Insert citation", "Insert bibliography").
- **Descontinuado como fonte automática de notas**: o campo `noteImportFolder` deve ficar vazio ou apontar pra pasta morta. `prumo paper sync-*` é dono da pasta `references/notes/`.

Esse papel reduzido é documentado em [`actions-by-context`](../../actions-by-context.md) na seção "Fase 2 · Evidência".

## Arquitetura

### Camadas

```
┌─────────────────────────────────────────────────────────────────┐
│  Zotero (upstream SQLite — não controlamos)                     │
│  parent items · attachments+annotations · child notes ·          │
│  standalone notes                                                │
└────────────────────────────────┬────────────────────────────────┘
                                 │ Local API (HTTP)
                                 │ + Better BibTeX JSON-RPC
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  prumo paper sync-*  (read-only Zotero → repo)                  │
│   sync, sync-annotations, sync-notes (NOVO), sync-all (NOVO)    │
└────────────────────────────────┬────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│  references/notes/<citekey>/  (CANÔNICO; versionado em git)     │
│   _meta.md  ·  _extract.md  ·  _annotations.md  ·  note__*.md   │
└────────────────────────────────┬────────────────────────────────┘
                ┌────────────────┴────────────────┐
                ▼                                 ▼
       ┌────────────────┐              ┌──────────────────────┐
       │ Obsidian       │              │ qmd MCP (BM25+vector │
       │ (humano)       │              │ + rerank; index local)│
       └────────────────┘              └──────────┬───────────┘
                                                  ▼
                                         ┌────────────────┐
                                         │  Agente / LLM  │
                                         │  (retrieval)   │
                                         └────────────────┘
```

### Fluxo de dados (caso típico)

1. Pesquisador adiciona paper no Zotero (PDF, DOI ou drag-and-drop).
2. BBT auto-export atualiza `_references.bib`.
3. Pesquisador abre PDF no Zotero, dá highlights, escreve child notes ("ideias da intro").
4. Em momento conveniente: `prumo paper sync-all <pj>`:
   - `sync` → cria/atualiza `<key>/_meta.md` a partir do `.bib`.
   - `sync-annotations` → escreve `<key>/_annotations.md` com highlights renderizados.
   - `sync-notes` (NOVO) → cria/atualiza `<key>/note__<itemKey>__<slug>.md` por child note.
5. qmd reindexa (gatilho próprio do MCP).
6. Agente responde retrieval com chunks pequenos e bem-rotulados.

### Anatomia de `<citekey>/`

**`_meta.md`** — gerado por `prumo paper sync`:

```yaml
---
id: smith2024multimodal
type: article-journal
title: "Multimodal fusion for breast cancer grading"
author:
  - { family: Smith, given: J }
issued: { date-parts: [[2024]] }
DOI: 10.xxxx
pdf: ../../pdfs/smith2024multimodal.pdf
role: supporting
status: unread
tldr: ""
cites: []
---

> [!tldr]
> _(uma frase: o que o paper fez e resultado principal)_

## Problema  ## Método  ## Resultados  ## Limitações
## Relevância para este projeto  ## Notas
```

**`_extract.md`** — gerado por `/prumo-assist:paper-extract`:

```markdown
<!-- paper-extract:begin -->
### TL;DR ...
### PICOT ...
### Método ...
### Resultados ...
### Limitações ...
<!-- paper-extract:end -->
```

**`_annotations.md`** — gerado por `prumo paper sync-annotations`:

```markdown
---
paper: smith2024multimodal
source: zotero-annotations
---

<!-- BEGIN ZOTERO ANNOTATIONS -->

### 🟡 p. 5 — highlight
> "Multimodal fusion improves..."

### 📍 p. 7 — note
verificar isso

<!-- END ZOTERO ANNOTATIONS -->
```

**`note__<itemKey>__<slug>.md`** — gerado por `prumo paper sync-notes` (NOVO):

```markdown
---
paper: smith2024multimodal
zotero_item_key: ABCD1234
source: zotero-child-note
date_added: 2026-04-30T14:23:00Z
date_modified: 2026-05-02T09:11:00Z
tags: [hipoteses, datasets]
title: "Ideias da introdução"
---

<!-- BEGIN ZOTERO -->

(conteúdo da child note convertido de HTML → Markdown)

<!-- END ZOTERO -->
```

## Comandos `prumo paper sync-*`

### Existentes (sem mudança comportamental, ajuste de path)

- `prumo paper sync <pj>` — `.bib` → `notes/<key>/_meta.md`. Antes escrevia em `notes/<key>.md`; agora cria a pasta e escreve dentro.
- `prumo paper sync-annotations <pj>` — Zotero annotations → `notes/<key>/_annotations.md`. Antes escrevia bloco delimitado dentro do `<key>.md`; agora arquivo dedicado com YAML próprio.

### Novo: `prumo paper sync-notes <pj>`

Lê child notes via `GET /users/<lib>/items/<key>/children?itemType=note` na API local. Pra cada child note:

1. Gera `<itemKey>__<slug>` derivado do `itemKey` (estável) e `title` (slug do conteúdo).
2. Renderiza HTML → Markdown via mesmo conversor minimalista que `sync-annotations` já usa em [zotero.py:html_to_markdown](../../../src/prumo_assist/domains/paper/zotero.py).
3. Compõe YAML com `paper`, `zotero_item_key`, `source`, `date_added`, `date_modified`, `tags`, `title`.
4. Escreve como `notes/<citekey>/note__<itemKey>__<slug>.md`.
5. Substitui apenas o bloco `<!-- BEGIN ZOTERO --> ... <!-- END ZOTERO -->`. YAML é regenerado integral; texto fora dos delimitadores não é tocado (espaço pra anotação humana abaixo se quiser).
6. Notas que sumiram do Zotero **não são deletadas** automaticamente — listadas como "órfãs" no relatório, decisão fica com o usuário.

### Novo orquestrador: `prumo paper sync-all <pj>`

Roda `sync` + `sync-annotations` + `sync-notes` em sequência, com relatório agregado. Atalho ergonômico — equivale ao que `make sync-paper` fazia no monorepo.

### Ajustes em comandos correlatos

- `prumo paper graph` — varre `notes/**/*.md` (recursivo) ao invés de `notes/*.md`. Lê `cites:` em qualquer arquivo do paper, agrega na pasta. Wikilinks `[[@key]]` continuam sendo a fonte.
- `prumo paper find` — idem, varre todos arquivos da pasta do paper. Score reflete ocorrências em `_meta`, `_extract`, `_annotations` e `note__*`.
- `prumo paper lint` — passa a verificar:
  - existência de `<key>/_meta.md` pra cada citekey do `.bib`
  - blocos delimitados intactos em `_annotations.md`, `_extract.md`, `note__*.md`
  - notas órfãs (arquivos `note__*.md` cujo `itemKey` não existe mais no Zotero)
  - notas duplicadas (mesmo `itemKey` em arquivos diferentes)

## Convenções

### YAML frontmatter (obrigatório)

Todo arquivo gerado tem YAML com no mínimo:
- `paper: <citekey>` — backlink
- `source: prumo-* | zotero-* | human` — origem
- `generated_at: ISO 8601` — quando o conteúdo derivado foi escrito (não quando o arquivo foi criado)

### Nomeação

| Arquivo | Padrão |
|---|---|
| `_meta.md`, `_extract.md`, `_annotations.md` | fixos, prefixo `_` |
| `note__<itemKey>__<slug>.md` | `itemKey` em `[A-Z0-9]{8}`; `slug` em kebab-case (≤30 chars) |
| `<citekey>/` | já regrado por BBT |

### Wikilinks

- `[[@<citekey>]]` continua sendo a forma canônica de citação.
- Resolve no Obsidian para qualquer arquivo do diretório `<citekey>/` cujo título inclua `<citekey>` no frontmatter — ou para `_meta.md` por convenção (preferido em caso de ambiguidade).

## Casos de borda

| Caso | Comportamento |
|---|---|
| Child note removida do Zotero | Arquivo `note__*.md` permanece; reportado no `lint` como "órfão". Decisão de remover é humana. |
| Child note renomeada (título mudou) | `slug` muda; arquivo é renomeado preservando `itemKey`. Git percebe como rename. |
| `itemKey` colide entre child notes | Impossível por design do Zotero. |
| Citekey renomeada no Zotero (ex.: BBT regenera) | Pasta `<citekey-velha>/` fica órfã; nova `<citekey-nova>/` é criada. `lint` reporta. Decisão humana de mover/deletar. |
| Standalone notes (`itemType: note` sem parent) | **Fora do escopo desta versão.** Avaliar em iteração futura — provavelmente vão pra `references/notes/_standalone/`. |
| Edição humana no Markdown da child note | Sobrescrita no próximo `sync-notes`. Convenção: edição humana fica fora dos delimitadores `BEGIN ZOTERO`/`END ZOTERO`. |
| Conflito de escrita simultânea (sync rodando + Obsidian salvando) | Improvável (sync é manual). Se acontecer: tmp file + atomic rename evita corrupção parcial. |

## Consumers downstream (informativo, fora do escopo desta spec)

Os arquivos gerados em `references/notes/<citekey>/` alimentam, além de Obsidian e qmd, uma **família de skills de escrita por finalidade** desenhada em `docs/canvas/project-flow.canvas` (removido do repo; conteúdo na tag `v0.65.0`) mas ainda não implementada:

- `/prumo-assist:write-projeto-cep` — projeto de Comitê de Ética em Pesquisa
- `/prumo-assist:write-paper` — paper acadêmico
- `/prumo-assist:write-statistics` — escrita estatística
- `/prumo-assist:write-scientific` — escrita científica geral

Essas skills consomem `_extract.md` (estrutura PICOT/Método), `_annotations.md` (citações ancoradas) e `note__*.md` (rascunhos de leitura) pra montar argumentos. Spec dedicada a escrever — **não é escopo desta**.

Implicação concreta pra esta spec: o YAML dos arquivos gerados precisa ser estável o suficiente pra essas skills consumirem. Os campos `paper`, `source`, `zotero_item_key`, `tags` formam o **contrato mínimo de leitura** — não removê-los nem renomeá-los sem coordenação com a próxima spec.

## Fora do escopo (deliberado)

- **Write-back ao Zotero** (POST/PUT na API). Tentação alta, custo real (HTML/MD lossy nos dois lados, conflict resolution, deletação cross-system). Reavaliar quando edição em Markdown for hábito real e voltar pro Zotero virar dor.
- **`zotero-better-notes`** (plugin bidirecional). Avaliado e descartado: limitações de wikilinks `[[@key]]`, YAML rígido próprio, sync time-based opaco. Caminho próprio é mais barato e mais aderente.
- **Banco canônico** (SQLite/NoSQL/graph DB). Reanalisado em detalhe — qmd já cumpre o papel de motor de retrieval embedded.
- **Standalone notes**. Próxima iteração.
- **Skills `write-projeto-cep` / `write-paper` / `write-statistics` / `write-scientific`**: escopo separado; spec dedicada. Esta spec garante apenas o *contrato de leitura* (YAML estável) que aquelas skills vão consumir.

## Quando re-avaliar

Triggers concretos pra mudar arquitetura. Cada trigger tem **métrica observável**.

| Trigger | Métrica | Resposta |
|---|---|---|
| `prumo paper graph` >5s | tempo cronometrado | Adicionar **Kuzu** como cache regenerável (não canônico) |
| Queries N-hop sobre citações ≥3x/semana | contagem do `_log.md` | Idem (Kuzu) |
| Volume passar de 5.000 child notes/annotations agregadas | `find references/notes -name 'note__*.md' \| wc -l` | Adicionar **SQLite cache** pra agregações |
| Edição em MD de child notes virar hábito (≥5 commits/mês mexendo nos `note__*.md`) | git log | Reavaliar **write-back** a partir do bloco `BEGIN ZOTERO` (não a partir de tudo) |
| Better Notes amadurecer e ganhar suporte a wikilinks | release notes do plugin | Reavaliar como import path |

## Plano de implementação (alto nível)

Quatro PRs sequenciais:

1. **PR-N1 — Migração de layout**: `references/notes/<key>.md` → `references/notes/<key>/_meta.md`. Atualiza:
   - `prumo paper sync` (gera `_meta.md` no novo caminho).
   - `prumo paper sync-annotations` (gera `_annotations.md` como arquivo dedicado, não mais bloco no `_meta.md`).
   - skill `/prumo-assist:paper-extract` (gera `_extract.md` como arquivo dedicado, não mais callout dentro do `<key>.md`).
   - `prumo paper migrate-layout` one-shot move arquivos existentes preservando histórico via `git mv` e desmembra o callout `paper-extract:begin/end` e o bloco `ZOTERO ANNOTATIONS` em arquivos separados.
   - Atualiza testes (passam a operar em pasta).
   - Atualiza template `references/templates/literature_note.md` pra refletir layout.
2. **PR-N2 — `sync-notes`**: novo comando. Reusa `_http_get_json` + `html_to_markdown` de `zotero.py`. Adiciona testes com fixtures. Documenta na skill `paper-manager`.
3. **PR-N3 — `sync-all` orquestrador + ajustes em comandos correlatos**: `graph`, `find`, `lint` aprendem o novo layout (varredura recursiva). Skill `paper-manager` atualizada.
4. **PR-N4 — Documentação**: skill `paper-manager` reflete o novo modelo; `actions-by-context.md` ganha gatilho "Quero importar minhas child notes do Zotero"; `templates/pj_base/CLAUDE.md` menciona pasta-por-paper; `[[Research Project Structure]]` ganha referência cruzada.

Cada PR é mergível independente; PR-N1 inclui flag de fallback pra layout antigo durante 1 release pra suavizar migração.

## Referências

- [Zotero Web API — items endpoints](https://www.zotero.org/support/dev/web_api/v3/basics)
- [Better BibTeX JSON-RPC](https://retorque.re/zotero-better-bibtex/exporting/json-rpc/index.html)
- [zotero-better-notes](https://github.com/windingwind/zotero-better-notes) — *avaliado, fora do caminho escolhido*
- [`constitution`](../../constitution.md) — princípios I e VI
- [`Research Project Structure`](../../Research%20Project%20Structure.md)
- [`actions-by-context`](../../actions-by-context.md)
