---
status: draft
verified: null
release: null
spec: "[[2026-06-11-repo-organization-redesign-design]]"
---

# Repo Organization Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Executar o spec `docs/superpowers/specs/2026-06-11-repo-organization-redesign-design.md` — CLAUDE.md raiz + rules, ADR log próprio (`docs/adr/`), constitution como fonte única de princípios, lifecycle de plans, índices gerados com check no CI, graphify, e um release MINOR v0.62.0 que remove os agents ML e reconcilia contratos de skill.

**Architecture:** Duas trilhas. Trilha A (Tasks 1–13, branch `chore/repo-organization-redesign`): organização pura, não-releasável. Trilha B (Tasks 14–17, branch `release/v0.62.0` criada **após** o merge da trilha A): mudanças visíveis ao consumidor num único release. Nenhum diretório load-bearing se move (`skills/`, `templates/`, `agents/`*, `.mcp.json`, `.claude-plugin/`). *`agents/` desaparece na trilha B por decisão (ADR-0012), não por reorganização.

**Tech Stack:** Python 3.11+ (uv, pytest, ruff, mypy), Typer/PyYAML já no projeto, git/gh CLI, graphify (CLI global do usuário). Nenhuma dependência nova.

**Convenções deste plano:** Todos os comandos rodam na raiz do repo. Data canônica das mudanças: `2026-06-11`. Onde um passo diz "Edit", o executor usa edição exata (old → new); onde diz "Write", cria/sobrescreve o arquivo com o conteúdo completo mostrado.

---

## File Structure (visão geral do que muda)

| Caminho | Ação | Trilha |
|---|---|---|
| `settings.json` (raiz) | deletar (config morta) | A |
| `.claude/settings.json` | criar | A |
| `.claude/rules/code.md`, `.claude/rules/release.md` | criar | A |
| `CLAUDE.md`, `AGENTS.md` (symlink) | criar | A |
| `.gitignore` | corrigir glob + graphify-out/ | A |
| `docs/adr/adr-0001…0014.md` + `docs/adr/_index.md` | criar | A |
| `docs/constitution.md` | emenda → v1.1.0 | A |
| `ARCHITECTURE.md` | reescrever (what/where) | A |
| `docs/superpowers/plans/*` | frontmatter + mover p/ `archive/` | A |
| `docs/superpowers/specs/2026-04-29-*.md` | marcar superseded | A |
| `.github/scripts/gen_indexes.py` + `tests/unit/test_gen_indexes.py` | criar (TDD) | A |
| `README.md`, `skills/start/SKILL.md`, `docs/_index.md` | marcadores + blocos gerados | A (start regenera de novo em B) |
| `.github/workflows/ci.yml` | +2 checks | A |
| `ROADMAP.md`, `CITATION.cff`, `CHANGELOG.md` (rodapé), `RELEASING.md` | refresh | A |
| tags `v0.3.0…v0.61.0` | criar retroativas | A |
| `agents/*.md`, seção Agents do README | remover | B |
| `skills/wiki-ingest/SKILL.md`, `skills/paper-extract/SKILL.md` | pdf-reader → Read + conserto de imports | B |
| `skills/{paper-extract,peer-review,wiki-lint,wiki-query}/SKILL.md` | findings canônico (D10) | B |
| 7 SKILL.md | namespacing `/prumo-assist:` (D11) | B |
| `src/prumo_assist/_version.py`, manifests, `CHANGELOG.md` | release 0.62.0 | B |

---

# TRILHA A — organização (branch `chore/repo-organization-redesign`)

### Task 1: Higiene do working tree (Fase 0)

**Files:**
- Delete: `settings.json`, `docs/Untitled Kanban.md`, `docs/Untitled Kanban 1.md`, `docs/superpowers/plans/2026-05-31-land-all-work-on-main.md`
- Move (fora do repo): `docs/Untitled.canvas`
- Modify: `.gitignore`
- Create: `.claude/settings.json`

- [ ] **Step 1: Mover o canvas com dados pessoais para fora do repo**

```bash
mkdir -p ~/Documents/prumo-private
mv docs/Untitled.canvas ~/Documents/prumo-private/
```

(É gitignored e untracked — `mv` simples basta. Contém organograma pessoal com nomes de indivíduos; não pertence ao repo.)

- [ ] **Step 2: Deletar stubs e runbook efêmero (todos untracked)**

```bash
rm "docs/Untitled Kanban.md" "docs/Untitled Kanban 1.md"
rm docs/superpowers/plans/2026-05-31-land-all-work-on-main.md
find skills tests -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
rm -f skills/.DS_Store
```

- [ ] **Step 3: Corrigir o glob do gitignore e ignorar graphify-out**

Edit `.gitignore` — substituir:

```
# Obsidian — accidental "Untitled" stubs
docs/Untitled.*
```

por:

```
# Obsidian — accidental "Untitled" stubs (qualquer variante: Untitled.canvas, Untitled Kanban.md, ...)
docs/Untitled*

# graphify — grafo de conhecimento local (regenerável)
graphify-out/
```

- [ ] **Step 4: Substituir o settings.json morto da raiz**

```bash
git rm settings.json
```

Write `.claude/settings.json`:

```json
{
  "enabledMcpjsonServers": ["qmd"]
}
```

- [ ] **Step 5: Verificar estado**

Run: `git status --short`
Expected: `D settings.json`, `M .gitignore`, `?? .claude/settings.json`, e os untracked de plans/kanban sumiram da lista (exceto os 3 plans de 2026-05-30 que ficam para a Task 8).

- [ ] **Step 6: Commit**

```bash
git add .gitignore .claude/settings.json
git commit -m "chore: higiene do working tree (settings morto, gitignore, stubs Obsidian)"
```

(O `git rm settings.json` do Step 4 já deixou a deleção staged.)

---

### Task 2: Rules modulares (`.claude/rules/`)

**Files:**
- Create: `.claude/rules/code.md`
- Create: `.claude/rules/release.md`

- [ ] **Step 1: Write `.claude/rules/code.md`**

```markdown
# Regras de código

- Layering: `core/` NUNCA importa de `domains/`; `domains/` importam `core/`; domínios são mutuamente independentes (única exceção justificada: `write` → `protocol`, guardada por ImportError em `compose.py`).
- Fachadas finas: `cli.py` raiz e `domains/<X>/cli.py` fazem só parsing + chamada do domínio + saída. Todo subcomando Typer envolto em `core/cli_op.cli_run(...)`. Nada de `print()` direto — sempre `core/output.Console`.
- `domains/<X>/api.py` é re-export puro (wrapper passthrough é defeito).
- Tipagem estrita (`mypy --strict`); `from __future__ import annotations` em todo módulo; dataclasses `frozen=True` para value objects; Pydantic só em schemas versionados (`domains/<X>/schemas/v1.py`), forward-only: campo nunca é removido ou renomeado.
- Regiões machine-owned em Markdown usam blocos delimitados HTML-comment (`<!-- x:begin -->` / `<!-- x:end -->`); conteúdo humano fora do bloco é preservado. Ver ADR-0009.
- Testes espelham o layout (`tests/unit/<dominio>/test_<modulo>.py`); dependências externas (Zotero, qmd, pandoc) sempre mockadas nos seams (`_binary_on_path`, `_port_open`, `check_external_deps`).
- Docstrings e mensagens de usuário em pt-BR, com o comando de correção embutido na mensagem de erro; identificadores em inglês.
```

- [ ] **Step 2: Write `.claude/rules/release.md`**

```markdown
# Regras de release

- A versão é a interface pública do plugin: bump só quando o consumidor precisa saber (ver RELEASING.md).
- PATCH: correções e refinamentos sem mudança de trigger/output. MINOR: algo invocável novo; breaking pré-1.0 vai em MINOR com "⚠ Breaking". NÃO-releasável: `.github/`, `README.md`, `CHANGELOG.md`, `.gitignore`, `docs/` — reorganização de docs/infra nunca bumpa versão.
- Fonte única de versão: `src/prumo_assist/_version.py`. Propagação: `python .github/scripts/sync_manifest_version.py` → `plugin.json` + `marketplace.json`. NUNCA editar versão nos manifests à mão (Princípio VII da constitution).
- Todo release: atualizar CHANGELOG (mover "Não publicado", completar refs do rodapé), bump + sync, validar (`validate_manifests.py` e `sync_manifest_version.py --check`), commit `release: X.Y.Z - <resumo>` via branch `release/vX.Y.Z` + PR, e após o merge: tag anotada `vX.Y.Z` + `gh release create`. Atualizar `CITATION.cff` (campo `version`).
- CHANGELOG cita princípios pela numeração romana da constitution e referencia ADRs por `ADR-NNNN`.
```

- [ ] **Step 3: Commit**

```bash
git add .claude/rules/
git commit -m "docs(claude): rules modulares de código e release"
```

---

### Task 3: CLAUDE.md raiz + AGENTS.md symlink

**Files:**
- Create: `CLAUDE.md`
- Create: `AGENTS.md` (symlink → CLAUDE.md)

- [ ] **Step 1: Write `CLAUDE.md`**

```markdown
# prumo-assist — guia do repo

Plugin Claude Code + CLI Python (`prumo`) de pesquisa clínica: bibliografia (Zotero/BBT), wiki (Obsidian), protocolo (PICOT) e escrita (Pandoc/Typst). Prosa em pt-BR; identificadores, comandos e nomes de schema em inglês.

## Regras

- @.claude/rules/code.md
- @.claude/rules/release.md

## Fontes de verdade

- Princípios de design: `docs/constitution.md` — autoridade máxima. NÃO editar sem emenda formal (PR + Sync impact report).
- Decisões registradas: `docs/adr/` — consulte antes de propor mudança estrutural; decisão estrutural nova = ADR novo (MADR minimal, imutável após aceito).
- Mapa do código: `ARCHITECTURE.md` (what/where). Status e fases: `ROADMAP.md`.
- Workflow de feature: brainstorm → spec (`docs/superpowers/specs/`) → plan (`docs/superpowers/plans/`) → TDD. Plano implementado recebe frontmatter `status: implemented` + `verified` + `release` e move para `docs/superpowers/plans/archive/`.

## Armadilhas deste repo

- `templates/pj_base/CLAUDE.md` é PRODUTO (scaffolding de projetos `pj_*`), não orientação deste repo.
- `skills/` e `templates/` são force-included no wheel (pyproject) e resolvidos por `core/paths.py` — mover qualquer um exige atualizar os dois lados juntos.
- Plugin root = raiz do repo (`.claude-plugin/marketplace.json` usa `source: "./"`) — não mover `skills/`, `.mcp.json`, `.claude-plugin/`.
- `.mcp.json` é, ao mesmo tempo, config MCP deste projeto E config MCP distribuída aos consumidores do plugin.
- Reorganização de docs/.github NÃO bumpa versão (RELEASING.md, "Quando NÃO bumpar").
- Índices têm blocos gerados (README, `skills/start/SKILL.md`, `docs/_index.md`, `docs/adr/_index.md`): edite a fonte e rode o gerador — nunca o bloco à mão.

## Comandos

- Testes: `uv run pytest`
- Lint: `uv run ruff check . && uv run ruff format --check .`
- Types: `uv run mypy`
- Índices: `uv run python .github/scripts/gen_indexes.py` (CI roda `--check`)
```

