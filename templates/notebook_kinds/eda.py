"""
Pergunta: <preencha>
Entrada: <preencha>
Saída: <preencha>
"""

import marimo

app = marimo.App(width="medium")


@app.cell
def titulo():
    import marimo as mo

    mo.md(
        """
        # __title__

        Exploração. Cada célula é uma função: o marimo lê as dependências entre elas e
        reexecuta o que depende do que você mudou. Leia esquema e agregados, não linhas.
        """
    )
    return (mo,)


@app.cell
def caminhos(mo):
    # Raiz do projeto a partir da pasta deste notebook (notebooks/<escopo>/).
    raiz = mo.notebook_dir().parents[1]
    dados = raiz / "content"
    return (dados,)


@app.cell
def carga(dados):
    # Código próprio se importa pelo NOME do pacote: `uv sync` instala o projeto em
    # editable, então não há caminho a consertar à mão.
    #
    #     from __pkg__.cohort import load_raw
    #
    #     df = load_raw()
    _ = dados
    return


if __name__ == "__main__":
    app.run()
