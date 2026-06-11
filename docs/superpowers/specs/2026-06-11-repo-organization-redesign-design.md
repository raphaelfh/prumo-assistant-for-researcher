---
title: Reorganização do repositório — CLAUDE.md, ADRs, lifecycle de specs/plans e índices gerados
date: 2026-06-11
status: approved
tags: [organization, adr, claude-md, rules, lifecycle, indexes, graphify, governance]
---

# Reorganização do repositório — spec-driven, ADRs e knowledge base

## Resumo executivo

Auditoria completa do repo (2026-06-11, v0.61.0) cruzada com pesquisa verificada das práticas de junho/2026 (Spec Kit, OpenSpec, doutrina oficial de CLAUDE.md/skills, MADR 4.0, AGENTS.md) concluiu: o prumo-assist **não sofre de falta de estrutura — sofre de estruturas paralelas não reconciliadas e ausência de lifecycle**. O fluxo superpowers (brainstorm → spec → plan → TDD) já é praticado com rigor; o que falta é um único lugar canônico para cada tipo de conhecimento, marcadores de status e índices gerados em vez de mantidos à mão.

Esta mudança: (1) cria o `CLAUDE.md` raiz + `.claude/rules/` que o repo prescreve aos consumidores mas não usa; (2) cria `docs/adr/` (MADR 4.0 minimal) consolidando as decisões hoje espalhadas em 5 lugares; (3) torna a constitution a única fonte de princípios via emenda formal; (4) adiciona lifecycle aos plans (frontmatter de status + `archive/`); (5) centraliza os 4 índices stale num gerador único com check de drift no CI; (6) adiciona graphify como camada de query do knowledge base; (7) numa trilha de release separada (MINOR v0.62.0), remove os 2 agents de ML pré-pivot, elimina a dependência fantasma `pdf-reader` e reconcilia os contratos de caminho entre prosa de skills e resolvers de `src/`.

Diretriz transversal acordada: **manter super simples, seguir o que o superpowers já prevê (zero tooling novo) e centralizar para facilitar a manutenção**.

## Contexto e problema

Evidências da auditoria (todas verificadas contra o working tree em HEAD `c71ea78`):

- **Sem CLAUDE.md na raiz.** O único é `templates/pj_base/CLAUDE.md` — produto (scaffolding), não orientação. O repo prescreve a hierarquia `CLAUDE.md → .claude/rules/` aos projetos `pj_*` e não a aplica a si mesmo. O `settings.json` da raiz é config morta (local que o Claude Code não lê).
- **Decisões em 5 lugares concorrentes:** 7 princípios arábicos em `ARCHITECTURE.md`, 6 romanos em `docs/constitution.md` (o CHANGELOG cita os romanos), deferrals no `ROADMAP.md`, decisões D-numeradas dentro dos specs, grupos de decisão em canvas. O repo distribui um gerador de ADR (`domains/protocol/adr.py`) e prescreve `docs/decisions/` aos consumidores, mas não mantém ADR log próprio.
- **ARCHITECTURE.md contradiz o código:** documenta 4 domínios (existem 5 — `protocol` ausente), lista comandos inexistentes (`write watch`, `prumo pack install`), omite `core/{deps,note_paths,scaffold}.py`, `_filters/` e `templates/modules/`.
- **Lifecycle invisível:** os 13 plans em `docs/superpowers/plans/` estão 100% implementados na main, nenhum tem marcador; 4 estão untracked no git; um runbook efêmero convive com plans duráveis; o spec de 2026-04-29 está superseded sem marcador.
- **Índices stale em toda entrada:** `skills/start` lista 8 de 14 skills; README lista 13 de 14; `docs/_index.md` linka 2 de 6 specs e omite `plans/`; existe registry programático (`core/skills.py:load_skill_registry`) que poderia gerar tudo.
- **Produto com drift:** 2 agents de ML pré-pivot (`ml-theory-expert` depende de `./theory/knowledge/` que não existe em lugar nenhum — quebrado como distribuído); `mcp__pdf-reader__read_pdf` usado por 2 agents + 2 skills sem declaração no `.mcp.json`; prosa de skills contradiz os resolvers (`docs/findings/` vs `docs/wiki/findings/`); `paper-extract` importa de `.claude/scripts/` que não existe mais.
- **Governança stale:** ROADMAP congelado em v0.3.0; CITATION.cff em 0.2.0-dev; footers do CHANGELOG param em 0.4.0; git tags param em v0.2.0; RELEASING descreve fluxo (push direto) abandonado em favor de PRs.
- **Higiene:** `docs/Untitled.canvas` (gitignored, no working tree) contém organograma pessoal com nomes de indivíduos; `__pycache__` em `skills/*/scripts/` e `tests/unit/`; 2 kanbans vazios escapam do glob `docs/Untitled.*`.

