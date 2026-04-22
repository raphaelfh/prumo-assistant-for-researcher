"""
create_eda_notebook.py
Gera um notebook Jupyter de EDA tabular clínico pré-populado com data profiling
completo e data quality assessment.

Uso:
    uv run python .claude/skills/tabular-eda/scripts/create_eda_notebook.py \
        --data pj_meu_projeto/data/01_raw/dados.csv \
        --label desfecho \
        --id patient_id \
        --output pj_meu_projeto/01_eda_clinical.ipynb
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime
from pathlib import Path

import nbformat as nbf
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_sample(path: Path, n: int = 5000) -> pd.DataFrame:
    """Carrega até n linhas para inspecionar tipos e nomes de colunas."""
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path).head(n)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, nrows=n)
    if suffix == ".tsv":
        return pd.read_csv(path, sep="\t", nrows=n)
    return pd.read_csv(path, nrows=n)


def _classify_columns(
    df: pd.DataFrame, label_col: str | None, id_col: str | None
) -> tuple[list[str], list[str], list[str]]:
    """Retorna listas de colunas por categoria."""
    numerics, categoricals, dates = [], [], []
    for col in df.columns:
        if col in {label_col, id_col}:
            continue
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            dates.append(col)
        elif pd.api.types.is_numeric_dtype(df[col]):
            numerics.append(col)
        else:
            categoricals.append(col)
    return numerics, categoricals, dates


def _pandera_schema_scaffold(
    df: pd.DataFrame, label_col: str | None, id_col: str | None
) -> str:
    lines = [
        "import pandera as pa",
        "from pandera import Column, DataFrameSchema",
        "",
    ]
    lines.append("schema = DataFrameSchema({")
    for col in df.columns:
        dtype = df[col].dtype
        if pd.api.types.is_integer_dtype(dtype):
            pa_type = "pa.Int64"
        elif pd.api.types.is_float_dtype(dtype):
            pa_type = "pa.Float64"
        elif pd.api.types.is_bool_dtype(dtype):
            pa_type = "pa.Bool"
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            pa_type = "pa.DateTime"
        else:
            pa_type = "pa.String"

        nullable = "nullable=True" if df[col].isna().any() else "nullable=False"
        coerce = "coerce=True"
        checks_comment = (
            "  # TODO: adicionar pa.Check.in_range(min_val, max_val)"
            " ou pa.Check.isin([...])"
        )
        lines.append(
            f'    "{col}": Column({pa_type}, {nullable}, {coerce}),{checks_comment}'
        )
    lines.append("})")
    lines.append("")
    lines.append("# df = schema.validate(df, lazy=True)  # descomente para ativar")
    return "\n".join(lines)


def _find_data_root(data_path: Path) -> Path:
    """Find the 'data/' ancestor directory from a data file path.

    Walks up from the file looking for a directory named 'data'.
    Falls back to data_path.parent.parent if not found.
    """
    for parent in data_path.parents:
        if parent.name == "data":
            return parent
    return data_path.parent.parent


# ---------------------------------------------------------------------------
# Cell builders
# ---------------------------------------------------------------------------


def _md_cell(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(source)


def _code_cell(source: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(source)


def build_notebook(
    data_path: Path,
    label_col: str | None,
    id_col: str | None,
    title: str,
) -> nbf.NotebookNode:
    nb = nbf.v4.new_notebook()
    cells: list[nbf.NotebookNode] = []

    df_sample = _load_sample(data_path)
    numerics, categoricals, dates = _classify_columns(df_sample, label_col, id_col)
    file_hash = _md5(data_path)
    suffix = data_path.suffix.lower()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ================================================================== #
    # 0 — Cabeçalho e proveniência
    # ================================================================== #
    cells.append(
        _md_cell(f"""\
# {title}

| Campo | Valor |
|-------|-------|
| **Arquivo** | `{data_path}` |
| **MD5** | `{file_hash}` |
| **Gerado em** | {now} |
| **Label** | `{label_col or "N/A"}` |
| **ID coluna** | `{id_col or "N/A"}` |

