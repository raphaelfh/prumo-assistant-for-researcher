# Code Snippets — EDA Tabular Clínico

Ready-made snippets for each notebook section. Paste and adapt to the current project. Visualização é **seaborn + matplotlib**.

---

## Setup & Proveniência

```python
from pathlib import Path
import hashlib
import itertools
import json
from datetime import datetime

import numpy as np
import pandas as pd
import pandera as pa
from pandera import Column, DataFrameSchema, Check
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

sns.set_theme(style="whitegrid", context="paper")

# ── Run identification ────────────────────────────────────────────────────────
RUN_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_RAW   = Path("data/01_raw")
REPORTS_DIR = Path("data/reports")
REPORTS_RUN = REPORTS_DIR / f"eda_report_{RUN_TIMESTAMP}"
REPORTS_RUN.mkdir(parents=True, exist_ok=True)

# ── Source file ──────────────────────────────────────────────────────────────
SOURCE_FILE = DATA_RAW / "source_file.csv"   # ← update

# ── Provenance ───────────────────────────────────────────────────────────────
def file_hash(path: Path, algo: str = "md5") -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

PROVENANCE = {
    "source": str(SOURCE_FILE),
    "md5": file_hash(SOURCE_FILE),
    "timestamp": RUN_TIMESTAMP,
    "generated_by": "01_eda_clinical.ipynb",
}

print(f"Source : {SOURCE_FILE}")
print(f"MD5    : {PROVENANCE['md5']}")
print(f"Run    : {RUN_TIMESTAMP}")
print(f"Reports: {REPORTS_RUN}")


def savefig(fig, name: str) -> Path:
    """Persist a figure as PNG 300 dpi under REPORTS_RUN."""
    path = REPORTS_RUN / f"{name}_{RUN_TIMESTAMP}.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    return path
```

---

## Carregamento dos dados

```python
df = pd.read_csv(SOURCE_FILE)   # ← adjust for parquet/excel/tsv

print(f"Shape: {df.shape[0]:,} linhas × {df.shape[1]} colunas")
print(f"Memory: {df.memory_usage(deep=True).sum() / 1e6:.1f} MB")
df.head()
```

---

## Visão geral & Tipos

```python
print("=== dtypes ===")
print(df.dtypes.to_string())
print()

# Type detection summary
type_summary = pd.DataFrame({
    "dtype_pandas": df.dtypes.astype(str),
    "n_unique": df.nunique(),
    "n_missing": df.isnull().sum(),
    "sample_value": [df[c].dropna().iloc[0] if df[c].notna().any() else None for c in df.columns],
}).reset_index().rename(columns={"index": "column"})
display(type_summary)

print()
print("=== describe (numérico) ===")
display(df.describe())
print()
print("=== describe (categórico) ===")
display(df.describe(include=["object", "string"]))
```

---

## Data Profiling completo

```python
def profile_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Comprehensive per-column profiling with clinical data in mind."""
    rows = []
    n_total = len(df)

    for col in df.columns:
        s = df[col]
        row: dict = {
            "column": col,
            "dtype_pandas": str(s.dtype),
            "n_total": n_total,
            "n_missing": int(s.isna().sum()),
            "pct_missing": round(100 * s.isna().mean(), 2),
            "n_present": int(s.notna().sum()),
            "n_unique": s.nunique(dropna=True),
            "pct_unique": round(100 * s.nunique(dropna=True) / max(s.notna().sum(), 1), 2),
        }

        if pd.api.types.is_numeric_dtype(s):
            desc = s.describe()
            row |= {
                "min": s.min(),
                "p01": s.quantile(0.01),
                "p05": s.quantile(0.05),
                "q1": desc.get("25%"),
                "median": desc.get("50%"),
                "q3": desc.get("75%"),
                "p95": s.quantile(0.95),
                "p99": s.quantile(0.99),
                "max": s.max(),
                "mean": round(s.mean(), 4),
                "std": round(s.std(), 4),
                "skewness": round(s.skew(), 4),
                "kurtosis": round(s.kurt(), 4),
                "n_zeros": int((s == 0).sum()),
                "n_negative": int((s < 0).sum()),
            }
        elif pd.api.types.is_datetime64_any_dtype(s):
            row |= {
                "min": str(s.min()),
                "max": str(s.max()),
                "n_future": int((s > pd.Timestamp.now()).sum()),
            }
        else:
            vc = s.value_counts(dropna=True)
            row |= {
                "mode": vc.index[0] if len(vc) > 0 else None,
                "mode_freq": int(vc.iloc[0]) if len(vc) > 0 else 0,
                "mode_pct": round(100 * vc.iloc[0] / n_total, 2) if len(vc) > 0 else 0,
            }

        rows.append(row)

    return pd.DataFrame(rows)


profile = profile_dataframe(df)
profile_path = REPORTS_RUN / f"data_profile_{RUN_TIMESTAMP}.csv"
profile.to_csv(profile_path, index=False)
print(f"Profile saved: {profile_path}")
display(profile)
```

