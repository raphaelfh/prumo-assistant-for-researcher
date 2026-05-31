---
title: Simplificação do `pj_base` — núcleo mínimo genérico + módulos opt-in
date: 2026-05-30
status: approved
tags: [pj_base, template, simplification, modules, prumo-init, prumo-add, onboarding, zotero]
---

# Simplificação do `pj_base` — núcleo mínimo + módulos

## Resumo executivo

O template `templates/pj_base/` (consumido por `prumo init`) hoje embute uma stack pesada de machine learning clínico — persona de ML em `CLAUDE.md`, regras de código, notebooks 01–05 e templates administrativos brasileiros — como se fossem **núcleo**. Isso contradiz a própria carta da ferramenta (a `ARCHITECTURE.md` declara "não é IDE de código nem framework de modelagem") e o próprio modelo "núcleo mínimo + módulos" descrito em [`docs/Research Project Structure.md`](../../Research%20Project%20Structure.md).

Esta mudança reduz o `pj_base` a um **núcleo mínimo genérico** — bibliografia (Zotero), wiki, escrita e decisões — servível a qualquer disciplina, e move a camada clínica e a stack de ML para **módulos opt-in**. A ativação é **guiada**: wizard à la carte no `prumo init`, e o comando `prumo add` (sem argumento → seletor interativo) para evoluir o projeto depois. O sistema de referenciamento (`references/`, `.bib`/BBT, citekeys, CSL, convenção `[[@key]]`) e a integração com Zotero **permanecem intactos no núcleo**.

Três invariantes mantêm a mudança lean e fácil:

1. **Módulos só adicionam arquivos novos** (regras em `.claude/rules/`, snippets de Makefile em `.claude/make/`, templates, 1 notebook). O `CLAUDE.md` genérico do núcleo **nunca é editado** por um módulo.
2. **`prumo add` é cópia-merge pura.** Sem merge estrutural de TOML, sem edição de arquivos existentes. Os `[dependency-groups]` ficam declarados (inertes) no `pyproject.toml` do núcleo. Os dois módulos construídos (`clinical`, `ml`) são **overlays de conteúdo puro**.
3. **Onboarding sem fricção.** Prefixo único `pj_`; wizard que explica cada módulo; `prumo add` que se descobre sozinho; e um bloco "Início rápido" no `CLAUDE.md` + uma skill `/prumo-assist:start` para o usuário saber o que invocar no Claude Code.

## Contexto e problema

`prumo init` copia `templates/pj_base/` para um novo `pj_*`. O template atual entrega, já no dia 0:

- **`CLAUDE.md`** com persona "pesquisador sênior de machine learning com foco em saúde", stack PyTorch Lightning/timm/TorchMetrics/albumentations e referência a notebooks `01_eda_clinical … 05_combinado_fusion`.
- **`pyproject.toml`** com grupos `tabular`, `viz`, `imaging`, `deep-learning`, `tabular-boosted`, `data-quality`, `dev`.
- **`.claude/rules/`** com `coding_style.md` e `code_library.md` (aplicam a `*.py`/`*.ipynb`) e `data_governance.md` (aplica a `content/**`).
- **`docs/`** com `protocol.md` clínico, `concepts/entities/findings/sources/` e `docs/templates/` (projeto CEP, plano de análise estatística, dicionário de dados, "Template submissão Plataforma Brasil.docx").
- **`Makefile`** com 17 alvos, incluindo `lint`/`format` (ruff), `watch` (Typst), `compose`, `extract-comments`.

Além de incoerências de **escopo** (impõe ML como núcleo), **doc vs. realidade** (o modelo idealizado já prevê data-pipeline como módulo) e **público** (persona fixa em ML clínico), há **fricção de uso**: o prefixo dobrado `srpj_`/`pj_`, a ausência de orientação no wizard, e a falta de uma porta de entrada para descobrir quais skills invocar no Claude Code.