> **TODO — Proveniência:** descrever origem dos dados, critérios de inclusão/exclusão, \
versão do dataset e aprovação ética (se aplicável).
""")
    )

    # ================================================================== #
    # 1 — Setup & Imports
    # ================================================================== #
    cells.append(_md_cell("## Setup & Imports"))
    cells.append(
        _code_cell(f"""\
import warnings
import hashlib
import json
import itertools
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

sns.set_theme(style="whitegrid", context="paper")
warnings.filterwarnings("ignore", category=FutureWarning)

# ── Run identification ────────────────────────────────────────────────────
RUN_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)

# ── Paths ─────────────────────────────────────────────────────────────────
DATA_PATH = Path(r"{data_path}")
REPORTS_DIR = Path(r"{_find_data_root(data_path) / "reports"}")
REPORTS_RUN = REPORTS_DIR / f"eda_report_{{RUN_TIMESTAMP}}"
REPORTS_RUN.mkdir(parents=True, exist_ok=True)

# ── Provenance ────────────────────────────────────────────────────────────
def file_hash(path: Path, algo: str = "md5") -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

PROVENANCE = {{
    "source": str(DATA_PATH),
    "md5": file_hash(DATA_PATH),
    "timestamp": RUN_TIMESTAMP,
    "generated_by": "01_eda_clinical.ipynb",
}}

LABEL_COL = {repr(label_col)}
ID_COL = {repr(id_col)}

print(f"Source : {{DATA_PATH}}")
print(f"MD5    : {{PROVENANCE['md5']}}")
print(f"Run    : {{RUN_TIMESTAMP}}")
print(f"Reports: {{REPORTS_RUN}}")


def savefig(fig, name: str) -> Path:
    \"\"\"Persist a figure as PNG 300 dpi under REPORTS_RUN.\"\"\"
    path = REPORTS_RUN / f"{{name}}_{{RUN_TIMESTAMP}}.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    return path
""")
    )

    # ================================================================== #
    # 2 — Carregamento
    # ================================================================== #
    cells.append(_md_cell("## Carregamento dos dados"))

    if suffix == ".parquet":
        load_code = "df = pd.read_parquet(DATA_PATH)"
    elif suffix in {".xlsx", ".xls"}:
        load_code = "df = pd.read_excel(DATA_PATH)"
    elif suffix == ".tsv":
        load_code = 'df = pd.read_csv(DATA_PATH, sep="\\t")'
    else:
        load_code = "df = pd.read_csv(DATA_PATH)"

    cells.append(
        _code_cell(f"""\
{load_code}

print(f"Shape: {{df.shape[0]:,}} linhas × {{df.shape[1]}} colunas")
print(f"Memory: {{df.memory_usage(deep=True).sum() / 1e6:.1f}} MB")
df.head()
""")
    )

    # ================================================================== #
    # 3 — Visão geral & Tipos
    # ================================================================== #
    cells.append(_md_cell("## Visão geral & Tipos"))
    cells.append(
        _code_cell("""\
print("=== dtypes ===")
print(df.dtypes.to_string())
print()

# Type detection summary
type_summary = pd.DataFrame({
    "dtype_pandas": df.dtypes.astype(str),
    "n_unique": df.nunique(),
    "n_missing": df.isnull().sum(),
    "sample_value": [
        df[c].dropna().iloc[0] if df[c].notna().any() else None
        for c in df.columns
    ],
}).reset_index().rename(columns={"index": "column"})
display(type_summary)

print()
print("=== describe (numérico) ===")
display(df.describe())
print()
print("=== describe (categórico) ===")
display(df.describe(include=["object", "string"]))
""")
    )

    # ================================================================== #
    # 4 — Data Profiling completo
    # ================================================================== #
    cells.append(
        _md_cell("""\
## Data Profiling completo

Estatísticas por coluna: completeness, cardinalidade, distribuição, skewness, kurtosis, \
percentis. O CSV gerado pode ser comparado com o profiling pós-limpeza.
""")
    )
    cells.append(
        _code_cell("""\
