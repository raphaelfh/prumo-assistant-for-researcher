# Architecture

> Documento de orientação para quem chega novo ao repo: **o quê** e **onde**. Os **porquês** moram em [`docs/constitution.md`](docs/constitution.md) (princípios) e [`docs/adr/`](docs/adr/) (decisões registradas). Status e fases em [`ROADMAP.md`](ROADMAP.md); histórico narrativo em [`CHANGELOG.md`](CHANGELOG.md).

## Tagline e escopo

> **prumo-assist** — Knowledge, bibliography & academic writing assistant for clinical research. Lives between Zotero, Obsidian, and your agent-host.

**É:** um assistente de pesquisa pra pesquisador clínico. Cobre gerir conhecimento (wiki), gerir bibliografia (Zotero ↔ notas), formalizar o protocolo (PICOT), capturar fontes e escrever (export Pandoc/Typst + revisão crítica).

**Não é:** uma IDE de código, um framework de modelagem, um runner de pipelines de dados.

## Princípios

Os princípios não-negociáveis (lógica em um lugar só, determinístico antes de agêntico, skills universais, forward-only schemas, provenance, YAGNI, derivados gerados) estão na [`docs/constitution.md`](docs/constitution.md) — fonte única, numeração romana I–VII, com processo formal de emenda. Este arquivo não os duplica.

## Cinco domínios + core

```
┌──────────────┐ ┌──────────────┐ ┌────────────┐ ┌──────────────┐ ┌──────────────┐
│ 📚 paper     │ │ 🧠 wiki      │ │ 📥 capture │ │ 🧪 protocol  │ │ ✍️ write      │
│ (Zotero+BBT) │ │ (Obsidian)   │ │ (router)   │ │ (PICOT+ADR)  │ │ (Pandoc/Typst)│
│              │ │              │ │            │ │              │ │              │
│ sync · graph │ │ lint · index │ │ capture    │ │ propagate    │ │ export       │
│ find · lint  │ │ stats        │ │ <input>    │ │ diff         │ │ compose      │
│ set-primary  │ │              │ │            │ │              │ │ list-styles  │
│ sync-pdfs    │ │              │ │            │ │              │ │ extract-     │
│ sync-        │ │              │ │            │ │              │ │   comments   │
│  annotations │ │              │ │            │ │              │ │ disclosure   │
│ sync-notes   │ │              │ │            │ │              │ │ list-        │
│ sync-all     │ │              │ │            │ │              │ │   templates  │
│ migrate-     │ │              │ │            │ │              │ │              │
│  layout      │ │              │ │            │ │              │ │              │
└──────┬───────┘ └──────┬───────┘ └─────┬──────┘ └──────┬───────┘ └──────┬───────┘
       └────────────────┴───────────────┼────────────────┴────────────────┘
                                 ┌──────▼──────┐
                                 │   prumo     │  ← CLI (Typer); raiz: init ·
                                 │             │     doctor · skills · add · capture
                                 └──────┬──────┘
                                 ┌──────▼──────────────────────┐
                                 │ core/ (transversal)         │
                                 │ bib · csl · obsidian ·      │
                                 │ skills · paths · cli_op ·   │
                                 │ output · deps · note_paths ·│
                                 │ scaffold · config ·         │
                                 │ provenance*                 │
                                 └─────────────────────────────┘
```

\* `core/provenance.py` está desenhado mas ainda não ligado em todos os produtores — ver constitution V e ROADMAP.

## Layout do repositório

