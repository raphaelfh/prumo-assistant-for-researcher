# Code Snippets — Data Cleaning

Ready-made snippets for each notebook section. Paste and adapt to the current project.

---

## Setup

```python
from pathlib import Path
import re
import json
from datetime import datetime

import pandas as pd
import pandera as pa
from pandera import Column, DataFrameSchema, Check
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="whitegrid", context="paper")

# ── Run identification ────────────────────────────────────────────────────────
RUN_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_RAW       = Path("data/raw")
DATA_PROCESSED = Path("data/processed")
REPORTS_DIR    = Path("data/reports")

# Timestamped subdirectories — each run gets its own folder
REPORTS_RUN    = REPORTS_DIR / f"cleaning_report_{RUN_TIMESTAMP}"
PROCESSED_RUN  = DATA_PROCESSED / f"dataset_processed_{RUN_TIMESTAMP}"

for d in (REPORTS_RUN, PROCESSED_RUN):
    d.mkdir(parents=True, exist_ok=True)

# ── Source file ──────────────────────────────────────────────────────────────
SOURCE_FILE = DATA_RAW / "source_file.csv"   # ← update

print(f"Source : {SOURCE_FILE}")
print(f"Run    : {RUN_TIMESTAMP}")
print(f"Reports: {REPORTS_RUN}")
print(f"Output : {PROCESSED_RUN}")
```

---

## Limpeza de nomes de colunas

```python
def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise to snake_case, strip accents and special characters. Logs renames."""
    ACCENT_MAP = str.maketrans(
        "àáâãäèéêëìíîïòóôõöùúûüç",
        "aaaaaeeeeiiiioooooouuuuc",
    )
    rename_map = {}
    for col in df.columns:
        new = col.strip().lower().translate(ACCENT_MAP)
        new = re.sub(r"[^a-z0-9]+", "_", new).strip("_")
        rename_map[col] = new

    renamed = {k: v for k, v in rename_map.items() if k != v}
    if renamed:
        print("Renamed columns:")
        for old, new in renamed.items():
            print(f"  '{old}' → '{new}'")
    else:
        print("No columns needed renaming.")

    return df.rename(columns=rename_map)


df_raw = pd.read_csv(SOURCE_FILE)
shape_original = df_raw.shape
print(f"Original shape: {shape_original}")

df = clean_column_names(df_raw.copy())
print(f"Columns: {df.columns.tolist()}")
```

---

## Dicionário de variáveis (Column Definition)

Every entry **must** include `name_en`, `description_en`, `dtype` (pandas dtype), and `variable_type`
(measurement scale). This separation keeps casting logic simple and makes statistical intent explicit
for EDA, validation, and downstream encoding.

**`dtype`** — the actual pandas dtype used for casting:

| dtype | pandas type |
|-------|------------|
| `"float64"` | continuous numeric |
| `"Int64"` | nullable integer (discrete counts, flags) |
| `"category"` | nominal or ordinal categorical |
| `"datetime64[ns]"` | dates and timestamps |
| `"str"` | identifiers (kept as string) |
| `"object"` | free text or mixed fields needing manual parsing |

**`variable_type`** — the measurement / statistical scale:

| variable_type | meaning | required extra fields |
|---------------|---------|----------------------|
| `"continuous"` | any real value (age, BMI) | `unit`, `expected_range` |
| `"discrete"` | countable integers (cycles, events) | `expected_range` |
| `"nominal"` | unordered categories (diagnosis, sex) | `categories` (optional, for validation) |
| `"ordinal"` | ordered categories (FIGO stage, grade) | `"order": [low…high]` (required) |
| `"binary"` | dichotomous 0/1 | — |
| `"id"` | identifier, no statistical meaning | — |
| `"date"` | temporal field | `format` (optional) |
| `"text"` | free text needing manual parsing | — |