def profile_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    \"\"\"Comprehensive per-column profiling.\"\"\"
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
            "pct_unique": round(
                100 * s.nunique(dropna=True) / max(s.notna().sum(), 1), 2
            ),
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
                "mode_pct": round(
                    100 * vc.iloc[0] / n_total, 2
                ) if len(vc) > 0 else 0,
            }

        rows.append(row)

    return pd.DataFrame(rows)


profile = profile_dataframe(df)

# Save profiling report
profile_path = REPORTS_RUN / f"data_profile_{RUN_TIMESTAMP}.csv"
profile.to_csv(profile_path, index=False)
print(f"Profile saved: {profile_path}")
display(profile)
""")
    )

    # ================================================================== #
    # 5 — Data Quality Assessment
    # ================================================================== #
    cells.append(
        _md_cell("""\
## Data Quality Assessment

Score por dimensão (0–100): **completeness**, **validity**, **consistency**, \
**uniqueness**, **timeliness** (se houver datas).
""")
    )

    id_repr = repr(id_col)
    date_repr = repr(dates) if dates else "[]"
    cells.append(
        _code_cell(f"""\
def assess_data_quality(
    df: pd.DataFrame,
    id_col: str | None = None,
    date_cols: list[str] | None = None,
) -> dict:
    \"\"\"Compute quality scores across five dimensions (0-100 each).\"\"\"
    n_total = len(df)
    scores = {{}}

    # ── Completeness ─────────────────────────────────────────────────────
    col_completeness = (1 - df.isnull().mean()) * 100
    scores["completeness"] = round(col_completeness.mean(), 2)
    scores["completeness_per_column"] = col_completeness.round(2).to_dict()

    # ── Uniqueness ───────────────────────────────────────────────────────
    n_exact_dup = df.duplicated().sum()
    row_uniqueness = 100 * (1 - n_exact_dup / max(n_total, 1))
    if id_col and id_col in df.columns:
        n_id_dup = df.duplicated(subset=[id_col]).sum()
        id_uniqueness = 100 * (1 - n_id_dup / max(n_total, 1))
        scores["uniqueness"] = round((row_uniqueness + id_uniqueness) / 2, 2)
        scores["uniqueness_detail"] = {{
            "exact_duplicates": int(n_exact_dup),
            "id_duplicates": int(n_id_dup),
        }}
    else:
        scores["uniqueness"] = round(row_uniqueness, 2)
        scores["uniqueness_detail"] = {{"exact_duplicates": int(n_exact_dup)}}

    # ── Validity ─────────────────────────────────────────────────────────
    validity_checks = []
    for col in df.columns:
        s = df[col].dropna()
        if len(s) == 0:
            continue
        if pd.api.types.is_numeric_dtype(s):
            validity_checks.append(100.0)
        elif pd.api.types.is_datetime64_any_dtype(s):
            validity_checks.append(100.0)
        else:
            types = s.apply(type).nunique()
            validity_checks.append(
                100.0 if types == 1
                else round(100 * (1 - (types - 1) / types), 2)
            )
    scores["validity"] = (
        round(np.mean(validity_checks), 2) if validity_checks else 100.0
    )

    # ── Consistency ──────────────────────────────────────────────────────
    consistency_issues = 0
    consistency_total = 0
    for col in df.select_dtypes(include="number").columns:
        s = df[col].dropna()
        if len(s) == 0:
            continue
        consistency_total += 1
        if s.min() < 0 and any(
            k in col.lower() for k in ("age", "count", "num", "n_")
        ):
            consistency_issues += 1

    date_cols = date_cols or [
        c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])
    ]
    for col in date_cols:
        if col in df.columns:
            consistency_total += 1
            n_future = (df[col] > pd.Timestamp.now()).sum()
            if n_future > 0:
                consistency_issues += 1

    scores["consistency"] = round(
        100 * (1 - consistency_issues / max(consistency_total, 1)), 2
    )
    scores["consistency_detail"] = {{
        "checks_run": consistency_total,
        "issues_found": consistency_issues,
    }}

    # ── Timeliness ───────────────────────────────────────────────────────
    if date_cols and any(c in df.columns for c in date_cols):
        timeliness_scores = []
        for col in date_cols:
            if col not in df.columns:
                continue
            s = pd.to_datetime(df[col], errors="coerce").dropna()
            if len(s) == 0:
                continue
            timeliness_scores.append(100 * len(s) / n_total)
        scores["timeliness"] = (
            round(np.mean(timeliness_scores), 2) if timeliness_scores else None
        )
    else:
        scores["timeliness"] = None

    # ── Global score ─────────────────────────────────────────────────────
    applicable = [
        v for k, v in scores.items()
        if k in ("completeness", "uniqueness", "validity", "consistency", "timeliness")
        and v is not None
    ]
    scores["global_score"] = round(np.mean(applicable), 2)

    return scores


