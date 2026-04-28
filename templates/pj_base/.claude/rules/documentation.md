---
paths:
  - "**/pj_*/docs/**"
  - "**/pj_*/references/**"
  - "**/pj_*/.obsidian/**"
---

<!-- Esta rule é cópia inicial do template global em .claude/rules/documentation.md.
     Pode ser customizada livremente para este projeto; vale sobre a rule
     da raiz dentro do escopo deste pj_*. Mantida sem alterações, o
     comportamento é idêntico ao global. -->

# Documentação de projeto e acervo bibliográfico

Contrato do que vive em cada `pj_*` para documentação de estudo e gestão de artigos. Cada `pj_*` **é um vault Obsidian** (o `.obsidian/` mora na raiz do submodule).

## Estrutura

| Pasta | Conteúdo |
|-------|----------|
| `docs/` | Documentação do estudo — `README.md`, `protocol.md`, `decisions/` |
| `references/` | Acervo bibliográfico — MOC, BibTeX, PDFs, notas, templates, views |
| `.obsidian/` | Config compartilhada do vault (versionada parcialmente; estado pessoal fica no `.gitignore`) |

```
pj_*/references/
├── _index.md             # MOC: paper primário, por tema, por status
├── _references.bib       # Zotero + Better BibTeX (auto-export)
├── pdfs/                 # PDFs gitignorados (copyright)
├── templates/literature_note.md
├── views/papers.base     # Obsidian Bases (core)
└── notes/<citekey>.md    # 1 .md por paper
```

## Citation key — fonte única de identidade

Padrão **Better BibTeX**: `<sobrenomeMinúsculo><ano><primeiraPalavraTítuloMinúscula>` em ASCII puro, sem espaços/acentos. Desempate com sufixo `a/b/c`.

Ex.: `smith2024cohort`, `jones2023trial`, `jones2023triala` (desempate).

A mesma string é usada em **todos** os artefatos:
- nome do PDF: `pdfs/<citekey>.pdf`
- nome da nota: `notes/<citekey>.md`
- entrada BibTeX: `@article{<citekey>, ...}`
- wikilink no corpo: `[[@<citekey>]]`

## YAML é a única fonte de verdade

Toda metadata de paper vive no **YAML frontmatter** da nota. Proibido usar inline fields do Dataview (`key:: value`) nas notas versionadas — não são indexados por Obsidian Properties nem por Bases, e poluem o RAG file-based.

Campos obrigatórios (subset CSL-JSON + curadoria):

| Campo | Tipo | Valores |
|-------|------|---------|
| `id` | string | = citekey |
| `type` | string | `article-journal`, `paper-conference`, `manuscript`, `chapter`, `review` |
| `title` | string | título do paper |
| `author` | lista | `[{family: "...", given: "..."}]` |
| `issued` | objeto | `{date-parts: [[YYYY]]}` |
| `DOI` | string | vazio se preprint sem DOI |
| `container-title` | string | journal / conferência / preprint server |
| `URL` | string | link canônico |
| `pdf` | string | caminho relativo `../pdfs/<citekey>.pdf` |
| `tags` | lista | keywords livres |
| `role` | string | `primary` (exatamente 1 por projeto), `supporting`, `background`, `replaced` |
| `status` | string | `unread`, `reading`, `read`, `skimmed` |
| `rating` | int ou null | 1–5 |
| `added` | date | ISO `YYYY-MM-DD` |
| `tldr` | string | 1 linha |
| `cites` | lista | citekeys de papers citados que estão neste acervo |

## Seções fixas da nota (corpo markdown)

Ordem canônica, cabeçalhos `##` exatos:

```
## Problema
## Método
## Resultados
## Limitações
## Relevância para este projeto
## Referências citadas
## Notas
```

Callouts Obsidian são padrão para highlights: `> [!tldr]`, `> [!quote]`, `> [!warning]`. Markdown puro, renderizam no GitHub, transparentes para o agente.

## Como o agente busca no acervo

| Intenção | Comando |
|----------|---------|
| Paper principal do projeto | `rg "^role: primary" references/notes/` |
| Fuzzy por autor/título | `/prumo-assist:paper-manager find "<query>"` ou `make cite PJ=pj_x Q="<query>"` |
| Papers sobre um tema | `rg -l "combinado" references/notes/` |
| O que um paper cita (grafo passivo) | `Read references/notes/<citekey>.md` (campo `cites:`, populado por `update-cites` ao fim de `sync`) |
| Quem cita um paper | `rg "\[\[@<citekey>\]\]" references/notes/` ou `/prumo-assist:paper-manager graph <citekey>` |
| Não lidos | `rg "^status: unread" references/notes/` |
| Bibliografia formatada | `Read references/_references.bib` |

## Skill dedicada

Operações de alto nível (adicionar paper via DOI, promover para `primary`, listar, sincronizar `.bib`) estão em `/prumo-assist:paper-manager`. Preferir a skill a editar YAML à mão quando for ingestão.

Para extrair conteúdo estruturado do PDF (TL;DR, PICOT, Método, Resultados, Limitações) e alimentar um callout delimitado acima das seções humanas, use `/prumo-assist:paper-extract <citekey>` (single) ou `/prumo-assist:paper-extract-all` (batch). Pressuposto: `/prumo-assist:paper-manager sync` + `make sync-pdfs` já executados.

## PDFs e copyright

`references/pdfs/*.pdf` é **gitignored**. Versionam-se apenas as notas `.md` e o `.bib`. Cada colaborador cuida do próprio diretório local de PDFs.