```python
# ── Column dictionary — single source of truth for types and semantics ────────
COLUMN_DEFINITIONS: dict[str, dict] = {
    # column_key: {name_en, description_en, dtype, variable_type, ...optional metadata}
    "patient_id": {
        "name_en":        "Patient ID",
        "description_en": "Unique patient identifier",
        "dtype":          "str",
        "variable_type":  "id",
    },
    "age": {
        "name_en":        "Age",
        "description_en": "Patient age in years",
        "dtype":          "float64",
        "variable_type":  "continuous",
        "unit":           "years",
        "expected_range": (0, 120),
    },
    "num_cycles": {
        "name_en":        "Number of Cycles",
        "description_en": "Number of treatment cycles administered",
        "dtype":          "Int64",
        "variable_type":  "discrete",
        "expected_range": (1, 30),
    },
    "sex": {
        "name_en":        "Sex",
        "description_en": "Biological sex",
        "dtype":          "category",
        "variable_type":  "nominal",
        "categories":     ["M", "F"],
    },
    "diagnosis": {
        "name_en":        "Diagnosis",
        "description_en": "Primary diagnosis",
        "dtype":          "category",
        "variable_type":  "nominal",
    },
    "tumour_grade": {
        "name_en":        "Tumour Grade",
        "description_en": "Histological tumour grade",
        "dtype":          "category",
        "variable_type":  "ordinal",
        "order":          ["G1", "G2", "G3"],
    },
    "exam_date": {
        "name_en":        "Exam Date",
        "description_en": "Date of examination",
        "dtype":          "datetime64[ns]",
        "variable_type":  "date",
        "format":         "%Y-%m-%d",
    },
    "outcome": {
        "name_en":        "Outcome",
        "description_en": "Outcome event (0=no, 1=yes)",
        "dtype":          "Int64",
        "variable_type":  "binary",
    },
    # ← add all columns here
}


def apply_column_types(df: pd.DataFrame, col_defs: dict) -> pd.DataFrame:
    """Cast each column to its declared pandas dtype.
    Uses 'variable_type' to distinguish ordinal from nominal when dtype == 'category'.
    """
    df = df.copy()
    for col, meta in col_defs.items():
        if col not in df.columns:
            print(f"[WARNING] Column not found in DataFrame: '{col}'")
            continue
        dtype = meta["dtype"]
        vtype = meta.get("variable_type", "")
        match dtype:
            case "float64":
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
            case "Int64":
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
            case "category" if vtype == "ordinal":
                order = meta.get("order")
                if order is None:
                    raise ValueError(f"'{col}': variable_type='ordinal' requires an 'order' list")
                df[col] = pd.Categorical(df[col], categories=order, ordered=True)
            case "category":
                df[col] = df[col].astype("category")
            case "datetime64[ns]":
                df[col] = pd.to_datetime(df[col], format=meta.get("format"), errors="coerce")
            case "str":
                df[col] = df[col].astype(str).str.strip()
            case "object":
                pass  # keep as-is; parse manually in Ajustes específicos da tabela
    return df


df = apply_column_types(df, COLUMN_DEFINITIONS)

# Export as audit artefact
dict_path = REPORTS_RUN / f"column_definitions_{RUN_TIMESTAMP}.json"
dict_path.write_text(json.dumps(COLUMN_DEFINITIONS, ensure_ascii=False, indent=2))
print(f"Column dictionary saved: {dict_path}")
```

---

## Data Profiling & Quality Assessment

```python
def profile_dataframe(df: pd.DataFrame, col_defs: dict) -> pd.DataFrame:
    rows = []
    n_total = len(df)
    for col in df.columns:
        meta = col_defs.get(col, {})
        s = df[col]
        row: dict = {
            "column":        col,
            "name_en":       meta.get("name_en", ""),
            "variable_type": meta.get("variable_type", "—"),
            "dtype_pandas":  str(s.dtype),
            "n_total":       n_total,
            "n_missing":     int(s.isna().sum()),
            "pct_missing":   round(100 * s.isna().mean(), 2),
            "n_unique":      s.nunique(dropna=True),
        }
        if pd.api.types.is_numeric_dtype(s):
            row |= {
                "min":    s.min(),
                "max":    s.max(),
                "mean":   round(s.mean(), 4),
                "median": s.median(),
                "std":    round(s.std(), 4),
            }
        rows.append(row)
    return pd.DataFrame(rows)


profile_before = profile_dataframe(df, COLUMN_DEFINITIONS)
profile_path   = REPORTS_RUN / f"data_profile_before_{RUN_TIMESTAMP}.csv"
profile_before.to_csv(profile_path, index=False)
print(f"Profile saved: {profile_path}")
display(profile_before)
```

### Pandera validation

```python
def build_pandera_schema(col_defs: dict) -> pa.DataFrameSchema:
    """Build schema from variable_type; dtype is handled by apply_column_types."""
    DTYPE_MAP = {
        "float64":        float,
        "Int64":          float,   # Pandera coerces; nullable=True handles NAs
        "category":       "category",
        "str":            str,
        "object":         str,
    }
    cols = {}
    for col, meta in col_defs.items():
        dtype = meta["dtype"]
        vtype = meta.get("variable_type", "")
        if dtype == "datetime64[ns]":
            continue  # datetime validated visually in the profile
        checks = []
        if vtype in ("continuous", "discrete") and "expected_range" in meta:
            lo, hi = meta["expected_range"]
            checks.append(Check.between(lo, hi, error=f"{col} outside expected range [{lo}, {hi}]"))
        if vtype == "nominal" and "categories" in meta:
            checks.append(Check.isin(meta["categories"], error=f"{col} value outside allowed categories"))
        if vtype == "ordinal" and "order" in meta:
            checks.append(Check.isin(meta["order"], error=f"{col} value outside declared ordinal levels"))
        if vtype == "binary":
            checks.append(Check.isin(meta.get("categories", [0, 1]), error=f"{col} must be binary (0/1)"))
        cols[col] = Column(DTYPE_MAP.get(dtype, object), checks=checks, nullable=True, required=False)
    return pa.DataFrameSchema(cols, coerce=False)


schema = build_pandera_schema(COLUMN_DEFINITIONS)
try:
    schema.validate(df, lazy=True)
    print("Pandera: schema valid — no errors found.")
except pa.errors.SchemaErrors as exc:
    print(f"Pandera: {len(exc.failure_cases)} validation errors")
    display(exc.failure_cases)
```