quality = assess_data_quality(df, id_col={id_repr}, date_cols={date_repr})

# Save quality report
quality_path = REPORTS_RUN / f"quality_assessment_{{RUN_TIMESTAMP}}.json"
quality_path.write_text(
    json.dumps(quality, ensure_ascii=False, indent=2, default=str)
)
print(f"Quality assessment saved: {{quality_path}}")

# Display summary
dims = [
    "completeness", "validity", "consistency",
    "uniqueness", "timeliness", "global_score",
]
summary = {{d: quality.get(d) for d in dims}}
display(pd.DataFrame([summary]).T.rename(columns={{0: "score (0-100)"}}))
""")
    )

    # Quality visualisation
    cells.append(
        _code_cell("""\
# Quality score visualisation
dim_names = ["Completeness", "Validity", "Consistency", "Uniqueness"]
dim_scores = [
    quality["completeness"], quality["validity"],
    quality["consistency"], quality["uniqueness"],
]

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
""")
    )

    # ================================================================== #
    # 6 — Missingness
    # ================================================================== #
    cells.append(
        _md_cell("""\
## Valores faltantes

> Exploratório: MCAR/MAR/MNAR requer análise mais profunda e não deve ser concluído \
apenas com correlação de co-ausência.
""")
    )
    cells.append(
        _code_cell("""\
missing_pct = df.isnull().mean().sort_values(ascending=False).mul(100)
missing_pct = missing_pct[missing_pct > 0]

if missing_pct.empty:
    print("Sem valores faltantes.")
else:
    print(f"{len(missing_pct)} colunas com valores faltantes:")
    display(missing_pct.rename("% missing").to_frame())

    fig, ax = plt.subplots(figsize=(max(6, 0.4 * len(missing_pct)), 3.5))
    sns.barplot(x=missing_pct.index, y=missing_pct.values, ax=ax, color="#c0392b")
    ax.set_title("Percentual de valores faltantes por coluna")
    ax.set_xlabel("Coluna"); ax.set_ylabel("% Missing")
    ax.tick_params(axis="x", rotation=45)
    for lbl in ax.get_xticklabels():
        lbl.set_ha("right")
    fig.tight_layout()
    savefig(fig, "missingness_rate")
    plt.show()
""")
    )

    # Heatmap de missingness
    cells.append(
        _code_cell("""\
# Heatmap de padrão de missingness (amostra de até 500 linhas)
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
""")
    )

    # Co-absence
    cells.append(
        _code_cell("""\
# Co-absence correlation — detects MAR/MNAR patterns
cols_miss = missing_pct[missing_pct > 1].index.tolist() if not missing_pct.empty else []
if len(cols_miss) > 1:
    corr_miss = df[cols_miss].isnull().astype(int).corr()
    fig, ax = plt.subplots(figsize=(0.6 * len(cols_miss) + 2, 0.5 * len(cols_miss) + 2))
    sns.heatmap(corr_miss, annot=True, fmt=".2f", cmap="RdBu_r",
                center=0, vmin=-1, vmax=1, ax=ax)
    ax.set_title("Co-absence correlation (possible MAR/MNAR)")
    fig.tight_layout()
    savefig(fig, "missingness_coabsence")
    plt.show()

    # Flag highly correlated missing pairs
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
    print("Insufficient columns with >1% missing for co-absence analysis.")

