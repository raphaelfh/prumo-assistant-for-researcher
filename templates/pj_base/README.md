# pj_<NOME>

Projeto de pesquisa: bibliografia (Zotero), wiki e escrita.

## Setup

```bash
uv sync                        # ambiente Python base
/plugin install prumo-assist   # no Claude Code: skills + agents + MCP qmd
```

## Estrutura

```
pj_<nome>/
├── docs/         Wiki + project_guide.md + decisions/ + canvas/
├── references/   Acervo bibliográfico (notas, .bib, pdfs) — Zotero
└── .claude/      Rules, config, make/
```

## Evoluir o projeto

```bash
prumo add            # lista e ativa módulos (clinical, ml, ...)
prumo add clinical   # protocolo, CEP, plano estatístico
prumo add ml         # stack de ML/dados + notebook
```

## Workflow (no Claude Code)

Veja a tabela "Início rápido" em [`CLAUDE.md`](CLAUDE.md) — ou rode `/prumo-assist:start`.

## Objetivo
_(preencher em `docs/project_guide.md`)_
