# Roadmap & Architecture Guide

> Documento didático para quem chega novo ao repo. Explica **o quê**, **por quê**
> e **onde** cada peça vive — e o caminho imaginado pra crescer sem perder a
> alma do projeto.

## 1. Tagline e escopo

> **prumo-assist** — Knowledge, bibliography & academic writing assistant for
> clinical research. Lives between Zotero, Obsidian, and your agent-host.

**É:** um assistente de pesquisa pra pesquisador clínico. Foca em três
atividades que consomem o dia: gerir conhecimento (wiki), gerir bibliografia
(Zotero ↔ notas) e escrever (export pra Pandoc/Typst/PDF + revisão crítica).

**Não é:** uma IDE de código, um framework de modelagem, um runner de pipelines
de dados. Para isso, use Claude Code, Cursor ou seu Jupyter.

## 2. Quatro pilares

```
┌─────────────────┐  ┌────────────────┐  ┌──────────────┐  ┌────────────────┐
│  📚 Bibliografia│  │  🧠 Conhecimento│  │  📥 Captura  │  │  ✍️  Escrita    │
│  (Zotero+BBT)   │  │  (Obsidian wiki)│  │  (router)    │  │  (Pandoc/Typst)│
│                 │  │                 │  │              │  │                │
│  paper sync     │  │  wiki ingest    │  │  capture     │  │  write export  │
│  paper extract  │  │  wiki query     │  │  <input>     │  │  write compose │
│  paper find     │  │  wiki lint      │  │              │  │  write watch   │
│  paper graph    │  │  wiki index     │  │              │  │  write peer-   │
│  paper lint     │  │  wiki stats     │  │              │  │     review     │
│  paper set-     │  │                 │  │              │  │                │
│   primary       │  │                 │  │              │  │                │
└────────┬────────┘  └────────┬────────┘  └──────┬───────┘  └────────┬───────┘
         │                    │                  │                    │
         └────────────────────┼──────────────────┴────────────────────┘
                              │
                       ┌──────▼──────┐
                       │   prumo     │  ← CLI Python instalável (uv tool install)
                       │   (Typer)   │
                       └──────┬──────┘
                              │
                ┌─────────────▼─────────────┐
                │      core/  (transversal) │  ← parser bib, csl, obsidian,
                │                           │     skills, provenance, output
                └───────────────────────────┘
```

## 3. Princípios não-negociáveis

1. **Lógica em um lugar só.** Cada operação determinística (sync, lint, export)
   tem **uma** implementação em `domains/<X>/`. CLI, Python API e skill são
   **fachadas finas** sobre ela. Adicionar um host (Cursor, Codex) nunca
   duplica lógica.

2. **DRY de metadata.** Toda skill tem **um único** arquivo de metadata: o
   frontmatter rico no `SKILL.md` (campo `prumo:`). Sem `manifest.yaml`
   paralelo. Sem versão duplicada em outro lugar. `_version.py` é fonte única.

3. **Determinístico ≠ agêntico.** Quando dá pra fazer com regex, AST, ou
   subprocess, **fazemos**. LLM só onde julgamento humano é necessário (extrair
   PICOT de PDF, sintetizar resposta de wiki, revisar draft). Reduz custo,
   aumenta reprodutibilidade.

4. **Skills universais.** `SKILL.md` é o formato canônico de Anthropic +
   comunidade. Quem usar Cursor, Codex ou Gemini só precisa de um adapter em
   `integrations/` — o conteúdo das skills nunca muda.

5. **Provenance em todo output.** Bloco `_meta` (run_id, modelo, prompt
   version, input hash, timestamp) inline em qualquer artefato gerado. Trace
   JSONL local. Auditável daqui a 5 anos sem SaaS de terceiros.

6. **Forward-only schemas.** `PaperCallout/v2` lê outputs de `v1`. Migrações
   explícitas em `schemas/migrations.py`. Nunca quebrar dado antigo.

7. **YAGNI militante.** Hooks, cache, lockfile, evals, multi-host, packs —
   tudo está **desenhado** mas só **implementado** quando dor real justifica.
   Adiar é mais sustentável do que adicionar especulativamente.

## 4. Layout do repositório (e por quê)