**Objetivo.** Tornar o `pj_base` fácil para qualquer pesquisador — inclusive o que não domina a ferramenta — preservando referenciamento e Zotero, trazendo o template para o desenho "núcleo mínimo + módulos" que o projeto já idealizou.

## Decisões

### Estruturais (travadas com o usuário)

- **D1 — Núcleo genérico + ML opcional.** O `pj_base` vira scaffold mínimo de qualquer pesquisador. A stack de ML/código sai do núcleo.
- **D2 — Toda a camada clínica vira módulo.** `protocol.md`, PICOT/`formulate-picot` e os templates CEP/SAP/Plataforma Brasil saem do núcleo para o módulo `clinical`.
- **D3 — Ativação por wizard + `prumo add <módulo>`.** Pasta `templates/modules/<nome>/`.
- **D4 — `docs/project_guide.md` no núcleo, com seções guiadas mas enxutas.** Objetivo, Hipótese e Research Questions. **Sem** cronograma e **sem** "papers planejados". Guia/carta de orientação, não o documento-vida que vira a entrega final.
- **D5 — `docs/canvas/project.canvas` no núcleo.**
- **D6 — Implementar só `clinical` + `ml` como overlays reais nesta rodada.** Os demais ficam documentados (YAGNI).
- **D7 — Módulos injetam contexto via arquivos aditivos.** O `CLAUDE.md` do núcleo nunca é editado por um módulo.

### Da revisão lean (P1–P5)

- **D8 (P1) — `pyproject.toml`: grupos inertes no núcleo + comentário.** O módulo `ml` **não toca** o pyproject. Caminho mais fácil para o usuário final (deps sempre disponíveis, zero passo manual) e o mais lean (sem merge TOML).
- **D9 (P2) — Remover do núcleo já nesta rodada** `docs/{concepts,entities,findings,sources}/` (criadas on-demand; verificado em `findings.py`) e os alvos avançados de Make (`watch`/`compose`/`export-doc`/`extract-comments`; comandos `prumo write` permanecem no CLI). `lint`/`format` → `ml`.
- **D10 (P3) — `prumo doctor` não reporta módulos.** O status de módulo vive no `prumo add` (D15), onde serve a uma ação direta.
- **D11 (P4) — Lógica de overlay/descoberta em `core/scaffold.py`**, reusada por `init` e `add`. `cli.py` permanece fachada fina.
- **D12 (P5) — `ml` traz 1 notebook-stub genérico (`eda.ipynb`).**

### De usabilidade (#1–#3)