---

## Data Quality Assessment

```python
def assess_data_quality(
    df: pd.DataFrame,
    id_col: str | None = None,
    date_cols: list[str] | None = None,
) -> dict:
    """Compute quality scores across five dimensions (0–100 each)."""
    n_total = len(df)
    scores = {}

    # Completeness
    col_completeness = (1 - df.isnull().mean()) * 100
    scores["completeness"] = round(col_completeness.mean(), 2)
    scores["completeness_per_column"] = col_completeness.round(2).to_dict()

    # Uniqueness
    n_exact_dup = df.duplicated().sum()
    row_uniqueness = 100 * (1 - n_exact_dup / max(n_total, 1))
    if id_col and id_col in df.columns:
        n_id_dup = df.duplicated(subset=[id_col]).sum()
        id_uniqueness = 100 * (1 - n_id_dup / max(n_total, 1))
        scores["uniqueness"] = round((row_uniqueness + id_uniqueness) / 2, 2)
        scores["uniqueness_detail"] = {
            "exact_duplicates": int(n_exact_dup),
            "id_duplicates": int(n_id_dup),
        }
    else:
        scores["uniqueness"] = round(row_uniqueness, 2)
        scores["uniqueness_detail"] = {"exact_duplicates": int(n_exact_dup)}

    # Validity
    validity_checks = []
    for col in df.columns:
        s = df[col].dropna()
        if len(s) == 0:
            continue
        if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_datetime64_any_dtype(s):
            validity_checks.append(100.0)
        else:
            types = s.apply(type).nunique()
            validity_checks.append(100.0 if types == 1 else round(100 * (1 - (types - 1) / types), 2))
    scores["validity"] = round(np.mean(validity_checks), 2) if validity_checks else 100.0

    # Consistency
    consistency_issues = 0
    consistency_total = 0
    for col in df.select_dtypes(include="number").columns:
        s = df[col].dropna()
        if len(s) == 0:
            continue
        consistency_total += 1
        if s.min() < 0 and ("age" in col.lower() or "count" in col.lower() or "num" in col.lower()):
            consistency_issues += 1

    date_cols = date_cols or [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    for col in date_cols:
        if col in df.columns:
            consistency_total += 1
            n_future = (df[col] > pd.Timestamp.now()).sum()
            if n_future > 0:
                consistency_issues += 1

    scores["consistency"] = round(100 * (1 - consistency_issues / max(consistency_total, 1)), 2)
    scores["consistency_detail"] = {
        "checks_run": consistency_total,
        "issues_found": consistency_issues,
    }

    # Timeliness
    if date_cols and any(c in df.columns for c in date_cols):
        timeliness_scores = []
        for col in date_cols:
            if col not in df.columns:
                continue
            s = pd.to_datetime(df[col], errors="coerce").dropna()
            if len(s) == 0:
                continue
            timeliness_scores.append(100 * len(s) / n_total)
        scores["timeliness"] = round(np.mean(timeliness_scores), 2) if timeliness_scores else None
    else:
        scores["timeliness"] = None

    applicable = [v for k, v in scores.items()
                  if k in ("completeness", "uniqueness", "validity", "consistency", "timeliness")
                  and v is not None]
    scores["global_score"] = round(np.mean(applicable), 2)

    return scores


LABEL_COL = None       # ← update if applicable
ID_COL = None          # ← update if applicable
DATE_COLS = []         # ← update: list of date column names

quality = assess_data_quality(df, id_col=ID_COL, date_cols=DATE_COLS)
quality_path = REPORTS_RUN / f"quality_assessment_{RUN_TIMESTAMP}.json"
quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2, default=str))
print(f"Quality assessment saved: {quality_path}")

dims = ["completeness", "validity", "consistency", "uniqueness", "timeliness", "global_score"]
summary = {d: quality.get(d) for d in dims}
display(pd.DataFrame([summary]).T.rename(columns={0: "score (0–100)"}))
```