- [ ] **Step 2: Criar o symlink AGENTS.md**

```bash
ln -s CLAUDE.md AGENTS.md
```

(Ecossistema AGENTS.md — Cursor, Codex, Jules etc. — lê o arquivo padrão; o Claude Code lê o CLAUDE.md diretamente.)

- [ ] **Step 3: Verificar que o symlink resolve**

Run: `cat AGENTS.md | head -3`
Expected: as 3 primeiras linhas do CLAUDE.md.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md AGENTS.md
git commit -m "docs: CLAUDE.md raiz com @imports + AGENTS.md symlink"
```

---

### Task 4: ADR log — diretório + ADRs 0001–0007

**Files:**
- Create: `docs/adr/adr-0001-adr-log-em-docs-adr.md` … `docs/adr/adr-0007-zotero-stdlib-urllib.md`

Formato comum (MADR 4.0 *minimal*, adaptado ao vault): H1 `# ADR-NNNN — Título`, campos `- Status:` / `- Data:` / `- Origem:`, seções `## Contexto`, `## Decisão`, `## Consequências`. ADR aceito é imutável; revisão = ADR novo que o substitui.

- [ ] **Step 1: Write `docs/adr/adr-0001-adr-log-em-docs-adr.md`**

```markdown
# ADR-0001 — ADR log do repo em `docs/adr/`; produto continua gerando `docs/decisions/`

- Status: aceito
- Data: 2026-06-11
- Origem: [[2026-06-11-repo-organization-redesign-design]] (D2)

## Contexto
As decisões do repo viviam em 5 lugares (ARCHITECTURE, constitution, ROADMAP, specs, canvas) sem canônico. O produto (`domains/protocol/adr.py` + `templates/pj_base`) gera ADRs em `docs/decisions/` nos projetos `pj_*` — o default do MADR 4.0 também é `decisions/`, enquanto `adr/` é a convenção do adr-tools e a mais reconhecível.

## Decisão
O repo mantém seu próprio log em `docs/adr/` (formato MADR 4.0 minimal, arquivos `adr-NNNN-slug.md`, numeração sequencial). O produto fica inalterado: consumidores continuam recebendo `docs/decisions/`.

## Consequências
Divergência nominal repo×produto, aceita por YAGNI. Trigger de revisão: na próxima mudança em `domains/protocol/adr.py`, decidir se o produto migra para `docs/adr/` (exigiria fallback para projetos existentes). Índice em `docs/adr/_index.md` é gerado por `gen_indexes.py`.
```

- [ ] **Step 2: Write `docs/adr/adr-0002-skills-e-templates-fora-de-src.md`**

```markdown
# ADR-0002 — `skills/` e `templates/` fora de `src/`, force-included no wheel

- Status: aceito
- Data: 2026-06-11
- Origem: ARCHITECTURE.md ("Por que skills/ está fora de src/", pré-existente; formalizado nesta data)

## Contexto
Skills e templates são conteúdo (Markdown/TOML), não código Python. Contribuir uma skill não deve exigir entender o pacote. Ao mesmo tempo, o wheel precisa carregá-los para `prumo init` funcionar em instalação não-editável.

## Decisão
`skills/` e `templates/` vivem na raiz do repo. O pyproject força a inclusão no wheel (`skills/` → `prumo_assist/_skills`, `templates/` → `prumo_assist/_templates`). `core/paths.resolve_resource` é o único resolvedor, funcionando em modo instalado, editável e worktree.

## Consequências
Mover/renomear qualquer um dos dois diretórios exige atualizar pyproject (force-include) E `core/paths.py` na mesma mudança. PRs de conteúdo não tocam Python.
```

- [ ] **Step 3: Write `docs/adr/adr-0003-skill-md-unica-fonte-de-metadata.md`**

```markdown
# ADR-0003 — SKILL.md é a única fonte de metadata por skill

- Status: aceito
- Data: 2026-06-11
- Origem: docstring de `core/skills.py` (pré-existente; formalizado nesta data); [[constitution#III · Skills universais]]

## Contexto
Hosts diferentes (Claude Code, Cursor, Codex, Gemini) consomem `name`/`description` do frontmatter. Um manifest paralelo duplicaria metadata e envelheceria em silêncio.

## Decisão
Todo metadata de skill mora no frontmatter do `SKILL.md`: `name`/`description` universais no topo, e o resto sob o namespace `prumo:` (version, schema, determinism, agent_compat, cost_estimate, guidelines_reviewed, inputs). Parser: `core/skills.py:parse_skill_file`, com modo strict (CI) e tolerante (`prumo init`). Campos desconhecidos preservados em `extra` (forward-compat).

## Consequências
Sem `manifest.yaml`. Catálogos (README, router `start`, `_index`) são derivados do registry via `gen_indexes.py` — nunca mantidos à mão (Princípio VII).
```

- [ ] **Step 4: Write `docs/adr/adr-0004-pacote-livre-de-llm.md`**

