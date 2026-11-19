"""
Pergunta: <preencha>
Entrada: content/02_processed/<arquivo>.parquet
Saída: experiments/<data>_<nome>/
"""

import marimo

app = marimo.App(width="medium")


@app.cell
def titulo():
    import marimo as mo

    mo.md(
        """
        # __title__

        Ajuste de modelo, na ordem do checklist de `.claude/rules/ml_modeling.md`:
        split por paciente antes de tudo, pré-processamento dentro do `Pipeline`, tuning por
        validação cruzada aninhada, teste usado uma vez, discriminação e calibração com
        intervalo por bootstrap, e a rodada gravada em `experiments/`.

        A carga abaixo gera **dado sintético** só para o notebook rodar de ponta a ponta.
        Troque pela sua antes de qualquer conclusão.
        """
    )
    return (mo,)


@app.cell
def configuracao():
    SEED = 42
    NOME_DA_RODADA = "baseline"
    ESCOPO = "__scope__"
    return ESCOPO, NOME_DA_RODADA, SEED


@app.cell
def carga(SEED):
    import numpy as np
    import pandas as pd
    from sklearn.datasets import make_classification

    # DADO SINTÉTICO. Troque por:
    #     df = pd.read_parquet(raiz / "content" / "02_processed" / "<arquivo>.parquet")
    _X, _y = make_classification(
        n_samples=600, n_features=6, n_informative=4, weights=[0.8], random_state=SEED
    )
    _rng = np.random.default_rng(SEED)
    df = pd.DataFrame(_X, columns=[f"x{i}" for i in range(_X.shape[1])])
    df["patient_id"] = _rng.integers(0, 400, size=len(df)).astype(str)
    df["desfecho"] = _y
    preditores = [c for c in df.columns if c.startswith("x")]
    return df, np, pd, preditores


@app.cell
def split(SEED, df):
    from sklearn.model_selection import GroupShuffleSplit

    # Split por paciente: o mesmo paciente nunca aparece em treino e teste.
    _gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
    _idx_treino, _idx_teste = next(_gss.split(df, groups=df["patient_id"]))
    treino = df.iloc[_idx_treino].reset_index(drop=True)
    teste = df.iloc[_idx_teste].reset_index(drop=True)
    assert not set(treino["patient_id"]) & set(teste["patient_id"])
    return teste, treino


@app.cell
def pipeline(SEED, preditores):
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    # Modelo de referência simples primeiro. Imputação e escala são ajustadas só no
    # treino de cada fold, porque estão dentro do Pipeline.
    _num = Pipeline([("imputa", SimpleImputer(strategy="median")), ("escala", StandardScaler())])
    modelo = Pipeline(
        [
            ("prep", ColumnTransformer([("num", _num, preditores)])),
            ("clf", LogisticRegression(max_iter=1000, random_state=SEED)),
        ]
    )
    grade = {"clf__C": [0.01, 0.1, 1.0, 10.0]}
    return grade, modelo


@app.cell
def validacao_cruzada_aninhada(grade, modelo, np, preditores, treino):
    from sklearn.base import clone
    from sklearn.metrics import roc_auc_score as _auc
    from sklearn.model_selection import GridSearchCV, GroupKFold

    # Fora: estima o desempenho do PROCEDIMENTO de ajuste. Dentro: escolhe o hiperparâmetro.
    _X, _y, _g = treino[preditores], treino["desfecho"], treino["patient_id"]
    _aucs = []
    for _tr, _va in GroupKFold(n_splits=5).split(_X, _y, groups=_g):
        _busca = GridSearchCV(clone(modelo), grade, cv=GroupKFold(n_splits=5), scoring="roc_auc")
        _busca.fit(_X.iloc[_tr], _y.iloc[_tr], groups=_g.iloc[_tr])
        _aucs.append(_auc(_y.iloc[_va], _busca.predict_proba(_X.iloc[_va])[:, 1]))
    auc_cv = (float(np.mean(_aucs)), float(np.std(_aucs)))

    # Ajuste final no treino inteiro, com o mesmo procedimento.
    busca = GridSearchCV(clone(modelo), grade, cv=GroupKFold(n_splits=5), scoring="roc_auc")
    busca.fit(_X, _y, groups=_g)
    return auc_cv, busca


