---
paths:
  - "**/*.py"
  - "**/*.ipynb"
---

<!-- Esta rule é cópia inicial do template global em .claude/rules/coding_style.md.
     Pode ser customizada livremente para este projeto; vale sobre a rule
     da raiz dentro do escopo deste pj_*. Mantida sem alterações, o
     comportamento é idêntico ao global. -->

# Estilo de código e legibilidade

## Ferramentas

- Formatação e lint: **Ruff** (`ruff format`, `ruff check`). Preferir configuração no `pyproject.toml` quando existir.
- Imports: ordem padrão (stdlib, terceiros, locais); evitar `import *`.

## Legibilidade (prioridade em healthcare)

- Nomes explícitos alinhados ao **domínio** (ex.: `patient_id`, `study_uid`, `label_positive`), não abreviações opacas.
- Funções **curtas** com responsabilidade única; quando uma célula de notebook crescer, extrair para módulo `.py` no mesmo `pj_*` e importar.
- Em código extraído para `.py`, usar **type hints** em funções públicas.
- Comentários em **português** só onde o “porquê” não for óbvio; evitar narrar o que o código já diz.

## PyTorch Lightning

- `LightningModule` com métodos nomeados (`encode_image`, `encode_clinical`, `fuse_features`, …) em vez de lógica monolítica em `forward`.
- `training_step` / `validation_step` **enxutos**: chamam helpers; métricas via **TorchMetrics** quando possível.

## Visualização

- Padrão do monorepo: **seaborn + matplotlib** (figuras publicáveis em papers).
- Setup recomendado no topo de cada notebook:

  ```python
  import matplotlib.pyplot as plt
  import seaborn as sns

  sns.set_theme(style="whitegrid", context="paper")  # "talk" em apresentações
  ```

- Sempre: título, rótulos de eixos com unidades clínicas, legenda nomeada. Preferir `ax = …` + retornar/salvar `fig` em vez de `plt.show()` global.
- Exportar para `data/reports/…` ou `docs/findings/_assets/…` via `fig.savefig(path, dpi=300, bbox_inches="tight")`.
- Plotly **só** em dashboards interativos explicitamente pedidos.