---

## Análise de Missing

```python
missing_pct = df.isnull().mean().sort_values(ascending=False).mul(100)
missing_pct = missing_pct[missing_pct > 0]

if missing_pct.empty:
    print("No missing values.")
else:
    print(f"{len(missing_pct)} columns with missing values:")
    display(missing_pct.rename("% missing").to_frame())

    fig, ax = plt.subplots(figsize=(max(6, 0.4 * len(missing_pct)), 3.5))
    sns.barplot(x=missing_pct.index, y=missing_pct.values, ax=ax, color="#c0392b")
    ax.set_title("Missing value rate per column")
    ax.set_xlabel("Column"); ax.set_ylabel("% Missing")
    ax.tick_params(axis="x", rotation=45)
    for lbl in ax.get_xticklabels():
        lbl.set_ha("right")
    fig.tight_layout()
    fig.savefig(REPORTS_RUN / f"missingness_rate_{RUN_TIMESTAMP}.png", dpi=300, bbox_inches="tight")
    plt.show()

    # Co-absence correlation — detects MAR/MNAR patterns
    cols_miss = missing_pct[missing_pct > 1].index.tolist()
    if len(cols_miss) > 1:
        corr_miss = df[cols_miss].isnull().astype(int).corr()
        fig2, ax2 = plt.subplots(figsize=(0.6 * len(cols_miss) + 2, 0.5 * len(cols_miss) + 2))
        sns.heatmap(corr_miss, annot=True, fmt=".2f", cmap="RdBu_r",
                    center=0, vmin=-1, vmax=1, ax=ax2)
        ax2.set_title("Co-absence correlation (possible MAR/MNAR)")
        fig2.tight_layout()
        fig2.savefig(REPORTS_RUN / f"missingness_coabsence_{RUN_TIMESTAMP}.png",
                     dpi=300, bbox_inches="tight")
        plt.show()
```

---

## Análise de Duplicatas

```python
ID_COLUMN = "patient_id"   # ← update; set to None to check exact duplicates only


def analyze_duplicates(
    df: pd.DataFrame,
    id_col: str | None,
    reports_dir: Path,
    timestamp: str,
) -> tuple[pd.DataFrame, pd.Series]:
    exact_mask = df.duplicated(keep=False)
    summary: dict = {"exact_duplicates": int(exact_mask.sum())}

    if id_col and id_col in df.columns:
        id_mask = df.duplicated(subset=[id_col], keep=False)
        summary[f"duplicates_by_{id_col}"] = int(id_mask.sum())
        dup_df = df[id_mask].sort_values(id_col)
    else:
        dup_df = df[exact_mask]

    csv_path  = reports_dir / f"duplicates_report_{timestamp}.csv"     # reports_dir = REPORTS_RUN
    json_path = reports_dir / f"duplicates_summary_{timestamp}.json"
    dup_df.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(summary, indent=2))

    print(f"Summary: {summary}")
    print(f"Duplicate rows → {csv_path}")
    return dup_df, exact_mask


dup_df, exact_mask = analyze_duplicates(df, ID_COLUMN, REPORTS_RUN, RUN_TIMESTAMP)

# Deduplication decision — document the criterion
# keep="first" | "last" | False (remove all occurrences)
df = df.drop_duplicates(
    subset=[ID_COLUMN] if ID_COLUMN else None,
    keep="first",          # ← adjust according to clinical rule
)
print(f"Shape after deduplication: {df.shape}")
```

---

## Ajustes específicos da tabela

This section changes per project. Template with the most common patterns — add, remove, or adapt as needed. **Every block requires a `# WHY:` comment explaining the decision.**

