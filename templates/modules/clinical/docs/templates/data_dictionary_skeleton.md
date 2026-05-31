---
tags: [protocol, data-dictionary, skeleton]
aliases: ["Dicionário de Dados (modelo)", "Data Dictionary skeleton"]
version: 0.1
date: YYYY-MM-DD
spec: "[[<link para spec/ADR>]]"
---

# Dicionário de Dados — _(nome do estudo)_

Estrutura em **duas camadas** (ver [[decisions/<ADR>]] para o racional):

- **Camada 1 — Estratégia de extração (fornecedor → nós).** O que pedir,
  como vem, regras de seleção/normalização. Leitor primário: equipe de
  TI / engenharia de dados do fornecedor.
- **Camada 2 — Engineered features.** Como construir cada coluna
  derivada por regra clínica/estatística, **organizadas por pergunta
  clínica do SAP** (não por tipo técnico). Leitor primário: analista
  alimentando o [[statistical_analysis_plan]].

> [!info] Por que duas camadas
> Em real-world data clínico (milhares de medições por paciente),
> achatar tudo numa lista confunde dois leitores diferentes (TI vs
> analista) e empurra decisões clínicas implícitas para o ETL sem
> rastreabilidade. Cada feature derivada deve ter âncora em
> paper/guideline rastreável via `[[citekey]]`.

## 0. Padrões do dataset final

| Item | Convenção |
|---|---|
| Separador decimal | `.` (ponto) |
| Separador de milhar | `,` (vírgula) |
| Encoding | UTF-8 (preferencial) ou ISO-8859-1 |
| Formato de data | `YYYY-MM-DD` ou `DD-MMM-YYYY` (especificar no header do dataset) |
| Delimitador de campo | `|` (pipe) |
| Aspas | `"` (double quotes) |
| Células vazias | `NA` ou `empty` (especificar no header) |
| Primeira linha | Nomes das variáveis em MAIÚSCULAS, ≤10 caracteres |
| Formato | `.csv` ou `.txt` |
| Identificação | Hash anônimo determinístico do identificador-fonte; **sem PII em texto livre** |

## 1. Layout do master file (N tabelas relacionadas pelo `ID`)

> _(Adapte ao escopo. Padrão recomendado: 1 tabela "wide" por paciente
> + N tabelas "long" por domínio. Cada linha das long preserva uma
> observação atômica.)_

1. **`master_patient.csv`** — 1 linha por paciente (baseline,
   demográficas, datas de evento e censura).
2. **`<dominio_1>_long.csv`** — formato longo: 1 linha por observação
   de _(ex.: exame laboratorial, sorologia, biomarcador)_.
3. **`<dominio_2>_long.csv`** — _(ex.: exame de imagem ou
   procedimento com flags estruturadas extraídas via NLP)_.
4. **`hcru_long.csv`** — 1 linha por encontro (consulta, ED, IP, ICU),
   procedimento ou dispensação.

> [!tip] Schema atômico recomendado para tabelas long
>
> ```
> ID | VAR | RESULT_N | RESULT_RAW | UNIT | DATE | STATUS
> ```
>
> `STATUS ∈ {NUM, BELOW_LLOQ, ABOVE_ULOQ, P, N, I}` resolve LOQ
> (limit of quantification) e resultados qualitativos sem inflar
> colunas. `RESULT_N` é numérico padronizado; `RESULT_RAW` preserva
> texto bruto quando informativo. Detalhe em §1.3.

> [!warning] Governança de dado sensível
> Texto livre de laudos / prontuário **não** é entregue. Apenas flags
> estruturadas em `FLAGS_JSON` + hash do documento (`REPORT_HASH`).

## Camada 1 — Estratégia de extração (fornecedor → nós)

Padrão recorrente em cada subseção: **(a)** tabela de saída,
**(b)** lista de variáveis com `VAR` code, **(c)** como vem do
fornecedor, **(d)** regras de seleção/normalização, **(e)** critérios
de qualidade (rejeitar / flagar).