O que a pesquisa de junho/2026 valida: CLAUDE.md curto com `@imports` e conhecimento ocasional em skills é doutrina oficial; o lifecycle de archive datado é o elemento do modelo OpenSpec que falta ao fluxo superpowers; MADR 4.0 minimal é o formato ADR vigente (tooling de ADR está estagnado — adotar formato, não ferramenta); AGENTS.md é padrão Linux Foundation com 60k+ projetos, mas o Claude Code não o lê nativamente (symlink é o workaround corrente).

## Decisões

### Estruturais (travadas com o usuário)

- **D1 — Seguir o superpowers, zero tooling novo.** Não adotar Spec Kit nem OpenSpec como ferramenta. O fluxo brainstorm → spec → plan → TDD permanece; esta mudança só adiciona convenção (lifecycle, ADRs, índices) sobre o que já existe.
- **D2 — ADR log do repo em `docs/adr/`, formato MADR 4.0 minimal.** Arquivos `adr-NNNN-slug.md` (~15 linhas: Contexto / Decisão / Consequências), imutáveis após aceitos, com wikilink para o spec de origem quando houver. O produto **continua gerando `docs/decisions/`** nos projetos `pj_*` (adr.py e templates intocados); a divergência é registrada no ADR-0001 com trigger de revisão: *alinhar quando `adr.py` for tocado de novo*.
- **D3 — Emenda completa da constitution agora.** A constitution vira a única fonte de princípios: emenda MINOR absorve o delta do ARCHITECTURE (ex.: "DRY de metadata"), atualiza o Sync impact report e fecha o TODO aberto desde v1.0.0. Numeração romana vence (o CHANGELOG já a usa). `ARCHITECTURE.md` perde a seção de princípios e vira só "what/where" corrigido (5 domínios, comandos reais), com as seções "Por que..." migradas para ADRs.
- **D4 — CLAUDE.md raiz (~50 linhas) + `.claude/rules/{code,release}.md` + `AGENTS.md` symlink.** CLAUDE.md contém apenas o sempre-aplicável: identidade do projeto, convenção bilíngue (prosa pt-BR / identificadores EN), `@imports` das duas rules, ponteiros para constitution/`docs/adr/`, as armadilhas do repo (pj_base é produto; force-include do wheel; plugin root fixo; reorganização não bumpa versão) e comandos `uv run`. `code.md` = layering core/domains, facades finas, padrão `cli_run`, typing estrito, blocos delimitados. `release.md` = política de bump por visibilidade ao consumidor + chain `_version.py` → manifests. `AGENTS.md` é symlink para CLAUDE.md (compat com o ecossistema que lê o padrão; Claude Code o ignora). `.claude/settings.json` substitui o `settings.json` morto da raiz (deletado).
- **D5 — Lifecycle de plans: frontmatter + `archive/`.** Todo plan ganha frontmatter `status: draft|in-progress|implemented`, `verified: <data>`, `release: <versão>`. Plans implementados movem para `docs/superpowers/plans/archive/`. Os 3 plans untracked de 2026-05-30 são commitados já com frontmatter, direto em `archive/`; o runbook efêmero `2026-05-31-land-all-work-on-main.md` é deletado (o próprio texto pede para não commitá-lo); o spec `2026-04-29-prumo-scientific-writer-design.md` ganha `status: superseded` apontando para o write-family. Specs permanecem em `specs/` (não-perecíveis), com `status: approved|superseded`.
- **D6 — Índices gerados, nunca mantidos à mão.** Script único `.github/scripts/gen_indexes.py` lê `load_skill_registry()` + filesystem e regenera, dentro de blocos delimitados HTML-comment (padrão já consagrado no repo), as regiões geradas de: tabela de skills do README, seção de catálogo do router `skills/start/SKILL.md`, catálogo de specs/plans/ADRs no `docs/_index.md` e índice de `docs/adr/`. CI ganha check de drift (`gen_indexes.py --check`) e finalmente wira `sync_manifest_version.py --check` (existe e não roda em workflow nenhum).
- **D7 — Graphify como camada de query.** Build inicial do grafo (código + docs + skills num grafo só), `graphify hook install` (pós-commit re-extrai AST das mudanças, sem LLM), `graphify claude install` (seção no CLAUDE.md novo) e `graphify-out/` inteiro no `.gitignore`. Posicionamento: complemento consultável ("o que chama X?", "trace o fluxo de Y") — a hierarquia CLAUDE.md/rules/skills/vault continua sendo o contexto primário.
- **D8 — Remover os 2 agents de ML pré-pivot.** `agents/ml-theory-expert.md` e `agents/stack-docs-researcher.md` saem do plugin (⚠ Breaking no CHANGELOG, release MINOR). Conteúdo preservado no git history (precedente do 0.3.0). Registrado no ADR-0012. O diretório `agents/` é removido por inteiro (git não rastreia diretório vazio, e um README ali seria auto-descoberto como agent); recriar quando existirem agents alinhados ao propósito clínico.
- **D9 — pdf-reader → Read nativo.** Remover todas as referências a `mcp__pdf-reader__read_pdf` (skills `paper-extract` e `wiki-ingest`, mais os agents removidos por D8) e instruir o uso do Read nativo do Claude Code, que lê PDF diretamente. Zero dependência externa nova. Registrado no ADR-0013.
- **D10 — Caminho canônico de findings = `docs/wiki/findings/`.** O que os resolvers (`wiki/findings.py`, `wiki/study.py`) já preferem vira canônico por ADR-0014; a prosa dos 4 skills divergentes (`paper-extract`, `peer-review`, `wiki-query`, `wiki-lint` vs `active-learning`) é corrigida para refletir o comportamento real (preferência + fallback). Nenhuma mudança de código em `src/`.
- **D11 — Contratos de skill reconciliados no mesmo release.** Consertar o import stale do `paper-extract` (`sys.path.insert('../.claude/scripts')` morto → invocação via `python -c` de `prumo_assist.domains.paper.callout`, como os demais skills) e a referência morta a `templates/pj_projeto/`; padronizar o namespacing de slash-commands na prosa de todos os skills para a forma qualificada `/prumo-assist:<skill>`; regenerar o router do `start` com os 14 skills (via D6).
- **D12 — Duas trilhas de PR.** Trilha A (organização, não-releasável por política do próprio RELEASING.md): higiene, CLAUDE.md/rules, ADRs, emenda, lifecycle, índices, CI, graphify, governança. Trilha B (produto, um único PR de release MINOR v0.62.0): D8 + D9 + D10 + D11 + regeneração do único índice distribuído (`skills/start`) + CHANGELOG citando os ADRs novos. A tabela do README é doc do repo (trilha A).
- **D13 — Higiene e governança.** Mover `docs/Untitled.canvas` (dados pessoais) para fora do repo; deletar `settings.json` da raiz, `__pycache__` de `skills/*/scripts/` e `tests/unit/`, e os 2 kanbans vazios; corrigir `.gitignore` (`docs/Untitled*`); atualizar ROADMAP até 0.61.0 (incluindo a reavaliação dos agents prometida "na próxima minor" — cumprida por D8); sincronizar CITATION.cff; completar footers do CHANGELOG; realinhar RELEASING.md ao fluxo real (PR-based) e registrar a criação de tag retroativa `v0.61.0` no commit `f755279`, com tags obrigatórias daí em diante.

