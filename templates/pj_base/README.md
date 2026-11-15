# pj_<NOME>

Projeto de pesquisa: bibliografia (Zotero), wiki e escrita.

## Setup

Abra esta pasta no seu agente, com o PAR instalado, e peça para começar com o PAR:
app Claude, aba Code (`/par:start`); Antigravity (`/start`); ou Codex no app ChatGPT
(`$par:start`). No terminal, `claude`, `agy` ou `codex` dentro da pasta.

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

- "quais módulos posso ativar?" (roda `prumo add`): lista os módulos (protocol, ml, ...);
- "ativa o módulo de protocolo" (roda `prumo add protocol`; `clinical` também funciona): protocolo, CEP ou CEUA, plano estatístico;
- "ativa o módulo de notebooks" (roda `prumo add notebooks`): `notebooks/<escopo>/`, marimo (.py) ou Jupyter (.ipynb);
- "ativa o módulo de ML" (roda `prumo add ml`): stack de ML/dados + notebook.

## Workflow

As invocações abaixo são as do Claude; no Codex troque `/par:` por `$par:`, no
Antigravity use só `/<skill>` (por exemplo `/paper library`).

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