# Save missingness report
miss_report = df.isnull().sum().reset_index()
miss_report.columns = ["column", "n_missing"]
miss_report["pct_missing"] = round(100 * miss_report["n_missing"] / len(df), 2)
miss_report = miss_report.sort_values("pct_missing", ascending=False)
miss_path = REPORTS_RUN / f"missingness_report_{RUN_TIMESTAMP}.csv"
miss_report.to_csv(miss_path, index=False)
print(f"Missingness report saved: {miss_path}")
""")
    )

    # ================================================================== #
    # 7 — Distribuições numéricas
    # ================================================================== #
    cells.append(_md_cell("## Distribuições numéricas"))
    if numerics:
        num_list = repr(numerics)
        cells.append(
            _code_cell(f"""\
NUM_COLS = {num_list}

for col in NUM_COLS:
    s = df[col].dropna()
    skew = s.skew()
    kurt = s.kurt()
    fig, axes = plt.subplots(1, 2, figsize=(8, 3),
                             gridspec_kw={{"width_ratios": [3, 1]}})
    sns.histplot(s, bins=40, ax=axes[0], color="#4c72b0", edgecolor="white")
    axes[0].set_title(f"{{col}} (skew={{skew:.2f}}, kurt={{kurt:.2f}})")
    axes[0].set_xlabel(col); axes[0].set_ylabel("Contagem")

    sns.boxplot(y=s, ax=axes[1], color="#4c72b0")
    axes[1].set_ylabel("")
    fig.tight_layout()
    savefig(fig, f"dist_num_{{col}}")
    plt.show()
""")
        )
    else:
        cells.append(_code_cell("# Nenhuma coluna numérica detectada automaticamente."))

    # ================================================================== #
    # 8 — Distribuições categóricas
    # ================================================================== #
    cells.append(_md_cell("## Distribuições categóricas"))
    if categoricals:
        cat_list = repr(categoricals)
        cells.append(
            _code_cell(f"""\
CAT_COLS = {cat_list}
TOP_N = 20  # exibir top N categorias

for col in CAT_COLS:
    vc = df[col].value_counts(dropna=False).head(TOP_N).reset_index()
    vc.columns = ["categoria", "contagem"]
    n_unique = df[col].nunique()

    fig, ax = plt.subplots(figsize=(max(5, 0.35 * len(vc)), 3.5))
    sns.barplot(data=vc, x="categoria", y="contagem", ax=ax, color="#4c72b0")
    for i, v in enumerate(vc["contagem"]):
        ax.text(i, v, str(v), ha="center", va="bottom", fontsize=8)
    ax.set_title(f"Top {{min(TOP_N, n_unique)}} categorias — {{col}} (únicas: {{n_unique}})")
    ax.set_xlabel(col); ax.set_ylabel("n")
    ax.tick_params(axis="x", rotation=45)
    for lbl in ax.get_xticklabels():
        lbl.set_ha("right")
    fig.tight_layout()
    savefig(fig, f"dist_cat_{{col}}")
    plt.show()

# ── Cardinality analysis ────────────────────────────────────────────────
cardinality = pd.DataFrame({{
    "column": CAT_COLS,
    "n_unique": [df[c].nunique() for c in CAT_COLS],
    "pct_unique": [
        round(100 * df[c].nunique() / max(df[c].notna().sum(), 1), 2)
        for c in CAT_COLS
    ],
}}).sort_values("n_unique", ascending=False)

print("Cardinality summary (categorical columns):")
display(cardinality)

high_card = cardinality[cardinality["pct_unique"] > 90]["column"].tolist()
low_card = cardinality[cardinality["n_unique"] < 2]["column"].tolist()
if high_card:
    print(f"Possible IDs (>90% unique): {{high_card}}")
if low_card:
    print(f"Near-constant (<2 unique): {{low_card}}")