### Seed de ADRs (extraídos do que já existe com rationale)

| ADR | Título | Fonte do rationale |
|---|---|---|
| 0001 | ADR log do repo em `docs/adr/`; produto continua `docs/decisions/` | Esta spec (D2) |
| 0002 | `skills/` e `templates/` fora de `src/`, force-included no wheel | ARCHITECTURE "Por que skills/ está fora de src/" + `core/paths.py` |
| 0003 | SKILL.md como única fonte de metadata (namespace `prumo:`) | docstring de `core/skills.py` |
| 0004 | Pacote Python 100% livre de LLM (split determinístico/agentic) | ARCHITECTURE + docstrings de domínio |
| 0005 | Layering core/domains + facades finas | ARCHITECTURE "Por que core/ e domains/ são separados" |
| 0006 | Schemas versionados forward-only (`schemas/v1.py`) | Princípio IV da constitution |
| 0007 | Zotero via stdlib urllib (sem requests/httpx) | docstring de `paper/zotero.py` |
| 0008 | Layout α para notas de referência | spec zotero-notes + `core/note_paths.py` |
| 0009 | Blocos delimitados HTML-comment como contrato humano/máquina | padrão transversal em 6 módulos |
| 0010 | Plugin root = repo root + marketplace self-hosting; lição do `repository`-string | `.claude-plugin/` + `.github/schemas/` |
| 0011 | SemVer por visibilidade ao consumidor; deferrals com trigger | RELEASING.md + ROADMAP "Decisões deliberadas postergadas" |
| 0012 | Remoção dos agents ML pré-pivot | Esta spec (D8) |
| 0013 | PDFs via Read nativo, sem MCP pdf-reader | Esta spec (D9) |
| 0014 | Caminho canônico de findings = `docs/wiki/findings/` | Esta spec (D10) + resolvers de `wiki/` |