### 1.1 Identificação e tempo → `master_patient`

Uma linha por paciente. Datas-chave derivadas a partir das tabelas long.

| Coluna | Origem / Regra de extração |
|---|---|
| `ID` | Hash determinístico do identificador-fonte aplicado pelo fornecedor antes da entrega |
| `DX_DT` | _(primeira evidência do diagnóstico — ex.: `min(DATE)` em `labs_long` onde `VAR ∈ {...}` AND `STATUS = P`)_ |
| `DX_MM` | Fallback `YYYY-MM` quando dia exato indisponível |
| `DX_CONF_DT` | _(critério de confirmação temporal — ex.: segunda observação positiva com `(DATE − DX_DT) ≥ Nd`)_ |
| `IDX_DT` | _(data índice = baseline analítico — ex.: `DX_DT + Nd`)_ |
| `ENTRY_DT` | `min(DATE)` em qualquer das N tabelas |
| `LAST_SEEN` | `max(DATE)` em qualquer das N tabelas |
| `DEATH_DT` | Quando disponível _(documentar limites temporais do registro)_ |
| `FU_STATUS` | `E` se ocorreu desfecho hard ou óbito; `L` se `LAST_SEEN − IDX_DT > Nm` sem contato; `C` censura administrativa em `YYYY-MM-DD` |

> [!info] Definição operacional do critério temporal
> _(Cite o guideline e a regra implementada — ex.: [[<citekey>]] p.X,
> "doença X = condição Y por ≥6 meses".)_

### 1.2 Demográficas e antropométricas → `master_patient`

Variáveis: _(listar — ex.: `SEX, AGE_DX, AGE, REGION, STATE, BMI, WT, HT, RACE`)_.

- **AGE_DX / AGE**: anos completos calculados pelo fornecedor; data de nascimento bruta **não** entregue.
- **BMI / WT / HT**: observações datadas; usar a **mais próxima ao `IDX_DT`** dentro de janela de ±Nd.
- **RACE**: _(documentar disponibilidade; se indisponível, entregar com `SI` — sem informação — para preservar schema)_.
- **REGION / STATE**: _(granularidade — ex.: macrorregião + UF de residência registrada)_.

### 1.3 _(Domínio crítico — ex.: marcadores HBV, biomarcadores, sorologias)_ → `<dominio>_long` ⚠ seção crítica

**Variáveis (VAR):** _(listar exaustivamente; UPPERCASE ≤10 chars)_.

Cada observação no schema padrão `(ID, VAR, RESULT_N, RESULT_RAW, UNIT, DATE, STATUS)`.
**Nada é dedupado nem agregado nesta camada** — toda medição é preservada.

**Regras de normalização (o fornecedor aplica antes da entrega):**

| Caso | Tratamento |
|---|---|
| Quantitativo numérico válido | `RESULT_N = valor`, `STATUS = NUM` |
| `<LLOQ` ("Não detectado", "<N unidades") | `RESULT_N = NULL`, `STATUS = BELOW_LLOQ`, `RESULT_RAW` preserva texto bruto |
| `>ULOQ` (acima do limite superior do assay) | `STATUS = ABOVE_ULOQ`, `RESULT_N = ULOQ` (right-censored) |
| Qualitativo positivo ("Reagente", "Detectado") | `STATUS = P`, `RESULT_N = NULL` |
| Qualitativo negativo | `STATUS = N` |
| Indeterminado / inconclusivo / borderline | `STATUS = I` |
| Unidades não-padrão | _(documentar fator de conversão e padrão de referência — ex.: WHO International Standard [[<citekey>]]; flagar `UNIT_CONV_SUSPECT = 1` quando assay desconhecido)_ |
| _(outros casos do domínio)_ | _(tratamento)_ |

**Critérios de qualidade (rejeitar/flagar):**
_(datas no futuro; datas pré-AAAA; `RESULT_N < 0`; valores acima de cap fisiológico/assay; etc.)_

