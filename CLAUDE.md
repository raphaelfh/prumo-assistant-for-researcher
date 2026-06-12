# prumo-assist — guia do repo

Plugin Claude Code + CLI Python (`prumo`) de pesquisa clínica: bibliografia (Zotero/BBT), wiki (Obsidian), protocolo (PICOT) e escrita (Pandoc/Typst). Prosa em pt-BR; identificadores, comandos e nomes de schema em inglês.

## Regras

- @.claude/rules/code.md
- @.claude/rules/release.md

## Fontes de verdade

- Princípios de design: `docs/constitution.md` — autoridade máxima. NÃO editar sem emenda formal (PR + Sync impact report).
- Decisões registradas: `docs/adr/` — consulte antes de propor mudança estrutural; decisão estrutural nova = ADR novo (MADR minimal, imutável após aceito).
- Mapa do código: `ARCHITECTURE.md` (what/where). Status e fases: `ROADMAP.md`.
- Workflow de feature: brainstorm → spec (`docs/superpowers/specs/`) → plan (`docs/superpowers/plans/`) → TDD. Plano implementado recebe frontmatter `status: implemented` + `verified` + `release` e move para `docs/superpowers/plans/archive/`.

## Armadilhas deste repo

- `templates/pj_base/CLAUDE.md` é PRODUTO (scaffolding de projetos `pj_*`), não orientação deste repo.
- `skills/` e `templates/` são force-included no wheel (pyproject) e resolvidos por `core/paths.py` — mover qualquer um exige atualizar os dois lados juntos.
- Plugin root = raiz do repo (`.claude-plugin/marketplace.json` usa `source: "./"`) — não mover `skills/`, `.mcp.json`, `.claude-plugin/`.
- `.mcp.json` é, ao mesmo tempo, config MCP deste projeto E config MCP distribuída aos consumidores do plugin.
- Reorganização de docs/.github NÃO bumpa versão (RELEASING.md, "Quando NÃO bumpar").
- Índices têm blocos gerados (README, `skills/start/SKILL.md`, `docs/_index.md`, `docs/adr/_index.md`): edite a fonte e rode o gerador — nunca o bloco à mão.

## Comandos

- Testes: `uv run pytest`
- Lint: `uv run ruff check . && uv run ruff format --check .`
- Types: `uv run mypy`
- Índices: `uv run python .github/scripts/gen_indexes.py` (CI roda `--check`)
