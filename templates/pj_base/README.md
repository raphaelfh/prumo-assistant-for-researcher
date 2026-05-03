# pj_<NOME>

Projeto de pesquisa em machine learning aplicado à saúde.

## Setup

### 1. Ambiente Python

```bash
uv sync --group tabular --group viz
# Adicionar --group imaging e/ou --group deep-learning conforme o estudo
```

### 2. Plugin do Claude Code

Este projeto assume o plugin [`prumo-assist`](https://github.com/raphaelfh/prumo-assist) instalado. No Claude Code:

```
/plugin marketplace add raphaelfh/prumo-assist
/plugin install prumo-assist
```

O plugin fornece as skills comuns (`/prumo-assist:paper-manager`, `/prumo-assist:paper-extract`, `/prumo-assist:wiki-ingest`, `/prumo-assist:wiki-query`, `/prumo-assist:wiki-lint`, `/prumo-assist:scientific-writing`, `/prumo-assist:peer-review`), agents (`ml-theory-expert`, `stack-docs-researcher`) e o MCP `qmd` (busca no wiki).

### 3. Contexto do estudo

Preencher antes de começar:

- `.claude/rules/project_context.md` — coorte, labels, ética
- `docs/protocol.md` — protocolo clínico, critérios, métricas

### 4. Vault Obsidian (opcional)

Abrir o projeto como vault no Obsidian (`.obsidian/` já vem configurado):
`Obsidian.app → Open folder as vault → pj_<nome>/`

Plugins recomendados: **Zotero Integration**, **Templater**, **Linter**.

## Estrutura

```
pj_<nome>/
├── content/{01_raw,02_processed}/   Dados (gitignored)
├── docs/                             Wiki do estudo (protocol, decisions, concepts, entities, findings, sources)
├── references/                       Acervo bibliográfico (notas, .bib, pdfs)
├── 01_eda_clinical.ipynb … 05_combinado_fusion.ipynb
└── .claude/{rules,skills}/           Rules e skills locais
```

Ver [`CLAUDE.md`](CLAUDE.md) para detalhes.

## Workflow

```bash
# Adicionar paper ao acervo (via Zotero + BBT auto-export)
/prumo-assist:paper-manager sync

# Extrair callouts de TODOS os papers novos
/prumo-assist:paper-extract-all

# Ingerir fonte não-paper no wiki
/prumo-assist:wiki-ingest <URL | PDF>

# Pergunta ancorada no wiki
/prumo-assist:wiki-query "<pergunta>"

# Auditar wiki
/prumo-assist:wiki-lint
```

## Objetivo

_(preencher em 1–3 linhas)_

## Status

_(rascunho | em execução | pausa | concluído)_