> [!warning] Indisponíveis no fornecedor
> _(Listar variáveis solicitadas mas que o fornecedor não entrega
> — ex.: genotipagem, teste de resistência. Manter colunas no
> esquema com `NA` em todas as linhas para preservar schema futuro.)_

### 1.4 _(Domínio funcional — ex.: função e injúria hepática, função renal)_ → `<dominio>_long`

**Variáveis:** _(listar)_. Schema padrão.

**Conversões frequentes (o fornecedor aplica):**
- _(unidade A ↔ unidade B: ×fator)_
- _(plaquetas: aceitar `10³/µL`, `10⁹/L`, `/mm³` — equivalentes; padronizar para `10⁹/L`)_

**Out-of-range (rejeitar):** _(listar caps fisiológicos)_.

> [!info] Cutoffs e ULN deferidos à Camada 2
> Comparação contra ULN / cutoffs **não acontece aqui**. Camada 1
> entrega valor cru + unidade padronizada. Toda categorização é
> decisão analítica registrada na Camada 2 (com fonte).

### 1.5 _(Domínio de coinfecção/comorbidade laboratorial)_ → `<dominio>_long`

**Variáveis:** _(listar)_. Schema padrão.

**Princípio:** extrair **todas** as observações em long-format. Nenhuma flag "ever" é construída aqui — composição é Camada 2.

### 1.6 Imagem e procedimentos → `exam_long`

Schema: `(ID, EXAM_TYPE, DATE, FLAGS_JSON, NUMERIC_VALUE, EXAM_LOC, REPORT_HASH)`.

| Campo | Descrição |
|---|---|
| `EXAM_TYPE` | _(enumerar — ex.: `US_ABD, ENDO, FIBSCAN, MRI_LIV, CT_LIV, BIOPSY`)_ |
| `DATE` | Data do exame |
| `FLAGS_JSON` | dict com chaves padronizadas extraídas do laudo pelo fornecedor via NLP/regex bilíngue: _(listar chaves + valores aceitos — ex.: `{cirrose: 0/1, hcc: 0/1, metavir: "F0..F4", lirads: "LR-1..LR-5/LR-M/LR-TIV"}`)_. Chaves não-aplicáveis ao tipo de exame ficam ausentes. |
| `NUMERIC_VALUE` | Para exames com valor numérico (ex.: FibroScan em kPa) |
| `EXAM_LOC` | `OP` (ambulatório) / `IP` (hospital) |
| `REPORT_HASH` | Hash determinístico do laudo (governança); texto livre **não** entregue |

### 1.7 HCRU — encontros, ICDs e procedimentos → `hcru_long`

Schema: `(ID, ENCOUNTER_TYPE, DATE_START, DATE_END, ICD10_LIST, PROC_CODE_LIST, MED_ATC, MED_DAYS_SUPPLY)`.

| Campo | Descrição |
|---|---|
| `ENCOUNTER_TYPE` | `OP` (consulta ambulatorial) / `ED` (emergência) / `IP` (internação) / `ICU` (UTI — sub-encontro de IP) / `DISP_MED` (dispensação) / `PROC` (procedimento) |
| `DATE_START` | Data de início do encontro/dispensação |
| `DATE_END` | Data de alta (IP, ICU); `DATE_START + MED_DAYS_SUPPLY` (DISP_MED); igual a `DATE_START` (OP/ED/PROC) |
| `ICD10_LIST` | Array de CIDs do encontro |
| `PROC_CODE_LIST` | TUSS / APAC / outros códigos de procedimento |
| `MED_ATC` | Código ATC do medicamento (somente para `DISP_MED`) |
| `MED_DAYS_SUPPLY` | Número de dias de tratamento dispensados (somente para `DISP_MED`) |

**Princípio:** todos os ICDs ficam aqui em long-format. Comorbidades como flags ever (`COMORB_*_F`) são Camada 2.

### 1.8 _(Tratamento específico ao estudo — ex.: antiviral, terapia adjuvante)_ → subset de `hcru_long`

Filtro: `ENCOUNTER_TYPE = DISP_MED` AND `MED_ATC ∈ {<lista de ATCs relevantes>}`.

