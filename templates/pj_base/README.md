# pj_<NOME>

Projeto de pesquisa: bibliografia (Zotero), wiki e escrita.

## Setup

```bash
uv sync                        # ambiente Python base
/plugin install par@prumo-assistant-for-researcher   # no Claude Code: skills + agents + MCP qmd
```

Editor recomendado: [Zettlr](https://www.zettlr.com) ≥ 3.0 — preview vivo de citações; setup em `docs/project_guide.md`.

## Estrutura

```
pj_<nome>/
├── docs/
│   ├── ...            Wiki + project_guide.md + templates/
│   ├── references/     Acervo bibliográfico do projeto (notas, .bib, pdfs) — Zotero
│   └── studies/<slug>/ Escopo de escrita: notes/, writing/, decisions/
└── .claude/      Rules, config
```

## Evoluir o projeto

```bash
prumo add            # lista e ativa módulos (clinical, ml, ...)
prumo add clinical   # protocolo, CEP, plano estatístico
prumo add notebooks  # notebooks/<escopo>/ — marimo (.py) ou Jupyter (.ipynb)
prumo add ml         # stack de ML/dados + notebook
```

## Workflow (no Claude Code)

| Quero… | Invoque |
|---|---|
| não sei por onde começar | `/par:start` |
| adicionar papers do Zotero ao acervo | `/par:paper library` |
| extrair um PDF → resumo estruturado | `/par:paper extract` |
| guardar uma fonte (URL/DOI/PDF) no wiki | `/par:wiki ingest <fonte>` |
| perguntar ao meu acervo, com citações | `/par:wiki query "..."` |
| revisar / escrever um texto | `/par:write style` · `:review critique` · `:write manuscript` |

## Objetivo
_(preencher em `docs/project_guide.md`)_
