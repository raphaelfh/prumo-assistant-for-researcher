---
name: tabular-eda
description: >
  Skill para análise exploratória de dados tabulares clínicos com data profiling completo
  e data quality assessment report. Gera um notebook Jupyter pré-populado (template EDA)
  via script, seguindo o padrão 01_eda_clinical.ipynb do monorepo. Invocar sempre que o
  usuário pedir EDA, profiling, análise exploratória, data quality, quality assessment,
  "dar uma olhada nos dados", "explorar o CSV/Parquet", "criar notebook de EDA", avaliar
  qualidade dos dados, "como estão os dados?", ou quando estiver iniciando trabalho no
  notebook 01_eda_clinical em qualquer pj_*. Também útil quando o usuário quer entender
  completeness, validity, consistency, uniqueness ou timeliness de um dataset clínico.
---

# EDA Tabular Clínico — Data Profiling & Quality Assessment

O objetivo é produzir um notebook **reprodutível e auditável** que documenta o estado completo dos dados antes de qualquer modelagem. O notebook gera artefatos de profiling e quality assessment em `data/reports/`, permitindo rastreabilidade entre execuções.

## Geração rápida do notebook template

Use o script bundled para gerar o notebook pré-populado com base no arquivo de dados real:

```bash
uv run python .claude/skills/tabular-eda/scripts/create_eda_notebook.py \
    --data pj_<nome>/data/01_raw/dados.csv \
    --label nome_coluna_desfecho \
    --id   coluna_paciente_id \
    --output pj_<nome>/01_eda_clinical.ipynb
```

**Parâmetros:**
| Flag | Obrigatório | Descrição |
|------|-------------|-----------|
| `--data` | Sim | Caminho CSV, Parquet, Excel (`.xlsx`) ou `.tsv` |
| `--label` | Não | Coluna alvo/desfecho (habilita análise estratificada) |
| `--id` | Não | Coluna de identificador do paciente/estudo (checa unicidade) |
| `--output` | Não | Destino do `.ipynb` (padrão: mesma pasta dos dados, nome `01_eda_clinical.ipynb`) |
| `--title` | Não | Título do notebook (padrão: derivado do nome do arquivo) |

O script lê o arquivo, detecta tipos de colunas e gera células pré-preenchidas com nomes reais das variáveis, schemas Pandera scaffold e código seaborn + matplotlib parametrizado.

---

## Artefatos de saída

Cada execução gera relatórios em `data/reports/eda_report_{RUN_TIMESTAMP}/`:

```
data/
├── 01_raw/                              # nunca modificado
├── 02_processed/                        # export pós-EDA (opcional)
└── reports/
    └── eda_report_{RUN_TIMESTAMP}/
        ├── data_profile_{RUN_TIMESTAMP}.csv          # profiling por coluna
        ├── quality_assessment_{RUN_TIMESTAMP}.json    # scores de qualidade
        ├── missingness_report_{RUN_TIMESTAMP}.csv     # detalhamento missing
        └── eda_summary_{RUN_TIMESTAMP}.json           # resumo executivo
```

Isso permite comparar o estado dos dados entre versões (antes/depois de limpeza, novas coortes, etc.).

---

## Estrutura do notebook gerado

| Seção | Conteúdo |
|-------|----------|
| **Setup & Proveniência** | Imports, caminhos, `RUN_TIMESTAMP`, metadados (origem, hash, data) |
| **Carregamento** | `pd.read_*` com detecção automática de formato |
| **Visão geral & Tipos** | Shape, dtypes, `.head()`, `.describe(include='all')`, validação de tipos |
| **Data Profiling completo** | Estatísticas por coluna: completeness, n_unique, min/max/mean/median/std, skewness, kurtosis, percentis, moda; salva CSV de profiling |
| **Data Quality Assessment** | Score por dimensão (completeness, validity, consistency, uniqueness, timeliness); score global; salva JSON |
| **Missingness** | Contagens absolutas/relativas, heatmap seaborn, co-absence correlation, padrão MCAR/MAR exploratório |
| **Distribuições numéricas** | `sns.histplot` + `sns.boxplot` lado a lado para cada coluna; estatísticas de assimetria |
| **Distribuições categóricas** | `sns.barplot` de frequências; top-N + "outros" para alta cardinalidade; análise de cardinalidade |
| **Outliers** | IQR flagging + `sns.violinplot`; z-score; lista de índices suspeitos |
| **Correlações** | Pearson (numéricas), Cramér's V (categóricas), point-biserial (binário × numérico) |
| **Análise por label** | Distribuições estratificadas, balanceamento, contingência (só se `--label` fornecido) |
| **Duplicatas & Integridade** | Duplicatas exatas, unicidade por ID, variância zero, consistência temporal |
| **Schema Pandera** | Schema scaffold gerado a partir dos dtypes reais; TODO para ranges/valores esperados |
| **Resumo executivo & Export** | Consolidação de findings, JSON summary, export Parquet |