""")
        )
    else:
        cells.append(
            _code_cell("# Nenhuma coluna categórica detectada automaticamente.")
        )

    # ================================================================== #
    # 9 — Outliers
    # ================================================================== #
    cells.append(
        _md_cell("""\
## Outliers (IQR + z-score)

Flagging por IQR (×1.5) e z-score (>3). Não remover aqui — apenas identificar e documentar.
""")
    )
    if numerics:
        num_list = repr(numerics)
        cells.append(
            _code_cell(f"""\
NUM_COLS = {num_list}

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

    outlier_summary.append({{
        "column": col,
        "n_outliers_iqr": int(n_out_iqr),
        "pct_iqr": round(100 * n_out_iqr / len(s), 2),
        "n_outliers_zscore": int(n_out_z),
        "pct_zscore": round(100 * n_out_z / len(s), 2),
        "iqr_lower": round(lo, 4),
        "iqr_upper": round(hi, 4),
    }})

outlier_df = pd.DataFrame(outlier_summary).sort_values("pct_iqr", ascending=False)
display(outlier_df)

# Violin plot for columns with IQR outliers
flagged = outlier_df[outlier_df["n_outliers_iqr"] > 0]["column"].tolist()
if flagged:
    for col in flagged[:6]:
        fig, ax = plt.subplots(figsize=(4, 4))
        sns.violinplot(y=df[col].dropna(), ax=ax, inner="box", color="#4c72b0")
        ax.set_title(f"Distribuição (violin) — {{col}}")
        ax.set_ylabel(col)
        fig.tight_layout()
        savefig(fig, f"outliers_violin_{{col}}")
        plt.show()
""")
        )

    # ================================================================== #
    # 10 — Correlações
    # ================================================================== #
    cells.append(_md_cell("## Correlações"))

    # Pearson
    if numerics:
        num_list = repr(numerics)
        cells.append(
            _code_cell(f"""\
# ── Pearson (numéricas) ──────────────────────────────────────────────────
_num = df[{num_list}].dropna()
corr = _num.corr(method="pearson")

fig, ax = plt.subplots(figsize=(0.5 * len(corr.columns) + 2, 0.45 * len(corr.columns) + 2))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r",
            center=0, vmin=-1, vmax=1, ax=ax, square=True)
ax.set_title("Heatmap de correlação de Pearson")
fig.tight_layout()
savefig(fig, "corr_pearson")
plt.show()

# Flag strong correlations
strong = []
for c1, c2 in itertools.combinations(corr.columns, 2):
    r = corr.loc[c1, c2]
    if abs(r) >= 0.7:
        strong.append({{"col_1": c1, "col_2": c2, "pearson_r": round(r, 3)}})
if strong:
    print("Strong correlations (|r| >= 0.7):")
    display(
        pd.DataFrame(strong).sort_values("pearson_r", key=abs, ascending=False)
    )
""")
        )

    # Cramér's V
    if categoricals:
        cat_list = repr(categoricals)
        cells.append(
            _code_cell(f"""\
# ── Cramér's V (categóricas) ────────────────────────────────────────────
def cramers_v(x: pd.Series, y: pd.Series) -> float:
    \"\"\"Cramér's V with bias correction.\"\"\"
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


CAT_COLS = {cat_list}
if len(CAT_COLS) >= 2:
    v_matrix = pd.DataFrame(
        np.zeros((len(CAT_COLS), len(CAT_COLS))),
        index=CAT_COLS, columns=CAT_COLS,
    )
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
""")
        )

    # Point-biserial
    if numerics:
        num_list = repr(numerics)
        cells.append(
            _code_cell(f"""\
# ── Point-biserial (binário × numérico) ─────────────────────────────────
binary_cols = [
    c for c in df.columns
    if df[c].nunique(dropna=True) == 2 and pd.api.types.is_numeric_dtype(df[c])
]
NUM_COLS = {num_list}

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
                pb_results.append({{
                    "binary_col": bc, "numeric_col": nc,
                    "r_pb": round(r, 3), "p_value": round(p, 4),
                }})
    if pb_results:
        print("Point-biserial correlations (|r| >= 0.2):")
        display(
            pd.DataFrame(pb_results).sort_values(
                "r_pb", key=abs, ascending=False
            )
        )
    else:
        print("No notable point-biserial correlations found.")
