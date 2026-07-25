---
name: write-scientific
description: "Gera prose acadêmica genérica quando o usuário tem texto-base ou só uma seção isolada e não cabe em paper/CEP/statistics. Aceita --seed, --section, --template. Citação strict do acervo."
when_to_use: |
  Quando o usuário pedir "escreve essa seção", "expande este parágrafo",
  "me ajuda a redigir X", sem gênero formal específico.
argument-hint: "[--section NAME] [--seed TEXT] [--template PATH] [--into PATH | --out PATH]"
allowed-tools: Read Write Edit Glob Grep Bash(prumo write *) Bash(cat *)
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
  requires: [cli]
---

# Write Scientific — prose acadêmica genérica

<!-- prumo:preflight:begin -->
> **Preflight (contrato ADR-0019) — execute ANTES de qualquer operação desta skill:**
>
> 1. **CLI:** rode `prumo --version`. Se o comando NÃO existir: não simule NENHUMA
>    operação desta skill; roteie para `/prumo-assist:start` (instalação guiada com
>    consentimento) e pare aqui.
> 2. **Drift CLI×plugin (evidência da Fase 0):** se `$CLAUDE_PLUGIN_ROOT` estiver
>    definido, compare a versão do CLI com o campo `version` de
>    `$CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json`. CLI mais antigo → avise
>    ("CLI X < plugin Y — comandos novos podem não existir") e ofereça
>    `uv tool upgrade prumo-assist` (rode SÓ com consentimento). Sem a variável,
>    pule este passo em silêncio.
> 3. **Estrutura:** se o diretório não tiver `references/` + `docs/` de um `pj_*`,
>    oriente `prumo init pj_<nome>` — NUNCA crie o scaffold manualmente (o agente
>    não simula trabalho do CLI) e NUNCA cite tooling do monorepo do autor.
>
> Recusar-se a operar sem dependência NÃO é falha — é o contrato fail-closed (D1):
> operação exata nunca é simulada.
<!-- prumo:preflight:end -->

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

Mesmo fluxo do `write-paper`, com `--kind scientific` — mais permissivo (PicotSpec
opcional; se ausente, gere a partir do seed/template):

1. **Carregar inputs** — `prumo write prep --kind scientific --json > /tmp/compose_prep.json`.
   Leia `inputs` + `template_path`. Use `--seed`/stdin como texto-base e `--section`
   pra focar uma seção, quando passados.
2-4. Resolver template → gerar prose → validar citação strict (idêntico aos outros).
5. **Escrever output** via `prumo write draft`:
   ```bash
   cat <<'DRAFT' | prumo write draft \
       --kind scientific \
       --mode drafts \
       --date "<hoje ISO>" \
       --slug "<slug derivado>" \
       --sections '["<seção>"]' --json
   <draft completo gerado>
   DRAFT
   ```
   (`--mode into --into <path> --section <nome>` ou `--mode out --out <path>` quando aplicável.)
6. Reportar.

## Boundaries

- **Não substitui** os outros 3 — se gênero é claro (paper / CEP / statistics), use a skill específica.
- **Não amplia escopo** sem pedido — se usuário pede 1 parágrafo, gere 1 parágrafo.