@app.cell
def teste_unico(SEED, busca, np, preditores, teste):
    import statsmodels.api as sm
    from sklearn.metrics import brier_score_loss, roc_auc_score

    # O teste é usado UMA vez, aqui.
    y_teste = teste["desfecho"].to_numpy()
    p_teste = busca.predict_proba(teste[preditores])[:, 1]

    _rng = np.random.default_rng(SEED)
    _boot = []
    for _ in range(1000):
        _i = _rng.integers(0, len(y_teste), len(y_teste))
        if len(set(y_teste[_i])) == 2:
            _boot.append(roc_auc_score(y_teste[_i], p_teste[_i]))

    _p = np.clip(p_teste, 1e-6, 1 - 1e-6)
    _logit = np.log(_p / (1 - _p))
    _inclinacao = sm.Logit(y_teste, sm.add_constant(_logit)).fit(disp=0).params[1]
    _intercepto = (
        sm.GLM(y_teste, np.ones_like(_logit), offset=_logit, family=sm.families.Binomial())
        .fit()
        .params[0]
    )
    metricas = [
        {"metrica": "auc", "valor": roc_auc_score(y_teste, p_teste)},
        {"metrica": "auc_ic95_inf", "valor": float(np.percentile(_boot, 2.5))},
        {"metrica": "auc_ic95_sup", "valor": float(np.percentile(_boot, 97.5))},
        {"metrica": "calibracao_intercepto", "valor": float(_intercepto)},
        {"metrica": "calibracao_inclinacao", "valor": float(_inclinacao)},
        {"metrica": "brier", "valor": brier_score_loss(y_teste, p_teste)},
    ]
    return metricas, p_teste, y_teste


@app.cell
def figura_calibracao(p_teste, y_teste):
    import matplotlib.pyplot as plt
    from sklearn.calibration import CalibrationDisplay

    fig_calibracao, _ax = plt.subplots(figsize=(4, 4))
    CalibrationDisplay.from_predictions(y_teste, p_teste, n_bins=10, ax=_ax)
    _ax.set_title("Calibração no teste")
    fig_calibracao
    return (fig_calibracao,)


@app.cell
def resumo(auc_cv, busca, metricas, mo, pd):
    mo.vstack(
        [
            mo.md(
                f"AUC na validação cruzada aninhada (treino): **{auc_cv[0]:.3f} ± "
                f"{auc_cv[1]:.3f}**. Hiperparâmetro escolhido: `{busca.best_params_}`."
            ),
            pd.DataFrame(metricas),
        ]
    )
    return


@app.cell
def botao_gravar(mo):
    gravar = mo.ui.run_button(label="Gravar rodada em experiments/")
    gravar
    return (gravar,)


@app.cell
def grava_rodada(ESCOPO, NOME_DA_RODADA, SEED, auc_cv, busca, fig_calibracao, gravar, metricas, mo):
    # Toda rodada que informa uma decisão fica em experiments/. Grava no clique do botão, ou
    # sempre que o notebook roda como script (`uv run python <este arquivo>`). O helper vem
    # do módulo `ml` (`prumo add ml`).
    from __pkg__.runs import start_run

    if gravar.value or mo.app_meta().mode == "script":
        _run = start_run(NOME_DA_RODADA, seed=SEED, scope=ESCOPO, root=mo.notebook_dir().parents[1])
        _run.log_params({**busca.best_params_, "auc_cv_media": auc_cv[0]})
        _run.log_metrics(metricas)
        _run.save_fig(fig_calibracao, "calibracao")
        _pasta = _run.finish("Descreva o que mudou nesta rodada e o que ela mostrou.")
        print(f"Rodada gravada em {_pasta}")
    return


if __name__ == "__main__":
    app.run()