- **D13 (#1) — Prefixo único `pj_`.** `_VALID_PREFIXES` passa de `("srpj_", "pj_")` para `("pj_",)`; default do wizard `pj_`; exemplos `pj_x`. Projetos `srpj_` existentes não são afetados (o prefixo só é validado no `init`).
- **D14 (#2a) — Wizard à la carte, sem perfis.** O `prumo init` interativo lista os módulos disponíveis **com descrição e "quando usar"**, todos desmarcados; o usuário marca os que quer. Sem perfis prontos (deferido). Não-interativo: `--with clinical,ml`.
- **D15 (#2b) — `prumo add` guiado é a porta única de evolução.** `prumo add` (sem argumento) abre um **seletor interativo** mostrando cada módulo, sua descrição e se **já está aplicado**; `prumo add <mod>` ativa direto; `prumo add --list` lista (com marcação de aplicado). O "aplicado?" usa um **anchor declarado** pelo próprio módulo (não heurística adivinhada).
- **D16 (#3) — Descoberta de skills no Claude Code.** (a) Bloco **"Início rápido"** no `CLAUDE.md` do núcleo (mapa "quero X → /prumo-assist:Y") que o próprio Claude lê e passa a sugerir; (b) nova skill leve **`/prumo-assist:start`** (nível plugin, em `skills/start/`) que orienta o novato e roteia para a skill certa.

## Desenho-alvo

### Núcleo mínimo (o que `prumo init pj_x` cria)

```
pj_<nome>/
├── README.md                      ← curto, genérico (setup + comandos do dia a dia)
├── CLAUDE.md                      ← persona genérica + bloco "Início rápido" (D16)
├── pyproject.toml                 ← ipykernel + [dependency-groups] inertes (comentados)
├── Makefile                       ← 12 alvos + `-include .claude/make/*.mk`
├── .claude/
│   ├── rules/
│   │   ├── documentation.md       ← mantém
│   │   └── project_context.md     ← versão genérica (sem campos clínicos fixos)
│   ├── make/                      ← (vazio no núcleo; módulos depositam *.mk)
│   ├── pj_config.toml             ← mantém
│   └── paper_extraction.md        ← mantém
├── .obsidian/                     ← mantém (vault base)
├── docs/
│   ├── README.md · _index.md · _log.md
│   ├── project_guide.md           ← NOVO (Objetivo · Hipótese · Research Questions)
│   ├── decisions/                 ← mantém (ADRs)
│   └── canvas/project.canvas      ← NOVO
└── references/                    ← INTACTO  ✅ referenciamento + Zotero
    ├── _index.md · _references.bib · notes/ · pdfs/ · templates/literature_note.md · views/papers.base
```

As pastas `docs/{concepts,entities,findings,sources}/` **não** ficam no núcleo: nascem on-demand quando uma skill wiki grava a primeira página; promovidas ao layout `docs/wiki/<tipo>/` pelo módulo `extended-wiki` quando ele existir.

### `CLAUDE.md` genérico + bloco "Início rápido" (núcleo, D16)

Persona reescrita para **assistente de pesquisa acadêmica** (rigor, reprodutibilidade, citações ancoradas, escrita formal, pt-BR). Mantém a estrutura, a hierarquia de instruções, a dependência do plugin e a seção "Como operar". **Remove** stack/notebooks/combinado (→ `ml`). **Adiciona** um bloco acionável:

```markdown
## Início rápido (no Claude Code)

| Quero… | Invoque |
|---|---|
| não sei por onde começar | `/prumo-assist:start` |
| adicionar papers do Zotero ao acervo | `/prumo-assist:paper-manager` |
| extrair um PDF → resumo estruturado | `/prumo-assist:paper-extract` |
| guardar uma fonte (URL/DOI/PDF) no wiki | `/prumo-assist:wiki-ingest <fonte>` |
| perguntar ao meu acervo, com citações | `/prumo-assist:wiki-query "..."` |
| revisar/escrever um texto | `/prumo-assist:scientific-writing` · `:peer-review` · `:write-paper` |
```

### `docs/project_guide.md` (núcleo, D4)

```markdown
# pj_<NOME>

## Objetivo
_(1–3 linhas)_

## Hipótese
_(a tese central do estudo)_

## Research Questions
- RQ1:
- RQ2:
```

### `pyproject.toml` do núcleo (D8)

Mantém `ipykernel` + os `[dependency-groups]` atuais, **inertes e comentados** (não instalam nada até `uv sync --group <nome>`). O módulo `ml` não edita este arquivo.

## Catálogo de módulos

Overlays em `templates/modules/<nome>/`, aplicados por cópia-merge não-destrutiva (`core/scaffold.py`). Cada módulo traz um `_module.toml` com `description`, `when_to_use` e `anchor` — lido pelo wizard e pelo `prumo add` (D14/D15).

| Módulo | Implementar agora | Conteúdo (migrado do template de hoje) | `anchor` |
|---|---|---|---|
| **`clinical`** | ✅ | `docs/protocol.md`; `docs/templates/{projeto-cep, statistical_analysis_plan_skeleton, data_dictionary_*, Template submissão Plataforma Brasil.docx, README}`; `.claude/rules/clinical_context.md` | `docs/protocol.md` |
| **`ml`** | ✅ | `.claude/rules/{ml_stack, coding_style, code_library, data_governance}.md`; `.claude/make/ml.mk` (`lint`, `format`); `eda.ipynb` (1 stub) | `.claude/rules/ml_stack.md` |
| `extended-wiki` | ⏸️ doc | layout avançado `docs/wiki/{concepts,entities,findings,sources,<domínio>}/` + READMEs | — |
| `obsidian-power` | ⏸️ doc | plugins Obsidian; alvo `watch` (Typst) | — |
| `peer-review-loop` | ⏸️ doc | `docs/comments/`; alvo `extract-comments` | — |
| `versioned-milestones` | ⏸️ doc | `docs/<marco>/{…, versions/}`; alvos `compose`/`export-doc` | — |
| `brainstorm-pipeline` | ⏸️ doc | `docs/brainstorm/{daily,topics}/` | — |
| `specify-workflow` | ⏸️ doc | `docs/superpowers/{specs,plans}/` | — |

Os dois módulos construídos são **conteúdo puro**. Os 6 não-tooled seguem descritos em `docs/Research Project Structure.md` e ganham overlay quando a dor real aparecer.

## Mecanismo de ativação e onboarding

### `core/scaffold.py` (D11)

Concentra a lógica compartilhada, extraída do `cli.py`:

- `overlay(src_dir, target)` — cópia não-destrutiva (lógica do `_merge_scaffold` atual), retorna `(copied, skipped)`.
- `discover_modules()` — lista `templates/modules/` lendo cada `_module.toml` (`name`, `description`, `when_to_use`, `anchor`).
- `is_applied(target, module)` — `True` se o `anchor` do módulo existe em `target`.

`init` e `add` viram fachadas finas sobre essas funções.

### `prumo init pj_x` — wizard guiado, à la carte (D13/D14)

1. Nome do projeto (default `pj_`; valida prefixo único `pj_`).
2. Modo (new/merge/force) — só quando o destino já existe.
3. **Módulos:** multi-select listando cada módulo com `description` + `when_to_use`, todos desmarcados; o usuário marca o que quiser.
4. git init.
5. "Próximos passos" ao final (já existe), agora incluindo `prumo add` e `/prumo-assist:start`.

Não-interativo / CI: `prumo init pj_x --with clinical,ml --yes`.

### `prumo add` — porta única de evolução (D15)

- `prumo add` (sem argumento) → seletor interativo via `discover_modules()`, mostrando descrição e `[aplicado]` quando `is_applied`.
- `prumo add <módulo>` → `overlay(templates/modules/<módulo>/, cwd)`, sem sobrescrever; reporta `copied`/`skipped`.
- `prumo add --list` → lista não-interativa (com marcação de aplicado).
- Saída dual Rich/JSON via `Console`.

### Skill `/prumo-assist:start` (D16)

Skill leve no plugin (`skills/start/SKILL.md`): se apresenta, lista as capacidades em linguagem simples, pergunta o que o usuário quer fazer e **roteia** para a skill certa (`paper-manager`, `wiki-ingest`, `wiki-query`, `write-*`, …). É a porta de entrada que o novato invoca dentro do Claude Code; complementa o bloco "Início rápido" do `CLAUDE.md`.

## Composição dos módulos (arquivos aditivos)

- **`CLAUDE.md`** — nunca editado. Módulos depositam regras em `.claude/rules/` (`ml` → `ml_stack.md`, `coding_style.md`; `clinical` → `clinical_context.md`).
- **Makefile** — núcleo termina com `-include .claude/make/*.mk`. Módulos depositam `.claude/make/<módulo>.mk` (`ml.mk` traz `lint`/`format`).
- **Dependências** — nunca editadas por módulo; os grupos vivem no núcleo (inertes).
- **`docs/` e templates** — arquivos novos, copiados direto pelo overlay.

## Makefile — núcleo vs. módulo

**Núcleo** (12 alvos): `help`, `sync-paper`, `sync-pdfs`, `sync-pdf-paper`, `sync-annotations`, `extract-paper-all`, `cite`, `cite-styles`, `wiki-index`, `wiki-search`, `export`, `preview`.

**Saem do núcleo:** `lint`/`format` → `ml`; `watch`/`compose`/`export-doc`/`extract-comments` → removidos e documentados (os comandos `prumo write …` permanecem; atalhos voltam quando os módulos nascerem). `make help` cai de 17 para 12.

## Preservado intacto (não-objetivos de mudança)

- **Referenciamento:** `references/` inteiro, `_references.bib`/BBT, citekeys, `[[@key]]`, CSL e o export (`prumo write export/compose`).
- **Zotero:** domínio `paper` completo (`sync`, `sync-pdfs`, `sync-annotations`, `graph`, `find`, `set-primary`, `lint`), `pj_config.toml`, `paper_extraction.md`.
- **`src/domains` e a maior parte de `src/core`.** Adições em `src/`: `core/scaffold.py` (extraído do `cli.py`), o comando `prumo add` e a etapa de módulos no wizard. Adição em `skills/`: `start/`.

## Não-objetivos

- Gating das skills do plugin por módulo (skills são globais). Nota para o futuro.
- Perfis prontos no `prumo init` (deferido; D14 ficou à la carte).
- Implementar overlays dos 6 módulos não-tooled.
- `prumo doctor` reportar módulos (D10) · merge estrutural de TOML em `prumo add` (D8) · `prumo remove` (deferido) · publicar site.

## Migração e compatibilidade

- `pj_*`/`srpj_*` já existentes **não são afetados** — já estão scaffoldados; a mudança é só no template e no `prumo init`/`add`. O prefixo `pj_` só restringe a criação de novos projetos.
- Mudança aditiva e não-destrutiva: nenhum schema, nota ou `.bib` muda de formato.
- Reconciliação de doc: alinhar `docs/Research Project Structure.md` e `CLAUDE.md` ao desenho final (incl. layout de `notes/`, que segue `core/note_paths.py`).
- Renomear `project.md` → `project_guide.md`: atualizar `docs/Research Project Structure.md` e skills `write-*` que leiam `docs/project.md` (ou aceitar ambos na transição).

## Riscos e mitigação

- **Atalhos `make` avançados saem sem módulo destino construído** — mitigado: comandos `prumo write …` permanecem; voltam com os módulos.
- **Pastas wiki ausentes no núcleo** — mitigado: criação on-demand (verificado em `findings.py`); garantir no plano que `wiki-index`/`wiki-lint` toleram pastas ausentes.
- **Detecção de "aplicado" no `prumo add`** — mitigada por `anchor` **declarado** no `_module.toml` (não adivinhado), e é só um hint de UI.

## Critérios de sucesso

1. `prumo init pj_x` cria um projeto sem persona/notebooks/regras de ML nem camada clínica; `make help` lista só os 12 alvos; `references/` + Zotero idênticos a hoje; `pyproject.toml` com grupos opcionais comentados. Só aceita prefixo `pj_`.
2. O wizard lista os módulos com descrição (à la carte); `--with clinical,ml --yes` funciona em CI.
3. `prumo add` sem argumento abre o seletor com status `[aplicado]`; `prumo add clinical`/`ml` restauram a respectiva camada por cópia-merge pura, sem sobrescrever; `--list` lista.
4. `CLAUDE.md` traz o bloco "Início rápido"; `/prumo-assist:start` orienta e roteia no Claude Code.
5. `core/scaffold.py` concentra `overlay`/`discover_modules`/`is_applied`; `init` e `add` reusam (sem duplicação; `cli.py` fino).
6. Testes cobrem `core/scaffold` (overlay não-destrutivo, idempotência, `discover_modules`, `is_applied`), a validação do prefixo `pj_`, e a criação on-demand das pastas wiki.
