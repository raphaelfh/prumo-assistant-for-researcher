import marimo

app = marimo.App(width="medium")


@app.cell
def titulo():
    import marimo as mo

    mo.md(
        """
        # Exploração

        Primeira análise deste escopo. Cada célula é uma função: o marimo lê as
        dependências entre elas e reexecuta o que depende do que você mudou.
        """
    )
    return (mo,)


@app.cell
def carga():
    # Código próprio se importa pelo NOME do pacote — `uv sync` instala o
    # projeto em editable, então não há caminho a consertar à mão:
    #
    #     from <pacote>.cohort import load_raw
    #
    #     df = load_raw()
    return


if __name__ == "__main__":
    app.run()
