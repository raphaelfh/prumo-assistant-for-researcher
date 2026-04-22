---
name: clinical-metrics
description: Guia completo para avaliação de classificadores clínicos — métricas (AUROC, PR-AUC, sensibilidade, especificidade, Brier score, calibração), figuras seaborn/matplotlib prontas para publicação e bootstrap CI. Invocar sempre que houver avaliação de modelo em contexto de saúde, escolha de threshold, análise de curva ROC/PR, comparação de modelos, reporte de performance ou quando o usuário pede "métricas" em notebooks de pj_* healthcare — mesmo que não mencione "métricas clínicas" explicitamente.
---

# Avaliação de modelos clínicos

Figuras destinadas a **publicação em papers** — padrão seaborn + matplotlib.

## Métricas obrigatórias

Sempre reportar:

| Métrica | Função sklearn | Observação |
|---------|---------------|------------|
| **AUROC** | `roc_auc_score` | Discriminação geral |
| **PR-AUC** | `average_precision_score` | Preferir ao AUROC em dados desbalanceados |
| **Sensibilidade / Especificidade** | via `roc_curve` | No threshold escolhido — explicitar critério |
| **Brier Score** | `brier_score_loss` | Calibração; 0 = perfeito, 0.25 = nulo em 50/50 |
| **IC 95% bootstrap** | ver snippet abaixo | Obrigatório para n < 500 ou publicação |

Complementares quando comparando com baseline clínico: NRI, IDI.
Fairness: AUC por subgrupo (sexo, faixa etária, sítio).

## Seleção de threshold

Não usar 0.5 arbitrariamente. Critérios:

- **Youden (J = Sens + Espec − 1)** — balanceado, ponto de partida padrão
- **Custo clínico explícito** — FN custa mais que FP (triagem de sepse, câncer)? Priorizar sensibilidade
- **Prevalência** — threshold ótimo muda com prevalência da coorte de aplicação

```python
from sklearn.metrics import roc_curve

fpr, tpr, thresholds = roc_curve(y_true, y_prob)
j_idx = (tpr - fpr).argmax()
best_threshold = thresholds[j_idx]
sens, spec = tpr[j_idx], 1 - fpr[j_idx]
```

## Setup padrão

```python
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="whitegrid", context="paper")    # "talk" em apresentações
```

Salvar figuras em `docs/findings/_assets/<slug>.png` ou `data/reports/.../fig_*.png` via `fig.savefig(path, dpi=300, bbox_inches="tight")`.

## Implementação

### Curva ROC

```python
from sklearn.metrics import roc_curve, auc

fpr, tpr, _ = roc_curve(y_true, y_prob)
roc_auc = auc(fpr, tpr)

fig, ax = plt.subplots(figsize=(4.5, 4.5))
sns.lineplot(x=fpr, y=tpr, ax=ax, linewidth=2,
             label=f"ROC (AUC = {roc_auc:.3f})")
ax.plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1)

# Threshold escolhido
ax.scatter([fpr[j_idx]], [tpr[j_idx]], color="red", s=60, zorder=5,
           label=f"Threshold = {best_threshold:.2f}")

ax.set_xlabel("1 − Especificidade (Taxa de FP)")
ax.set_ylabel("Sensibilidade")
ax.set_title("Curva ROC")
ax.set_xlim(0, 1); ax.set_ylim(0, 1.02)
ax.legend(loc="lower right")
fig.tight_layout()
```

### Curva Precision-Recall

```python
from sklearn.metrics import precision_recall_curve, average_precision_score

precision, recall, _ = precision_recall_curve(y_true, y_prob)
ap = average_precision_score(y_true, y_prob)
prevalence = y_true.mean()

fig, ax = plt.subplots(figsize=(4.5, 4.5))
sns.lineplot(x=recall, y=precision, ax=ax, linewidth=2,
             label=f"PR (AP = {ap:.3f})")
ax.axhline(prevalence, linestyle="--", color="gray", linewidth=1,
           label=f"Prevalência = {prevalence:.2f}")

ax.set_xlabel("Recall (Sensibilidade)")
ax.set_ylabel("Precisão (VPP)")
ax.set_title("Curva Precision-Recall")
ax.set_xlim(0, 1); ax.set_ylim(0, 1.02)
ax.legend(loc="lower left")
fig.tight_layout()
```

### Calibração (reliability diagram)

