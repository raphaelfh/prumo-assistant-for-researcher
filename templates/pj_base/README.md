# pj_<NOME>

Projeto de pesquisa: bibliografia (Zotero), wiki e escrita.

## Setup

Abra este projeto no app Claude, aba Code (ou `claude` no terminal), e peça `/par:start`.

Editor recomendado: [Zettlr](https://www.zettlr.com) recente (o export do PAR precisa de pandoc 3.8.2 ou mais novo; confira com `prumo doctor`) — preview vivo de citações; setup em `docs/project_guide.md`.

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

Peça ao Claude:

- "quais módulos posso ativar?" (roda `prumo add`): lista os módulos (clinical, ml, ...);
- "ativa o módulo clínico" (roda `prumo add clinical`): protocolo, CEP, plano estatístico;
- "ativa o módulo de notebooks" (roda `prumo add notebooks`): `notebooks/<escopo>/`, marimo (.py) ou Jupyter (.ipynb);
- "ativa o módulo de ML" (roda `prumo add ml`): stack de ML/dados + notebook.

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