```
prumo-assist/
├── pyproject.toml             ← entry point: prumo = prumo_assist.cli:app
├── CHANGELOG.md
├── LICENSE
├── README.md
├── ROADMAP.md                 ← este arquivo
│
├── .claude-plugin/            ← preserva compat com plugin marketplace
│   ├── plugin.json            ← versão lê de _version.py (1 fonte)
│   └── marketplace.json
│
├── src/prumo_assist/
│   ├── _version.py            ← FONTE ÚNICA de versão
│   ├── __init__.py            ← exceções (PrumoError, ConfigError, ...)
│   ├── api.py                 ← Python API pública (notebook gateway)
│   ├── cli.py                 ← Typer root (init, doctor, skills)
│   │
│   ├── core/                  ← TRANSVERSAL — sem lógica de domínio
│   │   ├── config.py          ← carrega pj_config.toml com defaults
│   │   ├── bib.py             ← parser BBT tolerante (3 delimitadores)
│   │   ├── csl.py             ← resolve estilos CSL do Zotero
│   │   ├── obsidian.py        ← Obsidian → Pandoc Markdown normalizer
│   │   ├── skills.py          ← parser SKILL.md + SkillRegistry
│   │   ├── provenance.py      ← _meta block + JSONL trace local
│   │   └── output.py          ← Console (Rich + JSON dual)
│   │
│   ├── domains/               ← NEGÓCIO — uma pasta por pilar
│   │   ├── paper/             ← (PR1)
│   │   ├── wiki/              ← (PR2)
│   │   ├── capture/           ← (PR2)
│   │   └── write/             ← (PR2)
│   │
│   └── integrations/          ← adapters por agent-host
│       ├── base.py            ← BaseIntegration (interface)
│       └── claude_code/       ← MVP: único host
│           └── installer.py   ← copia skills pra .claude/skills/
│
├── skills/                    ← FONTE CANÔNICA de skills (universal SKILL.md)
│   ├── paper-extract/SKILL.md
│   ├── wiki-{ingest,query,lint}/SKILL.md
│   ├── peer-review/SKILL.md   ← entra no PR2
│   └── ... (existentes preservadas)
│
├── packs/                     ← bundles de skills+templates+commands (PR3+)
│   └── core/                  ← MVP
│
├── templates/
│   └── pj_base/               ← template do pj_*; consumido por `prumo init`
│
├── tests/                     ← unit + integration; VCR cassettes (futuro)
│
└── docs/                      ← MkDocs (PR3)
```

### Por que `core/` e `domains/` são separados

Regra mental simples: **`core/` nunca importa de `domains/`; `domains/` pode
importar de `core/`**. Isso garante que dá pra arrancar um domínio inteiro
(spin-off em outro pacote) sem quebrar a fundação. E garante que um teste de
`core/bib.py` nunca vai ficar dependente de Pandoc estar instalado.

### Por que `skills/` está fora de `src/`

Skills são **conteúdo**, não código Python. Vivem em `skills/` na raiz do
repo, são consumidas pelo CLI quando invoca `integrations/<host>/install()`.
Quando publicarmos packs em separado, `skills/` da raiz é o `core` pack;
`packs/radiology/skills/` é um pack adicional. Manter na raiz facilita pull
requests de comunidade (não precisa entender Python pra contribuir uma skill).

## 5. Como dados fluem (caso típico: extrair um paper)

```
Pesquisador no Claude Code:                       ───────────────┐
   /paper-extract @smith2024                                     │
                                                                 │
                   ▼                                             │
   Claude Code lê pj_x/.claude/skills/paper-extract/SKILL.md     │
   instalada anteriormente por `prumo init`                      │
                                                                 │
                   ▼                                             │
   Claude executa o prompt da skill,                             │
   chamando ferramentas (Read, Write) e/ou MCP qmd               │
                                                                 │
                   ▼                                             │
   Output estruturado (PaperCallout/v1) escrito em               │
   references/notes/smith2024.md (callout delimitado)            │
   COM bloco _meta no frontmatter                                │
                                                                 │
                   ▼                                             │
   .prumo/traces/YYYY-MM-DD.jsonl ganha eventos da execução      │
   (start, tool_call, end) — auditável localmente   ─────────────┘
```

