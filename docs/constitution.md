<!--
Sync impact report:
  Version: 1.2.3 (2026-10-06) — emenda PATCH: distribuição pelo plugin com CLI
    travado no `uv.lock` (ADR-0038); stack externa com piso do Pandoc e qmd como
    CLI opcional; Princípio III sem a menção a `BaseIntegration`, que deixou de
    existir. Nenhuma norma alterada: os termos 'hooks plugáveis' e 'lockfile' do
    Princípio VI continuam designando o sistema de hooks interno e o lockfile de
    packs que o ROADMAP posterga; o hook `SessionStart` é config do agent-host e
    o `uv.lock` já existia.
  Anterior: 1.2.2 (2026-09-12) — emenda PATCH: a stack externa do projeto-cliente
    cita o Zettlr como front do wiki; o Obsidian, legado desde a v0.62.1, sai do
    texto. Nenhuma norma alterada.
  Anterior: 1.2.1 (2026-09-12) — emenda PATCH: renomeação do projeto para
    prumo-assistant-for-researcher (PAR), pacote `par` (ADR-0034). Título, caminhos
    `src/par/` e comando de distribuição atualizados. Nenhuma norma alterada.
  Anterior: 1.2.0 (2026-09-06) — emenda MINOR: adicionado o Princípio VIII
    (Simplicidade é o default). Trigger concreto: auditoria de organização do
    `pj_prolapse_polymorphism` (2026-09-06), cujo plano de correção adicionava
    três issue codes, um módulo e um comando para problemas com um remédio só —
    todos defensáveis sob o VI e ainda assim mais superfície para o pesquisador
    aprender. O VI governa código escrito; o VIII governa o que o pesquisador
    precisa saber. Nenhum princípio existente foi alterado.
  Anterior: 1.1.2 (2026-08-09) — emenda PATCH: caminho do Princípio IV atualizado
    ("references/notes/" → "docs/references/papers/") para o layout por escopo
    (ADR-0022, ADR-0023). Nenhuma norma alterada — outputs antigos continuam
    DEVENDO permanecer legíveis indefinidamente, só o caminho de exemplo mudou.
  1.1.1 (2026-07-14) — emenda PATCH: correção textual do Princípio VI
    ("a burra de prova" → "o ônus da prova"). Nenhuma norma alterada.
  1.1.0 (2026-06-11) — emenda via PR chore/repo-organization-redesign
  1.0.0 (2026-05-03)

  Added principles (1.2.0):
    - VIII. Simplicidade é o default

  Added principles (1.1.0):
    - VII. Artefatos derivados são gerados

  Changed:
    - IV: referência a "schemas/migrations.py" corrigida para "migração explícita
      por domínio (domains/<X>/schemas/)" — o arquivo único nunca existiu (clarificação).
    - Governança: registrado o ADR log do repo (docs/adr/, MADR minimal) como
      registro de decisões pontuais; princípios continuam morando aqui.

  Templates ou docs a alinhar (1.2.0):
    - ROADMAP.md        ⏳ registrar em "Decisões deliberadas postergadas" os
                           triggers de `unknown_type` no wiki-lint e do padrão
                           de `experiments/` (módulo ml)
    - CLAUDE.md (raiz)  ✅ já aponta a constitution como autoridade máxima

  Templates ou docs a alinhar (1.1.0):
    - ARCHITECTURE.md   ✅ deixou de duplicar princípios; aponta pra cá (2026-06-11)
    - ROADMAP.md        ✅ deferrals espelhados em [[adr/adr-0011-semver-por-visibilidade]]
    - RELEASING.md      ✅ alinhado; fluxo PR-based registrado
    - CLAUDE.md (raiz)  ✅ aponta constitution + docs/adr/ como fontes de verdade

  Follow-up TODOs (1.0.0) — encerrados:
    - "Atualizar templates/pj_base/CLAUDE.md pra refletir o catálogo pós-0.3.0"
      → resolvido pela simplificação do pj_base (v0.61.0, spec 2026-05-30).
-->

# PAR Constitution

## Core Principles

### I · Lógica em um lugar só

Cada operação determinística (sync, lint, export, find, graph) DEVE existir em **uma** implementação dentro de `src/par/domains/<X>/`.

