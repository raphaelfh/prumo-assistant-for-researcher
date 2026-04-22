---
name: wiki-ingest
description: Ingere uma fonte nova (paper, blog, tutorial, doc, slide, video, transcript, decisão) no wiki de um pj_* ativo. Cria a página, atualiza docs/_index.md, anexa entrada em docs/_log.md e reindexa o CLI qmd. Invocar quando o usuário pedir "adicionar fonte", "ingerir paper", "registrar tutorial", "salvar este link no wiki", "indexar artigo", ou quando colar uma URL/DOI/arXiv/PDF com intenção de processar. Para papers científicos (DOI/arXiv), delega a /paper-manager e depois costura a entrada no wiki do projeto.
---

# Wiki Ingest — adicionar fonte ao wiki de um `pj_*`

Opera sobre o schema canônico em `/docs/wiki-schema.md` do monorepo. Não reescreve regras — aplica.

## Pressupostos

- cwd é um `pj_*` com scaffold padrão (`docs/_index.md`, `docs/_log.md`, `docs/{concepts,entities,findings,sources}/`, `references/`).
- Se faltar estrutura, orientar `make new-project` (para pj_ novo) ou criar o scaffold manualmente seguindo o schema.

## Fluxo

### 1. Classificar a fonte

| Input | Caminho |
|---|---|
| DOI, arXiv ID, URL de journal | **Orientar o usuário a adicionar o paper no Zotero** e rodar `/paper-manager sync`. A skill não resolve metadata diretamente; Zotero é a fonte de verdade. |
| URL de blog, tutorial, doc, slide, vídeo, transcript | Continuar nesta skill. Cria `docs/sources/<slug>.md`. |
| PDF local que não é paper acadêmico (relatório, white paper, slide deck) | Continuar nesta skill. Usar `mcp__pdf-reader__read_pdf` para extrair conteúdo. |
| Decisão clínica ou editorial (memo, ata) | Continuar nesta skill. `kind: decision`. |

Se houver dúvida, perguntar ao usuário uma vez antes de escolher o caminho.

### 2. Ler a fonte

- `WebFetch` para URL pública (passar prompt pedindo takeaways + autores + data).
- `mcp__pdf-reader__read_pdf` para PDF local (páginas específicas se >10).
- Quando inacessível, pedir ao usuário o conteúdo colado.

### 3. Discutir takeaways com o usuário

Antes de escrever qualquer arquivo, responder com:

1. **3–5 pontos-chave** da fonte.
2. **Páginas candidatas a tocar**: usar `Glob docs/{concepts,entities}/*.md` + `qmd search "<termo>"` (via `mcp__qmd__*` se disponível, senão `Bash("qmd search ...")`) para checar o que já existe.
3. **Páginas novas sugeridas**: conceitos centrais da fonte que ainda não têm arquivo.

Esperar confirmação/direcionamento do usuário antes do passo 4.

### 4. Criar `docs/sources/<slug>.md`

Slug: kebab-case do título, ASCII minúsculo, sem stopwords. Colisão → sufixo numérico.

Frontmatter (ver schema canônico):

```yaml
---
id: <slug>
type: source
kind: blog | tutorial | doc | slide | video | transcript | decision
title: "<título>"
url: <link canônico>
authors: ["Nome Sobrenome", ...]
date: YYYY-MM-DD         # data da fonte (ou vazio)
added: YYYY-MM-DD        # data da ingestão
status: read
tldr: "<1 linha>"
tags: [...]
links_to: []             # preenchido no passo 5
---
```

Corpo (seções fixas):

```markdown
## TL;DR
<1–3 linhas>

## Contexto
<por que essa fonte importa aqui; relação com o projeto>

## Conteúdo chave
<bullets ou parágrafos curtos; 1 seção por ponto-chave identificado no passo 3>

## Aplicação neste projeto
<como isso muda decisões no pj_*; apontar para findings/concepts/entities>

## Notas
<links complementares, leituras futuras>
```

### 5. Criar/atualizar páginas relacionadas

Até **10–15 páginas** por ingest. Para cada conceito/entidade central:

- Se já existe `docs/concepts/<slug>.md` ou `docs/entities/<slug>.md`: `Edit` para acrescentar a fonte em `sources:` e um bullet em `## Evidências`.
- Se não existe e o usuário confirmou no passo 3: criar o arquivo com frontmatter apropriado (ver schema para `concept`/`entity`) e seção `## Evidências` com bullet apontando para `[[<slug-da-source>]]`.

Voltar ao arquivo do passo 4 e preencher `links_to:` com a lista final de wikilinks tocados.

### 6. Atualizar `docs/_index.md`

Na seção correta (`## Sources`, `## Concepts`, `## Entities`), inserir em ordem alfabética:

```
- [[<slug>]] — <tldr curto>
```

Atualizar rodapé: `**Última atualização:** YYYY-MM-DD`.

### 7. Anexar entrada em `docs/_log.md`

**Topo do arquivo** (após o header), nova entrada:

```
## [YYYY-MM-DD] ingest | <título curto>

- Fonte: [[<slug>]] (<kind>)
- Páginas tocadas: [[a]], [[b]], [[c]]
- Insight: <1 linha de por que essa fonte muda algo>
```

### 8. Reindexar qmd

Se o MCP `mcp__qmd__*` estiver ativo: chamar `qmd embed` via tool.

Caso contrário, mostrar ao usuário o comando para rodar:

```bash
qmd embed                                     # incremental
# ou na primeira vez:
qmd collection add . --name <pj_nome>
qmd embed
```

### 9. Resumo final ao usuário

```
✓ Ingest: <título> (<kind>)
  Fonte:   docs/sources/<slug>.md
  Páginas: docs/concepts/x.md, docs/entities/y.md  (+N novas)
  Log:     docs/_log.md (entrada de YYYY-MM-DD)
  Index:   docs/_index.md (+1 em Sources, +N em Concepts/Entities)
  qmd:     reindexado (ou: rode `qmd embed`)
```

## Boundaries

- **Nunca baixa PDF automaticamente** (copyright). Para paper, o usuário coloca o PDF em `references/pdfs/<citekey>.pdf` manualmente.
- **Não mexe em** `content/`, `pyproject.toml`, notebooks.
- **Paper científico** nunca entra direto pelo `/wiki-ingest`. Orientar o usuário: (1) adicionar no Zotero; (2) `/paper-manager sync`; (3) voltar aqui para costurar a fonte a outras páginas do wiki se quiser.
- **Máximo de 15 páginas tocadas** por ingest. Se mais forem necessárias, quebrar em ingests separados e deixar claro no log que é parte N/M.

## Erros comuns

- **Slug colide com arquivo existente** → sufixo `-2`, `-3`…
- **Usuário cola URL de paper mas DOI não resolve** → orientar a adicionar no Zotero via URL ou arXiv ID; senão salvar como `source` genérico com `kind: doc` até o usuário conseguir o DOI.
- **qmd indisponível** → fluxo não trava; só documenta no output que a reindexação não aconteceu e pede ao usuário para rodar depois.
- **Páginas relacionadas em conflito com ingest anterior** → mostrar o diff proposto antes de escrever; nunca sobrescrever seções de autoria humana sem perguntar.