""")
        )

    # ================================================================== #
    # 11 — Análise por label
    # ================================================================== #
    if label_col:
        cells.append(
            _md_cell(f"""\
## Análise por label (`{label_col}`)

> **Anti-leakage:** esta seção é exploratória. Estatísticas descritivas abaixo NÃO devem \
ser usadas como critério de seleção de features.
""")
        )
        cells.append(
            _code_cell(f"""\
LABEL = "{label_col}"

# Balanceamento de classes
vc = df[LABEL].value_counts().reset_index()
vc.columns = ["classe", "n"]
vc["pct"] = round(vc["n"] / len(df) * 100, 1)
display(vc)

fig, ax = plt.subplots(figsize=(4.5, 3.5))
sns.barplot(data=vc, x="classe", y="n", ax=ax, color="#4c72b0")
for i, (n, p) in enumerate(zip(vc["n"], vc["pct"])):
    ax.text(i, n, f"{{n}}\\n({{p:.1f}}%)", ha="center", va="bottom", fontsize=9)
ax.set_title(f"Distribuição do label: {{LABEL}}")
ax.set_xlabel(LABEL); ax.set_ylabel("n")
fig.tight_layout()
savefig(fig, "label_balance")
plt.show()
""")
        )
        if numerics:
            num_list = repr(numerics)
            cells.append(
                _code_cell(f"""\
# Distribuições numéricas por classe
for col in {num_list}[:6]:
    fig, ax = plt.subplots(figsize=(5, 3.5))
    sns.violinplot(data=df.dropna(subset=[col, LABEL]),
                   x=LABEL, y=col, ax=ax, inner="box")
    ax.set_title(f"{{col}} por {{LABEL}}")
    fig.tight_layout()
    savefig(fig, f"label_num_{{col}}")
    plt.show()
""")
            )
        if categoricals:
            cat_list_short = repr(categoricals[:3])
            cells.append(
                _code_cell(f"""\
# Tabelas de contingência para categóricas
for col in {cat_list_short}:
    ct = pd.crosstab(df[col], df[LABEL], normalize="index") * 100
    display(ct.round(1))
""")
            )

    # ================================================================== #
    # 12 — Duplicatas & Integridade
    # ================================================================== #
    cells.append(_md_cell("## Duplicatas & Integridade"))
    id_check = ""
    if id_col:
        id_check = f"""\
# Unicidade por ID
n_unique_ids = df["{id_col}"].nunique()
n_total = len(df)
print(f"IDs únicos: {{n_unique_ids}} / {{n_total}} linhas")
if n_unique_ids < n_total:
    dup_ids = (
        df[df.duplicated("{id_col}", keep=False)]["{id_col}"]
        .value_counts().head(10)
    )
    print("IDs duplicados (top 10):")
    display(dup_ids)
print()
"""
    cells.append(
        _code_cell(f"""\
# Duplicatas exatas
n_dup = df.duplicated().sum()
print(f"Duplicatas exatas: {{n_dup}} ({{100 * n_dup / len(df):.1f}}%)")

{id_check}\
# Colunas com variância zero (candidatas a remoção)
zero_var = [c for c in df.columns if df[c].nunique() <= 1]
if zero_var:
    print(f"Colunas com variância zero: {{zero_var}}")
else:
    print("Nenhuma coluna com variância zero.")
""")
    )

    if dates:
        date_list = repr(dates)
        cells.append(
            _code_cell(f"""\