- CLI (`domains/<X>/cli.py`), Python API (`domains/<X>/api.py`) e skills (`skills/<nome>/SKILL.md`) são **fachadas finas** sobre essa implementação.
- A camada de fachada NÃO contém lógica de negócio: parsing de argumentos, formatação de saída, captura padronizada via `core/cli_op.cli_run`.
- `domains/<X>/api.py` é re-export puro dos módulos do domínio. Wrappers passthrough (`def x(p): return _x.x(p)`) são considerados defeito.
- Adicionar um agent-host novo (Cursor, Codex, Gemini) NUNCA pode duplicar lógica — vira `integrations/<host>/installer.py`.

### II · Determinístico antes de agêntico

Quando o resultado pode ser produzido com regex, AST, subprocess ou consulta a um índice, ele DEVE sê-lo.

- LLM é reservado pra tarefas onde julgamento humano é genuinamente necessário (extrair PICOT de PDF livre, sintetizar resposta de wiki, criticar draft).
- Cada `SKILL.md` declara `prumo.determinism: agentic | deterministic | hybrid` no frontmatter; o nível DEVE refletir o que a skill realmente faz.
- Skill agêntica que poderia ser determinística é candidata a refator pra script Python sob `domains/`.
- Resultado prático: reprodutibilidade alta, custo baixo, auditoria viável sem replay de LLM.

### III · Skills universais

`SKILL.md` (frontmatter rico + corpo Markdown) é a **única** fonte de metadata por skill.

- Não existe `manifest.yaml` paralelo, nem `description` duplicada em `plugin.json`.
- Versão da skill mora apenas em `prumo.version` no frontmatter.
- O catálogo do plugin Claude Code é montado por `core/skills.py::load_skill_registry`; um host novo consumirá o mesmo arquivo (Princípio I).
- Quem contribui uma skill nova NÃO precisa tocar Python.

### IV · Forward-only schemas

Schemas Pydantic versionados (`schemas/v1.py`, `schemas/v2.py`, ...) DEVEM ser aditivos.

- `vN+1` lê outputs gerados por `vN`. Campos novos são opcionais com default ou são preenchidos por migração explícita por domínio (`domains/<X>/schemas/`).
- Renomear ou remover campo é proibido entre minor versions; só em major bump com nota `⚠ Breaking` no [`CHANGELOG.md`](../CHANGELOG.md).
- Outputs antigos (notas em `docs/references/papers/`, callouts gerados, traces) DEVEM permanecer legíveis indefinidamente.
- Mudanças de schema DEVEM passar por teste que carrega um output `vN` antigo e valida com o parser `vN+1`.

### V · Provenance em todo output

Todo artefato gerado pelo PAR (callout de paper, export, peer-review, ingest) DEVE conter um bloco `_meta`.

- `_meta` inclui no mínimo: `run_id`, `model`, `prompt_version`, `input_hash`, `timestamp`, `prumo_version`.
- Eventos de execução (`start`, `tool_call`, `end`) DEVEM ser gravados em `.prumo/traces/YYYY-MM-DD.jsonl` no projeto local.
- Trace é local e por projeto — sem SaaS, sem telemetria externa, sem dependência de serviço de terceiros pra reproduzir uma análise daqui a 5 anos.
- Output sem `_meta` é considerado defeito pelo `wiki-lint`.

### VI · YAGNI militante

Hooks plugáveis, cache de LLM, lockfile, eval gates em CI, multi-host, packs externos: TUDO está desenhado em [`ROADMAP.md`](../ROADMAP.md), mas só vira código quando uma dor real justifica.

- Adições especulativas DEVEM ser recusadas — o ônus da prova fica com quem quer adicionar.
- Cada item na seção "Decisões deliberadas postergadas" do ROADMAP tem um *trigger* concreto. Sem o trigger, não entra.
- Refatorações que viram abstrações novas DEVEM eliminar mais código do que introduzem (saldo líquido negativo) ou reduzir complexidade verificável.
- Três linhas de código semelhantes são preferíveis a uma abstração prematura.

### VII · Artefatos derivados são gerados

Todo artefato que deriva de uma fonte única DEVE ser produzido por script, nunca mantido à mão.

- Versão: `src/par/_version.py` é a fonte; `.github/scripts/sync_manifest_version.py` propaga para `plugin.json`/`marketplace.json`. Editar versão num manifest à mão é defeito.
- Índices e catálogos (tabela de skills do README, router `start`, `docs/_index.md`, `docs/adr/_index.md`) derivam do registry (`core/skills.py`) e do filesystem via `.github/scripts/gen_indexes.py`, dentro de blocos delimitados (ADR-0009).
- O CI DEVE falhar quando um derivado está dessincronizado da fonte (`--check`).
- Metadata de skill segue o princípio III (frontmatter único); este princípio cobre o restante da cadeia derivada.

