# PAR (prumo-assistant-for-researcher) — guia do repo

Plugin Claude Code + CLI Python (`prumo`) de pesquisa clínica: bibliografia (Zotero/BBT), wiki (Markdown; front Zettlr), protocolo (PICOT) e escrita (Pandoc/Typst). Prosa em pt-BR; identificadores, comandos e nomes de schema em inglês.

## Regras

- @.claude/rules/code.md
- @.claude/rules/release.md

## Fontes de verdade

- `docs/constitution.md` — autoridade máxima. NÃO editar sem emenda formal (PR + Sync impact report).
- `docs/adr/` — consulte antes de propor mudança estrutural; decisão estrutural nova = ADR novo (MADR minimal, imutável após aceito).
- `ARCHITECTURE.md` (mapa do código), `ROADMAP.md` (status e fases), `RELEASING.md` (processo de release).
- Feature: brainstorm → spec (`docs/superpowers/specs/`) → plan (`docs/superpowers/plans/`) → TDD. Plano implementado move para `plans/archive/` com frontmatter de fechamento — copie o de qualquer plano já arquivado.

## Armadilhas deste repo

- `templates/pj_base/CLAUDE.md` é PRODUTO (scaffolding de projetos `pj_*`), não orientação deste repo.
- `skills/` e `templates/` são force-included no wheel (pyproject) e resolvidos por `src/par/core/paths.py` — mover qualquer um exige atualizar os dois lados juntos.
- Plugin root = raiz do repo (`.claude-plugin/marketplace.json` usa `source: "./"`) — não mover `skills/`, `.mcp.json`, `.claude-plugin/`, `shims/`, `hooks/`.
- `.mcp.json` é só do plugin (o dev do repo o rejeita como servidor de projeto em `.claude/settings.json` e carrega o plugin com `claude --plugin-dir .`).
- Índices têm blocos gerados (README, `skills/start/SKILL.md`, `docs/_index.md`, `docs/adr/_index.md`, o bloco `prumo:runtime` das 5 portas, do `start` e de `agents/reader.md`): edite a fonte e rode o gerador — nunca o bloco à mão.
- `shims/` contém só `prumo` (100755); nunca crie `bin/` na raiz — chat e Cowork recusam o plugin inteiro.
- o venv do lançador é chaveado pelo conteúdo de `uv.lock` + `shims/prumo`: mudar qualquer um faz cada pesquisadora baixar o ambiente de novo (cerca de 60 MB, uma vez) — diga isso no CHANGELOG.
- o canal da conta (Customize → Plugins) copia a árvore git inteira: limite de 5.000 arquivos e 200 MB.

## Comandos

- Testes: `uv run pytest`
- Lint: `uv run ruff check . && uv run ruff format --check .`
- Types: `uv run mypy`
- Índices: `uv run python .github/scripts/gen_indexes.py` (CI roda `--check`)

## graphify

Grafo local opcional, gitignored — ausente em worktree recém-criado. Quando `graphify-out/graph.json` existir:
`graphify query "<pergunta>"` antes de grep (`path "A" "B"` para relações, `explain "X"` para um conceito) e `graphify update .` depois de mudar código.