**Para uso headless** (CI, batch de 200 papers): `prumo paper extract --batch`
shell-outa pra `claude -p`, mesma skill, mesmo output. Sem código duplicado.

## 6. Status (atualizado 2026-04-28)

| PR | Status | Conteúdo |
|---|---|---|
| **PR0** | ✅ entregue | Fundação `core/` + Typer + `prumo init/doctor/skills` + integration `claude_code` + templates |
| **PR1** | ✅ entregue | Domínio `paper` completo (7 subcomandos, 6 scripts migrados + `lint.py` novo + schemas v1) |
| **PR2** | ✅ entregue | Domínios `wiki`, `capture`, `write` (4 subcomandos cada) |
| **PR3** | ✅ entregue | Skill `peer-review` + `CITATION.cff` + CHANGELOG + 97 testes |
| PR4 | 📌 backlog | Pack `clinical-checklists` (TRIPOD+AI, CLAIM, CONSORT-AI, PRISMA, STROBE) |
| PR5 | 📌 backlog | Multi-host (Cursor, Codex, Gemini, Jupyter integrations) |

## 7. PR0 — fundação (referência histórica)

| Arquivo | Status | Papel |
|---|---|---|
| `pyproject.toml` | NEW | Build (hatchling), deps, ruff, mypy, pytest, entry `prumo` |
| `_version.py` | NEW | Fonte única de versão |
| `__init__.py` | NEW | Hierarquia de exceções `PrumoError` |
| `core/config.py` | TRANSFORM | de `_project_config.py` (1 mudança: `ConfigError`) |
| `core/bib.py` | TRANSFORM | de `_bib.py` (zero mudança comportamental) |
| `core/csl.py` | TRANSFORM | de `_csl.py` (1 mudança: hierarquia `ConfigError`) |
| `core/obsidian.py` | TRANSFORM | de `_obsidian_md.py` (zero mudança) |
| `core/skills.py` | NEW | Parser SKILL.md (frontmatter rico) + registry |
| `core/provenance.py` | NEW | `_meta` block + `TraceWriter` JSONL |
| `core/output.py` | NEW | Console Rich/JSON dual |
| `cli.py` | NEW | Typer root: `init`, `doctor`, `skills`, `--version` |
| `api.py` | NEW (stub) | Python API; preenche em PR1+ |
| `integrations/base.py` | NEW | Interface `BaseIntegration` |
| `integrations/claude_code/installer.py` | NEW | Adapter pra `.claude/skills/` |
| `templates/pj_base/` | NEW | Cópia de `pj_projeto` **sem** vendor scripts |
| `tests/unit/test_*.py` | NEW | 7 arquivos cobrindo cada módulo de core/ + CLI |
| `.github/workflows/ci.yml` | NEW | ruff + mypy strict + pytest matrix 3.11/3.12 |

