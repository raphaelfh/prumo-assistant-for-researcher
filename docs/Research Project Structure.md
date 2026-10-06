---
title: Estrutura de Projeto de Pesquisa
tags: [structure, template, journey]
---

# Estrutura de Projeto de Pesquisa

> Modelo **"mínimo + módulos"** pros projetos `pj_*`. Núcleo único pra todos; módulos ativados por necessidade real, coerente com [[constitution#VI · YAGNI militante]]. Documento vivo — ajuste conforme os projetos forem ensinando.

---

## Núcleo mínimo

Sempre presente, qualquer que seja o projeto (paper único, exploratório, tese).
`docs/` é a **raiz única de leitura** — bibliografia e escopos de escrita vivem
todos abaixo dela (ADR-0022). Saída de máquina fica fora de `docs/`, na raiz do
projeto: `build/exports/` (docx/pdf exportados, gitignorado) e `reviews/<slug>/`
(estado de trabalho do ciclo de revisão docx↔CriticMarkup).

```
pj_<nome>/
├── README.md                    ← entry point humano (1 página)
├── CLAUDE.md                    ← persona + escopo + deps do plugin
├── pyproject.toml               ← deps Python
├── .claude/                     ← infra automática (gerada por `prumo init`)
│   ├── pj_config.toml           ← sentinela do projeto (`find_pj_root`)
│   ├── paper_extraction.md
│   ├── rules/{documentation.md, project_context.md}
│   └── skills/                  ← só skills próprias do projeto, com nome que não seja do PAR
├── build/exports/               ← saída de `prumo write export` (docx/pdf), gitignorada
├── reviews/<slug>/              ← estado do ciclo `prumo write review` (review.md, events.yaml)
└── docs/                        ← RAIZ ÚNICA DE LEITURA
    ├── _index.md                ← MOC content-oriented (catálogo)
    ├── _log.md                  ← append-only (ingests, decisões, queries)
    ├── project_guide.md         ← guia enxuto (Objetivo/Hipótese/Research Questions)
    ├── templates/                ← modelos (ex.: `reference.docx` do Pandoc)
    ├── references/                ← DO PROJETO — bibliografia (ADR-0022)
    │   ├── .gitignore
    │   ├── _index.md             ← MOC do acervo (mantido por `paper library`)
    │   ├── _note_template.md     ← modelo de nota de leitura
    │   ├── _references.bib       ← BBT auto-export
    │   ├── papers/<citekey>/     ← 1 pasta por paper (layout α, ADR-0008/ADR-0023)
    │   └── pdfs/<citekey>.pdf    ← symlinks pro Zotero (gitignorado)
    └── studies/<slug>/            ← O ESCOPO — unidade de escrita (ADR-0024)
        ├── notes/                 ← prosa humana, inclusive findings (`type: finding`)
        ├── writing/               ← o produto (drafts; `protocol.md` quando `clinical` ativo)
        └── decisions/             ← ADRs do escopo, append-only
```

### Papel de cada elemento (mínimo)

| Caminho | Função | Quem mantém |
|---|---|---|
| `README.md` | Tour de 1 página pra humano externo | Pesquisador (raro) |
| `CLAUDE.md` | Persona, stack, dependências, hierarquia de instruções | Pesquisador |
| `.claude/pj_config.toml` | Sentinela do projeto — é o que `find_pj_root` procura subindo o filesystem | `prumo init` |
| `project_guide.md` | Guia enxuto do projeto — **Objetivo**, **Hipótese**, **Research Questions**. Orienta o trabalho, não é a entrega final (escrita formal vive nos módulos `peer-review-loop`/`versioned-milestones`). | Pesquisador |
| `docs/_index.md` | Catálogo do wiki — uma linha por página existente | Modo `wiki ingest` |
| `docs/_log.md` | Diário append-only de eventos (ingest, decisão, query) | Modo `wiki ingest` + manual |
| `docs/references/_references.bib` | Acervo bibliográfico — fonte única é o Zotero, BBT auto-export | Zotero + BBT |
| `docs/references/papers/<key>/` | Pasta por paper, com `_meta.md` (callout estruturado: PICOT, método, …) e `_extract.md` (`_annotations.md`: legado, se existir) | Modos `paper library`, `paper extract` |
| `docs/studies/<slug>/notes/` | Prosa humana do escopo, inclusive findings (nota com `type: finding` — ADR-0023) | Pesquisador + modos `wiki query`/`wiki study`/`paper extract` |
| `docs/studies/<slug>/writing/` | O produto do escopo — drafts (`bibliography:` sempre `../../../references/_references.bib`) | Pesquisador + família `write-*` |
| `docs/studies/<slug>/decisions/` | ADRs do escopo (`adr-NNNN-*.md`); imutável após aceito | Pesquisador |
| `build/exports/` | Saída de `prumo write export` (docx/pdf) — gitignorada, regenerável | `prumo write export` |
| `reviews/<slug>/` | Estado do ciclo `prumo write review` (`review.md`, `events.yaml`, `review-comments.yaml`) | `prumo write review` |
| `.claude/` | Infra técnica (Claude Code lê daqui) | `prumo init` + plugin |

### `.claude/skills/` — infraestrutura, não área de trabalho

`pj_x/.claude/skills/` é lugar só de **skills próprias do projeto** (opcional): capabilities que só fazem sentido nesse `pj_*` e não vale promover pro plugin (ex.: `pj_x/.claude/skills/cpu-profile-rsl-2024/`), com nome que não seja de skill do PAR. As skills do PAR vêm do plugin (`/par:<nome>`), sem cópia no projeto. Vira módulo formal só quando a primeira skill local nascer.

Não é área de trabalho do pesquisador: o diretório só guarda o que é do projeto, e o fluxo do PAR continua vindo do plugin.

---

## Módulos opcionais

Duas categorias bem diferentes — não confundir uma com a outra:

- **Módulos com `_module.toml`** — ativados por `prumo add <nome>` (overlay não-destrutivo), com `anchor` que o CLI usa pra detectar se já estão ativos. São os únicos cinco que existem hoje.
- **Convenções documentadas** — padrões que o pesquisador aplica à mão quando o trigger acontece; não têm `_module.toml` nem comando `prumo add`. Se uma convenção aparecer em ≥2 projetos com a mesma forma, ela é candidata a virar módulo formal.

### Módulos (`prumo add <nome>`)

Cada módulo é independente. Ative quando o trigger acontecer; não ative antes (YAGNI).

| Módulo | Localização | Trigger |
|---|---|---|
| `code` | **pacote instalável** em `src/<pkg>/` + `tests/` espelhado + `pyproject.toml` com `[build-system]` — ative com `prumo add code` | O projeto vai ter script ou pacote Python próprio |
| `data` | `content/01_raw/` (somente leitura) + `content/02_processed/` — ative com `prumo add data` | Entra o primeiro dataset no projeto |
| `notebooks` | `notebooks/<escopo>/` (fora da raiz de leitura `docs/`) — ative com `prumo add notebooks` (`--scope <slug>` se houver mais de um escopo); aceita **marimo** (`.py`, padrão) e Jupyter (`.ipynb`), com rule `.claude/rules/notebooks.md` e alvos `nb-edit`/`nb-run`/`nb-convert` | Primeira análise exploratória em notebook |
| `ml` | `.claude/rules/ml_stack.md` (stack, governança de código) + notebook de EDA (`.ipynb`) — ative com `prumo add ml` | Vai treinar modelos ou fazer análise tabular/de imagem |
| `clinical` | `docs/studies/<slug>/writing/protocol.md` + `docs/templates/` (projeto CEP, plano estatístico/SAP, dicionário de dados) — ative com `prumo add clinical` (`--scope <slug>` se houver mais de um escopo) | Estudo clínico/empírico com coorte e submissão a CEP |

### Onde o código mora (módulo `code`)

O `pj_*` com o módulo `code` é um **pacote instalável** ([ADR-0027](adr/adr-0027-pj-instalavel.md)):
`uv sync` instala o projeto em editable no `.venv`, e o import de código próprio resolve por
instalação — não por `cwd` nem por `sys.path`.

```
pj_prolapse_polymorphism/
├── src/prolapse_polymorphism/     ← pacote de import (nome do projeto sem `pj_`)
│   ├── cohort.py                  ← COMPARTILHADO entre estudos e notebooks
│   └── polymorphism/prep.py       ← só deste estudo
├── tests/                         ← espelha src/
├── notebooks/polymorphism/        ← notebook do estudo
└── docs/studies/01_polymorphism/  ← prosa, draft, ADR
```

| O que | Onde |
|---|---|
| Código usado por ≥2 estudos ou notebooks | `src/<pkg>/<modulo>.py` |
| Código de um estudo só | `src/<pkg>/<estudo>/<modulo>.py` |
| Notebook | `notebooks/<estudo>/` (marimo `.py` ou Jupyter `.ipynb`) |
| Prosa, draft, ADR | `docs/studies/<slug>/` |

A raiz do pacote é o compartilhado de propósito: o caminho curto pertence ao código
reutilizável. O nome do subpacote sai do slug de `docs/studies/` sem o prefixo numérico
(`01_polymorphism` → `polymorphism`); o slug da escrita não muda.

**Não** existe `scripts/` nem um segundo tree `studies/` na raiz — código auxiliar de um
estudo é `src/<pkg>/<estudo>/`. E **não** há configuração de IDE a versionar: com o pacote
instalado, PyCharm e VS Code resolvem pelo interpretador do `.venv`, sem source root e sem
`python.analysis.extraPaths`. `prumo doctor` acusa `projeto_nao_instalavel`,
`pacote_sem_nome`, `sys_path_hack` e `projeto_nao_sincronizado`.

### Convenções documentadas (sem `_module.toml`)

| Convenção | Localização | Trigger |
|---|---|---|
| `extended-wiki` | `docs/studies/<escopo>/notes/<domínio>/` | Uma área temática do escopo junta páginas suficientes pra merecer subpasta própria (ex.: `notes/statistics/`) |
| `brainstorm-pipeline` | `docs/brainstorm/{daily, topics}/` | Projeto ≥3 meses; ideação volumosa; precisa de pipeline `daily → topic → ADR` |
| `peer-review-loop` | `docs/comments/` | Vai submeter / receberá feedback de orientador ou revisor |
| `versioned-milestones` | `docs/<marco>/{<doc>.md, versions/, README.md}` | Há entregas formais (banca, submissão de paper, capítulo de tese) |
| `specify-workflow` | `docs/superpowers/{specs, plans}/` | Usa skills `superpowers:brainstorming` / `writing-plans` pra design formal |

### Detalhamento das convenções mais densas

**`brainstorm-pipeline`** — pipeline `daily → topic → ADR → project_guide.md` :

- `daily/YYYY-MM-DD.md` — escrita livre, sem schema, sem lint. Captura e segue.
- `topics/<kebab-case>.md` — promovido quando uma ideia aparece em ≥2 dailies. Tem **tese**, **contras**, **perguntas em aberto**, **status** (aberto/amadurecendo/pronto-para-ADR/arquivado).
- Quando topic fecha → ADR em `docs/studies/<slug>/decisions/adr-NNNN-*.md`.
- Quando decisão pesa → seção atualizada em `docs/project_guide.md`.

**`extended-wiki`** — subpasta temática dentro do `notes/` de um escopo. Não há pasta por tipo de página: `concept`, `entity`, `finding` e `source` são o campo `type:` do frontmatter (ADR-0025), então o que sobra pra agrupar é assunto, não taxonomia.

- `docs/studies/<escopo>/notes/<domínio>/` — área teórica custom (ex.: `statistics/`, `radiology/`) com `README.md` próprio.
- Continua sob o alcance das ferramentas: `prumo wiki stats` conta essas páginas no `notes/` do escopo e `prumo wiki lint` audita citekey, link morto e órfã dentro delas. A única checagem que não desce é `no_frontmatter`, que olha só os filhos diretos de `notes/`, `writing/` e `decisions/`.

**`versioned-milestones`** — padrão genérico de entrega formal:

```
docs/<marco>/
├── README.md            ← contexto, convenções, trajetória editorial
├── <doc>.md             ← working doc vigente (ex.: projeto.md, paper-2.md)
└── versions/
    └── YYYY-MM-DD-<tag>.md  ← snapshots frozen (ex.: v9-banca-oficial)
```

Pj_multimodal_ml_phd usa esse padrão pra `qualification/`. Outros projetos podem usar pra `paper-1/`, `chapter-3/`, etc.

---

## Composições típicas

| Nível | Quem é | Mínimo + módulos |
|---|---|---|
| **L0 — exploratório curto** (≤3 meses) | Estudo de viabilidade, PoC, scoping review rápido | só núcleo mínimo |
| **L1 — paper único** | Submissão única, sem multi-marco | + `peer-review-loop` |
| **L2 — paper com leitura profunda** | Paper que exige RSL ou benchmark amplo | L1 + `extended-wiki` + `ml` |
| **L3 — tese / dissertação** | Multi-ano, multi-paper, banca, capítulos | tudo + `brainstorm-pipeline` + `versioned-milestones` + `specify-workflow` |

Esses níveis não são prescritivos. São pontos de partida para você compor.

---

## Como evoluir

- **Ative um módulo no momento da dor**, não antes. Sintoma típico: você está prestes a fazer um workaround manual repetidamente — o módulo já existe pra esse padrão.
- **Não desative módulos retroativamente**. Se ativou e não usa mais, deixe ali — o histórico tem valor.
- **Module novo** que não está nesta lista é candidato a ser proposto aqui. Se aparecer em ≥2 projetos, formaliza.
- **Variantes do mínimo** (ex.: ativar o módulo `clinical` só quando o projeto for clínico) são aceitas — esta lista é guia, não lei.

Ver também: [[journey|Canvas de jornada]].