```markdown
# ADR-0004 — O pacote Python é 100% livre de LLM

- Status: aceito
- Data: 2026-06-11
- Origem: [[constitution#II · Determinístico antes de agêntico]] (pré-existente; formalizado nesta data)

## Contexto
Reprodutibilidade e auditoria de pesquisa clínica exigem que operações repetíveis não dependam de um modelo. Custo e latência de LLM são desperdício quando regex/AST/subprocess resolvem.

## Decisão
`src/prumo_assist/` nunca chama um LLM. A metade agêntica vive nos skills (`skills/*/SKILL.md`), que delegam todo trabalho determinístico de volta ao pacote (CLI `prumo` ou `uv run python -c` importando `prumo_assist.domains.*`). Cada domínio documenta no docstring qual skill é seu par agêntico.

## Consequências
Skill agêntica que poderia ser determinística é candidata a refator para `domains/`. Os contratos entre as duas metades (YAML de notas, blocos delimitados, schemas) são load-bearing e mudam só de forma coordenada.
```

- [ ] **Step 5: Write `docs/adr/adr-0005-layering-core-domains.md`**

```markdown
# ADR-0005 — Layering: core ← domains ← fachadas finas

- Status: aceito
- Data: 2026-06-11
- Origem: ARCHITECTURE.md ("Por que core/ e domains/ são separados", pré-existente; formalizado nesta data); [[constitution#I · Lógica em um lugar só]]

## Contexto
É preciso poder arrancar um domínio inteiro (spin-off) sem quebrar a fundação, e testar `core/` sem dependências externas instaladas.

## Decisão
`core/` nunca importa de `domains/`; `domains/` importam `core/`; domínios são mutuamente independentes (única exceção: `write` → `protocol`, com ImportError guard em `compose.py`). CLI raiz e `domains/<X>/cli.py` são fachadas finas (`cli_run` + chamada + saída); `domains/<X>/api.py` é re-export puro.

## Consequências
Lógica nova entra em `domains/<X>/<op>.py` com teste espelhado em `tests/unit/<X>/`. Violações de camada são defeito de revisão. Exceções de camada novas exigem justificativa explícita (e idealmente um ADR).
```

- [ ] **Step 6: Write `docs/adr/adr-0006-schemas-forward-only.md`**

```markdown
# ADR-0006 — Schemas versionados forward-only

- Status: aceito
- Data: 2026-06-11
- Origem: [[constitution#IV · Forward-only schemas]] (pré-existente; formalizado nesta data)

## Contexto
Outputs gerados (callouts, PICOT, disclosure, session logs) precisam permanecer legíveis por anos — um projeto de pesquisa clínica é auditável muito depois do release que o gerou.

## Decisão
Cada domínio versiona seus contratos em `domains/<X>/schemas/v1.py` (Pydantic, campo `schema_version` Literal). Evolução é aditiva: campos só entram, nunca saem ou mudam de nome entre minors; `vN+1` lê outputs `vN`. Remoção/renome só em major com "⚠ Breaking".

## Consequências
Mudança de schema vem com teste que valida output antigo no parser novo. Schemas são citados por nome/versão (`PaperCallout/v1`) no frontmatter das skills (`prumo.schema`).
```

- [ ] **Step 7: Write `docs/adr/adr-0007-zotero-stdlib-urllib.md`**

```markdown
# ADR-0007 — Zotero/BBT via stdlib urllib, endpoint 127.0.0.1:23119

- Status: aceito
- Data: 2026-06-11
- Origem: docstrings de `domains/paper/zotero.py` (pré-existente; formalizado nesta data)

## Contexto
A integração Zotero usa a API local do Better BibTeX. Adicionar `requests`/`httpx` traria uma dependência inteira para meia dúzia de chamadas HTTP locais.

## Decisão
Todas as chamadas Zotero/BBT usam `urllib` da stdlib. O endpoint default é `http://127.0.0.1:23119` (IP literal, não `localhost`, para evitar surpresas de resolução IPv6), com override via env `PRUMO_ZOTERO_BASE`.

## Consequências
Helpers HTTP próprios e mensagens de erro acionáveis ("abra o Zotero..."). Dívida conhecida: `write/export.py` hardcoda o endpoint e ignora o env var — corrigir quando aquele módulo for tocado (não justifica release próprio).
```

- [ ] **Step 8: Commit**

```bash
git add docs/adr/
git commit -m "docs(adr): ADRs 0001-0007 — log próprio + decisões estruturais formalizadas"
```

---

### Task 5: ADRs 0008–0014

**Files:**
- Create: `docs/adr/adr-0008-layout-alfa-de-notas.md` … `docs/adr/adr-0014-findings-canonico.md`

- [ ] **Step 1: Write `docs/adr/adr-0008-layout-alfa-de-notas.md`**

```markdown
# ADR-0008 — Layout α para notas de referência

- Status: aceito
- Data: 2026-06-11
- Origem: [[2026-05-03-zotero-notes-integration-design]] (pré-existente; formalizado nesta data)

## Contexto
O layout flat (`references/notes/<citekey>.md`) não comporta múltiplos artefatos por paper (metadata, extração, anotações, notas-filhas do Zotero) sem conflito de ownership humano/máquina.

## Decisão
Cada citekey vira pasta: `references/notes/<citekey>/{_meta.md, _extract.md, _annotations.md, note__<itemKey>__<slug>.md}`. `core/note_paths.py` é a única autoridade de caminhos; o layout flat legado continua legível durante a transição; `prumo paper migrate-layout` converte preservando histórico via `git mv`.

## Consequências
Todo código novo usa `note_paths`; lugares que ainda globam o layout flat (ex.: `wiki/stats.py`) são dívida conhecida. O merge de YAML em `paper/sync.py` define ownership por campo (metadata = máquina, curadoria = humano).
```

- [ ] **Step 2: Write `docs/adr/adr-0009-blocos-delimitados.md`**

```markdown
# ADR-0009 — Blocos delimitados HTML-comment como contrato humano/máquina

- Status: aceito
- Data: 2026-06-11
- Origem: padrão transversal em `paper/callout.py`, `protocol/propagate.py`, `write/compose.py`, `paper/zotero.py` (pré-existente; formalizado nesta data)

## Contexto
Artefatos Markdown são editados por humanos E regenerados por máquina. Sem fronteira explícita, cada regeneração destruiria curadoria humana.

## Decisão
Toda região machine-owned dentro de Markdown humano é delimitada por comentários HTML pareados (`<!-- x:begin ... -->` / `<!-- x:end -->`), opcionalmente com hash/versão no marcador para detectar staleness (`picot:begin v=N hash=sha8`). A máquina só reescreve dentro do bloco; o humano só escreve fora.

## Consequências
Regeneração idempotente e diffs limpos. O padrão se estende aos índices gerados deste repo (`prumo:skills-table`, `prumo:kb-index` etc. via `gen_indexes.py`). Delimitador corrompido é erro reportável, nunca "best effort".
```

- [ ] **Step 3: Write `docs/adr/adr-0010-plugin-root-na-raiz.md`**

```markdown
# ADR-0010 — Plugin root = raiz do repo; marketplace self-hosting; schemas vivos do validador

- Status: aceito
- Data: 2026-06-11
- Origem: `.claude-plugin/` + `.github/schemas/` (pré-existente; formalizado nesta data)

## Contexto
O Claude Code descobre skills em `skills/<nome>/SKILL.md`, agents em `agents/*.md` e MCP em `.mcp.json` relativos ao plugin root. O validador oficial de manifests é opaco (a lição da 0.1.1: `repository` deve ser string, não objeto).

## Decisão
O repo é o próprio marketplace (`marketplace.json` com `source: "./"`), com plugin root = raiz. Zero overrides de path no `plugin.json`. O conhecimento reverso do validador vive em `.github/schemas/*.schema.json` ("referência viva"), aplicado por `validate_manifests.py` no CI.

## Consequências
`skills/`, `.mcp.json` e `.claude-plugin/` são imóveis — mover quebraria todos os consumidores instalados. Os schemas em `.github/schemas/` devem ser preservados em qualquer reorganização e atualizados quando o validador oficial mudar de comportamento.
```

- [ ] **Step 4: Write `docs/adr/adr-0011-semver-por-visibilidade.md`**

```markdown
# ADR-0011 — SemVer por visibilidade ao consumidor; deferrals com trigger

- Status: aceito
- Data: 2026-06-11
- Origem: RELEASING.md + ROADMAP.md "Decisões deliberadas postergadas" (pré-existente; formalizado nesta data)

## Contexto
Num plugin, "breaking" é o que muda o que o usuário invoca — não o tamanho do diff. Releases ruidosos treinam o consumidor a ignorá-los.

## Decisão
Bump guiado pela interface pública do plugin (regra-mãe do RELEASING.md). Mudanças em `.github/`, README, CHANGELOG, `.gitignore` e `docs/` são não-releasáveis. Pré-1.0, breaking vai em MINOR com "⚠ Breaking". Cada adição postergada (hooks, cache LLM, lockfile, multi-host, packs, MkDocs) tem trigger concreto registrado no ROADMAP — sem trigger, não entra (Princípio VI).

## Consequências
Reorganizações de repo (como a de 2026-06-11) não geram release. A lista de deferrals do ROADMAP funciona como mini-ADRs de adiamento; promover um deferral a feature exige citar o trigger atingido.
```

- [ ] **Step 5: Write `docs/adr/adr-0012-remocao-agents-ml.md`**

```markdown
# ADR-0012 — Remoção dos agents ML pré-pivot

- Status: aceito
- Data: 2026-06-11
- Origem: [[2026-06-11-repo-organization-redesign-design]] (D8)

## Contexto
`agents/ml-theory-expert.md` e `agents/stack-docs-researcher.md` vêm do monorepo de ML anterior ao pivot clínico. O primeiro depende de `./theory/knowledge/` que não existe em nenhum lugar (quebrado como distribuído); o segundo allowlista tools host-específicas ausentes do Claude Code puro. A descrição do marketplace promete "agents para pesquisa clínica" — nenhum dos dois é isso, e nenhum dos 14 skills os usa.

## Decisão
Remover ambos no release v0.62.0 (MINOR com "⚠ Breaking"). Conteúdo preservado no histórico git (mesmo precedente das skills removidas na 0.3.0). O diretório `agents/` deixa de existir até haver agents alinhados ao propósito clínico.

## Consequências
Consumidores perdem dois agents que provavelmente nunca funcionaram como distribuídos. Agent futuro deve: servir o fluxo clínico, funcionar standalone (sem diretórios externos fantasma) e allowlistar apenas tools universais.
```

- [ ] **Step 6: Write `docs/adr/adr-0013-pdf-via-read-nativo.md`**

```markdown
# ADR-0013 — PDFs lidos com a tool Read nativa; sem MCP pdf-reader

- Status: aceito
- Data: 2026-06-11
- Origem: [[2026-06-11-repo-organization-redesign-design]] (D9)

## Contexto
`mcp__pdf-reader__read_pdf` era referenciado por 2 skills e 2 agents, mas nunca foi declarado em `.mcp.json` nem documentado como pré-requisito — consumidores sem um servidor global tinham falha silenciosa. O Read nativo do Claude Code lê PDF diretamente (com seleção de páginas).

## Decisão
Remover todas as referências ao MCP pdf-reader. Skills instruem a leitura de PDF com a tool `Read` (em blocos de páginas quando o PDF é longo).

## Consequências
Um pré-requisito externo a menos; `prumo doctor` continua cobrindo apenas qmd e Zotero. Se um host futuro do plugin não ler PDF nativamente, reavaliar aqui (novo ADR), nunca reintroduzindo dependência não-declarada.
```

- [ ] **Step 7: Write `docs/adr/adr-0014-findings-canonico.md`**

```markdown
# ADR-0014 — Caminho canônico de findings: `docs/wiki/findings/` com fallback

- Status: aceito
- Data: 2026-06-11
- Origem: [[2026-06-11-repo-organization-redesign-design]] (D10); `domains/wiki/findings.py:_resolve_findings_dir`

## Contexto
A prosa das skills divergia: `active-learning` dizia `docs/wiki/findings/`; `paper-extract`, `peer-review`, `wiki-query` e `wiki-lint` diziam `docs/findings/`. O resolver real prefere `docs/wiki/findings/` quando `docs/wiki/` existe e cai para `docs/findings/` caso contrário — ou seja, toda prosa estava condicionalmente errada.

## Decisão
O comportamento do resolver é o canônico: `docs/wiki/findings/` (preferido), `docs/findings/` (fallback em projetos sem `docs/wiki/`). A prosa de todas as skills descreve exatamente isso. Nenhuma mudança de código em `src/`.

## Consequências
Skills param de contradizer o runtime. Mudar a preferência do resolver no futuro exige novo ADR + atualização coordenada da prosa de todas as skills que citam findings.
```

- [ ] **Step 8: Commit**

```bash
git add docs/adr/
git commit -m "docs(adr): ADRs 0008-0014 — layout α, blocos delimitados, plugin root, semver, decisões novas"
```

---

### Task 6: Emenda da constitution → v1.1.0

**Files:**
- Modify: `docs/constitution.md`

- [ ] **Step 1: Substituir o comentário "Sync impact report" (linhas 1–30)**

Edit `docs/constitution.md` — substituir o bloco `<!-- Sync impact report: ... -->` inteiro (da linha 1 até `-->`) por:

```markdown
<!--
Sync impact report:
  Version: 1.1.0 (2026-06-11) — emenda via PR chore/repo-organization-redesign
  Anterior: 1.0.0 (2026-05-03)

  Added principles:
    - VII. Artefatos derivados são gerados

  Changed:
    - IV: referência a "schemas/migrations.py" corrigida para "migração explícita
      por domínio (domains/<X>/schemas/)" — o arquivo único nunca existiu (clarificação).
    - Governança: registrado o ADR log do repo (docs/adr/, MADR minimal) como
      registro de decisões pontuais; princípios continuam morando aqui.

  Templates ou docs a alinhar:
    - ARCHITECTURE.md   ✅ deixou de duplicar princípios; aponta pra cá (2026-06-11)
    - ROADMAP.md        ✅ deferrals espelhados em [[adr/adr-0011-semver-por-visibilidade]]
    - RELEASING.md      ✅ alinhado; fluxo PR-based registrado
    - CLAUDE.md (raiz)  ✅ aponta constitution + docs/adr/ como fontes de verdade

  Follow-up TODOs (1.0.0) — encerrados:
    - "Atualizar templates/pj_base/CLAUDE.md pra refletir o catálogo pós-0.3.0"
      → resolvido pela simplificação do pj_base (v0.61.0, spec 2026-05-30).
-->
```

- [ ] **Step 2: Corrigir o Princípio IV (referência a arquivo inexistente)**

Edit — substituir:

```markdown
- `vN+1` lê outputs gerados por `vN`. Campos novos são opcionais com default ou são preenchidos por migração explícita em `schemas/migrations.py`.
```

por:

```markdown
- `vN+1` lê outputs gerados por `vN`. Campos novos são opcionais com default ou são preenchidos por migração explícita por domínio (`domains/<X>/schemas/`).
```

- [ ] **Step 3: Adicionar o Princípio VII (após o bloco do princípio VI, antes de `## Restrições de Tecnologia`)**

Inserir:

```markdown
### VII · Artefatos derivados são gerados

Todo artefato que deriva de uma fonte única DEVE ser produzido por script, nunca mantido à mão.

- Versão: `src/prumo_assist/_version.py` é a fonte; `.github/scripts/sync_manifest_version.py` propaga para `plugin.json`/`marketplace.json`. Editar versão num manifest à mão é defeito.
- Índices e catálogos (tabela de skills do README, router `start`, `docs/_index.md`, `docs/adr/_index.md`) derivam do registry (`core/skills.py`) e do filesystem via `.github/scripts/gen_indexes.py`, dentro de blocos delimitados (ADR-0009).
- O CI DEVE falhar quando um derivado está dessincronizado da fonte (`--check`).
- Metadata de skill segue o princípio III (frontmatter único); este princípio cobre o restante da cadeia derivada.
```

- [ ] **Step 4: Atualizar a Governança**

Edit — substituir:

```markdown
- Versão atual: **1.0.0** (2026-05-03).
```

por:

```markdown
- Decisões estruturais pontuais são registradas em `docs/adr/` (MADR minimal, `adr-NNNN-slug.md`, imutáveis após aceitas — revisão = ADR novo). Princípios (normas vivas) moram aqui; o que muda por emenda nunca mora num ADR.
- Versão atual: **1.1.0** (2026-06-11).
```

- [ ] **Step 5: Verificar e commitar**

Run: `grep -n "1.1.0\|VII" docs/constitution.md | head`
Expected: header com 1.1.0, princípio VII presente, governança citando docs/adr/.

```bash
git add docs/constitution.md
git commit -m "docs(constitution): emenda 1.1.0 — princípio VII (derivados gerados), ADR log, IV clarificado"
```

---

### Task 7: Reescrever ARCHITECTURE.md (what/where, 5 domínios)

**Files:**
- Modify: `ARCHITECTURE.md` (substituição completa)

- [ ] **Step 1: Write `ARCHITECTURE.md` (conteúdo completo)**

```markdown
# Architecture

> Documento de orientação para quem chega novo ao repo: **o quê** e **onde**. Os **porquês** moram em [`docs/constitution.md`](docs/constitution.md) (princípios) e [`docs/adr/`](docs/adr/) (decisões registradas). Status e fases em [`ROADMAP.md`](ROADMAP.md); histórico narrativo em [`CHANGELOG.md`](CHANGELOG.md).

## Tagline e escopo

> **prumo-assist** — Knowledge, bibliography & academic writing assistant for clinical research. Lives between Zotero, Obsidian, and your agent-host.

**É:** um assistente de pesquisa pra pesquisador clínico. Cobre gerir conhecimento (wiki), gerir bibliografia (Zotero ↔ notas), formalizar o protocolo (PICOT), capturar fontes e escrever (export Pandoc/Typst + revisão crítica).

**Não é:** uma IDE de código, um framework de modelagem, um runner de pipelines de dados.

## Princípios

Os princípios não-negociáveis (lógica em um lugar só, determinístico antes de agêntico, skills universais, forward-only schemas, provenance, YAGNI, derivados gerados) estão na [`docs/constitution.md`](docs/constitution.md) — fonte única, numeração romana I–VII, com processo formal de emenda. Este arquivo não os duplica.

## Cinco domínios + core

```
┌──────────────┐ ┌──────────────┐ ┌────────────┐ ┌──────────────┐ ┌──────────────┐
│ 📚 paper     │ │ 🧠 wiki      │ │ 📥 capture │ │ 🧪 protocol  │ │ ✍️ write      │
│ (Zotero+BBT) │ │ (Obsidian)   │ │ (router)   │ │ (PICOT+ADR)  │ │ (Pandoc/Typst)│
│              │ │              │ │            │ │              │ │              │
│ sync · graph │ │ lint · index │ │ capture    │ │ propagate    │ │ export       │
│ find · lint  │ │ stats        │ │ <input>    │ │ diff         │ │ compose      │
│ set-primary  │ │              │ │            │ │              │ │ list-styles  │
│ sync-pdfs    │ │              │ │            │ │              │ │ extract-     │
│ sync-        │ │              │ │            │ │              │ │   comments   │
│  annotations │ │              │ │            │ │              │ │ disclosure   │
│ sync-notes   │ │              │ │            │ │              │ │ list-        │
│ sync-all     │ │              │ │            │ │              │ │   templates  │
│ migrate-     │ │              │ │            │ │              │ │              │
│  layout      │ │              │ │            │ │              │ │              │
└──────┬───────┘ └──────┬───────┘ └─────┬──────┘ └──────┬───────┘ └──────┬───────┘
       └────────────────┴───────────────┼────────────────┴────────────────┘
                                 ┌──────▼──────┐
                                 │   prumo     │  ← CLI (Typer); raiz: init ·
                                 │             │     doctor · skills · add · capture
                                 └──────┬──────┘
                                 ┌──────▼──────────────────────┐
                                 │ core/ (transversal)         │
                                 │ bib · csl · obsidian ·      │
                                 │ skills · paths · cli_op ·   │
                                 │ output · deps · note_paths ·│
                                 │ scaffold · config ·         │
                                 │ provenance*                 │
                                 └─────────────────────────────┘
```

\* `core/provenance.py` está desenhado mas ainda não ligado em todos os produtores — ver constitution V e ROADMAP.

## Layout do repositório

```
prumo-assist/
├── pyproject.toml             ← entry point: prumo = prumo_assist.cli:app;
│                                 force-include: templates/ e skills/ no wheel (ADR-0002)
├── CLAUDE.md / AGENTS.md      ← guia do repo pra agentes (AGENTS.md é symlink)
├── .claude/rules/             ← regras modulares (code, release)
├── ARCHITECTURE.md            ← este arquivo (what/where)
├── ROADMAP.md · CHANGELOG.md · RELEASING.md · README.md · CITATION.cff · LICENSE
│
├── .claude-plugin/            ← plugin.json + marketplace.json (self-hosting, ADR-0010)
├── .mcp.json                  ← MCP qmd — config do projeto E do plugin distribuído
├── .github/
│   ├── workflows/             ← ci.yml (lint+types+test+índices) · validate-manifests.yml
│   ├── schemas/               ← schemas vivos do validador de plugin (ADR-0010)
│   └── scripts/               ← sync_manifest_version.py · validate_manifests.py · gen_indexes.py
│
├── src/prumo_assist/
│   ├── _version.py            ← FONTE ÚNICA de versão (constitution VII)
│   ├── __init__.py            ← hierarquia de exceções (PrumoError, ...)
│   ├── api.py                 ← Python API pública (SemVer)
│   ├── cli.py                 ← Typer root: init · doctor · skills · add (+ capture)
│   ├── _filters/              ← filtros Lua vendorados do Pandoc (zotero_live_docx.lua)
│   ├── core/                  ← transversal; NUNCA importa domains/ (ADR-0005)
│   ├── domains/               ← paper · wiki · capture · protocol · write
│   │   └── <X>/               ← cli.py + api.py + <op>.py + schemas/v1.py (ADR-0006)
│   └── integrations/          ← adapters por agent-host (claude_code)
│
├── skills/                    ← 14 skills (SKILL.md = única metadata, ADR-0003)
├── templates/
│   ├── pj_base/               ← núcleo mínimo copiado por `prumo init`
│   └── modules/{clinical,ml}/ ← overlays opt-in (`prumo add`), self-describing (_module.toml)
│
├── tests/unit/                ← espelha domains/ 1:1
└── docs/                      ← vault Obsidian: constitution · adr/ · canvases ·
    └── superpowers/           ← specs/ (não-perecíveis) + plans/ + plans/archive/
```

## Como dados fluem (caso típico: extrair um paper)

```
/prumo-assist:paper-extract @smith2024
        ▼
Claude Code carrega skills/paper-extract/SKILL.md (instalada via plugin)
        ▼
A skill valida pré-requisitos (Bash), lê config (core/config.py),
despacha subagent que lê o PDF com a tool Read
        ▼
O JSON extraído é aplicado pelo backend determinístico
(domains/paper/callout.py) dentro do bloco delimitado (ADR-0009) em
references/notes/smith2024/_extract.md  — layout α (ADR-0008)
        ▼
_meta.md ganha extracted_at / extracted_template_hash (staleness por hash)
```

## Como contribuir

1. **Skill nova:** crie `skills/<nome>/SKILL.md` com frontmatter rico (`prumo:`); não precisa tocar Python. Rode `uv run python .github/scripts/gen_indexes.py` para atualizar os catálogos.
2. **Comando determinístico novo:** `domains/<X>/<op>.py` + exposição em `domains/<X>/cli.py` (via `cli_run`) + re-export em `domains/<X>/api.py` + teste em `tests/unit/<X>/test_<op>.py`.
3. **Host novo (Cursor, Codex, ...):** subclasse `BaseIntegration` em `integrations/<host>/installer.py`. Skills universais: zero mudança. (Trigger no ROADMAP, fase 3.0.)
4. **Decisão estrutural:** registre em `docs/adr/adr-NNNN-slug.md` e cite no PR.

## Glossário rápido

- **Skill** — capability agêntica empacotada como `SKILL.md` universal.
- **Integration** — adapter do formato canônico pro layout de um agent-host.
- **`pj_*`** — projeto de pesquisa do usuário; vault Obsidian + `.claude/` scaffoldado por `prumo init`.
- **Determinismo** — `agentic` | `deterministic` | `hybrid` (frontmatter `prumo.determinism`).
- **Layout α** — `references/notes/<citekey>/` com `_meta/_extract/_annotations/note__*` (ADR-0008).
- **Bloco delimitado** — região machine-owned `<!-- x:begin -->…<!-- x:end -->` (ADR-0009).
```

- [ ] **Step 2: Verificar links e commitar**

Run: `grep -c "adr-\|ADR-" ARCHITECTURE.md`
Expected: ≥ 8 (referências aos ADRs no lugar dos antigos "Por que...").

```bash
git add ARCHITECTURE.md
git commit -m "docs(architecture): reescrita what/where — 5 domínios, comandos reais, porquês via ADRs"
```

---

### Task 8: Lifecycle dos plans + spec superseded (Fase 3, parte 1)

**Files:**
- Create: `docs/superpowers/plans/archive/` (via git mv)
- Modify: frontmatter de 12 plans + 1 spec

- [ ] **Step 1: Adicionar frontmatter aos 9 plans rastreados e mover para archive/**

Mapeamento plan → release (conferido contra o CHANGELOG):

| Plan | release |
|---|---|
| 2026-05-03-zotero-notes-pr-n1-layout-migration.md | 0.4.0 |
| 2026-05-03-active-learning-implementation.md | 0.5.0 |
| 2026-05-03-formulate-picot-implementation.md | 0.5.0 |
| 2026-05-03-write-family-implementation.md | 0.5.0 |
| 2026-05-30-clinical-guidelines-refresh.md | 0.61.0 |
| 2026-05-30-guideline-staleness-doctor.md | 0.61.0 |
| 2026-05-30-pj-base-simplification.md | 0.61.0 |
| 2026-05-30-wiki-lint-deterministic-checks.md | 0.61.0 |
| 2026-05-30-write-disclosure.md | 0.61.0 |

```bash
mkdir -p docs/superpowers/plans/archive
cd docs/superpowers/plans
for spec in \
  "2026-05-03-zotero-notes-pr-n1-layout-migration.md:0.4.0" \
  "2026-05-03-active-learning-implementation.md:0.5.0" \
  "2026-05-03-formulate-picot-implementation.md:0.5.0" \
  "2026-05-03-write-family-implementation.md:0.5.0" \
  "2026-05-30-clinical-guidelines-refresh.md:0.61.0" \
  "2026-05-30-guideline-staleness-doctor.md:0.61.0" \
  "2026-05-30-pj-base-simplification.md:0.61.0" \
  "2026-05-30-wiki-lint-deterministic-checks.md:0.61.0" \
  "2026-05-30-write-disclosure.md:0.61.0"; do
  f="${spec%%:*}"; rel="${spec##*:}"
  printf -- '---\nstatus: implemented\nverified: 2026-06-11\nrelease: "%s"\n---\n\n' "$rel" | cat - "$f" > "$f.tmp" && mv "$f.tmp" "$f"
  git mv "$f" "archive/$f" 2>/dev/null || { git add "$f"; git mv "$f" "archive/$f"; }
done
cd ../../..
```

- [ ] **Step 2: Adicionar os 3 plans untracked já com frontmatter, direto em archive/**

```bash
cd docs/superpowers/plans
for f in 2026-05-30-external-deps-doctor-and-docs.md 2026-05-30-harden-zotero-client.md 2026-05-30-sync-notes-and-sync-all.md; do
  printf -- '---\nstatus: implemented\nverified: 2026-06-11\nrelease: "0.61.0"\n---\n\n' | cat - "$f" > "$f.tmp" && mv "$f.tmp" "$f"
  mv "$f" "archive/$f"
done
cd ../../..
git add docs/superpowers/plans/archive/
```

- [ ] **Step 3: Marcar o spec de 2026-04-29 como superseded**

O arquivo `docs/superpowers/specs/2026-04-29-prumo-scientific-writer-design.md` não tem frontmatter — prepender:

```yaml
---
title: prumo scientific writer — design original
date: 2026-04-29
status: superseded
superseded-by: "[[2026-05-03-write-family-design]]"
tags: [write, superseded]
---
```

```bash
cd docs/superpowers/specs
printf -- '---\ntitle: prumo scientific writer — design original\ndate: 2026-04-29\nstatus: superseded\nsuperseded-by: "[[2026-05-03-write-family-design]]"\ntags: [write, superseded]\n---\n\n' | cat - 2026-04-29-prumo-scientific-writer-design.md > tmp && mv tmp 2026-04-29-prumo-scientific-writer-design.md
cd ../../..
```

- [ ] **Step 4: Verificar**

Run: `ls docs/superpowers/plans/ docs/superpowers/plans/archive/ && head -6 docs/superpowers/plans/archive/2026-05-30-pj-base-simplification.md`
Expected: `plans/` contém apenas `archive/` e o plano ativo desta reorganização (`2026-06-11-repo-organization-redesign.md`); `archive/` contém 12 arquivos; o head mostra o frontmatter `status: implemented`.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/
git commit -m "docs(plans): lifecycle — frontmatter status/verified/release + archive/ (12 plans); spec 2026-04-29 superseded"
```

---

### Task 9: `gen_indexes.py` — TDD do gerador de índices

**Files:**
- Create: `.github/scripts/gen_indexes.py`
- Test: `tests/unit/test_gen_indexes.py`

- [ ] **Step 1: Write the failing test (`tests/unit/test_gen_indexes.py`)**

```python
"""Testa o gerador de índices (.github/scripts/gen_indexes.py).

O script é carregado via importlib (vive fora de src/). Testa as funções puras
de renderização/substituição e o contrato --check contra o repo real.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "gen_indexes.py"


@pytest.fixture(scope="module")
def gen() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_indexes", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_replace_block_substitui_apenas_o_miolo(gen: ModuleType) -> None:
    text = "antes\n<!-- prumo:x:begin -->\nvelho\n<!-- prumo:x:end -->\ndepois\n"
    out = gen.replace_block(text, "x", "novo")
    assert "velho" not in out
    assert "novo" in out
    assert out.startswith("antes\n") and out.endswith("depois\n")


def test_replace_block_eh_idempotente(gen: ModuleType) -> None:
    text = "<!-- prumo:x:begin -->\na\n<!-- prumo:x:end -->\n"
    once = gen.replace_block(text, "x", "corpo")
    twice = gen.replace_block(once, "x", "corpo")
    assert once == twice


def test_replace_block_falha_sem_marcadores(gen: ModuleType) -> None:
    with pytest.raises(SystemExit):
        gen.replace_block("sem marcadores", "x", "corpo")


def test_skills_table_cobre_o_registry_inteiro(gen: ModuleType) -> None:
    table = gen.render_skills_table()
    assert "`/prumo-assist:start`" in table
    assert "`/prumo-assist:paper-extract`" in table
    # uma linha por skill + 2 de cabeçalho
    n_skills = len(list((gen.REPO / "skills").glob("*/SKILL.md")))
    assert table.count("\n") + 1 == n_skills + 2