## Estrutura-alvo

```
prumo-assist/
├── CLAUDE.md                  ← novo (~50 linhas, @imports)
├── AGENTS.md                  ← symlink → CLAUDE.md
├── .claude/
│   ├── settings.json          ← substitui settings.json da raiz (deletado)
│   └── rules/
│       ├── code.md
│       └── release.md
├── ARCHITECTURE.md            ← corrigido e emagrecido (what/where, 5 domínios)
├── docs/                      ← continua vault Obsidian
│   ├── _index.md              ← regenerado (bloco delimitado)
│   ├── constitution.md        ← única fonte de princípios (emenda)
│   ├── adr/                   ← novo: adr-0001…0014 + índice gerado
│   └── superpowers/
│       ├── specs/             ← status: approved | superseded
│       └── plans/
│           └── archive/       ← 13 plans implementados movem pra cá
```

Invariantes: `skills/`, `templates/`, `agents/`, `.mcp.json` e `.claude-plugin/` não se movem (marketplace `source: "./"` + force-include do wheel + `core/paths.resolve_resource`).

## Fora de escopo (YAGNI)

- Adotar Spec Kit ou OpenSpec como tooling (D1) ou qualquer ferramenta de ADR (log4brains etc. — ecossistema estagnado).
- Renomear `docs/decisions/` no produto (`adr.py`, templates) — deferido com trigger no ADR-0001.
- Reescrever/substituir os agents removidos por agents clínicos — só quando houver demanda real.
- `llms.txt`, export `--wiki` do graphify, servidor MCP do grafo — sem evidência de necessidade agora.
- Refatorações de código em `src/` (orphans `core/config.py`/`core/provenance.py`, dead code em `export.py`, duplicação de endpoint Zotero) — são qualidade de código, não organização; candidatos a spec próprio.
- Mudar o fluxo de release além do realinhamento documental (RELEASING continua manual + PR).
- Dogfooding do `prumo wiki lint` sobre `docs/` — revisitar quando o lint suportar vault de plugin.

## Critérios de sucesso

1. Agente que abre o repo recebe contexto correto: `CLAUDE.md` raiz existe, aponta para constitution/ADRs e avisa que `templates/pj_base/CLAUDE.md` é produto.
2. Uma única numeração de princípios viva (romana); `ARCHITECTURE.md` sem contradição material com o código (5 domínios, comandos reais).
3. `docs/adr/` com 14 ADRs aceitos; toda decisão futura estrutural referencia ou cria ADR.
4. Zero plans sem status; `plans/` contém só trabalho ativo; `archive/` preserva a história com `verified`/`release`.
5. `gen_indexes.py --check` verde no CI; os 4 índices (README, start, `_index.md`, ADRs) regenerados de uma única fonte; `sync_manifest_version.py --check` rodando no CI.
6. `graphify query` responde perguntas estruturais sobre o repo; hook pós-commit mantém o grafo atualizado.
7. Release v0.62.0 publicado com tag, ⚠ Breaking documentado (agents), zero referências a `mcp__pdf-reader__` e zero contradições de caminho entre prosa de skill e resolver.
8. Working tree limpo: sem dados pessoais, sem config morta, sem `__pycache__` rastreável, gitignore cobrindo `docs/Untitled*`.

## Fases de execução

| Fase | Trilha | Conteúdo |
|---|---|---|
| 0 | A | Higiene: canvas pessoal fora, settings.json morto, pycache, kanbans, gitignore, commit dos 3 plans untracked, delete do runbook |
| 1 | A | CLAUDE.md + `.claude/rules/` + AGENTS.md symlink + `.claude/settings.json` |
| 2 | A | `docs/adr/` (14 seeds) + emenda da constitution + ARCHITECTURE corrigido |
| 3 | A | Lifecycle de plans (frontmatter + archive) + `gen_indexes.py` + checks no CI + governança (ROADMAP, CITATION, CHANGELOG footers, RELEASING, tag retroativa) |
| 4 | A | Graphify: build inicial + hook + claude install + gitignore |
| 5 | B | Release v0.62.0: remover agents, pdf-reader → Read, contratos de skill (D10/D11), regenerar índices distribuídos, CHANGELOG + tag |
