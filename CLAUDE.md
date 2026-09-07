# prumo-assist — guia do repo

Plugin Claude Code + CLI Python (`prumo`) de pesquisa clínica: bibliografia (Zotero/BBT), wiki (Markdown; front Zettlr — legado Obsidian), protocolo (PICOT) e escrita (Pandoc/Typst). Prosa em pt-BR; identificadores, comandos e nomes de schema em inglês.

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
- `skills/` e `templates/` são force-included no wheel (pyproject) e resolvidos por `src/prumo_assist/core/paths.py` — mover qualquer um exige atualizar os dois lados juntos.
- Plugin root = raiz do repo (`.claude-plugin/marketplace.json` usa `source: "./"`) — não mover `skills/`, `.mcp.json`, `.claude-plugin/`.
- `.mcp.json` é, ao mesmo tempo, config MCP deste projeto E config MCP distribuída aos consumidores do plugin.
- Índices têm blocos gerados (README, `skills/start/SKILL.md`, `docs/_index.md`, `docs/adr/_index.md`): edite a fonte e rode o gerador — nunca o bloco à mão.

## Comandos

- Testes: `uv run pytest`
- Lint: `uv run ruff check . && uv run ruff format --check .`
- Types: `uv run mypy`
- Índices: `uv run python .github/scripts/gen_indexes.py` (CI roda `--check`)

## graphify

Grafo local opcional, gitignored — ausente em worktree recém-criado. Quando `graphify-out/graph.json` existir:
`graphify query "<pergunta>"` antes de grep (`path "A" "B"` para relações, `explain "X"` para um conceito) e `graphify update .` depois de mudar código.
