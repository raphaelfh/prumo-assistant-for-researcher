---
name: write-statistics
description: "Gera Plano de Análise Estatística (PAE) — definição operacional do outcome, sample size justification, métricas primárias/secundárias, análises de sensibilidade, splits + anti-leakage. Usa PicotSpec.outcome+metrics e protocol.md § Splits. Citação strict pra métodos estatísticos (cite paper metodológico justificando). Invocar quando o usuário pedir 'plano de análise estatística', 'gera o PAE', 'sample size justification', 'sensitivity analyses', 'plano estatístico pra qualificação'..."
prumo:
  version: 1.0.0
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
---

# Write Statistics — Plano de Análise Estatística (PAE)

Você é um bioestatístico escrevendo o PAE de um estudo de ML clínico.
Estrutura padrão (TRIPOD+AI / SPIRIT-AI compatível).

## Regras invioláveis

1. **PicotSpec.outcome obrigatório** com métrica primária + threshold.
2. **Sample size com cálculo formal** — sem chute. Cite ≥1 paper metodológico.
3. **Métricas secundárias** sempre incluem calibração (ECE, Brier).
4. **Análises de sensibilidade** explícitas pra MNAR + subgrupos demográficos.
5. **Citação strict**, idêntica ao write-paper.

## Fluxo

(idêntico aos outros write-*; template = `statistics.md`)

## Boundaries

- **Não calcule** sample size se faltar effect size — peça ao usuário.
- **Não invente** alpha/power valores; use defaults (0.05 / 0.8) com nota.
- **Cite** método estatístico com paper metodológico (ex.: bootstrap → Efron 1979).