### Quality score visualisation

```python
dim_names = ["Completeness", "Validity", "Consistency", "Uniqueness"]
dim_scores = [quality["completeness"], quality["validity"],
              quality["consistency"], quality["uniqueness"]]

if quality.get("timeliness") is not None:
    dim_names.append("Timeliness")
    dim_scores.append(quality["timeliness"])

colors = ["#2ecc71" if s >= 90 else "#f39c12" if s >= 70 else "#e74c3c" for s in dim_scores]

fig, ax = plt.subplots(figsize=(6, 0.45 * len(dim_names) + 1))
sns.barplot(x=dim_scores, y=dim_names, palette=colors, ax=ax)
for i, s in enumerate(dim_scores):
    ax.text(s + 1, i, f"{s:.1f}", va="center", fontsize=9)
ax.set_xlim(0, 105)
ax.set_xlabel("Score (0–100)")
ax.set_ylabel("")
ax.set_title(f"Data Quality Assessment — Global: {quality['global_score']:.1f}/100")
fig.tight_layout()
savefig(fig, "quality_scores")
plt.show()
```

---

## Missingness

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
    ax.set_xlabel("Coluna")
    ax.set_ylabel("% Missing")
    ax.set_title("Taxa de valores faltantes por coluna")
    ax.tick_params(axis="x", rotation=45)
    for lbl in ax.get_xticklabels():
        lbl.set_ha("right")
    fig.tight_layout()
    savefig(fig, "missingness_rate")
    plt.show()
```

### Heatmap de padrão de missingness

```python
_sample = df.isnull().astype(int).head(500)
if _sample.any().any():
    fig, ax = plt.subplots(figsize=(10, max(3, 0.3 * len(_sample.columns))))
    sns.heatmap(_sample.T, cmap=["white", "#ef553b"], cbar=False, ax=ax,
                xticklabels=False, yticklabels=_sample.columns.tolist())
    ax.set_title("Padrão de missingness (vermelho = faltante, amostra 500 linhas)")
    ax.set_xlabel("Índice da observação")
    fig.tight_layout()
    savefig(fig, "missingness_pattern")
    plt.show()
```

### Co-absence correlation (MAR/MNAR patterns)

```python
cols_miss = missing_pct[missing_pct > 1].index.tolist()
if len(cols_miss) > 1:
    corr_miss = df[cols_miss].isnull().astype(int).corr()

    fig, ax = plt.subplots(figsize=(0.6 * len(cols_miss) + 2, 0.5 * len(cols_miss) + 2))
    sns.heatmap(corr_miss, annot=True, fmt=".2f", cmap="RdBu_r",
                center=0, vmin=-1, vmax=1, ax=ax)
    ax.set_title("Co-absence correlation (possible MAR/MNAR)")
    fig.tight_layout()
    savefig(fig, "missingness_coabsence")
    plt.show()

    threshold = 0.5
    pairs = []
    for c1, c2 in itertools.combinations(cols_miss, 2):
        r = corr_miss.loc[c1, c2]
        if abs(r) >= threshold:
            pairs.append({"col_1": c1, "col_2": c2, "corr": round(r, 3)})
    if pairs:
        print(f"Co-absence pairs with |r| >= {threshold}:")
        display(pd.DataFrame(pairs))
    else:
        print(f"No co-absence pairs with |r| >= {threshold}.")
else:
    print("Insufficient columns with >1% missing for co-absence analysis.")

miss_report = df.isnull().sum().reset_index()
miss_report.columns = ["column", "n_missing"]
miss_report["pct_missing"] = round(100 * miss_report["n_missing"] / len(df), 2)
miss_report = miss_report.sort_values("pct_missing", ascending=False)
miss_path = REPORTS_RUN / f"missingness_report_{RUN_TIMESTAMP}.csv"
miss_report.to_csv(miss_path, index=False)
print(f"Missingness report saved: {miss_path}")
```

---

## Distribuições numéricas

```python
NUM_COLS = df.select_dtypes(include="number").columns.tolist()
# ← remove ID/label columns if needed:
# NUM_COLS = [c for c in NUM_COLS if c not in [ID_COL, LABEL_COL]]

