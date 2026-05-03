# Architecture

> Documento de orientação para quem chega novo ao repo. Cobre **o quê**, **por quê** e **onde** cada peça vive. O que muda a cada release fica em [`ROADMAP.md`](ROADMAP.md); o histórico narrativo fica em [`CHANGELOG.md`](CHANGELOG.md).

## Tagline e escopo

> **prumo-assist** — Knowledge, bibliography & academic writing assistant for clinical research. Lives between Zotero, Obsidian, and your agent-host.

**É:** um assistente de pesquisa pra pesquisador clínico. Foca em três atividades que consomem o dia: gerir conhecimento (wiki), gerir bibliografia (Zotero ↔ notas) e escrever (export pra Pandoc/Typst/PDF + revisão crítica).

**Não é:** uma IDE de código, um framework de modelagem, um runner de pipelines de dados. Para isso, use Claude Code, Cursor ou seu Jupyter.

## Quatro pilares

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

## Princípios não-negociáveis

1. **Lógica em um lugar só.** Cada operação determinística (sync, lint, export) tem **uma** implementação em `domains/<X>/`. CLI, Python API e skill são **fachadas finas** sobre ela. Adicionar um host (Cursor, Codex) nunca duplica lógica.

2. **DRY de metadata.** Toda skill tem **um único** arquivo de metadata: o frontmatter rico no `SKILL.md` (campo `prumo:`). Sem `manifest.yaml` paralelo. Sem versão duplicada em outro lugar. `_version.py` é fonte única; o script `.github/scripts/sync_manifest_version.py` propaga pra `plugin.json`/`marketplace.json` quando há release.

3. **Determinístico ≠ agêntico.** Quando dá pra fazer com regex, AST, ou subprocess, **fazemos**. LLM só onde julgamento humano é necessário (extrair PICOT de PDF, sintetizar resposta de wiki, revisar draft). Reduz custo, aumenta reprodutibilidade.

4. **Skills universais.** `SKILL.md` é o formato canônico de Anthropic + comunidade. Quem usar Cursor, Codex ou Gemini só precisa de um adapter em `integrations/` — o conteúdo das skills nunca muda.

5. **Provenance em todo output.** Bloco `_meta` (run_id, modelo, prompt version, input hash, timestamp) inline em qualquer artefato gerado. Trace JSONL local. Auditável daqui a 5 anos sem SaaS de terceiros.

6. **Forward-only schemas.** `PaperCallout/v2` lê outputs de `v1`. Migrações explícitas em `schemas/migrations.py`. Nunca quebrar dado antigo.

7. **YAGNI militante.** Hooks, cache, lockfile, evals, multi-host, packs — tudo pode estar **desenhado** mas só **implementado** quando dor real justifica. Adiar é mais sustentável do que adicionar especulativamente.

## Layout do repositório (e por quê)

```
prumo-assist/
├── pyproject.toml             ← entry point: prumo = prumo_assist.cli:app
├── ARCHITECTURE.md            ← este arquivo
├── ROADMAP.md                 ← status atual + próximas fases
├── CHANGELOG.md
├── RELEASING.md
├── README.md
├── LICENSE
│
├── .claude-plugin/            ← preserva compat com plugin marketplace
│   ├── plugin.json            ← versão sincronizada por sync_manifest_version.py
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
│   │   ├── paths.py           ← localiza recursos empacotados (templates/skills)
│   │   ├── cli_op.py          ← context manager pros subcomandos Typer
│   │   └── output.py          ← Console (Rich + JSON dual)
│   │
│   ├── domains/               ← NEGÓCIO — uma pasta por pilar
│   │   ├── paper/
│   │   ├── wiki/
│   │   ├── capture/
│   │   └── write/
│   │
│   └── integrations/          ← adapters por agent-host
│       ├── base.py            ← BaseIntegration (interface)
│       └── claude_code/       ← MVP: único host
│           └── installer.py   ← copia skills pra .claude/skills/
│
├── skills/                    ← FONTE CANÔNICA de skills (universal SKILL.md)
│   ├── paper-extract/SKILL.md
│   ├── wiki-{ingest,query,lint}/SKILL.md
│   ├── peer-review/SKILL.md
│   ├── scientific-writing/SKILL.md
│   └── ...
│
├── templates/
│   └── pj_base/               ← template do pj_*; consumido por `prumo init`
│
├── tests/                     ← unit + integration; layout espelha domains/
│
└── docs/                      ← specs e RFCs (raramente publicados)
```

### Por que `core/` e `domains/` são separados

Regra mental simples: **`core/` nunca importa de `domains/`; `domains/` pode importar de `core/`**. Isso garante que dá pra arrancar um domínio inteiro (spin-off em outro pacote) sem quebrar a fundação. E garante que um teste de `core/bib.py` nunca fica dependente de Pandoc estar instalado.

### Por que `skills/` está fora de `src/`

Skills são **conteúdo**, não código Python. Vivem em `skills/` na raiz do repo, são consumidas pelo CLI quando invoca `integrations/<host>/install()`. Manter na raiz facilita pull requests da comunidade (não precisa entender Python pra contribuir uma skill).

### Por que `cli.py` é tão fino

Cada subcomando Typer é envolvido em [`core/cli_op.cli_run`](src/prumo_assist/core/cli_op.py): context manager que cria `Console`, captura `PrumoError` + exceções específicas, e mapeia pra `typer.Exit(1)`. O comando em si só faz: parsing de args, chamada do domínio, formatação de saída. Toda lógica fica em `domains/<X>/`.

E os `api.py` de cada domínio são **re-exports puros** (`from .sync import sync`) — não wrappers passthrough. A superfície fica estável (SemVer) sem boilerplate.

## Como dados fluem (caso típico: extrair um paper)

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

**Para uso headless** (CI, batch de 200 papers): `prumo paper extract --batch` shell-outa pra `claude -p`, mesma skill, mesmo output. Sem código duplicado.

## Como contribuir

1. **Para uma skill nova:** crie `skills/<nome>/SKILL.md` com frontmatter rico, `prompt.md` opcional, `tests/golden/` opcional. Não precisa tocar Python.

2. **Para um comando determinístico novo:** adicione ao domínio certo (`domains/<X>/<op>.py`); exponha via `domains/<X>/cli.py` (envolvendo em `cli_run`) e re-exporte de `domains/<X>/api.py`. Teste em `tests/unit/<X>/test_<op>.py`.

3. **Para um host novo (Cursor, Codex, ...):** subclasse `BaseIntegration` em `integrations/<host>/installer.py`, registre em `integrations/__init__.py`. Skills universais: zero mudança.

4. **Para um pack novo:** `packs/<nome>/pack.toml` + `packs/<nome>/skills/`. `prumo pack install <nome>` carrega.

## Glossário rápido

- **Skill** — capability agêntica empacotada como `SKILL.md` universal.
- **Pack** — bundle versionado de skills + templates + commands.
- **Integration** — adapter que traduz skills do formato canônico pro layout específico de um agent-host (Claude Code, Cursor, Codex, ...).
- **Provenance** — bloco `_meta` em todo output + trace JSONL local.
- **`pj_*`** — projeto de pesquisa do usuário; vault Obsidian + dependências declaradas no `pyproject.toml` local.
- **Determinismo** — `agentic` (LLM faz julgamento), `deterministic` (Python puro), `hybrid` (mistura, ex: `wiki-lint`).
- **Forward-only schema** — `v2` adiciona campos; nunca remove ou redefine. Outputs antigos sempre legíveis.