```python
# ── Category normalisation ────────────────────────────────────────────────────
# WHY: source system recorded "sim", "Sim", "SIM" without standardisation
df["diagnosis"] = df["diagnosis"].str.strip().str.upper()

# ── Sentinel value replacement ────────────────────────────────────────────────
# WHY: value 999 means "not collected" in the source system (confirmed with team)
df["age"] = df["age"].replace(999, pd.NA)

# ── Date parsing and standardisation ─────────────────────────────────────────
# WHY: system migration in 2021 produced two formats in the same field
df["exam_date"] = pd.to_datetime(df["exam_date"], infer_datetime_format=True, errors="coerce")

# ── Outlier clipping (confirmed data-entry errors) ────────────────────────────
# WHY: validated with clinical team — values > 120 years are entry errors
df["age"] = df["age"].clip(lower=0, upper=120)

# ── Derived columns ───────────────────────────────────────────────────────────
# WHY: age bands standardised by study protocol (Appendix B)
df["age_group"] = pd.cut(
    df["age"],
    bins=[0, 18, 40, 60, 80, 120],
    labels=["<18", "18-40", "40-60", "60-80", ">80"],
    right=False,
)

# ── Adjustments log ───────────────────────────────────────────────────────────
ADJUSTMENTS_LOG = [
    "Category normalisation for 'diagnosis': strip + upper",
    "Sentinel 999 → NA in 'age'",
    "Unified date parsing for 'exam_date'",
    "Clipped 'age' to [0, 120]",
    "Derived 'age_group' (study protocol Appendix B bins)",
]
log_path = REPORTS_RUN / f"adjustments_log_{RUN_TIMESTAMP}.txt"
log_path.write_text("\n".join(ADJUSTMENTS_LOG))
print(f"Adjustments log: {log_path}")
```

---

## Reavaliação e Relatório Final

```python
# ── Post-cleaning profile ─────────────────────────────────────────────────────
profile_after = profile_dataframe(df, COLUMN_DEFINITIONS)
profile_after.to_csv(REPORTS_RUN / f"data_profile_after_{RUN_TIMESTAMP}.csv", index=False)

# Missing before vs after comparison
diff = (
    profile_before[["column", "pct_missing"]]
    .merge(profile_after[["column", "pct_missing"]], on="column", suffixes=("_before", "_after"))
    .assign(delta=lambda x: x["pct_missing_before"] - x["pct_missing_after"])
)
changed = diff[diff["delta"] != 0]
if not changed.empty:
    print("Missing rate change (before → after):")
    display(changed)

# ── Boxplots for continuous/discrete variables (visual validation) ────────────
numeric_cols = [
    c for c, m in COLUMN_DEFINITIONS.items()
    if m.get("variable_type") in ("continuous", "discrete") and c in df.columns
]
if numeric_cols:
    fig, axes = plt.subplots(1, len(numeric_cols),
                             figsize=(2.5 * len(numeric_cols), 3.5),
                             squeeze=False)
    for i, col in enumerate(numeric_cols):
        sns.boxplot(y=df[col].dropna(), ax=axes[0, i], color="#4c72b0")
        axes[0, i].set_title(col)
        axes[0, i].set_ylabel("")
    fig.suptitle("Continuous/discrete variable distributions — post-cleaning")
    fig.tight_layout()
    fig.savefig(REPORTS_RUN / f"post_cleaning_boxplots_{RUN_TIMESTAMP}.png",
                dpi=300, bbox_inches="tight")
    plt.show()

# ── Consolidated final report ─────────────────────────────────────────────────
final_report = {
    "timestamp":            RUN_TIMESTAMP,
    "source":               str(SOURCE_FILE),
    "shape_original":       list(shape_original),
    "shape_final":          list(df.shape),
    "rows_removed":         shape_original[0] - df.shape[0],
    "exact_duplicates":     int(exact_mask.sum()),
    "adjustments":          ADJUSTMENTS_LOG,
    "missing_residual_pct": (
        profile_after.set_index("column")["pct_missing"].to_dict()
    ),
}
report_path = REPORTS_RUN / f"final_report_{RUN_TIMESTAMP}.json"
report_path.write_text(json.dumps(final_report, ensure_ascii=False, indent=2))
print(f"\nFinal report: {report_path}")

# ── Parquet output (versioned + latest) ──────────────────────────────────────
import shutil

# Versioned snapshot in timestamped subdirectory
versioned_parquet = PROCESSED_RUN / "dataset_clean.parquet"
df.to_parquet(versioned_parquet, index=False)
print(f"Versioned dataset : {versioned_parquet}")

# Latest copy at root of data/processed/ — downstream notebooks read from here
latest_parquet = DATA_PROCESSED / "dataset_clean.parquet"
shutil.copy2(versioned_parquet, latest_parquet)
print(f"Latest dataset    : {latest_parquet}")

# ── Final column definitions (versioned + latest) ───────────────────────────
versioned_col_def = PROCESSED_RUN / "column_definitions.json"
versioned_col_def.write_text(json.dumps(COLUMN_DEFINITIONS, ensure_ascii=False, indent=2))

latest_col_def = DATA_PROCESSED / "column_definitions.json"
shutil.copy2(versioned_col_def, latest_col_def)
print(f"Column definitions : {versioned_col_def}")
print(f"Latest col defs    : {latest_col_def}")

display(df.head(3))
```