Cada dispensação é uma linha. Regimes (`TX_REGIMEN`), datas agregadas (`TX_START`, `TX_END`) e duração total (`TX_DUR`) são **Camada 2**.

### 1.9 Edge cases gerais

**Resultados borderline / "zona cinza":**
- Convenção: `STATUS = I`, `RESULT_N = valor numérico` se disponível.
- Strings "indeterminado", "fronteira", "zona cinza" → `STATUS = I`.

**Múltiplos resultados no mesmo dia (mesma VAR):**
- Qualitativos com STATUS divergente: **manter ambas as linhas**; marcar `MULT_SAME_DAY = 1`. Resolução para análise (ex.: regra de máxima positividade `P > I > N`) é Camada 2.
- Quantitativos divergentes: **manter ambas as linhas** com `MULT_SAME_DAY = 1`. Resolução (ex.: mediana intra-dia) é Camada 2.
- **Razão:** divergência mesma-data sinaliza qualidade do dado; descartar na Camada 1 perde informação.

**Exames cancelados / corrigidos:**
- Status do LIS = `cancelled` / `void` / `repeat-pending` → **não entregar** (fornecedor filtra na origem).
- Status = `amended` / `corrected` → entregar **só a versão final** com `AMENDED = 1`; descartar versões anteriores.
- Repetições confirmatórias bem-sucedidas → entregar como observação normal (não dedupar; long-format preserva).

## Camada 2 — Engineered features

Construídas em pós-extração no pipeline ETL (planejar em spec separado).
Cada feature traz: **(a)** fórmula/regra, **(b)** fonte da regra
(`[[citekey]]`), **(c)** objetivo do SAP que serve.

Janela baseline padrão: `[IDX_DT − Nd, IDX_DT + Nd]` _(definir N)_.

### 2.1 Objetivo primário — _(nome curto)_

| Feature | Cálculo | Fonte |
|---|---|---|
| `<FEAT_BL>` | _(ex.: Mediana de `RESULT_N` onde `VAR=<X>, STATUS=NUM` na janela baseline)_ | SAP §X |
| `<FEAT_C_BL>` | _(categoria — ex.: `<100 / 100-1000 / >1000` unidades)_ | [[<citekey>]] |
| `<FEAT_MED_Y1..Y5>` | _(mediana anual por ano de follow-up)_ | SAP §X |
| `<FEAT_NADIR>` | _(mínimo pós-IDX_DT)_ | SAP §X |
| `<FEAT_LATEST>` | _(último valor antes de censura)_ | SAP §X |
| `<FEAT_SLOPE>` | _(slope linear (log10) ~ DATE, ≥3 pontos)_ | SAP §X |
| `<EVENT_F>` | _(critério confirmatório do desfecho primário)_ | [[<citekey>]] |
| `<EVENT_DT>` | Data da observação que abre o par confirmatório | — |

> [!info] Categorias e cutoffs
> _(Justificar cada cutoff com `[[citekey]]` — não inventar cortes
> ad-hoc; ancorar em guideline ou paper de derivação/validação.)_

### 2.2 Secundário 1 — Carga clínica e HCRU

| Feature | Cálculo | Fonte |
|---|---|---|
| `<DISEASE_F>` | _(combinação: ICD ∈ {...} OR exam_long flag = 1 OR biópsia com resultado X)_ | [[<citekey>]] |
| `<DISEASE_DT>` | `min(DATE)` da primeira evidência | — |
| `HOSP_N`, `HOSP_DAYS` | `ENCOUNTER_TYPE=IP` no follow-up | — |
| `ICU_N`, `ICU_DAYS` | Análogo para `ICU` | — |
| `ED_N` | Contagem de `ED` | — |
| `EXAM_N_<DOM>_Y` | Contagem de obs do domínio por ano de follow-up | — |
| `SURV_ADHERENCE` | Proporção de _(janela temporal)_ com ≥1 _(exame de vigilância)_: `aderente` (≥0.8) / `parcial` (0.4-0.8) / `não-aderente` (<0.4) | [[<citekey>]] |

