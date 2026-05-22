---
name: write-scientific
description: "Gera prose acadêmica genérica quando o usuário tem texto-base ou só uma seção isolada e não cabe em paper/CEP/statistics. Aceita --seed, --section, --template. Citação strict do acervo."
when_to_use: |
  Quando o usuário pedir "escreve essa seção", "expande este parágrafo",
  "me ajuda a redigir X", sem gênero formal específico.
argument-hint: "[--section NAME] [--seed TEXT] [--template PATH] [--into PATH | --out PATH]"
allowed-tools: Read Write Edit Glob Grep Bash(uv run python *) Bash(python3 *)
prumo:
  version: 1.0.0
  schema: WriteOutput/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~5-15k tokens
  inputs:
    section: optional
    seed: optional
    template: optional
    into: optional
    out: optional
    slug: optional
---

# Write Scientific — prose acadêmica genérica

Skill flexível pra geração que não se encaixa em paper/CEP/statistics. Template
default co-localizado: [`./template.md`](template.md) — minimal. Override por
projeto: `<pj>/.claude/writing_templates/scientific.md`. Override ad-hoc:
`--template <path>`.

## Regras invioláveis

1. **Citação strict** (mesmo padrão da família).
2. **Aceita seed text** via `--seed <text>` ou stdin (se conversa).
3. **`--section <name>`** foca em uma seção quando template tem várias.
4. **PicotSpec opcional** — se ausente, gera baseado só no seed/template.

## Fluxo

(idêntico aos outros, mais permissivo)

## Boundaries

- **Não substitui** os outros 3 — se gênero é claro (paper / CEP / statistics), use a skill específica.
- **Não amplia escopo** sem pedido — se usuário pede 1 parágrafo, gere 1 parágrafo.
