# pj_<NOME>

Documentação do projeto. Preencha conforme o estudo evolui — este README é o ponto de entrada para quem chega no repositório.

## Estrutura

| Arquivo / pasta | Conteúdo |
|---|---|
| [`_index.md`](_index.md) | Catálogo content-oriented do wiki (mantido pela `/prumo-assist:wiki-ingest`) |
| [`_log.md`](_log.md) | Append-only chronological (ingests, queries, lints, decisões) |
| [`protocol.md`](protocol.md) | Protocolo clínico, coorte, critérios, labels, métricas |
| [`decisions/`](decisions/) | ADRs do estudo — congelar escolhas com motivação |
| [`concepts/`](concepts/) | Ideias, métodos, abordagens (1 `.md` por conceito) |
| [`entities/`](entities/) | Modelos, datasets, coortes, ferramentas, instituições |
| [`findings/`](findings/) | Resultados arquivados (análises, respostas de `/prumo-assist:wiki-query`) |
| [`sources/`](sources/) | Fontes não-paper: blogs, tutoriais, docs, slides, videos, transcripts, decisões |
| [`../references/_index.md`](../references/_index.md) | Acervo bibliográfico (papers). Paper principal marcado `role: primary`. |

**Schema canônico**: frontmatter, convenções de link e formato de `_log.md` estão documentados nas próprias skills `/prumo-assist:wiki-*` e nos templates de cada subpasta (`concepts/`, `entities/`, `findings/`, `sources/`, `decisions/`).

## Operações wiki

```bash
# Ingerir fonte nova
/prumo-assist:wiki-ingest <URL | DOI | arXiv | PDF>

# Perguntar sobre o projeto
/prumo-assist:wiki-query "<pergunta>"

# Auditar consistência
/prumo-assist:wiki-lint

# Buscar no wiki (CLI)
qmd query "<termo>"
```

## Objetivo do estudo

_(preencher em 1–3 linhas)_

## Status

_(rascunho | em execução | pausa | concluído)_
