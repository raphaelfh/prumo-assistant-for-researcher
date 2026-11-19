"""
Pergunta: <preencha>
Entrada: experiments/<rodada>/metrics.csv
Saída: experiments/<rodada>/figs/
"""

import marimo

app = marimo.App(width="medium")


@app.cell
def titulo():
    import marimo as mo

    mo.md(
        """
        # __title__

        Figuras e tabelas do manuscrito, a partir de uma rodada gravada. A figura sai do
        que a rodada registrou, não de um ajuste refeito aqui: assim o número do texto e
        o da figura vêm da mesma fonte.
        """
    )
    return (mo,)


@app.cell
def escolhe_rodada(mo):
    raiz = mo.notebook_dir().parents[1]
    _rodadas = sorted(p.parent.name for p in (raiz / "experiments").glob("*/metrics.csv"))
    rodada = mo.ui.dropdown(
        options=_rodadas, value=_rodadas[-1] if _rodadas else None, label="Rodada"
    )
    rodada
    return raiz, rodada


@app.cell
def metricas(mo, raiz, rodada):
    import pandas as pd

    mo.stop(rodada.value is None, mo.md("Nenhuma rodada com `metrics.csv` em `experiments/`."))
    pasta = raiz / "experiments" / rodada.value
    tabela = pd.read_csv(pasta / "metrics.csv")
    tabela
    return pasta, tabela


@app.cell
def figura(pasta, tabela):
    import matplotlib.pyplot as plt
    import seaborn as sns

    sns.set_theme(style="whitegrid", context="paper")
    fig, _ax = plt.subplots(figsize=(5, 3))
    sns.barplot(data=tabela, x="valor", y="metrica", ax=_ax)
    _ax.set_xlabel("")
    _ax.set_ylabel("")
    (pasta / "figs").mkdir(exist_ok=True)
    fig.savefig(pasta / "figs" / "metricas.png", dpi=300, bbox_inches="tight")
    fig
    return


if __name__ == "__main__":
    app.run()