### VIII · Simplicidade é o default

O custo de uma adição se mede em **conceitos que o pesquisador precisa aprender**, não em linhas de código. O princípio VI recusa código especulativo; este recusa superfície desnecessária no que já foi decidido construir.

- Dois problemas com o MESMO remédio DEVEM produzir **uma** mensagem, não duas. Issue code novo só quando a ação de correção difere de todas as existentes.
- Comando novo só quando nenhum existente absorve a tarefa; flag nova só quando o default não serve à maioria dos casos.
- Toda saída DEVE dizer cada coisa uma vez. Informação repetida em modo texto é defeito, não cosmética.
- O caminho feliz NÃO DEVE exigir configuração: default útil primeiro, opção depois.
- Entre duas implementações que resolvem o mesmo problema, vence a que exige **menos estado persistido**. Estado gravado pode dessincronizar; leitura ao vivo, não.
- Reusar um seam existente é preferível a criar um módulo simétrico. Simetria de layout NÃO justifica arquivo novo.

## Restrições de Tecnologia

- **Linguagem**: Python ≥ 3.11. Tipagem estrita (`mypy --strict`); `from __future__ import annotations` em todos os módulos.
- **CLI**: Typer + `core/cli_op.cli_run` (context manager que injeta `Console` e captura `PrumoError`). Nada de `print()` direto fora de `core/output.py`.
- **Qualidade**: `ruff check` e `mypy strict` zerados em `main`. CI roda matrix Python 3.11/3.12.
- **Build**: hatchling; versão única em `src/par/_version.py`. `_templates/` empacotado via `force-include`.
- **Distribuição**: plugin do Claude Code (marketplace), que executa o próprio CLI `prumo` travado no `uv.lock` da versão instalada (pré-requisito: `uv`). `uv tool install`/`uv run` só para desenvolvimento.
- **Stack externa do projeto-cliente** (`pj_*`): Zotero + Better BibTeX (bibliografia), Zettlr (front do wiki Markdown), Pandoc ≥ 3.8.2 + Typst (opcional) + CSL (export), `qmd` opcional (CLI de busca BM25 + vector + rerank local, instalado pelo pesquisador).
- **Sem dependência de SaaS para operação core**: tudo que importa para reproduzir uma análise existe localmente no `pj_*`.

## Fluxo de Desenvolvimento

- Feature nova: `superpowers:brainstorming` → spec em `docs/superpowers/specs/AAAA-MM-DD-*.md` → plano → implementação TDD.
- Cada subcomando Typer envolvido em `cli_run`; cada operação determinística testada em `tests/unit/<domain>/`.
- Tests espelham layout do código (`tests/unit/<area>/test_<modulo>.py` ↔ `src/par/<area>/<modulo>.py`).
- Commits atômicos. Mensagem indica intenção (`refactor:`, `feat:`, `fix:`, `release:`); detalhes no corpo, não no título.
- Revisão DEVE checar conformidade com os princípios desta constitution. Conflito entre prática e princípio: o princípio prevalece, ou o princípio é emendado.
- Skills agênticas DEVEM ter `tests/golden/` quando o output é estruturado (callouts, JSON schema).

## Governança

Esta constitution é o documento de mais alta autoridade para decisões de design no PAR. Quando uma prática conflita com um princípio aqui declarado, a constitution prevalece.

- Emendas DEVEM passar por PR explícito que atualiza este arquivo + a tabela "Sync impact report" no topo.
- Bump de versão da constitution segue [SemVer](https://semver.org/lang/pt-BR/) aplicado a *princípios*: `MAJOR` quando um princípio é removido ou redefinido, `MINOR` quando um princípio é adicionado, `PATCH` para clarificação textual.
- Decisões estruturais pontuais são registradas em `docs/adr/` (MADR minimal, `adr-NNNN-slug.md`, imutáveis após aceitas — revisão = ADR novo). Princípios (normas vivas) moram aqui; o que muda por emenda nunca mora num ADR.
- Versão atual: **1.2.3** (2026-10-06).
- Princípios novos DEVEM ter trigger concreto (não "pode ser útil no futuro") — coerência com o princípio VI.
- O agent-host (Claude Code, Cursor, Codex, Gemini) NÃO pode reescrever esta constitution sem revisão humana.
