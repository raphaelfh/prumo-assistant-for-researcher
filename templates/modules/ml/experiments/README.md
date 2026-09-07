# Rodadas persistidas

Cada rodada é uma pasta irmã aqui: `experiments/<run_id>/`. Superadas vão
para `experiments/_archive/<run_id>/` — mesma estrutura, sem perder o
histórico.

```
experiments/
├── _archive/           # rodadas superadas
└── 2026-09-07_baseline/
    ├── README.md       # o que mudou nesta rodada e o que ela mostrou
    ├── metrics.csv     # versionado
    ├── figs/           # versionado
    └── model.joblib    # gitignorado: regenerável
```

## Por que na raiz, e não em `docs/`

`docs/` é a raiz única de leitura — é o que o `qmd` indexa e o que as skills
de wiki varrem. Bundle de modelo ali polui o índice de busca do projeto sem
nunca ser conteúdo de leitura. Saída de máquina fica ao lado de `build/` e
`reviews/`, fora da árvore de prosa.

## O que versionar

O `README.md` da rodada é o que sobrevive: registra a configuração, o
resultado e a decisão que saiu dele. Métricas e figuras acompanham. O bundle
serializado não — ele se regenera a partir do código e dos dados, e alguns MB
por rodada afundam um repo que já carrega PDFs.