### 2.3 Secundário 2 — Coinfecções / comorbidades laboratoriais

| Feature | Cálculo | Fonte |
|---|---|---|
| `<COINF_F>` | _(critério de coinfecção ativa — combinar marcadores serológicos + carga viral)_ | [[<citekey>]] |
| `<COINF_DT>` | `min(DATE)` da primeira evidência positiva | — |
| `<COINF_EXPOSURE_F>` | _(exposição prévia/atual, ex.: anticorpo positivo ever)_ | — |
| `<SCREEN_F>` | _(houve qualquer obs do marcador — cobertura de rastreamento)_ | [[<citekey>]] |

### 2.4 Secundário 3 — Tratamento e _(faseamento clínico)_

**Tratamento:**

| Feature | Cálculo | Fonte |
|---|---|---|
| `TX_NAIVE_F` | 1 se nenhuma `DISP_MED` antes de `IDX_DT` | — |
| `ON_TX_F` | 1 se ≥1 dispensação no follow-up pós-IDX_DT | — |
| `TX_START` | `min(DATE_START)` em `DISP_MED` | — |
| `TX_END` | `max(DATE_START + MED_DAYS_SUPPLY)` | — |
| `TX_DUR_TOTAL` | Soma de dias-supply, em meses | — |
| `TX_REGIMEN_FIRST` | Primeira classe dispensada | — |
| `TX_SWITCH_F` | 1 se `TX_REGIMEN_FIRST ≠ TX_REGIMEN_LATEST` | — |
| `TX_GAP_MAX` | Maior intervalo (dias) entre dispensações consecutivas | — |
| `MPR` | Medication Possession Ratio = soma de dias-supply ÷ dias entre 1ª e última dispensação | Convenção HCRU |

**_(Faseamento clínico — ex.: `EASL_PHASE`, estadiamento, status funcional)_** no baseline:
janela `[IDX_DT−Nd, IDX_DT+Nd]`, combinando _(listar variáveis envolvidas)_.
Fonte: [[<citekey>]] Table X.

| `<PHASE>` | _(critério A)_ | _(critério B)_ | _(critério C)_ | _(critério D)_ |
|---|---|---|---|---|
| `1` | — | — | — | — |
| `2` | — | — | — | — |
| `3` | — | — | — | — |
| `IND` | combinação atípica que não preenche 1–N | — | — | — |

**Outras features de tratamento:**

| Feature | Cálculo | Fonte |
|---|---|---|
| `<SEROCONV_F>` | _(trajetória confirmada — ex.: 2 medições N separadas por ≥Nm)_ | [[<citekey>]] |
| `<SEROCONV_DT>` | Data da 1ª observação `N` que abre o par confirmatório | — |
| `<SUPPRESSION_F>` | _(≥1 obs com `STATUS=BELOW_LLOQ` pós-IDX_DT)_ | — |
| `<SUPPRESSION_DT>` | Data da primeira `BELOW_LLOQ` | — |
| `<TIME_TO_SUPPR>` | Meses de `TX_START` até `<SUPPRESSION_DT>` | — |

### 2.5 Critérios de coorte e exclusões

| Feature | Cálculo | Fonte |
|---|---|---|
| `COHORT` | _(label principal)_ / _(label secundário)_ / `EXCL_<motivo>` | [[decisions/001_cohort_definition]] |
| `RECENT_DX` | 1 se houve obs `<negativa>` no lookback ≤Nm antes de `DX_DT` | Protocolo §X |
| `<EXCL_F>` | 1 se _(critério de exclusão — ex.: forma aguda da doença)_ | [[<citekey>]] |
| `<ACUTE_FLARE_F>` | _(critério de flare/exacerbação)_ | [[<citekey>]] |

### 2.6 Escores não-invasivos e sumárias longitudinais

Todos calculados em janela baseline (`[IDX_DT−Nd, IDX_DT+Nd]`).

