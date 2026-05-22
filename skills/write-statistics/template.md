---
title: "Plano de análise estatística"
revisao: 1
---

# Plano de análise estatística (PAE)

<!-- 2-3 frases sobre escopo do plano (qual estudo, hipótese central). -->

## Definição operacional do outcome

<!-- PicotSpec.outcome formalizado:
     - Variável dependente: tipo (binária / contínua / time-to-event)
     - Definição clínica
     - Janela de mensuração
     - Critérios de exclusão por outcome ausente -->

## Sample size justification

<!-- Cálculo formal:
     - Métrica primária + threshold (PicotSpec.hypothesis.metrics)
     - Effect size esperado
     - Power (geralmente 0.8)
     - Alpha (geralmente 0.05)
     - Cite ≥1 paper metodológico sustentando o cálculo. -->

## Métricas primárias e secundárias

<!-- Lista detalhada:
     - Primária: ... (com IC 95% via bootstrap)
     - Secundárias: ECE, Brier, calibração por subgrupo -->

## Análises de sensibilidade

<!-- - Sensitivity to MNAR mechanism
     - Subgroup analysis
     - Influence diagnostics -->

## Splits e anti-leakage

<!-- protocol.md § Splits:
     - Estratégia (GroupKFold/temporal/...)
     - Seeds reportadas
     - Validação externa cross-cohort -->

## Software e reprodutibilidade

<!-- Bibliotecas + versões; código liberado em <repo>; seeds reportadas. -->