for col in NUM_COLS:
    s = df[col].dropna()
    skew = s.skew()
    kurt = s.kurt()

    fig, axes = plt.subplots(1, 2, figsize=(8, 3),
                             gridspec_kw={"width_ratios": [3, 1]})
    sns.histplot(s, bins=40, ax=axes[0], color="#4c72b0", edgecolor="white")
    axes[0].set_title(f"{col} (skew={skew:.2f}, kurt={kurt:.2f})")
    axes[0].set_xlabel(col)
    axes[0].set_ylabel("Contagem")

    sns.boxplot(y=s, ax=axes[1], color="#4c72b0")
    axes[1].set_ylabel("")
    fig.tight_layout()
    savefig(fig, f"dist_num_{col}")
    plt.show()
```

---

## Distribuições categóricas

```python
CAT_COLS = df.select_dtypes(include=["object", "string", "category"]).columns.tolist()
TOP_N = 20

for col in CAT_COLS:
    vc = df[col].value_counts(dropna=False).head(TOP_N).reset_index()
    vc.columns = ["categoria", "contagem"]
    n_unique = df[col].nunique()

    fig, ax = plt.subplots(figsize=(max(5, 0.35 * len(vc)), 3.5))
    sns.barplot(data=vc, x="categoria", y="contagem", ax=ax, color="#4c72b0")
    for i, v in enumerate(vc["contagem"]):
        ax.text(i, v, str(v), ha="center", va="bottom", fontsize=8)
    ax.set_title(f"Top {min(TOP_N, n_unique)} categorias — {col} (únicas: {n_unique})")
    ax.set_xlabel(col)
    ax.set_ylabel("n")
    ax.tick_params(axis="x", rotation=45)
    for lbl in ax.get_xticklabels():
        lbl.set_ha("right")
    fig.tight_layout()
    savefig(fig, f"dist_cat_{col}")
    plt.show()

cardinality = pd.DataFrame({
    "column": CAT_COLS,
    "n_unique": [df[c].nunique() for c in CAT_COLS],
    "pct_unique": [round(100 * df[c].nunique() / max(df[c].notna().sum(), 1), 2) for c in CAT_COLS],
}).sort_values("n_unique", ascending=False)

print("Cardinality summary (categorical columns):")
display(cardinality)

high_card = cardinality[cardinality["pct_unique"] > 90]["column"].tolist()
low_card = cardinality[cardinality["n_unique"] < 2]["column"].tolist()
if high_card:
    print(f"⚠ Possible IDs (>90% unique): {high_card}")
if low_card:
    print(f"⚠ Near-constant (<2 unique): {low_card}")
```

---

## Outliers (IQR)

```python
NUM_COLS = df.select_dtypes(include="number").columns.tolist()

outlier_summary = []
for col in NUM_COLS:
    s = df[col].dropna()
    if len(s) == 0:
        continue
    q1, q3 = s.quantile([0.25, 0.75])
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    n_out_iqr = ((s < lo) | (s > hi)).sum()

    z = np.abs(stats.zscore(s, nan_policy="omit"))
    n_out_z = (z > 3).sum()

    outlier_summary.append({
        "column": col,
        "n_outliers_iqr": int(n_out_iqr),
        "pct_iqr": round(100 * n_out_iqr / len(s), 2),
        "n_outliers_zscore": int(n_out_z),
        "pct_zscore": round(100 * n_out_z / len(s), 2),
        "iqr_lower": round(lo, 4),
        "iqr_upper": round(hi, 4),
    })

outlier_df = pd.DataFrame(outlier_summary).sort_values("pct_iqr", ascending=False)
display(outlier_df)

flagged = outlier_df[outlier_df["n_outliers_iqr"] > 0]["column"].tolist()
if flagged:
    for col in flagged[:6]:
        fig, ax = plt.subplots(figsize=(4, 4))
        sns.violinplot(y=df[col].dropna(), ax=ax, inner="box", color="#4c72b0")
        ax.set_title(f"Distribuição (violin) — {col}")
        ax.set_ylabel(col)
        fig.tight_layout()
        savefig(fig, f"outliers_violin_{col}")
        plt.show()