**_(Escore A — ex.: FIB-4)_** (`<SCORE>_BL`):

$$\text{<SCORE>} = \frac{\text{<numerador>}}{\text{<denominador>}}$$

- Cutoffs: _(listar — ex.: ≤1.45 baixo risco; ≥3.25 alto risco)_
- Fonte: [[<citekey>]] _(derivação)_; [[<citekey>]] _(validação no contexto da doença)_.

**_(Escore B — ex.: APRI, PAGE-B, MELD)_** (`<SCORE>_BL`):

- Variáveis: _(listar)_
- Categorias: _(listar)_
- ⚠ _(advertir sobre variáveis com disponibilidade incerta — checar antes de incluir; marcar `NA` com flag de motivo se faltar componente)_
- Fonte: [[<citekey>]]

**Sumárias longitudinais:**

| Feature | Cálculo | Fonte |
|---|---|---|
| `<FLARE_F>` | 1 se qualquer obs `VAR=X, RESULT_N > N×ULN` | [[<citekey>]] |
| `<FLARE_N>` | Contagem de eventos de flare | — |
| `<BIOMARKER>_PEAK` | `max(RESULT_N)` em todo histórico | — |
| `<BIOMARKER>_LATEST` | Último `RESULT_N` ou `STATUS` | — |
| `<UNDET_DURATION>` | Meses contínuos com `STATUS ∈ {BELOW_LLOQ}` | — |
| `<TIME_TO_EVENT>` | Meses de `IDX_DT` a `<EVENT_DT>` | — |

### 2.7 Auxiliares (categorias e comorbidades)

| Feature | Cálculo |
|---|---|
| `AGE_C` | _(faixas — ex.: `18-29 / 30-44 / 45-59 / ≥60`)_ |
| `BMI_C` | `<18.5 / 18.5-24.9 / 25.0-29.9 / ≥30` (categorias OMS) |
| `COMORB_DM_F` | 1 se ICD `E10.* / E11.*` ever em `hcru_long` |
| `COMORB_HAS_F` | 1 se ICD `I10.* / I11.*` ever |
| `COMORB_OBES_F` | 1 se ICD `E66.*` ever OR `BMI_C = ≥30` |
| `COMORB_DCV_F` | 1 se ICD `I20-I25 / I50.*` ever |
| `COMORB_DRC_F` | 1 se ICD `N18.*` ever |
| `COMORB_NEO_F` | 1 se ICD `C00-C97` (excluindo _(C primário do estudo)_) ever |
| `COMORB_<DOENCA>_F` | _(comorbidade relevante ao estudo)_ |
| `COMORB_F_JSON` | dict consolidado das flags acima |

## Anexo A — Bibliografia das regras

### Já em `references/_references.bib`

| Citekey | Uso na Camada 2 / Camada 1 |
|---|---|
| `<citekey-1>` | _(features que dependem desta fonte)_ |
| `<citekey-2>` | _(...)_ |
| `benchimol2015reporting` | Aderência RECORD para reporte do dataset |
| `vonelm2007strengthening` | Aderência STROBE |

### A adicionar a `references/_references.bib` (via Zotero + Better BibTeX)

| Citekey | Paper / Documento | Necessário para |
|---|---|---|
| `<citekey-pending>` | _(referência completa)_ | _(seção / feature que precisa)_ |

## Anexo B — Tabela operacional (CSV companion)

A tabela operacional pipe-delimited para a equipe de TI do fornecedor
está em `docs/data_dictionary.csv`, gerada a partir da seção tabular
deste MD via `tools/build_data_dict_csv.py` _(quando aplicável ao
projeto)_. Schema padrão:

```
VAR | TABELA_DESTINO | DESCRICAO | TIPO | UNIDADE_PADRAO | RANGE_MIN | RANGE_MAX | OBRIGATORIO | NOTAS
```

## Histórico de mudanças

| Data | Quem | O quê |
|------|------|-------|
| YYYY-MM-DD | _____ | Versão 0.1 — esqueleto inicial copiado de `docs/templates/`. |