def test_adr_index_lista_todos_os_adrs(gen: ModuleType) -> None:
    body = gen.render_adr_index()
    n_adrs = len(list((gen.REPO / "docs" / "adr").glob("adr-*.md")))
    assert n_adrs >= 14
    assert body.count("[[adr/adr-") == n_adrs
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_gen_indexes.py -v`
Expected: ERROS de coleta/fixture — o arquivo `.github/scripts/gen_indexes.py` não existe.

- [ ] **Step 3: Write `.github/scripts/gen_indexes.py`**

```python
"""Regenera os blocos delimitados de índice a partir das fontes únicas.

Fontes (constitution, princípio VII):
- skills/<nome>/SKILL.md  → tabela do README + catálogo do router `start`
- docs/superpowers/{specs,plans,plans/archive}/*.md (frontmatter) → docs/_index.md
- docs/adr/adr-*.md → docs/adr/_index.md

Uso:
    uv run python .github/scripts/gen_indexes.py          # reescreve os blocos
    uv run python .github/scripts/gen_indexes.py --check  # exit 1 se algo está stale (CI)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from prumo_assist.core.skills import load_skill_registry  # noqa: E402

_FRONT_RE = re.compile(r"\A---\n(.*?)\n---", re.DOTALL)


def replace_block(text: str, tag: str, body: str) -> str:
    """Substitui o miolo entre os marcadores `prumo:<tag>` preservando o resto."""
    begin = f"<!-- prumo:{tag}:begin -->"
    end = f"<!-- prumo:{tag}:end -->"
    pattern = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(text):
        raise SystemExit(f"gen_indexes: marcadores 'prumo:{tag}' não encontrados.")
    return pattern.sub(begin + "\n" + body.strip() + "\n" + end, text)


def _front_field(path: Path, field: str) -> str:
    match = _FRONT_RE.match(path.read_text(encoding="utf-8"))
    if not match:
        return "—"
    found = re.search(rf"^{field}:\s*(.+)$", match.group(1), re.MULTILINE)
    return found.group(1).strip().strip('"') if found else "—"


def render_skills_table() -> str:
    registry, _ = load_skill_registry(REPO / "skills", strict=True)
    lines = ["| Skill | Uso |", "|---|---|"]
    for name in registry.names():
        desc = " ".join(registry.get(name).description.split())
        lines.append(f"| `/prumo-assist:{name}` | {desc} |")
    return "\n".join(lines)


def render_skills_catalog() -> str:
    registry, _ = load_skill_registry(REPO / "skills", strict=True)
    lines = []
    for name in registry.names():
        desc = " ".join(registry.get(name).description.split())
        lines.append(f"- `/prumo-assist:{name}` — {desc}")
    return "\n".join(lines)


def render_kb_index() -> str:
    sp = REPO / "docs" / "superpowers"
    lines = ["**Specs** (não-perecíveis):", ""]
    for p in sorted((sp / "specs").glob("*.md")):
        lines.append(f"- [[superpowers/specs/{p.stem}]] · {_front_field(p, 'status')}")
    lines += ["", "**Plans ativos:**", ""]
    active = sorted((sp / "plans").glob("*.md"))
    if active:
        lines += [f"- [[superpowers/plans/{p.stem}]] · {_front_field(p, 'status')}" for p in active]
    else:
        lines.append("- (nenhum)")
    archived = sorted((sp / "plans" / "archive").glob("*.md"))
    lines += ["", f"**Plans arquivados:** {len(archived)} em `superpowers/plans/archive/`", ""]
    lines += ["**ADRs:** ver [[adr/_index|índice de ADRs]]"]
    return "\n".join(lines)


def render_adr_index() -> str:
    lines = []
    for p in sorted((REPO / "docs" / "adr").glob("adr-*.md")):
        text = p.read_text(encoding="utf-8")
        h1 = next(
            (ln.removeprefix("# ").strip() for ln in text.splitlines() if ln.startswith("# ")),
            p.stem,
        )
        status_m = re.search(r"^- Status:\s*(.+)$", text, re.MULTILINE)
        status = status_m.group(1).strip() if status_m else "—"
        title = h1.split("—", 1)[1].strip() if "—" in h1 else h1
        lines.append(f"- [[adr/{p.stem}]] — {title} · {status}")
    return "\n".join(lines)


def _targets() -> list[tuple[Path, str, str]]:
    return [
        (REPO / "README.md", "skills-table", render_skills_table()),
        (REPO / "skills" / "start" / "SKILL.md", "skills-catalog", render_skills_catalog()),
        (REPO / "docs" / "_index.md", "kb-index", render_kb_index()),
        (REPO / "docs" / "adr" / "_index.md", "adr-index", render_adr_index()),
    ]


def main() -> int:
    check = "--check" in sys.argv
    stale: list[str] = []
    for path, tag, body in _targets():
        old = path.read_text(encoding="utf-8")
        new = replace_block(old, tag, body)
        if new != old:
            if check:
                stale.append(str(path.relative_to(REPO)))
            else:
                path.write_text(new, encoding="utf-8")
                print(f"gen_indexes: atualizado {path.relative_to(REPO)}")
    if check and stale:
        print("gen_indexes --check: índices dessincronizados:", ", ".join(stale))
        print("Rode: uv run python .github/scripts/gen_indexes.py")
        return 1
    if check:
        print("gen_indexes --check: tudo em dia.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Rodar os testes de função pura (os de filesystem ainda dependem da Task 10)**

Run: `uv run pytest tests/unit/test_gen_indexes.py -v -k "replace_block or skills_table"`
Expected: PASS nos 4 (replace_block ×3 + skills_table; o registry real já existe).

`test_adr_index_lista_todos_os_adrs` também já passa (Task 4/5 criou os 14 ADRs). Confirmar:

Run: `uv run pytest tests/unit/test_gen_indexes.py -v`
Expected: PASS em todos os 6.

- [ ] **Step 5: Gates de qualidade**

Run: `uv run ruff check .github/scripts/gen_indexes.py tests/unit/test_gen_indexes.py && uv run ruff format --check .github/scripts/gen_indexes.py tests/unit/test_gen_indexes.py && uv run mypy`
Expected: tudo verde (se `ruff format --check` reclamar, rodar `uv run ruff format` nos dois arquivos e re-checar).

- [ ] **Step 6: Commit**

```bash
git add .github/scripts/gen_indexes.py tests/unit/test_gen_indexes.py
git commit -m "feat(infra): gen_indexes.py — índices gerados de fonte única, com --check pra CI"
```

---

### Task 10: Inserir marcadores, regenerar índices e wirear o CI

**Files:**
- Modify: `README.md`, `skills/start/SKILL.md`, `docs/_index.md`
- Create: `docs/adr/_index.md`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Envolver a tabela de skills do README em marcadores**

Edit `README.md` — substituir o bloco inteiro da tabela (da linha `| Skill | Uso |` até a linha `| `/prumo-assist:write-scientific` | ... |`, inclusive) por:

```markdown
<!-- prumo:skills-table:begin -->
<!-- prumo:skills-table:end -->
```

(O conteúdo será regenerado no Step 5 a partir do registry — a tabela atual omite `start` e diverge das descriptions do frontmatter.)

- [ ] **Step 2: Adicionar o catálogo gerado ao router `start`**

Edit `skills/start/SKILL.md` — adicionar ao FINAL do arquivo (após a linha `Comece perguntando: ...`):

```markdown

## Catálogo completo (gerado — não editar à mão)

<!-- prumo:skills-catalog:begin -->
<!-- prumo:skills-catalog:end -->
```

- [ ] **Step 3: Adicionar o bloco de catálogo vivo ao `docs/_index.md`**

Edit `docs/_index.md`:

(a) substituir a linha:

```markdown
- `superpowers/specs/` — specs vivas de design de skills (não-perecíveis).
```

por:

```markdown
- `superpowers/specs/` — specs vivas de design (não-perecíveis; `status: approved | superseded`).
- `superpowers/plans/` — planos ativos; implementados movem pra `plans/archive/` com `status/verified/release`.
- `adr/` — decisões registradas (MADR minimal, imutáveis). Índice: [[adr/_index]].
```

(b) substituir a linha da tabela "Por onde começar":

```markdown
| Quais são os princípios não-negociáveis do projeto? | [[constitution\|Constitution]] |
```

por:

```markdown
| Quais são os princípios não-negociáveis do projeto? | [[constitution\|Constitution]] |
| Por que essa decisão estrutural foi tomada? | [[adr/_index\|Índice de ADRs]] |
```

(c) adicionar ao FINAL do arquivo:

```markdown

## Catálogo vivo (gerado — não editar à mão)

<!-- prumo:kb-index:begin -->
<!-- prumo:kb-index:end -->
```

- [ ] **Step 4: Write `docs/adr/_index.md`**

```markdown
---
title: Índice de ADRs
tags: [adr, index]
---

# Decisões registradas (ADRs)

Formato [MADR 4.0](https://adr.github.io/madr/) minimal: Contexto / Decisão / Consequências. ADR aceito é imutável — revisão = ADR novo. Decisão estrutural nova em PR = ADR novo aqui.

<!-- prumo:adr-index:begin -->
<!-- prumo:adr-index:end -->
```

- [ ] **Step 5: Regenerar tudo e verificar**

```bash
uv run python .github/scripts/gen_indexes.py
uv run python .github/scripts/gen_indexes.py --check
```

Expected: primeira chamada imprime 4 linhas "atualizado ..."; segunda imprime "tudo em dia." e exit 0.

Run: `grep -c "prumo-assist:" README.md`
Expected: ≥ 14 (todas as skills, incluindo `start`).

- [ ] **Step 6: Wirear os checks no CI**

Edit `.github/workflows/ci.yml` — após o step `- name: Pytest` (último do job), adicionar:

```yaml
      - name: Índices gerados em dia (constitution VII)
        run: uv run python .github/scripts/gen_indexes.py --check

      - name: Versão sincronizada nos manifests
        run: uv run python .github/scripts/sync_manifest_version.py --check
```

- [ ] **Step 7: Testes + commit**

Run: `uv run pytest tests/unit/test_gen_indexes.py -v && uv run python .github/scripts/sync_manifest_version.py --check`
Expected: PASS em todos; sync --check verde (0.61.0 já está sincronizado).

```bash
git add README.md skills/start/SKILL.md docs/_index.md docs/adr/_index.md .github/workflows/ci.yml
git commit -m "feat(infra): blocos gerados nos 4 índices + checks de drift e versão no CI"
```

**Nota (trilha A vs B):** a regeneração do `skills/start/SKILL.md` altera conteúdo distribuído, mas só ADICIONA um catálogo (sem mudar trigger/fluxo) — entra no release v0.62.0 da trilha B como "Documentação". Não criar release só por isso.

---

### Task 11: Governança — ROADMAP, CITATION, CHANGELOG (rodapé), RELEASING, tags retroativas

**Files:**
- Modify: `ROADMAP.md`, `CITATION.cff`, `CHANGELOG.md`, `RELEASING.md`
- Create: git tags `v0.3.0`–`v0.61.0`

- [ ] **Step 1: Write `ROADMAP.md` (conteúdo completo)**

```markdown
# Roadmap

> Status atual + próximas fases. Layout em [`ARCHITECTURE.md`](ARCHITECTURE.md); princípios em [`docs/constitution.md`](docs/constitution.md); histórico narrativo em [`CHANGELOG.md`](CHANGELOG.md).

## Status (atualizado 2026-06-11)

| Release | Data | Conteúdo |
|---------|------|----------|
| 0.2.0 | 2026-04-28 | Fundação do CLI Python (core/ + Typer + domains paper/wiki/capture/write + peer-review + 97 testes) |
| 0.3.0 | 2026-05-03 | Spin-off das skills de código + simplificação interna + split ARCHITECTURE/ROADMAP |
| 0.4.0 | 2026-05-03 | Layout α de notas (`references/notes/<citekey>/`) + `paper migrate-layout` |
| 0.5.0 | 2026-05-04 | Domínio `protocol` (PICOT + ADRs) + família `write-*` + `formulate-picot` + `active-learning` |
| 0.6.0 | 2026-05-17 | Wizard interativo do `prumo init` |
| 0.61.0 | 2026-05-31 | Disclosure de IA, citações Word vivas (zotero_live_docx.lua), sync-notes/sync-all, doctor de deps externas, pj_base simplificado (módulos clinical/ml), wiki-lint determinístico, refresh de guidelines |
| — | 2026-06-11 | Reorganização do repo (CLAUDE.md, `docs/adr/`, lifecycle, índices gerados — não-releasável) |
| 0.62.0 | planejado | Remoção agents ML (ADR-0012) + pdf-reader → Read (ADR-0013) + contratos de skill reconciliados (ADR-0014) |

## Em curso

- `prumo-code-assist` ainda **não existe**. As skills `tabular-eda`, `data-cleaning`, `clinical-metrics` (removidas na v0.3.0) seguem acessíveis via histórico git. Mover quando o repo for criado.
- Agents `ml-theory-expert` e `stack-docs-researcher`: decisão tomada em [ADR-0012](docs/adr/adr-0012-remocao-agents-ml.md) — remoção no v0.62.0.

## Fases pós-MVP (cada uma justificada por dor real, **nunca antes**)

| Fase | Adição | Trigger |
|------|--------|---------|
| 2.1  | Pack `clinical-checklists` (TRIPOD+AI, CLAIM, CONSORT-AI, PRISMA, STROBE, SPIRIT) | Reportar resultados de modelo de predição |
| 2.2  | Pack `schematics` (CONSORT/PRISMA flow via Mermaid+TikZ) | Submissão de paper |
| 2.3  | Pack `venue-clinical` (NEJM, JAMA, Lancet, Nature Medicine, Radiology) | Submeter pra venue específico |
| 2.4  | Pack `thesis` (chapter-from-findings, snapshot, defense-summary) | Aproximação da defesa |
| 2.5  | `kg/` module (grafo de papers, paths de citação) | Wiki passar de 50+ papers |
| 3.0  | `integrations/{cursor,codex,gemini,jupyter}/` | Colega adotar host diferente |
| 3.1  | Hooks system (PII redaction, cost gates) | Houver ≥3 cross-cutting concerns |
| 3.2  | Eval gate em CI | Drift de prompt observado em prod |

## Decisões deliberadas postergadas

> Espelhadas em [ADR-0011](docs/adr/adr-0011-semver-por-visibilidade.md); promover qualquer item exige citar o trigger atingido.

- **Sem hooks system.** Trace e provenance são chamadas explícitas em `domains/`, não decoradores plugáveis. Quando ≥3 cross-cutting forem competir, refatora.
- **Sem cache de LLM.** Idempotência por hash do input fica para quando algum caller real precisar.
- **Sem lockfile.** Faz sentido quando packs externos virarem realidade.
- **Sem multi-host.** Um adapter (`claude_code`) prova a interface; expandir é trivial depois (não é refactor, é adição).
- **Sem packs externos.** Único pack hoje é o implícito da raiz (`skills/` na raiz). Estrutura `packs/<name>/` está prevista mas vazia.
- **Sem MkDocs publicado.** Documentação vive no repo em Markdown. Site só quando `prumo --version` justificar (volume de usuários externos).
- **Produto continua gerando `docs/decisions/`** nos `pj_*` enquanto o repo usa `docs/adr/` — alinhar na próxima mudança em `domains/protocol/adr.py` ([ADR-0001](docs/adr/adr-0001-adr-log-em-docs-adr.md)).
```

- [ ] **Step 2: Sincronizar CITATION.cff**

Edit `CITATION.cff` — substituir a última linha:

```yaml
version: 0.2.0-dev
```

por:

```yaml
version: 0.61.0
```

(O ORCID placeholder `0000-0000-0000-0000` permanece com o TODO — depende de dado que só o Raphael tem; o RELEASING passa a incluir o CITATION.cff no checklist.)

- [ ] **Step 3: Completar o rodapé do CHANGELOG**

Edit `CHANGELOG.md` — substituir o bloco final de refs:

```markdown
[Não publicado]: https://github.com/raphaelfh/prumo-assist/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/raphaelfh/prumo-assist/compare/v0.3.0...v0.4.0
```

por:

```markdown
[Não publicado]: https://github.com/raphaelfh/prumo-assist/compare/v0.61.0...HEAD
[0.61.0]: https://github.com/raphaelfh/prumo-assist/compare/v0.6.0...v0.61.0
[0.6.0]: https://github.com/raphaelfh/prumo-assist/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/raphaelfh/prumo-assist/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/raphaelfh/prumo-assist/compare/v0.3.0...v0.4.0
```

(As linhas `[0.3.0]`…`[0.1.0]` existentes permanecem.)

- [ ] **Step 4: Realinhar RELEASING.md ao fluxo real**

Edit `RELEASING.md` — substituir os steps 5–7 do "Processo de release":

```markdown
5. **Commit** com mensagem `release: X.Y.Z - <resumo>`:
   ```bash
   git add CHANGELOG.md .claude-plugin/plugin.json .claude-plugin/marketplace.json
   git commit -m "release: X.Y.Z - resumo curto"
   git push origin main
   ```
6. **Aguarde o CI passar** (workflow `validate-manifests`).
7. **Crie a tag e o release no GitHub:**
```

por:

```markdown
5. **Atualize também `CITATION.cff`** (campo `version`) no mesmo commit.
6. **Commit via branch de release + PR** (fluxo adotado desde a v0.61.0):
   ```bash
   git checkout -b release/vX.Y.Z
   git add CHANGELOG.md CITATION.cff src/prumo_assist/_version.py .claude-plugin/plugin.json .claude-plugin/marketplace.json
   git commit -m "release: X.Y.Z - resumo curto"
   git push -u origin release/vX.Y.Z
   gh pr create --title "release: vX.Y.Z" --fill
   ```
   Aguarde o CI (`CI` + `validate-manifests`) e faça o merge.
7. **Crie a tag e o release no GitHub (obrigatório — tags retroativas v0.3.0–v0.61.0 criadas em 2026-06-11):**
```

- [ ] **Step 5: Criar as tags retroativas**

```bash
git tag -a v0.3.0 c1acdfd -m "v0.3.0 (retroativa, 2026-06-11)"
git tag -a v0.4.0 6bf8b45 -m "v0.4.0 (retroativa, 2026-06-11)"
git tag -a v0.5.0 2ba0632 -m "v0.5.0 (retroativa, 2026-06-11)"
# 0.6.0 não tem commit "release:" — localizar pelo bump do manifest:
V060=$(git log --oneline -S'"version": "0.6.0"' -- .claude-plugin/plugin.json | tail -1 | cut -d' ' -f1)
echo "v0.6.0 -> $V060"  # conferir visualmente antes de taggear
git tag -a v0.6.0 "$V060" -m "v0.6.0 (retroativa, 2026-06-11)"
git tag -a v0.61.0 f755279 -m "v0.61.0 (retroativa, 2026-06-11)"
git push origin v0.3.0 v0.4.0 v0.5.0 v0.6.0 v0.61.0
```

Expected: `git tag -l` mostra v0.1.0–v0.61.0 completos.

- [ ] **Step 6: Commit**

```bash
git add ROADMAP.md CITATION.cff CHANGELOG.md RELEASING.md
git commit -m "docs(governanca): ROADMAP até 0.61.0, CITATION sync, rodapé do CHANGELOG, RELEASING PR-based"
```

---

### Task 12: Graphify — build, hook e seção no CLAUDE.md (Fase 4)

**Files:**
- Modify: `CLAUDE.md` (seção adicionada por `graphify claude install`)
- (gitignore de `graphify-out/` já feito na Task 1)

- [ ] **Step 1: Build inicial do grafo (passo agêntico)**

Invocar o skill `/graphify .` na raiz do repo (pipeline completo: código + docs + skills num grafo só). Ao final deve existir `graphify-out/graph.json` e `graphify-out/GRAPH_REPORT.md`.

Run: `test -f graphify-out/graph.json && echo OK`
Expected: `OK`

- [ ] **Step 2: Hook pós-commit (AST sem LLM)**

```bash
graphify hook install
graphify hook status
```

Expected: status reporta hook instalado.

- [ ] **Step 3: Seção graphify no CLAUDE.md**

```bash
graphify claude install
```

Expected: `CLAUDE.md` ganha uma seção `## graphify` instruindo consultar o grafo antes de responder perguntas de codebase.

- [ ] **Step 4: Verificar que nada do graphify vaza pro git**

Run: `git status --short | grep graphify || echo "limpo"`
Expected: `limpo` (apenas `M CLAUDE.md` aparece no status).

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): seção graphify — grafo local como camada de query do repo"
```

---

### Task 13: Fechar a trilha A — gates, PR e merge

- [ ] **Step 1: Gates completos**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run python .github/scripts/gen_indexes.py --check`
Expected: tudo verde (365+ testes). (`validate_manifests.py` não roda aqui: a trilha A não toca `.claude-plugin/`; ele roda na trilha B.)

- [ ] **Step 2: Marcar este plano como in-progress → será `implemented` no fim da trilha B**

Edit `docs/superpowers/plans/2026-06-11-repo-organization-redesign.md` frontmatter: `status: draft` → `status: in-progress`. Commit junto com o PR.

- [ ] **Step 3: PR da trilha A**

```bash
git push -u origin chore/repo-organization-redesign
gh pr create --title "chore: reorganização do repo — CLAUDE.md, ADRs, lifecycle, índices gerados" --body "$(cat <<'EOF'
Implementa a trilha A (não-releasável) do spec docs/superpowers/specs/2026-06-11-repo-organization-redesign-design.md:

- CLAUDE.md raiz + .claude/rules/ + AGENTS.md symlink (doutrina: curto + @imports)
- docs/adr/ com 14 ADRs (MADR 4.0 minimal) + constitution emendada → v1.1.0 (princípio VII)
- ARCHITECTURE.md reescrito (5 domínios, comandos reais, porquês via ADR)
- Lifecycle de plans: frontmatter + archive/ (12 planos); spec 2026-04-29 superseded
- gen_indexes.py + 4 índices gerados + checks no CI (drift + sync de versão)
- Governança: ROADMAP até 0.61.0, CITATION.cff, rodapé do CHANGELOG, RELEASING PR-based, tags retroativas
- Higiene: settings.json morto, gitignore, stubs; graphify (hook + seção no CLAUDE.md)

Não-releasável por política (RELEASING.md). Trilha B (release v0.62.0) segue em PR separado.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Aguardar CI verde e merge (gate humano)**

O merge é do Raphael. Trilha B só começa depois do merge na main.

---

# TRILHA B — release v0.62.0 (branch `release/v0.62.0`, criada da main pós-merge)

### Task 14: Remover os agents ML (ADR-0012)

**Files:**
- Delete: `agents/ml-theory-expert.md`, `agents/stack-docs-researcher.md`
- Modify: `README.md`

- [ ] **Step 1: Criar a branch a partir da main atualizada**

```bash
git checkout main && git pull
git checkout -b release/v0.62.0
```

- [ ] **Step 2: Remover os agents**

```bash
git rm agents/ml-theory-expert.md agents/stack-docs-researcher.md
```

(O diretório `agents/` desaparece — git não rastreia diretórios vazios. Auto-discovery do plugin passa a não encontrar agents, que é o estado correto.)

- [ ] **Step 3: Remover a seção Agents do README**

Edit `README.md` — deletar o bloco inteiro:

```markdown
### Agents

| Agent | Uso |
|---|---|
| `ml-theory-expert` | Fundamentação teórica (estatística/ML) com citações da base de conhecimento. |
| `stack-docs-researcher` | Consulta documentação atualizada da stack (scikit-learn, Lightning, albumentations, etc.). |
```

E na seção Instalação, substituir:

```markdown
Após a instalação, as skills aparecem com o prefixo `/prumo-assist:...` e os agents ficam disponíveis via `Agent` tool.
```

por:

```markdown
Após a instalação, as skills aparecem com o prefixo `/prumo-assist:...`.
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "feat!: remove agents ML pré-pivot (ml-theory-expert, stack-docs-researcher) — ADR-0012"
```

---

### Task 15: pdf-reader → Read nativo + conserto do paper-extract (ADR-0013, D11)

**Files:**
- Modify: `skills/wiki-ingest/SKILL.md`, `skills/paper-extract/SKILL.md`

- [ ] **Step 1: wiki-ingest — frontmatter e 2 menções**

Edit `skills/wiki-ingest/SKILL.md`:

(a) na linha 9, remover ` mcp__pdf-reader__read_pdf` do `allowed-tools` (mantendo o resto igual).

(b) substituir:

```markdown
| PDF local que não é paper acadêmico (relatório, white paper, slide deck) | Continuar nesta skill. Usar `mcp__pdf-reader__read_pdf` para extrair conteúdo. |
```

por:

```markdown
| PDF local que não é paper acadêmico (relatório, white paper, slide deck) | Continuar nesta skill. Ler com a tool `Read` (lê PDF nativamente; use o parâmetro de páginas se >10). |
```

(c) substituir:

```markdown
- `mcp__pdf-reader__read_pdf` para PDF local (páginas específicas se >10).
```

por:

```markdown
- Tool `Read` para PDF local (lê PDF nativamente; páginas específicas se >10).
```

- [ ] **Step 2: paper-extract — frontmatter, prompt do subagent e Read**

Edit `skills/paper-extract/SKILL.md`:

(a) na linha 9, remover ` mcp__pdf-reader__read_pdf` do `allowed-tools`.

(b) no prompt do subagent (linha 57), substituir:

```
     Leia o PDF em <absolute_path_to_pdf> usando mcp__pdf-reader__read_pdf.
```

por:

```
     Leia o PDF em <absolute_path_to_pdf> com a tool Read (lê PDF nativamente;
     leia em blocos de páginas se o PDF tiver >10 páginas).
```

- [ ] **Step 3: paper-extract — conserto do import de config (passo 2 da skill)**

Substituir:

````markdown
2. **Ler config:**
   ```bash
   python3 -c "import sys, json; sys.path.insert(0, '../.claude/scripts'); from _project_config import load_config; print(json.dumps(load_config(__import__('pathlib').Path('.'))))"
   ```
   Extrair `paper_extract.language`.
````

por:

````markdown
2. **Ler config:**
   ```bash
   uv run python -c "import json; from pathlib import Path; from prumo_assist.core.config import load_project_config; print(json.dumps(load_project_config(Path('.'))))"
   ```
   Extrair `paper_extract.language`.
````

- [ ] **Step 4: paper-extract — conserto do apply_extraction (passo 5 da skill, assinatura REAL)**

Substituir o bloco inteiro do passo 5:

````markdown
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
````

por:

````markdown
5. **Aplicar extração** via `Bash` (backend determinístico em `domains/paper/callout.py`):
   ```bash
   uv run python -c '
   import json
   from pathlib import Path
   from prumo_assist.domains.paper.callout import apply_extraction
   content = json.loads("""<JSON_AQUI>""")
   changed = apply_extraction(
       pj_path=Path("."),
       citekey="<citekey>",
       template_path=Path(".claude/paper_extraction.md"),
       content=content,
       model="<modelo_atual>",
       date="<hoje>",
   )
   print("MUDOU" if changed else "IDÊNTICO")
   '
   ```
````

- [ ] **Step 5: paper-extract — conserto do hint de restauração (Erros comuns)**

Substituir:

```markdown
- `paper_extraction.md` ausente → "Restaure do scaffold: `cp ../.claude/templates/pj_projeto/.claude/paper_extraction.md .claude/`"
```

por:

```markdown
- `paper_extraction.md` ausente → "Restaure rodando `prumo init --merge` no diretório do projeto (recoloca arquivos ausentes do template sem sobrescrever os existentes)."
```

- [ ] **Step 6: Verificar que não sobrou referência fantasma**

Run: `grep -rn "pdf-reader\|_project_config\|pj_projeto\|\.claude/scripts" skills/ && echo "FALHOU" || echo "limpo"`
Expected: `limpo`

- [ ] **Step 7: Commit**

```bash
git add skills/wiki-ingest/SKILL.md skills/paper-extract/SKILL.md
git commit -m "fix(skills): PDFs via Read nativo (ADR-0013) + paper-extract usa backends reais do pacote"
```

---

### Task 16: Findings canônico (ADR-0014) + namespacing `/prumo-assist:` (D11)

**Files:**
- Modify: `skills/paper-extract/SKILL.md`, `skills/peer-review/SKILL.md`, `skills/wiki-lint/SKILL.md`, `skills/wiki-query/SKILL.md` (findings)
- Modify: os 7 SKILL.md com slash-commands sem prefixo (namespacing)

- [ ] **Step 1: Findings — frase canônica**

A frase canônica (espelha `wiki/findings.py:_resolve_findings_dir`): **`docs/wiki/findings/` (ou `docs/findings/` em projetos sem `docs/wiki/`)**.

Substituições exatas:

(a) `skills/paper-extract/SKILL.md` (passo 6): `` finding em `docs/findings/` `` → `` finding em `docs/wiki/findings/` (ou `docs/findings/` em projetos sem `docs/wiki/`) ``

(b) `skills/peer-review/SKILL.md`: `` arquivar o relatório em `docs/findings/_peer_review_<draft-stem>_<YYYY-MM-DD>.md` `` → `` arquivar o relatório em `docs/wiki/findings/_peer_review_<draft-stem>_<YYYY-MM-DD>.md` (ou `docs/findings/` em projetos sem `docs/wiki/`) ``

(c) `skills/wiki-query/SKILL.md`: nas 3 ocorrências (`description`, oferta de arquivar, `_assets`), trocar `docs/findings/` por `docs/wiki/findings/` e, na primeira ocorrência de cada contexto, acrescentar `(ou docs/findings/ em projetos sem docs/wiki/)`.

(d) `skills/wiki-lint/SKILL.md`: nas 4 ocorrências (description, leitura, geração do relatório, exemplo de output), trocar `docs/findings/` por `docs/wiki/findings/`; na description acrescentar `(fallback: docs/findings/)`. Na leitura (linha ~108), o comando passa a: `Ler docs/wiki/findings/*.md (ou docs/findings/*.md como fallback) e docs/concepts/*.md ...`.

- [ ] **Step 2: Verificar consistência de findings**

Run: `grep -rn "docs/findings" skills/*/SKILL.md | grep -v "ou \`docs/findings\|fallback" && echo "FALHOU" || echo "ok"`
Expected: `ok` (toda menção restante a `docs/findings` é como fallback explícito).

- [ ] **Step 3: Namespacing — prefixar slash-commands nos 7 arquivos**

Arquivos com referências sem prefixo: `paper-extract`, `paper-manager`, `peer-review`, `scientific-writing`, `wiki-ingest`, `wiki-lint`, `wiki-query`.

Regra mecânica: toda menção a slash-command de skill do plugin no corpo (`/paper-manager`, `/paper-extract`, `/paper-extract-all`, `/wiki-ingest`, `/wiki-query`, `/wiki-lint`, `/peer-review`, `/scientific-writing`, `/write-paper`, `/active-learning`, `/formulate-picot`, `/start`) ganha o prefixo `/prumo-assist:`. NÃO alterar: nomes de arquivos/paths, o campo `name:` do frontmatter, e comandos de terminal (`prumo ...`).

Para localizar cada ocorrência:

```bash
grep -rnE '(^|[^:a-z-])/(paper-manager|paper-extract|paper-extract-all|wiki-ingest|wiki-query|wiki-lint|peer-review|scientific-writing|write-paper|write-projeto-cep|write-scientific|write-statistics|active-learning|formulate-picot|start)\b' skills/*/SKILL.md
```

Aplicar o prefixo em cada uma (edição manual arquivo a arquivo).

- [ ] **Step 4: Verificar zero referência sem prefixo**

Run: o mesmo grep do Step 3.
Expected: saída vazia (toda referência agora contém `:` antes do nome, i.e., `/prumo-assist:<skill>`).

- [ ] **Step 5: Gates + commit**

Run: `uv run pytest` (inclui `test_guidelines_present.py`, que protege a prosa clínica)
Expected: PASS.

```bash
git add skills/
git commit -m "fix(skills): findings canônico com fallback (ADR-0014) + namespacing /prumo-assist: (D11)"
```

---

### Task 17: Release v0.62.0 — CHANGELOG, bump, manifests, PR, tag

**Files:**
- Modify: `CHANGELOG.md`, `src/prumo_assist/_version.py`, `CITATION.cff`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (via script)
- Modify: `docs/superpowers/plans/2026-06-11-repo-organization-redesign.md` (status final)

- [ ] **Step 1: Regenerar índices (descriptions podem ter mudado na Task 16)**

```bash
uv run python .github/scripts/gen_indexes.py
git diff --stat
```

Expected: README/start/_index regenerados se houve mudança de description (wiki-query e wiki-lint mudaram).

- [ ] **Step 2: CHANGELOG — nova seção 0.62.0**

Edit `CHANGELOG.md` — após a linha `## [Não publicado]` (e o que houver nela), inserir:

```markdown
## [0.62.0] - 2026-06-11

### Removido
- **⚠ Breaking** — agents `ml-theory-expert` e `stack-docs-researcher` (pré-pivot, quebrados como distribuídos; [ADR-0012](docs/adr/adr-0012-remocao-agents-ml.md)). Conteúdo preservado no histórico git.

### Mudado
- Skills `paper-extract` e `wiki-ingest` leem PDF com a tool `Read` nativa — removida a dependência fantasma do MCP `pdf-reader` ([ADR-0013](docs/adr/adr-0013-pdf-via-read-nativo.md)).
- Caminho de findings unificado na prosa das skills: `docs/wiki/findings/` com fallback `docs/findings/`, espelhando o resolver real ([ADR-0014](docs/adr/adr-0014-findings-canonico.md)).
- `paper-extract` invoca os backends reais do pacote (`core/config.py`, `domains/paper/callout.py`) — o import legado de `.claude/scripts/` estava quebrado desde a migração pro pacote.

### Documentação
- Slash-commands citados na prosa das skills padronizados na forma qualificada `/prumo-assist:<skill>`.
- Router `start` ganhou catálogo completo gerado (14 skills) — Princípio VII.
```

E no rodapé, acima de `[0.61.0]:`, adicionar:

```markdown
[0.62.0]: https://github.com/raphaelfh/prumo-assist/compare/v0.61.0...v0.62.0
```

(atualizando também `[Não publicado]:` para `compare/v0.62.0...HEAD`).

- [ ] **Step 3: Bump + sync + validação**

Edit `src/prumo_assist/_version.py`: `0.61.0` → `0.62.0`.
Edit `CITATION.cff`: `version: 0.61.0` → `version: 0.62.0`.

```bash
python .github/scripts/sync_manifest_version.py
uv run --with jsonschema==4.23.0 python .github/scripts/validate_manifests.py
python .github/scripts/sync_manifest_version.py --check
uv run pytest && uv run ruff check . && uv run mypy && uv run python .github/scripts/gen_indexes.py --check
```

Expected: tudo verde; manifests em 0.62.0.

- [ ] **Step 4: Fechar o lifecycle deste plano**

Edit `docs/superpowers/plans/2026-06-11-repo-organization-redesign.md` frontmatter:

```yaml
---
status: implemented
verified: 2026-06-11
release: "0.62.0"
spec: "[[2026-06-11-repo-organization-redesign-design]]"
---
```

```bash
git mv docs/superpowers/plans/2026-06-11-repo-organization-redesign.md docs/superpowers/plans/archive/
uv run python .github/scripts/gen_indexes.py
```

- [ ] **Step 5: Commit de release + PR**

```bash
git add -A
git commit -m "release: 0.62.0 - remoção agents ML + contratos de skill reconciliados (ADR-0012/0013/0014)"
git push -u origin release/v0.62.0
gh pr create --title "release: v0.62.0" --body "$(cat <<'EOF'
Trilha B do spec 2026-06-11-repo-organization-redesign: release MINOR com ⚠ Breaking (remoção dos agents ML), pdf-reader → Read nativo, findings canônico e namespacing qualificado. Detalhes no CHANGELOG 0.62.0; decisões em docs/adr/adr-0012..0014.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 6: Pós-merge (gate humano): tag + release**

Após o merge do PR pelo Raphael:

```bash
git checkout main && git pull
git tag -a v0.62.0 -m "v0.62.0"
git push origin v0.62.0
gh release create v0.62.0 --title "v0.62.0" --notes "$(awk '/^## \[0.62.0\]/{flag=1;next}/^## \[/{flag=0}flag' CHANGELOG.md)"
```

Expected: release publicado; consumidores atualizam com `/plugin marketplace update prumo-assist` + `/reload-plugins`.

---

## Critérios de aceitação finais (espelham o spec)

1. `CLAUDE.md` raiz existe com @imports e armadilhas; `AGENTS.md` symlink resolve.
2. Uma numeração de princípios (romana, I–VII); ARCHITECTURE sem contradição material (5 domínios, comandos reais).
3. `docs/adr/` com 14 ADRs aceitos + índice gerado.
4. Zero plans sem status; `plans/` só com trabalho ativo; `archive/` com 13 (12 históricos + este).
5. `gen_indexes.py --check` e `sync_manifest_version.py --check` verdes no CI.
6. `graphify query` funcional; hook pós-commit instalado.
7. v0.62.0 publicado com tag; zero `mcp__pdf-reader__` em `skills/`; zero contradição de findings.
8. Working tree sem dados pessoais, sem config morta, gitignore cobrindo `docs/Untitled*`.
