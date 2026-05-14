---
tags: [sap, statistical-analysis-plan, skeleton]
aliases: ["SAP skeleton", "Plano Estatístico (modelo)"]
---

# Statistical Analysis Plan (SAP) — _(nome do estudo)_

> Versão 0.1 — _(YYYY-MM-DD)_
> Alinhado a STROBE e RECORD (quando applicável também a CONSORT, SPIRIT, TRIPOD-AI).
> Estudo: _(coorte / caso-controle / corte transversal / ensaio)_ — [[protocol]].

## 0. Princípios

1. **Tipo de estudo.** _(descritivo / explicativo / preditivo)_. Toda análise multivariável que não derive diretamente da hipótese pré-especificada deve ser rotulada como **exploratória/geradora de hipóteses**.
2. **Pré-especificação.** Toda análise, subgrupo, sumarização e sensitivity check listada aqui é considerada pré-especificada; alterações posteriores devem ser registradas em `docs/decisions/` com data e justificativa (ADR).
3. **Bootstrap para IC.** ICs por bootstrap não-paramétrico (`n_boot = 2000`) com BCa para proporções e medianas; paramétricos (Poisson, Wald, Wilson) onde apropriado.
4. **Missing data.** Reportar n disponível para cada análise. Imputação **não** será usada como análise primária; análise de complete-case é a primária. Multiple imputation por chained equations (MICE, `n_imp = 20`) **apenas** como análise de sensibilidade.
5. **Software.** _(Python 3.12+ / R / SAS)_. Versionamento de ambiente via `pyproject.toml` ou `renv.lock`. Seeds fixadas em `42`.

## 1. Tamanho amostral e poder

_(Se descritivo: precisão alvo das estimativas. Se explicativo: cálculo formal de poder com α=0,05, β=0,20, effect-size de interesse clínico, software usado.)_

## 2. População de análise

| Conjunto | Definição |
|---|---|
| **Coorte ampla** | _(filtro inicial)_ |
| **Análise principal** | _(definição operacional + critérios de exclusão)_ |
| **Subanálise A** | _(definição)_ |
| **Subanálise B** | _(definição)_ |

Flowchart STROBE/CONSORT será o **Figure 1** do paper.

## 3. Análise descritiva

### 3.1 Tabela 1 — Características baseline

Por toda a coorte e estratificada por _(exposição / fase / status / etc.)_.

| Tipo | Variáveis | Sumário |
|---|---|---|
| Contínuas | _(listar)_ | Mediana (IQR), Mín–Máx, n disponível |
| Categóricas | _(listar)_ | n (%), IC95% Wilson |

> [!warning] Sem comparações inferenciais na Tabela 1
> NÃO incluir p-valores na Tabela 1 (consenso CONSORT 2010 / SPIRIT). Diferenças entre estratos são descritas, não testadas.

### 3.2 Objetivo primário

_(Descrever as análises diretamente ligadas ao desfecho/exposição primária. Para estudos descritivos, listar sumarizações; para explicativos, hipótese e teste.)_

### 3.3 Objetivos secundários

_(Listar cada objetivo e a análise correspondente.)_

## 4. Análises de sobrevida / tempo até evento (quando aplicável)

- **Kaplan-Meier** com IC95% (estimador de Greenwood) para sobrevida global / livre de evento
- **Fine-Gray** para incidência cumulativa quando houver evento competidor (e.g., óbito por causa não-relacionada para desfechos clínicos)
- **Taxas de incidência** (Poisson) por 1.000 pessoas-ano, global e por subgrupos
- **Tempo mediano até evento** com IC95% (Brookmeyer-Crowley)
- Verificação de proporcionalidade (Cox): Schoenfeld residuals + cum-haz plots; se violado, HR estratificado por tempo

## 5. Análises longitudinais (quando aplicável)

- Trajetórias por paciente — spaghetti plot + LOWESS sobreposta
- Mediana / mediana anual da variável longitudinal
- Heatmap de categoria × tempo
- Diagrama de Sankey para transições entre estados
- Pior cenário anual para variáveis qualitativas: P > I > N

## 6. Análises exploratórias (geradoras de hipótese)

- Regressão de Cox / logística / linear para o desfecho primário
- Reportar HR/OR/β com IC95%; **NÃO interpretar como causal**
- Modelos de fragilidade quando houver clustering
- Performance de escores externos (c-index, calibração) com bootstrap

## 7. Análises de sensibilidade pré-especificadas

| # | Análise | Objetivo |
|---|---|---|
| S1 | _(definição alternativa de exposição/desfecho)_ | Robustez à classificação |
| S2 | Excluir pacientes com seguimento <12m | Imortal time bias |
| S3 | Lookback estendido | Definição mais conservadora |
| S4 | Multiple imputation (MICE, n=20) para variáveis com missing 5–40% | Robustez ao MAR |
| S5 | Restrição a um período específico (ex.: pós-mudança de cuidado) | Mudança de padrão |
| S6 | Definição alternativa do índice | Sensibilidade da escolha de índice |

## 8. Subgrupos pré-especificados

1. _(subgrupo A — definição operacional)_
2. _(subgrupo B)_
3. _(subgrupo C)_

Para **cada subgrupo**, reportar Tabela 1 reduzida + análise principal + taxa por 1.000 pessoas-ano dos principais desfechos.

## 9. Apresentação dos resultados

### 9.1 Figuras-chave previstas

| # | Figura | Tipo |
|---|---|---|
| F1 | Flowchart STROBE/CONSORT | Diagrama |
| F2 | _(figura descritiva da população)_ | _(pirâmide / mapa / histograma)_ |
| F3 | _(trajetória / sobrevida / desfecho primário)_ | _(KM / line / heatmap)_ |
| F4 | _(subgrupos)_ | Forest plot |

### 9.2 Tabelas-chave previstas

| # | Tabela |
|---|---|
| T1 | Características baseline (geral + estratos) |
| T2 | _(desfechos primários)_ |
| T3 | _(taxas e HR/OR exploratórios)_ |
| T4 | Análises de sensibilidade |

### 9.3 Estilo gráfico

- `seaborn.set_theme(style="whitegrid", context="paper")` — DPI ≥300
- Paleta: `colorblind`
- Anotar `n=` em cada subgrupo

## 10. Reprodutibilidade

- Pipeline em notebooks numerados (`01_eda`, `02_cohort_build`, `03_descriptives`, ...)
- Funções utilitárias em `src/`
- Seed global = `42`
- Cada notebook gera HTML + figuras `.png` + tabelas `.csv` em `outputs/`
- Números finais congelados em `outputs/manuscript_results.json`

## 11. Reporting checklist

- **STROBE** (cohort/case-control/cross-sectional) — anexar ao manuscrito
- **RECORD** — quando dados de rotina coletados eletronicamente
- **RECORD-PE** — se análise de exposição a fármacos for primária
- **TRIPOD-AI** — quando houver modelo preditivo
- Registro prospectivo em **OSF** ou **EU PAS Register**

## 12. Histórico de mudanças

| Data | Quem | O quê |
|------|------|-------|
| YYYY-MM-DD | _____ | Versão 0.1 — esqueleto inicial copiado de `docs/templates/`. |