**Não toca:** `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
`skills/*/SKILL.md`, `agents/*.md`. O plugin atual continua funcionando no
marketplace inalterado durante toda a fase 1-3.

## 7. Roadmap pós-PR0

### PR1 — Domínio `paper` (~2 sem)

Migrar `paper_sync.py` (294 ll), `cite_graph.py` (80), `cite_lookup.py` (99),
`paper_extract.py` (147), `sync_zotero_pdfs.py` (84), `sync_zotero_annotations.py`
(367) **sem reescrita**: só fixar imports, separar lógica de IO, adicionar
testes em `tests/unit/test_paper_*.py`.

Skill `paper-extract/SKILL.md` ganha frontmatter rico (`prumo: schema:
PaperCallout/v1, version: 1.0.0`) + `tests/golden/` com 5 PDFs reais.

**Gate:** `prumo paper sync` num vault real reproduz output do Makefile.

### PR2 — Domínios `wiki`, `capture`, `write` (~2-3 sem)

`wiki/`: migra parte determinística de `wiki-lint`; runners delegam ao
`claude -p` pras agênticas (`ingest`, `query`).

`capture/`: router fino que detecta tipo (URL/DOI/arXiv/PDF) e chama
`paper.sync`, `wiki.ingest` ou `paper.extract`.

`write/`: 70% pronto (`export_page.py`, `extract_comments.py`, `_csl.py` já
existem). Comandos `prumo write {export, compose, watch, preview}`. Skill
nova `peer-review/` (única agêntica do pilar).

**Gate:** `prumo write export ch.qmd --to pdf` em vault real; `prumo write
peer-review draft.md` produz JSON contra schema.

### PR3 — Hardening + release (~1 sem)

Trace polish, lockfile básico, MkDocs site, CITATION.cff, Zenodo DOI workflow,
v0.2.0 publicado. `uv tool install prumo-assist` funciona.

### Fases pós-MVP (cada uma justificada por dor real, **nunca antes**)

| Fase | Adição | Trigger |
|---|---|---|
| 2.1 | Pack `clinical-checklists` (TRIPOD+AI, CLAIM, CONSORT-AI, PRISMA, STROBE, SPIRIT) | Você reportar resultados de modelo de predição |
| 2.2 | Pack `schematics` (CONSORT/PRISMA flow via Mermaid+TikZ) | Submissão de paper |
| 2.3 | Pack `venue-clinical` (NEJM, JAMA, Lancet, Nature Medicine, Radiology) | Submeter pra venue específico |
| 2.4 | Pack `thesis` (chapter-from-findings, snapshot, defense-summary) | Aproximação da defesa |
| 2.5 | `kg/` module (grafo de papers, paths de citação) | Wiki passar de 50+ papers |
| 3.0 | `integrations/{cursor,codex,gemini,jupyter}/` | Colega adotar host diferente |
| 3.1 | Hooks system (PII redaction, cost gates) | Houver ≥3 cross-cutting concerns |
| 3.2 | Eval gate em CI | Drift de prompt observado em prod |

## 8. Decisões deliberadas que NÃO foram tomadas no PR0

- **Sem hooks system.** Trace e provenance são chamadas explícitas em
  `domains/`, não decoradores plugáveis. Quando ≥3 cross-cutting forem
  competir, refatora.
- **Sem cache de LLM.** Idempotência por hash do input fica no PR1+ quando
  `paper-extract` for o primeiro consumidor real.
- **Sem lockfile.** Faz sentido quando packs externos virarem realidade.
- **Sem multi-host.** Um adapter (`claude_code`) prova a interface; expandir
  é trivial depois (não é refactor, é adição).
- **Sem packs externos.** Único pack hoje é o implícito da raiz (`skills/`
  na raiz). Estrutura `packs/<name>/` está prevista mas vazia.
- **Sem MkDocs publicado.** Documento aqui em Markdown vive no repo. Site só
  no PR3, quando `prumo --version` justificar.

## 9. Como contribuir (resumo pra quem chega depois)

1. **Para uma skill nova:** crie `skills/<nome>/SKILL.md` com frontmatter rico,
   `prompt.md` opcional, `tests/golden/` opcional. Não precisa tocar Python.

2. **Para um comando determinístico novo:** adicione ao domínio certo
   (`domains/<X>/<op>.py`); exponha via `domains/<X>/cli.py` e `api.py`. Teste
   em `tests/unit/test_<X>_<op>.py`.

3. **Para um host novo (Cursor, Codex, ...):** subclasse `BaseIntegration`
   em `integrations/<host>/installer.py`, registre em `integrations/__init__.py`.
   Skills universais: zero mudança.

4. **Para um pack novo:** `packs/<nome>/pack.toml` + `packs/<nome>/skills/`.
   `prumo pack install <nome>` carrega.

## 10. Glossário rápido

- **Skill** — capability agêntica empacotada como `SKILL.md` universal.
- **Pack** — bundle versionado de skills + templates + commands.
- **Integration** — adapter que traduz skills do formato canônico pro layout
  específico de um agent-host (Claude Code, Cursor, Codex, ...).
- **Provenance** — bloco `_meta` em todo output + trace JSONL local.
- **`pj_*`** — projeto de pesquisa do usuário; vault Obsidian + dependências
  declaradas no `pyproject.toml` local.
- **Determinismo** — `agentic` (LLM faz julgamento), `deterministic` (Python
  puro), `hybrid` (mistura, ex: `wiki-lint`).
- **Forward-only schema** — `v2` adiciona campos; nunca remove ou redefine.
  Outputs antigos sempre legíveis.