```
prumo-assist/
├── pyproject.toml             ← entry point: prumo = prumo_assist.cli:app;
│                                 force-include: templates/ e skills/ no wheel (ADR-0002)
├── CLAUDE.md / AGENTS.md      ← guia do repo pra agentes (AGENTS.md é symlink)
├── .claude/rules/             ← regras modulares (code, release)
├── ARCHITECTURE.md            ← este arquivo (what/where)
├── ROADMAP.md · CHANGELOG.md · RELEASING.md · README.md · CITATION.cff · LICENSE
│
├── .claude-plugin/            ← plugin.json + marketplace.json (self-hosting, ADR-0010)
├── .mcp.json                  ← MCP qmd — config do projeto E do plugin distribuído
├── .github/
│   ├── workflows/             ← ci.yml (lint+types+test+índices) · validate-manifests.yml
│   ├── schemas/               ← schemas vivos do validador de plugin (ADR-0010)
│   └── scripts/               ← sync_manifest_version.py · validate_manifests.py · gen_indexes.py
│
├── src/prumo_assist/
│   ├── _version.py            ← FONTE ÚNICA de versão (constitution VII)
│   ├── __init__.py            ← hierarquia de exceções (PrumoError, ...)
│   ├── api.py                 ← Python API pública (SemVer)
│   ├── cli.py                 ← Typer root: init · doctor · skills · add (+ capture)
│   ├── _filters/              ← filtros Lua vendorados do Pandoc (zotero_live_docx.lua)
│   ├── core/                  ← transversal; NUNCA importa domains/ (ADR-0005)
│   ├── domains/               ← paper · wiki · capture · protocol · write
│   │   └── <X>/               ← cli.py + api.py + <op>.py + schemas/v1.py (ADR-0006)
│   └── integrations/          ← adapters por agent-host (claude_code)
│
├── skills/                    ← 14 skills (SKILL.md = única metadata, ADR-0003)
├── templates/
│   ├── pj_base/               ← núcleo mínimo copiado por `prumo init`
│   └── modules/{clinical,ml}/ ← overlays opt-in (`prumo add`), self-describing (_module.toml)
│
├── tests/unit/                ← espelha domains/ 1:1
└── docs/                      ← vault Obsidian: constitution · adr/ · canvases ·
    └── superpowers/           ← specs/ (não-perecíveis) + plans/ + plans/archive/
```

## Como dados fluem (caso típico: extrair um paper)

```
/prumo-assist:paper-extract @smith2024
        ▼
Claude Code carrega skills/paper-extract/SKILL.md (instalada via plugin)
        ▼
A skill valida pré-requisitos (Bash), lê config (core/config.py),
despacha subagent que lê o PDF com a tool Read
        ▼
O JSON extraído é aplicado pelo backend determinístico
(domains/paper/callout.py) dentro do bloco delimitado (ADR-0009) em
references/notes/smith2024/_extract.md  — layout α (ADR-0008)
        ▼
_meta.md ganha extracted_at / extracted_template_hash (staleness por hash)
```

## Como contribuir

1. **Skill nova:** crie `skills/<nome>/SKILL.md` com frontmatter rico (`prumo:`); não precisa tocar Python. Rode `uv run python .github/scripts/gen_indexes.py` para atualizar os catálogos.
2. **Comando determinístico novo:** `domains/<X>/<op>.py` + exposição em `domains/<X>/cli.py` (via `cli_run`) + re-export em `domains/<X>/api.py` + teste em `tests/unit/<X>/test_<op>.py`.
3. **Host novo (Cursor, Codex, ...):** subclasse `BaseIntegration` em `integrations/<host>/installer.py`. Skills universais: zero mudança. (Trigger no ROADMAP, fase 3.0.)
4. **Decisão estrutural:** registre em `docs/adr/adr-NNNN-slug.md` e cite no PR.

## Glossário rápido

- **Skill** — capability agêntica empacotada como `SKILL.md` universal.
- **Integration** — adapter do formato canônico pro layout de um agent-host.
- **`pj_*`** — projeto de pesquisa do usuário; vault Obsidian + `.claude/` scaffoldado por `prumo init`.
- **Determinismo** — `agentic` | `deterministic` | `hybrid` (frontmatter `prumo.determinism`).
- **Layout α** — `references/notes/<citekey>/` com `_meta/_extract/_annotations/note__*` (ADR-0008).
- **Bloco delimitado** — região machine-owned `<!-- x:begin -->…<!-- x:end -->` (ADR-0009).
