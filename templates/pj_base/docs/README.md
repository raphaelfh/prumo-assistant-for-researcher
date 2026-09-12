# pj_<NOME>

Documentação do projeto. Preencha conforme o estudo evolui — este README é o ponto de entrada para quem chega no repositório.

## Estrutura

| Arquivo / pasta | Conteúdo |
|---|---|
| [`_index.md`](_index.md) | Catálogo content-oriented do wiki (mantido pela `/prumo-assist:wiki ingest`) |
| [`_log.md`](_log.md) | Append-only chronological (ingests, queries, lints, decisões) |
| [`studies/<slug>/notes/`](studies/) | Toda página do wiki, uma por arquivo, distinguida pelo `type:` do frontmatter: `concept` (ideias, métodos), `entity` (modelos, datasets, coortes, ferramentas), `finding` (resultados arquivados), `source` (blogs, tutoriais, slides, transcrições) |
| [`studies/<slug>/writing/protocol.md`](studies/) | Protocolo clínico, coorte, critérios, labels, métricas — por escopo de escrita |
| [`studies/<slug>/decisions/`](studies/) | ADRs do escopo — congelar escolhas com motivação |
| [`references/_index.md`](references/_index.md) | Acervo bibliográfico (papers). Paper principal marcado `role: primary`. |

**Schema canônico**: frontmatter de cada `type:`, convenções de link e formato de `_log.md` estão documentados nos modos da skill `/prumo-assist:wiki` (`ingest`, `query`, `lint`). Não existe diretório por tipo — o tipo é campo do frontmatter, não pasta.

## Operações wiki

```bash
# Ingerir fonte nova
/prumo-assist:wiki ingest <URL | DOI | arXiv | PDF>

# Perguntar sobre o projeto
/prumo-assist:wiki query "<pergunta>"

# Auditar consistência
/prumo-assist:wiki lint

# Buscar no wiki (CLI)
qmd query "<termo>"
```

## Objetivo do estudo

_(preencher em 1–3 linhas)_

## Status

_(rascunho | em execução | pausa | concluído)_