```

---

## Correlações

### Pearson (numéricas)

```python
NUM_COLS = df.select_dtypes(include="number").columns.tolist()
if len(NUM_COLS) >= 2:
    corr = df[NUM_COLS].corr(method="pearson")

    fig, ax = plt.subplots(figsize=(0.5 * len(NUM_COLS) + 2, 0.45 * len(NUM_COLS) + 2))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r",
                center=0, vmin=-1, vmax=1, ax=ax, square=True)
    ax.set_title("Heatmap de correlação de Pearson")
    fig.tight_layout()
    savefig(fig, "corr_pearson")
    plt.show()

    strong = []
    for c1, c2 in itertools.combinations(NUM_COLS, 2):
        r = corr.loc[c1, c2]
        if abs(r) >= 0.7:
            strong.append({"col_1": c1, "col_2": c2, "pearson_r": round(r, 3)})
    if strong:
        print("Strong correlations (|r| >= 0.7):")
        display(pd.DataFrame(strong).sort_values("pearson_r", key=abs, ascending=False))
```

### Cramér's V (categóricas)

```python
def cramers_v(x: pd.Series, y: pd.Series) -> float:
    """Cramér's V with bias correction (Bergsma & Wicher, 2013)."""
    ct = pd.crosstab(x, y)
    n = ct.sum().sum()
    if n == 0:
        return 0.0
    chi2 = stats.chi2_contingency(ct, correction=False)[0]
    r, k = ct.shape
    phi2 = chi2 / n
    phi2_corr = max(0, phi2 - (k - 1) * (r - 1) / (n - 1))
    k_corr = k - (k - 1) ** 2 / (n - 1)
    r_corr = r - (r - 1) ** 2 / (n - 1)
    denom = min(k_corr - 1, r_corr - 1)
    return np.sqrt(phi2_corr / denom) if denom > 0 else 0.0


CAT_COLS = df.select_dtypes(include=["object", "string", "category"]).columns.tolist()
if len(CAT_COLS) >= 2:
    v_matrix = pd.DataFrame(np.zeros((len(CAT_COLS), len(CAT_COLS))),
                            index=CAT_COLS, columns=CAT_COLS)
    for c1, c2 in itertools.combinations(CAT_COLS, 2):
        v = cramers_v(df[c1].fillna("__NA__"), df[c2].fillna("__NA__"))
        v_matrix.loc[c1, c2] = v
        v_matrix.loc[c2, c1] = v
    np.fill_diagonal(v_matrix.values, 1.0)

    fig, ax = plt.subplots(figsize=(0.55 * len(CAT_COLS) + 2, 0.5 * len(CAT_COLS) + 2))
    sns.heatmap(v_matrix.astype(float), annot=True, fmt=".2f", cmap="Blues",
                vmin=0, vmax=1, ax=ax, square=True)
    ax.set_title("Cramér's V — associação entre variáveis categóricas")
    fig.tight_layout()
    savefig(fig, "corr_cramers_v")
    plt.show()
```

### Point-biserial (binário × numérico)

```python
binary_cols = [c for c in df.columns
               if df[c].nunique(dropna=True) == 2
               and pd.api.types.is_numeric_dtype(df[c])]

if binary_cols and NUM_COLS:
    pb_results = []
    for bc in binary_cols:
        for nc in NUM_COLS:
            if bc == nc:
                continue
            mask = df[[bc, nc]].dropna()
            if len(mask) < 10:
                continue
            r, p = stats.pointbiserialr(mask[bc], mask[nc])
            if abs(r) >= 0.2:
                pb_results.append({
                    "binary_col": bc, "numeric_col": nc,
                    "r_pb": round(r, 3), "p_value": round(p, 4),
                })
    if pb_results:
        print("Point-biserial correlations (|r| >= 0.2):")
        display(pd.DataFrame(pb_results).sort_values("r_pb", key=abs, ascending=False))
```

---

## Análise por label

Only generated when `LABEL_COL` is provided. This section is exploratory — statistics here should NOT be used for feature selection (that happens on training data only).

```python
LABEL_COL = None   # ← update