# Análise temporal básica
DATE_COLS = {date_list}
for col in DATE_COLS:
    df[col] = pd.to_datetime(df[col], errors="coerce")
    s = df[col].dropna()
    n_future = (s > pd.Timestamp.now()).sum()
    print(f"{{col}}: {{s.min()}} → {{s.max()}}")
    if n_future > 0:
        print(f"  ⚠ {{n_future}} dates in the future")
    fig, ax = plt.subplots(figsize=(6, 3))
    sns.histplot(s, bins=40, ax=ax, color="#4c72b0", edgecolor="white")
    ax.set_title(f"Distribuição temporal — {{col}}")
    ax.set_xlabel(col); ax.set_ylabel("n")
    fig.tight_layout()
    savefig(fig, f"date_dist_{{col}}")
    plt.show()
""")
        )

    # ================================================================== #
    # 13 — Schema Pandera
    # ================================================================== #
    cells.append(
        _md_cell("""\
## Validação de schema (Pandera)

> **TODO:** revise os ranges e valores esperados antes de ativar a validação.
""")
    )
    cells.append(_code_cell(_pandera_schema_scaffold(df_sample, label_col, id_col)))

    # ================================================================== #
    # 14 — Resumo executivo & Export
    # ================================================================== #
    cells.append(
        _md_cell("""\
## Resumo executivo & Export

Consolidação dos principais achados do EDA. Preencher os TODOs com observações clínicas.
""")
    )
    cells.append(
        _code_cell(f"""\
# ── Executive summary ────────────────────────────────────────────────────
eda_summary = {{
    "provenance": PROVENANCE,
    "shape": list(df.shape),
    "quality_scores": {{
        k: quality.get(k)
        for k in [
            "completeness", "validity", "consistency",
            "uniqueness", "timeliness", "global_score",
        ]
    }},
    "missing_columns": int((df.isnull().sum() > 0).sum()),
    "total_missing_pct": round(100 * df.isnull().mean().mean(), 2),
    "exact_duplicates": int(df.duplicated().sum()),
    "zero_variance_cols": zero_var,
}}

summary_path = REPORTS_RUN / f"eda_summary_{{RUN_TIMESTAMP}}.json"
summary_path.write_text(
    json.dumps(eda_summary, ensure_ascii=False, indent=2, default=str)
)
print(f"EDA summary saved: {{summary_path}}")
print()
print("=== Quality Scores ===")
for k, v in eda_summary["quality_scores"].items():
    print(f"  {{k:>15s}}: {{v}}")

# TODO: documentar 3–5 achados principais:
# 1. ...
# 2. ...
# 3. ...

# ── Optional: Export to processed ────────────────────────────────────────
# OUT_DIR = DATA_PATH.parent.parent / "02_processed"
# OUT_DIR.mkdir(parents=True, exist_ok=True)
# df.to_parquet(OUT_DIR / "{data_path.stem}_processed.parquet", index=False)
""")
    )

    nb.cells = cells
    return nb


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Gera notebook Jupyter de EDA tabular clínico com data profiling "
            "e quality assessment."
        ),
    )
    parser.add_argument(
        "--data",
        required=True,
        help="Caminho para CSV, Parquet, TSV ou Excel",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Coluna alvo/desfecho",
    )
    parser.add_argument(
        "--id",
        default=None,
        dest="id_col",
        help="Coluna de ID do paciente",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Caminho de saída do .ipynb",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Título do notebook",
    )
    args = parser.parse_args()

    data_path = Path(args.data).resolve()
    if not data_path.exists():
        sys.exit(f"Arquivo não encontrado: {data_path}")

    title = args.title or f"EDA — {data_path.stem}"

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = data_path.parent.parent / "01_eda_clinical.ipynb"

    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Lendo {data_path.name} para detectar schema...")
    nb = build_notebook(data_path, args.label, args.id_col, title)

    with open(out_path, "w", encoding="utf-8") as f:
        nbf.write(nb, f)

    n_cells = len(nb.cells)
    print(f"Notebook gerado: {out_path}  ({n_cells} células)")
    print()
    print("Próximos passos:")
    print("  1. Abrir o notebook e executar todas as células.")
    print("  2. Preencher os TODO de proveniência e schema Pandera.")
    print("  3. Revisar quality assessment e documentar findings.")
    print("  4. Ajustar seções de alta cardinalidade e colunas de data.")


if __name__ == "__main__":
    main()
