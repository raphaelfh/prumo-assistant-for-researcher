"""
Pergunta: <preencha>
Entrada: content/01_raw/<arquivo>
Saída: content/02_processed/<arquivo>.parquet
"""

import marimo

app = marimo.App(width="medium")


@app.cell
def titulo():
    import marimo as mo

    mo.md(
        """
        # __title__

        Preparo: lê o dado bruto, confere o contrato e grava o derivado em Parquet.
        `content/01_raw/` é somente leitura; tudo que muda vai para `content/02_processed/`.
        Quando este preparo for usado por mais de um notebook, ele sobe para
        `src/__pkg__/` e este notebook passa a só chamá-lo.
        """
    )
    return (mo,)


@app.cell
def caminhos(mo):
    raiz = mo.notebook_dir().parents[1]
    bruto = raiz / "content" / "01_raw"
    processado = raiz / "content" / "02_processed"
    return bruto, processado


@app.cell
def carga(bruto):
    import pandas as pd

    # Troque pelo seu arquivo. Nunca grave de volta em `bruto`.
    df = pd.read_csv(bruto / "dados.csv")
    return (df,)


@app.cell
def contrato(df):
    import pandera as pa

    # Contrato mínimo do dado: colunas, tipos e faixas que o resto da análise assume.
    # Falhou aqui, a análise para aqui, antes de virar número errado mais adiante.
    schema = pa.DataFrameSchema(
        {
            "patient_id": pa.Column(str, nullable=False),
        },
        strict=False,
    )
    validado = schema.validate(df)
    return (validado,)


@app.cell
def grava(processado, validado):
    processado.mkdir(parents=True, exist_ok=True)
    validado.to_parquet(processado / "dados.parquet", index=False)
    return


if __name__ == "__main__":
    app.run()