if LABEL_COL and LABEL_COL in df.columns:
    vc = df[LABEL_COL].value_counts().reset_index()
    vc.columns = ["classe", "n"]
    vc["pct"] = round(vc["n"] / len(df) * 100, 1)
    display(vc)

    fig, ax = plt.subplots(figsize=(4.5, 3.5))
    sns.barplot(data=vc, x="classe", y="n", ax=ax, color="#4c72b0")
    for i, (n, p) in enumerate(zip(vc["n"], vc["pct"])):
        ax.text(i, n, f"{n}\n({p:.1f}%)", ha="center", va="bottom", fontsize=9)
    ax.set_title(f"Distribuição do label: {LABEL_COL}")
    ax.set_xlabel(LABEL_COL)
    ax.set_ylabel("n")
    fig.tight_layout()
    savefig(fig, f"label_balance_{LABEL_COL}")
    plt.show()

    NUM_COLS_LABEL = [c for c in df.select_dtypes(include="number").columns
                      if c != LABEL_COL]
    for col in NUM_COLS_LABEL[:6]:
        fig, ax = plt.subplots(figsize=(5, 3.5))
        sns.violinplot(data=df.dropna(subset=[col, LABEL_COL]),
                       x=LABEL_COL, y=col, ax=ax, inner="box")
        ax.set_title(f"{col} por {LABEL_COL}")
        fig.tight_layout()
        savefig(fig, f"label_num_{col}")
        plt.show()

    CAT_COLS_LABEL = [c for c in df.select_dtypes(include=["object", "string", "category"]).columns
                      if c != LABEL_COL]
    for col in CAT_COLS_LABEL[:3]:
        ct = pd.crosstab(df[col], df[LABEL_COL], normalize="index") * 100
        display(ct.round(1))
```

---

## Duplicatas & Integridade

```python
ID_COL = None   # ← update

n_dup = df.duplicated().sum()
print(f"Duplicatas exatas: {n_dup} ({100 * n_dup / len(df):.1f}%)")

if ID_COL and ID_COL in df.columns:
    n_unique_ids = df[ID_COL].nunique()
    n_total = len(df)
    print(f"IDs únicos: {n_unique_ids} / {n_total} linhas")
    if n_unique_ids < n_total:
        dup_ids = df[df.duplicated(ID_COL, keep=False)][ID_COL].value_counts().head(10)
        print("IDs duplicados (top 10):")
        display(dup_ids)

zero_var = [c for c in df.columns if df[c].nunique() <= 1]
if zero_var:
    print(f"Colunas com variância zero (candidatas a remoção): {zero_var}")
else:
    print("Nenhuma coluna com variância zero.")

DATE_COLS = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
for col in DATE_COLS:
    s = df[col].dropna()
    n_future = (s > pd.Timestamp.now()).sum()
    print(f"{col}: {s.min()} → {s.max()}")
    if n_future > 0:
        print(f"  ⚠ {n_future} dates in the future")

    fig, ax = plt.subplots(figsize=(6, 3))
    sns.histplot(s, bins=40, ax=ax, color="#4c72b0", edgecolor="white")
    ax.set_title(f"Distribuição temporal — {col}")
    ax.set_xlabel(col); ax.set_ylabel("n")
    fig.tight_layout()
    savefig(fig, f"date_dist_{col}")
    plt.show()
```

---

## Schema Pandera (scaffold)

```python
# ← This cell is auto-generated by create_eda_notebook.py with real column names.
# Paste the generated Pandera scaffold here and fill in TODOs.

# schema = DataFrameSchema({
#     "column_name": Column(pa.Float64, nullable=True, coerce=True),
#     # TODO: add pa.Check.in_range(min_val, max_val) for clinical constraints
# })
# schema.validate(df, lazy=True)
```

---

## Resumo executivo & Export

```python
eda_summary = {
    "provenance": PROVENANCE,
    "shape": list(df.shape),
    "quality_scores": {
        k: quality.get(k) for k in
        ["completeness", "validity", "consistency", "uniqueness", "timeliness", "global_score"]
    },
    "missing_columns": int((df.isnull().sum() > 0).sum()),
    "total_missing_pct": round(100 * df.isnull().mean().mean(), 2),
    "exact_duplicates": int(df.duplicated().sum()),
    "zero_variance_cols": zero_var,
    "high_cardinality_categoricals": high_card if "high_card" in dir() else [],
    "strong_correlations_count": len(strong) if "strong" in dir() else 0,
}

summary_path = REPORTS_RUN / f"eda_summary_{RUN_TIMESTAMP}.json"
summary_path.write_text(json.dumps(eda_summary, ensure_ascii=False, indent=2, default=str))
print(f"EDA summary saved: {summary_path}")

# TODO: documentar 3–5 achados principais:
# 1. ...
# 2. ...
# 3. ...

# Opcional: export processed
# OUT_DIR = Path("data/02_processed"); OUT_DIR.mkdir(parents=True, exist_ok=True)
# df.to_parquet(OUT_DIR / "dataset_eda.parquet", index=False)
```