```python
from sklearn.calibration import calibration_curve

frac_pos, mean_pred = calibration_curve(y_true, y_prob, n_bins=10, strategy="quantile")

fig, ax = plt.subplots(figsize=(4.5, 4.5))
sns.lineplot(x=mean_pred, y=frac_pos, ax=ax, marker="o", linewidth=2, label="Modelo")
ax.plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1, label="Calibração perfeita")

ax.set_xlabel("Probabilidade predita média")
ax.set_ylabel("Fração de positivos observados")
ax.set_title("Curva de calibração")
ax.set_xlim(0, 1); ax.set_ylim(0, 1.02)
ax.legend(loc="upper left")
fig.tight_layout()
```

### Bootstrap CI (AUROC e PR-AUC)

```python
import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score


def bootstrap_metrics(y_true, y_prob, n_bootstrap: int = 1000,
                      ci: float = 0.95, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    aucs, aps = [], []
    for _ in range(n_bootstrap):
        idx = rng.integers(0, len(y_true), len(y_true))
        yt, yp = y_true[idx], y_prob[idx]
        if len(np.unique(yt)) < 2:
            continue
        aucs.append(roc_auc_score(yt, yp))
        aps.append(average_precision_score(yt, yp))
    alpha = (1 - ci) / 2
    lo, hi = 100 * alpha, 100 * (1 - alpha)
    return {
        "auroc": (float(np.mean(aucs)), np.percentile(aucs, [lo, hi])),
        "ap":    (float(np.mean(aps)),  np.percentile(aps,  [lo, hi])),
    }


# Uso:
# m = bootstrap_metrics(y_true, y_prob)
# print(f"AUROC {m['auroc'][0]:.3f} (IC95%: {m['auroc'][1][0]:.3f}–{m['auroc'][1][1]:.3f})")
```

### Comparação de modelos (curvas sobrepostas)

```python
# Dict de modelos: {"Logistic": (y_prob_lr), "XGB": (y_prob_xgb), ...}
fig, ax = plt.subplots(figsize=(4.5, 4.5))
for name, y_prob in modelos.items():
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    auc_ = auc(fpr, tpr)
    sns.lineplot(x=fpr, y=tpr, ax=ax, linewidth=2, label=f"{name} (AUC={auc_:.3f})")
ax.plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1)
ax.set_xlabel("1 − Especificidade"); ax.set_ylabel("Sensibilidade")
ax.set_title("Comparação ROC")
ax.legend(loc="lower right")
fig.tight_layout()
```

### AUC por subgrupo (fairness)

```python
# df tem colunas: y_true, y_prob, subgroup (categoria)
rows = []
for sg, g in df.groupby("subgroup"):
    if g["y_true"].nunique() < 2:
        continue
    rows.append({
        "subgroup": sg,
        "n": len(g),
        "auroc": roc_auc_score(g["y_true"], g["y_prob"]),
    })
res = pd.DataFrame(rows).sort_values("auroc")

fig, ax = plt.subplots(figsize=(5, 0.4 * len(res) + 1))
sns.barplot(data=res, y="subgroup", x="auroc", ax=ax, color="#4c72b0")
for i, (_, r) in enumerate(res.iterrows()):
    ax.text(r["auroc"] + 0.005, i, f"{r['auroc']:.3f} (n={r['n']})",
            va="center", fontsize=9)
ax.set_xlim(0.5, 1.0)
ax.set_xlabel("AUROC"); ax.set_ylabel("")
ax.set_title("Discriminação por subgrupo")
fig.tight_layout()
```

## Reporte mínimo (publicação / notebook final)

```
Modelo X:
  AUROC:    0.847 (IC95%: 0.821–0.873)
  PR-AUC:   0.612 (IC95%: 0.578–0.646)
  Brier:    0.112
  Threshold: 0.42 (Youden) → Sens 0.81 / Espec 0.76
```

- Nunca reportar apenas acurácia em coortes desbalanceadas.
- Calibração ruim (curva longe da diagonal) invalida uso de probabilidades para tomada de decisão.
- Explicitar sempre: critério de threshold, prevalência da coorte, se split é temporal ou aleatório.

## Arquivamento no wiki

Quando o notebook gerar uma comparação ou análise reutilizável, arquivar como finding:

```
/wiki-query "qual modelo performa melhor no subgrupo <X>?"   # usa os resultados
# A skill oferece arquivar em docs/findings/<slug>.md com frontmatter
# type: finding, sources: [<notebook>], tags: [roc, auroc, …].
```

Figuras vão em `docs/findings/_assets/` e são linkadas no markdown do finding.
