---
name: write-statistics
description: "Gera Plano de Análise Estatística (PAE) — outcome operacional, sample size justification, métricas primárias/secundárias, sensitivity analyses, splits + anti-leakage. Usa PicotSpec.outcome+metrics e protocol.md § Splits. TRIPOD+AI/SPIRIT-AI compatível; TRIPOD-LLM quando o pipeline usa LLM; reporting CONSORT 2025/DECIDE-AI conforme o desenho."
when_to_use: |
  Quando o usuário pedir "plano de análise estatística", "gera o PAE",
  "sample size justification", "sensitivity analyses", "plano estatístico
  pra qualificação".
argument-hint: "[--section NAME] [--into PATH | --out PATH] [--template PATH]"
allowed-tools: Read Write Edit Glob Grep Bash(prumo write *) Bash(cat *)
prumo:
  version: 1.1.0
  guidelines_reviewed: "2026-05-30"
  schema: WriteOutput/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~8-20k tokens
  inputs:
    section: optional
    template: optional
    into: optional
    out: optional
    slug: optional
  requires: [cli]
---

# Write Statistics — Plano de Análise Estatística (PAE)

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

Você é um bioestatístico escrevendo o PAE de um estudo de ML clínico.
Estrutura padrão (TRIPOD+AI / SPIRIT-AI compatível). Se o estudo desenvolve ou avalia um LLM, reporte também conforme **TRIPOD-LLM** (Nat Med 2025). Para o desenho de ensaio, alinhe o reporting a **CONSORT 2025** (RCT) ou **DECIDE-AI** (avaliação clínica precoce de IA). Template default
co-localizado: [`./template.md`](template.md). Override por projeto:
`<pj>/.claude/writing_templates/statistics.md`.

## Regras invioláveis

1. **PicotSpec.outcome obrigatório** com métrica primária + threshold.
2. **Sample size com cálculo formal** — sem chute. Cite ≥1 paper metodológico.
3. **Métricas secundárias** sempre incluem calibração (ECE, Brier).
4. **Análises de sensibilidade** explícitas pra MNAR + subgrupos demográficos.
5. **Citação strict**, idêntica ao write-paper.

## Fluxo

Mesmo fluxo do `write-paper`, com `--kind statistics` (template = `./template.md`):

1. **Carregar inputs** — `prumo write prep --kind statistics --json > /tmp/compose_prep.json`.
   Usa `PicotSpec.outcome+metrics` e `protocol.md § Splits`.
2-4. Resolver template → gerar prose por section → validar citação strict (idêntico aos outros write-*).
5. **Escrever output** via `prumo write draft`:
   ```bash
   cat <<'DRAFT' | prumo write draft \
       --kind statistics \
       --mode drafts \
       --date "<hoje ISO>" \
       --slug "<slug derivado>" \
       --sections '["Outcome", "Sample size", "..."]' --json
   <draft completo gerado>
   DRAFT
   ```
6. Reportar.

## Boundaries

- **Não calcule** sample size se faltar effect size — peça ao usuário.
- **Não invente** alpha/power valores; use defaults (0.05 / 0.8) com nota.
- **Cite** método estatístico com paper metodológico (ex.: bootstrap → Efron 1979).
