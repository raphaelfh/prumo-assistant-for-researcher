---
paths:
  - "**/pj_*/docs/**"
  - "**/pj_*/references/**"
---

<!-- Esta rule é cópia inicial do template global em .claude/rules/documentation.md.
     Pode ser customizada livremente para este projeto; vale sobre a rule
     da raiz dentro do escopo deste pj_*. Mantida sem alterações, o
     comportamento é idêntico ao global. -->

# Documentação de projeto e acervo bibliográfico

Contrato do que vive em cada `pj_*` para documentação de estudo e gestão de artigos. A fonte é Markdown Pandoc puro versionado em git; o front humano é o **Zettlr** (workspace na raiz do projeto — setup one-time em `docs/project_guide.md`, seção Editor).

## Estrutura

| Pasta | Conteúdo |
|-------|----------|
| `docs/` | Documentação do estudo — `README.md`, `protocol.md`, `decisions/`, `templates/` (reference.docx + perfil Zettlr gerado) |
| `references/` | Acervo bibliográfico — MOC, BibTeX, PDFs, notas, templates |

```
pj_*/references/
├── _index.md             # MOC: paper primário, por tema, por status
├── _references.bib       # Zotero + Better BibTeX (auto-export)
├── pdfs/                 # PDFs gitignorados (copyright)
├── templates/literature_note.md
└── notes/<citekey>/_meta.md    # 1 pasta por paper (layout α)
```

## Citation key — fonte única de identidade

Padrão **Better BibTeX**: `<sobrenomeMinúsculo><ano><primeiraPalavraTítuloMinúscula>` em ASCII puro, sem espaços/acentos. Desempate com sufixo `a/b/c`.

Ex.: `smith2024cohort`, `jones2023trial`, `jones2023triala` (desempate).

A mesma string é usada em **todos** os artefatos:

- nome do PDF: `pdfs/<citekey>.pdf`
- nome da nota: `notes/<citekey>/_meta.md`
- entrada BibTeX: `@article{<citekey>, ...}`
- citação no corpo: `[@<citekey>]` — sintaxe Pandoc; o Zettlr renderiza no editor e autocompleta ao digitar `@`

## YAML é a única fonte de verdade

Toda metadata de paper vive no **YAML frontmatter** da nota. Proibido metadata inline no corpo das notas versionadas — polui o RAG file-based.

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
| `pdf` | string | caminho relativo `../../pdfs/<citekey>.pdf` |
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

Destaques usam Markdown puro: parágrafo com **TL;DR** em negrito, blockquote `> "trecho exato" (p. XX)` para citações literais. Callouts do Obsidian são legado — não usar em material novo.

## Como o agente busca no acervo

| Intenção | Comando |
|----------|---------|
| Paper principal do projeto | `rg "^role: primary" references/notes/` |
| Fuzzy por autor/título | `/prumo-assist:paper-manager find "<query>"` ou `make cite Q="<query>"` |
| Papers sobre um tema | `rg -l "combinado" references/notes/` |
| O que um paper cita (grafo passivo) | `Read references/notes/<citekey>/_meta.md` (campo `cites:`, populado por `update-cites` ao fim de `sync`) |
| Quem cita um paper | `rg "@<citekey>" references/notes/` ou `/prumo-assist:paper-manager graph <citekey>` |
| Não lidos | `rg "^status: unread" references/notes/` |
| Bibliografia formatada | `Read references/_references.bib` |

## Skill dedicada

Operações de alto nível (adicionar paper via DOI, promover para `primary`, listar, sincronizar `.bib`) estão em `/prumo-assist:paper-manager`. Preferir a skill a editar YAML à mão quando for ingestão.

Para extrair conteúdo estruturado do PDF (TL;DR, PICOT, Método, Resultados, Limitações), use `/prumo-assist:paper-extract <citekey>` (single) ou `/prumo-assist:paper-extract-all` (batch). Pressuposto: `/prumo-assist:paper-manager sync` + `make sync-pdfs` já executados.

## PDFs e copyright

`references/pdfs/*.pdf` é **gitignored**. Versionam-se apenas as notas `.md` e o `.bib`. Cada colaborador cuida do próprio diretório local de PDFs.
