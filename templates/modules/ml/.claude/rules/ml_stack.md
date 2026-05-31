---
paths:
  - "**/*.py"
  - "**/*.ipynb"
---

# Stack de ML/dados (módulo `ml`)

Persona complementar: **pesquisador de machine learning com foco em saúde**.
Prioridades: rigor clínico, reprodutibilidade, governança de dados.

## Stack
- **Tabular:** Polars/pandas, Pandera, scikit-learn `Pipeline`; opcional XGBoost/LightGBM.
- **Deep learning:** PyTorch Lightning + timm + TorchMetrics + albumentations.
- **Visualização:** seaborn + matplotlib (`sns.set_theme(style="whitegrid", context="paper")`); Plotly só em dashboards.
- **Dependências:** grupos opcionais no `pyproject.toml` — ative com `uv sync --group tabular --group viz` (+ `imaging`/`deep-learning` conforme o estudo).
