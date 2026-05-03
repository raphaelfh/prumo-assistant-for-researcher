---
title: Estrutura de Projeto de Pesquisa
tags: [structure, template, journey]
---

# Estrutura de Projeto de Pesquisa

> Modelo **"mínimo + módulos"** pros projetos `pj_*`. Núcleo único pra todos; módulos ativados por necessidade real, coerente com [[constitution#VI · YAGNI militante]]. Documento vivo — ajuste conforme os projetos forem ensinando.

Visualizações:
- [[canvas/project-structure|Canvas estrutural — núcleo + módulos por composição]]
- [[canvas/project-flow|Canvas de fluxo — como ideia e citação atravessam o repo]]

---

## Núcleo mínimo

Sempre presente, qualquer que seja o projeto (paper único, exploratório, tese).

```
pj_<nome>/
├── README.md                    ← entry point humano (1 página)
├── CLAUDE.md                    ← persona + escopo + deps do plugin
├── pyproject.toml               ← deps Python
├── .claude/                     ← infra automática (gerada por `prumo init`)
│   ├── rules/project_context.md
│   ├── pj_config.toml
│   ├── paper_extraction.md
│   └── skills/                  ← cópia local das skills do plugin
├── .obsidian/                   ← config base do vault
├── docs/
│   ├── _index.md                ← MOC content-oriented (catálogo)
│   ├── _log.md                  ← append-only (ingests, decisões, queries)
│   ├── project.md               ← escrita do projeto (documento-vida)
│   ├── protocol.md              ← operacional clínico (coorte, métricas, ética)
│   ├── decisions/               ← ADRs (governança imutável)
│   └── canvas/
│       └── project.canvas       ← whiteboard panorâmico
└── references/
    ├── _index.md                ← MOC do acervo (mantido por paper-manager)
    ├── _references.bib          ← BBT auto-export
    ├── notes/                   ← 1 nota por paper (`<citekey>.md`)
    └── pdfs/                    ← symlinks pro Zotero (gitignored)
```

### Papel de cada elemento (mínimo)

| Caminho | Função | Quem mantém |
|---|---|---|
| `README.md` | Tour de 1 página pra humano externo | Pesquisador (raro) |
| `CLAUDE.md` | Persona, stack, dependências, hierarquia de instruções | Pesquisador |
| `project.md` | Texto formal do projeto (tese, hipótese, pilares, RQs, papers planejados, cronograma). É a **escrita-vida** — vira a entrega final. | Pesquisador |
| `protocol.md` | Operacional clínico (coorte, critérios, labels, métricas, splits, ética) | Pesquisador |
| `docs/_index.md` | Catálogo do wiki — uma linha por página existente | Skill `wiki-ingest` |
| `docs/_log.md` | Diário append-only de eventos (ingest, decisão, query) | Skill `wiki-ingest` + manual |
| `docs/decisions/` | ADRs numeradas (`adr-NNNN-*.md`); imutável após aceito | Pesquisador |
| `docs/canvas/project.canvas` | Whiteboard panorâmico (tese, RQs, datasets, ADRs, papers) | Pesquisador |
| `references/_references.bib` | Acervo bibliográfico — fonte única é o Zotero, BBT auto-export | Zotero + BBT |
| `references/notes/<key>.md` | Nota por paper, com callout estruturado (PICOT, método, …) | Skills `paper-manager`, `paper-extract` |
| `.claude/`, `.obsidian/` | Infra técnica (Claude Code + Obsidian leem daqui) | `prumo init` + plugin |

### `.claude/skills/` — infraestrutura, não área de trabalho

`pj_x/.claude/skills/` é onde o **Claude Code** procura as skills pra disparar `/prumo-assist:<nome>`. Tem dois usos:

1. **Cópia local das skills universais** do plugin — preenchida automaticamente por `prumo init` e atualizada por `prumo doctor`. Pesquisador não toca.
2. **Skills específicas do projeto** (opcional) — capabilities que só fazem sentido nesse `pj_*` e não vale promover pro plugin (ex.: `pj_x/.claude/skills/cpu-profile-rsl-2024/`). Vira módulo formal só quando a primeira skill local nascer.

Não é um "fluxo" paralelo no sentido de área de trabalho do pesquisador — é o mesmo fluxo do plugin, materializado dentro do projeto.

---

## Módulos opcionais

Cada módulo é independente. Ative quando o trigger acontecer; não ative antes (YAGNI).

| Módulo | Localização | Trigger |
|---|---|---|
| `extended-wiki` | `docs/wiki/{concepts, entities, sources, findings, <dominio>}/` | Wiki passa de ~20 páginas; há área teórica que merece pasta própria (ex.: `docs/wiki/statistics/`) |
| `brainstorm-pipeline` | `docs/brainstorm/{daily, topics}/` | Projeto ≥3 meses; ideação volumosa; precisa de pipeline `daily → topic → ADR` |
| `peer-review-loop` | `docs/comments/` | Vai submeter / receberá feedback de orientador ou revisor |
| `versioned-milestones` | `docs/<marco>/{<doc>.md, versions/, README.md}` | Há entregas formais (banca, submissão de paper, capítulo de tese) |
| `data-pipeline` | `content/{01_raw, 02_processed}/` + notebooks numerados | Há dados primários + análise tabular/imagem |
| `obsidian-power` | `references/{templates, views}/` + plugins zotero/pandoc/linter | Vault Obsidian é a ferramenta principal de trabalho |
| `specify-workflow` | `docs/superpowers/{specs, plans}/` | Usa skills `superpowers:brainstorming` / `writing-plans` pra design formal |

### Detalhamento dos módulos mais densos

**`brainstorm-pipeline`** — pipeline `daily → topic → ADR → project.md` :

- `daily/YYYY-MM-DD.md` — escrita livre, sem schema, sem lint. Captura e segue.
- `topics/<kebab-case>.md` — promovido quando uma ideia aparece em ≥2 dailies. Tem **tese**, **contras**, **perguntas em aberto**, **status** (aberto/amadurecendo/pronto-para-ADR/arquivado).
- Quando topic fecha → ADR em `docs/decisions/adr-NNNN-*.md`.
- Quando decisão pesa → seção atualizada em `docs/project.md`.

**`extended-wiki`** — quatro tipos canônicos + domínios custom:

- `concepts/` — métodos, abordagens, ideias.
- `entities/` — modelos, datasets, coortes, ferramentas, instituições.
- `sources/` — fontes não-paper (blogs, tutoriais, slides, transcrições).
- `findings/` — resultados arquivados, respostas de `wiki-query` que valeram parar.
- `<dominio>/` — área teórica custom (ex.: `statistics/`, `radiology/`) com `README.md` próprio.

**`versioned-milestones`** — padrão genérico de entrega formal:

```
docs/<marco>/
├── README.md            ← contexto, convenções, trajetória editorial
├── <doc>.md             ← working doc vigente (ex.: projeto.md, paper-2.md)
└── versions/
    └── YYYY-MM-DD-<tag>.md  ← snapshots frozen (ex.: v9-banca-oficial)
```

Pj_piloto_ml usa esse padrão pra `qualification/`. Outros projetos podem usar pra `paper-1/`, `chapter-3/`, etc.

---

## Composições típicas

| Nível | Quem é | Mínimo + módulos |
|---|---|---|
| **L0 — exploratório curto** (≤3 meses) | Estudo de viabilidade, PoC, scoping review rápido | só núcleo mínimo |
| **L1 — paper único** | Submissão única, sem multi-marco | + `peer-review-loop` + `obsidian-power` |
| **L2 — paper com leitura profunda** | Paper que exige RSL ou benchmark amplo | L1 + `extended-wiki` + `data-pipeline` |
| **L3 — tese / dissertação** | Multi-ano, multi-paper, banca, capítulos | tudo + `brainstorm-pipeline` + `versioned-milestones` + `specify-workflow` |

Esses níveis não são prescritivos. São pontos de partida para você compor.

---

## Como evoluir

- **Ative um módulo no momento da dor**, não antes. Sintoma típico: você está prestes a fazer um workaround manual repetidamente — o módulo já existe pra esse padrão.
- **Não desative módulos retroativamente**. Se ativou e não usa mais, deixe ali — o histórico tem valor.
- **Module novo** que não está nesta lista é candidato a ser proposto aqui. Se aparecer em ≥2 projetos, formaliza.
- **Variantes do mínimo** (ex.: cortar `protocol.md` se o projeto não é clínico) são aceitas — esta lista é guia, não lei.

Ver também: [[actions-by-context|Contextos → ações]] e [[journey|Canvas de jornada]].