---

## Dimensões de Data Quality

O assessment avalia cinco dimensões padronizadas, cada uma com score 0–100:

| Dimensão | O que mede | Como calcula |
|----------|-----------|--------------|
| **Completeness** | Dados presentes vs. esperados | `100 - mean(pct_missing)` por coluna |
| **Validity** | Valores dentro de ranges esperados | % de valores passando Pandera checks |
| **Consistency** | Coerência interna entre campos | Regras como datas futuras, negativos impossíveis, tipo detectado vs. declarado |
| **Uniqueness** | Ausência de duplicatas | `100 × (1 - n_duplicatas / n_total)` para registros e IDs |
| **Timeliness** | Cobertura temporal adequada | Presença de gaps, distribuição temporal, datas no intervalo esperado |

O **score global** é a média ponderada das dimensões aplicáveis (timeliness é ignorada se não houver colunas de data).

---

## Convenções seaborn + matplotlib (padrão do monorepo)

Setup no topo do notebook:

```python
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="whitegrid", context="paper")
```

Toda figura gerada deve seguir:

```python
fig, ax = plt.subplots(figsize=(5, 3.5))
sns.<plot>(data=df, x=..., y=..., ax=ax)
ax.set_title("<Título descritivo>")
ax.set_xlabel("<variável> (<unidade>)")
ax.set_ylabel("<métrica>")
fig.tight_layout()
fig.savefig(REPORTS_RUN / f"<nome>_{RUN_TIMESTAMP}.png", dpi=300, bbox_inches="tight")
```

- Unidades clínicas sempre nos rótulos dos eixos.
- Exportar PNG estático (`dpi=300`) para o relatório e/ou `docs/findings/_assets/` quando for ser citado num finding.
- Plotly só em dashboards interativos explicitamente solicitados.

---

## Anti-leakage no EDA

Antes de qualquer split:
1. **Definir janela temporal** e ordem de eventos.
2. **Não calcular estatísticas** globais que seriam usadas para normalização — comentar como TODO.
3. **Verificar duplicatas por patient_id** antes de separar treino/teste.
4. Análise estratificada por label é exploratória — não usar para seleção de features.

---

## How to use the code reference

Read `references/code_snippets.md` for ready-made snippets for each section. The file is organised in the same section order and can be pasted directly into notebook cells.

When adapting to the current project:
- Replace `"source_file.csv"` with the actual file under `data/01_raw/`
- Adjust `LABEL_COL` and `ID_COL` for the project's outcome and patient identifier
- In the quality assessment, add project-specific consistency rules
- The profiling function is generic — column-specific interpretation should be added as markdown commentary

---

## Checklist de seções obrigatórias

Ao completar o `01_eda_clinical.ipynb`, verificar:

- [ ] Célula de proveniência com caminho de origem, hash MD5/SHA256 dos dados e data
- [ ] Data profiling CSV salvo em `data/reports/`
- [ ] Data quality assessment JSON com scores por dimensão
- [ ] Missingness: percentual por coluna, heatmap e co-absence
- [ ] Distribuição de cada feature numérica (histograma + box)
- [ ] Frequência de cada feature categórica com análise de cardinalidade
- [ ] Outliers: IQR flagging com contagem e percentual
- [ ] Correlação entre features: Pearson (numéricas) e Cramér's V (categóricas)
- [ ] Se label disponível: balanceamento de classes e distribuições por classe
- [ ] Seção de integridade: duplicatas, IDs únicos, variância zero
- [ ] Schema Pandera com pelo menos tipos corretos (ranges podem ser TODO)
- [ ] Resumo executivo consolidando principais findings

---

## Ajuste manual após geração

O notebook gerado é um ponto de partida. Após rodar o script, revisar:
1. **Schema Pandera**: preencher `pa.Check.in_range(min, max)` com valores clínicos reais.
2. **Consistency rules**: adicionar regras de negócio específicas do domínio (ex.: data de óbito > data de diagnóstico).
3. **Colunas de data**: refinar parsing e análise temporal na seção de integridade.
4. **Features de alta cardinalidade**: decidir se agrupa ou remove na seção categóricas.
5. **Label encoding**: garantir que a coluna alvo está no formato correto.
6. **Comentários clínicos**: adicionar contexto de domínio nos markdowns gerados (TODO markers deixados propositalmente).
7. **Quality thresholds**: ajustar limiares de aceitabilidade para cada dimensão de qualidade.
