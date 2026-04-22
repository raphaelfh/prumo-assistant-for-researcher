---
name: data-cleaning
description: Standardised clinical/tabular data-cleaning workflow for pj_* notebooks. Invoke whenever the user asks for cleaning, pre-processing, data cleaning, data treatment, data quality analysis, missing values, duplicates, dataset preparation, "fix the CSV", "QC the table", or wants to structure a cleaning notebook — even if they do not use the exact term "data cleaning". Covers automatic report generation in data/reports/ and Parquet output.
---

# Data Cleaning — standardised workflow

The goal is to produce a **traceable, auditable, and reproducible** notebook where every cleaning decision is documented with its rationale. Raw data in `data/raw/` is never modified; the cleaned output goes to `data/processed/` as Parquet, and text/JSON reports to `data/reports/`.

### Timestamped output directories

Each execution creates its own subdirectory named with a prefix inside both `data/reports/` and `data/processed/`:

```
data/
├── raw/                             # never modified
├── processed/
│   ├── dataset_processed_20260329_143000/   # versioned snapshot
│   │   ├── dataset_clean.parquet
│   │   └── column_definitions.json
│   ├── dataset_clean.parquet              # ← latest (symlink or copy)
│   └── column_definitions.json            # ← latest (symlink or copy)
└── reports/
    ├── cleaning_report_20260329_143000/   # all audit artefacts for this run
    │   ├── column_definitions_20260329_143000.json
    │   ├── data_profile_before_20260329_143000.csv
    │   ├── data_profile_after_20260329_143000.csv
    │   ├── duplicates_report_20260329_143000.csv
    │   ├── duplicates_summary_20260329_143000.json
    │   ├── adjustments_log_20260329_143000.txt
    │   └── final_report_20260329_143000.json
    └── cleaning_report_20260401_091500/   # another run — coexists without conflict
        └── ...
```

This isolation means you can re-run the same notebook multiple times and always know which artefacts came from which execution. The "latest" copies at the root of `processed/` let downstream notebooks (`03_clinical_model`, etc.) load data without knowing the timestamp.

---

## Required notebook structure

Create **exactly** these sections (`##` headings) in this order. Do not skip or reorder — this ensures traceability for clinical reviewers and future reproducibility.

| Section | Purpose |
|---------|---------|
| **Setup** | Imports, paths, run timestamp |
| **Limpeza de nomes de colunas** | snake_case + accent removal before anything else |
| **Dicionário de variáveis** | Single source of truth for types, semantics, and English names; automatic cast |
| **Data Profiling & Quality Assessment** | Per-column summary + Pandera validation |
| **Análise de Missing** | Quantification, heatmap, co-absence patterns |
| **Análise de Duplicatas** | Exact and per-ID duplicates; CSV report generated automatically |
| **Ajustes específicos da tabela** | Replaces, dates, outliers, derived columns — each block with `# WHY:` |
| **Reavaliação e Relatório Final** | Post-cleaning profile, validation visualisations, JSON + Parquet |

---

## Principles to follow in every section

**Mandatory inline documentation.** Every non-obvious decision in **Ajustes específicos da tabela** gets a `# WHY:` comment explaining the clinical or technical reason. This applies even to things that seem trivial — a future reviewer will have no context.

**Never modify `data/raw/`** in any cell. All transformations start from an explicit in-memory copy.

**Reports are artefacts, not prints.** Instead of `print(df.duplicated().sum())`, save a CSV to `data/reports/`. Prints are ephemeral; files survive between sessions.

**One `RUN_TIMESTAMP` per execution.** All output artefacts carry the same timestamp in their name, making it easy to trace which run produced which report.

**All column definitions in English.** `COLUMN_DEFINITIONS` must include `name_en` and `description_en` for every column. When the source data is in another language, use the original (snake_case-normalised) column key and document its English meaning via these two fields. This keeps the data dictionary machine-readable and interoperable in English regardless of the source language.

**Two separate fields govern type and measurement scale:**

- **`dtype`** — the actual pandas dtype used for casting. This is what `apply_column_types` uses directly, keeping the function simple and predictable:

  | `dtype` | pandas type | typical use |
  |---------|-------------|-------------|
  | `"float64"` | `float64` | continuous numeric |
  | `"Int64"` | nullable integer | discrete counts, binary flags |
  | `"category"` | `CategoricalDtype` | nominal or ordinal categorical |
  | `"datetime64[ns]"` | `datetime64[ns]` | dates and timestamps |
  | `"str"` | `object` (stripped) | identifiers |
  | `"object"` | `object` | free text needing manual parsing |

- **`variable_type`** — the measurement / statistical scale. Used by `build_pandera_schema`, EDA visualisations, and downstream encoding decisions:

  | `variable_type` | meaning | required extra fields |
  |----------------|---------|----------------------|
  | `"continuous"` | any real value (age, BMI) | `unit`, `expected_range` |
  | `"discrete"` | countable integers (cycles, events) | `expected_range` |
  | `"nominal"` | unordered categories (diagnosis, sex) | `categories` (optional, for isin check) |
  | `"ordinal"` | ordered categories (FIGO stage, grade) | `"order": [low…high]` (**required**) |
  | `"binary"` | dichotomous 0/1 | — |
  | `"id"` | identifier, no statistical meaning | — |
  | `"date"` | temporal field | `format` (optional) |
  | `"text"` | free text needing manual parsing | — |

When `dtype == "category"` and `variable_type == "ordinal"`, `apply_column_types` casts to `pd.Categorical(ordered=True)` using the `"order"` list. All other `"category"` columns are cast unordered.

---

## How to use the code reference

Read `references/code_snippets.md` for ready-made snippets for each section. The file is organised in the same section order and can be pasted directly into notebook cells.

When adapting to the current project:
- Replace `"source_file.csv"` with the actual file under `DATA_RAW`
- Fill in `COLUMN_DEFINITIONS` with every column before running **Dicionário de variáveis**; `name_en` and `description_en` are required for every entry
- In **Ajustes específicos da tabela** add project-specific adjustments — do not delete the template, just extend it
- The `ID_COLUMN` in **Análise de Duplicatas** must be the study's unique key (e.g. `"patient_id"`, `"study_id"`)

---

## Closing checklist

Before marking the notebook as complete:

- [ ] `data/raw/` untouched — zero in-place writes
- [ ] `data/processed/dataset_processed_{RUN_TIMESTAMP}/dataset_clean.parquet` generated (versioned snapshot)
- [ ] `data/processed/dataset_clean.parquet` exists as latest copy (for downstream notebooks)
- [ ] `data/processed/dataset_processed_{RUN_TIMESTAMP}/column_definitions.json` generated
- [ ] `data/processed/column_definitions.json` exists as latest copy
- [ ] `data/reports/cleaning_report_{RUN_TIMESTAMP}/` contains: `column_definitions_*.json`, `data_profile_*.csv`, `duplicates_report_*.csv`, `duplicates_summary_*.json`, `adjustments_log_*.txt`, `final_report_*.json`
- [ ] Every `COLUMN_DEFINITIONS` entry has `name_en`, `description_en`, `dtype`, and `variable_type`
- [ ] Every `variable_type: "ordinal"` entry has an `"order"` list (lowest → highest)
- [ ] Every adjustment in **Ajustes específicos da tabela** has `# WHY:` with clinical or technical justification
- [ ] Pandera reported no critical validation errors on the final check
- [ ] `uv run ruff check . && uv run ruff format .` passing (if `dev` group is synced)
