"""Notebooks numerados, cabeçalho e índice gerado do escopo (ADR-0047).

Tudo sintético: o projeto é um ``pj_exemplo`` em ``tmp_path`` e os modelos de tipo são
escritos pelo próprio teste, não lidos do plugin.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from par import ConfigError, PrumoError
from par.core import notebooks as N

_HEADER = '"""\nPergunta: {q}\nEntrada: {i}\nSaída: {o}\n"""\n'


def _kinds(tmp_path: Path) -> Path:
    kinds = tmp_path / "_kinds"
    kinds.mkdir()
    for kind in N.KINDS:
        (kinds / f"{kind}.py").write_text(
            '"""\n'
            "Pergunta: <preencha>\n"
            "Entrada: <preencha>\n"
            "Saída: <preencha>\n"
            '"""\n\n'
            "import marimo\n\n"
            "app = marimo.App()\n"
            f"# tipo {kind}: __title__\n",
            encoding="utf-8",
        )
    (kinds / "eda.ipynb").write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "markdown",
                        "metadata": {},
                        "source": [
                            "# __title__\n",
                            "\n",
                            "Pergunta: <preencha>\n",
                            "Entrada: <preencha>\n",
                            "Saída: <preencha>\n",
                        ],
                    }
                ],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            }
        ),
        encoding="utf-8",
    )
    return kinds


def _pj(tmp_path: Path, *scopes: str) -> Path:
    root = tmp_path / "pj_exemplo"
    (root / ".claude").mkdir(parents=True)
    (root / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    for slug in scopes or ("estudo",):
        (root / "docs" / "studies" / slug / "writing").mkdir(parents=True)
    return root


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --- numeração -----------------------------------------------------------------


def test_next_number_comeca_na_faixa_do_tipo(tmp_path: Path) -> None:
    assert N.next_number(tmp_path, "eda") == 0
    assert N.next_number(tmp_path, "prep") == 10
    assert N.next_number(tmp_path, "model") == 20
    assert N.next_number(tmp_path, "figures") == 30


def test_next_number_pula_os_ocupados_da_faixa_inclusive_ipynb(tmp_path: Path) -> None:
    _write(tmp_path / "20_baseline.py", "")
    _write(tmp_path / "21_xgb.ipynb", "{}")
    _write(tmp_path / "00_exploracao.py", "")
    assert N.next_number(tmp_path, "model") == 22


def test_next_number_faixa_cheia_sugere_consolidar(tmp_path: Path) -> None:
    for n in range(10, 20):
        _write(tmp_path / f"{n}_p{n}.py", "")
    with pytest.raises(PrumoError) as exc:
        N.next_number(tmp_path, "prep")
    assert "src/" in str(exc.value)


def test_tipo_desconhecido_lista_os_validos(tmp_path: Path) -> None:
    with pytest.raises(PrumoError) as exc:
        N.next_number(tmp_path, "treino")
    assert "eda, prep, model, figures" in str(exc.value)


# --- cabeçalho -----------------------------------------------------------------


def test_read_header_le_docstring_sem_executar(tmp_path: Path) -> None:
    nb = _write(
        tmp_path / "00_a.py",
        _HEADER.format(q="Qual a idade média?", i="content/02_processed/x.parquet", o="nenhuma")
        + "raise SystemExit('não pode executar')\n",
    )
    h = N.read_header(nb)
    assert h == N.NotebookHeader("Qual a idade média?", "content/02_processed/x.parquet", "nenhuma")
    assert h.complete


def test_read_header_placeholder_e_campo_ausente_contam_como_vazio(tmp_path: Path) -> None:
    nb = _write(tmp_path / "00_a.py", '"""\nPergunta: <preencha>\nEntrada: x\n"""\n')
    h = N.read_header(nb)
    assert h == N.NotebookHeader(None, "x", None)
    assert not h.complete
    assert h.missing == ("Pergunta", "Saída")


def test_read_header_py_invalido_ou_sem_docstring_e_vazio(tmp_path: Path) -> None:
    assert N.read_header(_write(tmp_path / "00_a.py", "def (:\n")) == N.NotebookHeader()
    assert N.read_header(_write(tmp_path / "01_b.py", "x = 1\n")) == N.NotebookHeader()


def test_read_header_ipynb_primeira_celula_markdown(tmp_path: Path) -> None:
    nb = _write(
        tmp_path / "00_a.ipynb",
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "markdown",
                        "source": "# EDA\n\n- **Pergunta:** Quantos?\n- **Entrada:** a\n"
                        "- **Saída:** b\n",
                    }
                ]
            }
        ),
    )
    assert N.read_header(nb) == N.NotebookHeader("Quantos?", "a", "b")


def test_read_header_ipynb_ilegivel_e_vazio(tmp_path: Path) -> None:
    assert N.read_header(_write(tmp_path / "00_a.ipynb", "não é json")) == N.NotebookHeader()


# --- listagem e índice -----------------------------------------------------------


def test_list_notebooks_ordena_e_ignora_o_que_nao_e_notebook_numerado(tmp_path: Path) -> None:
    _write(tmp_path / "10_preparo.py", _HEADER.format(q="q", i="i", o="o"))
    _write(tmp_path / "00_exploracao.py", "")
    _write(tmp_path / "solto.py", "")
    _write(tmp_path / "README.md", "")
    _write(tmp_path / "__marimo__" / "00_x.py", "")
    names = [e.filename for e in N.list_notebooks(tmp_path)]
    assert names == ["00_exploracao.py", "10_preparo.py"]


def test_render_index_tem_uma_linha_por_notebook_e_traco_no_vazio(tmp_path: Path) -> None:
    _write(tmp_path / "00_exploracao.py", _HEADER.format(q="Q | com barra", i="i", o="o"))
    _write(tmp_path / "10_preparo.py", "")
    block = N.render_index(N.list_notebooks(tmp_path))
    assert block.startswith(N.BLOCK_BEGIN)
    assert block.endswith(N.BLOCK_END)
    assert "| 00 | [00_exploracao.py](00_exploracao.py) | Q \\| com barra | i | o |" in block
    assert "| 10 | [10_preparo.py](10_preparo.py) | — | — | — |" in block


def test_sync_index_cria_readme_quando_falta(tmp_path: Path) -> None:
    _write(tmp_path / "00_a.py", "")
    assert N.sync_index(tmp_path, "estudo") == "created"
    text = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert text.startswith("# Notebooks — estudo")
    assert "00_a.py" in text


def test_sync_index_preserva_texto_humano_e_e_idempotente(tmp_path: Path) -> None:
    _write(tmp_path / "00_a.py", "")
    N.sync_index(tmp_path, "estudo")
    readme = tmp_path / "README.md"
    readme.write_text(
        "Nota antes.\n\n" + readme.read_text(encoding="utf-8") + "\nNota depois.\n",
        encoding="utf-8",
    )
    _write(tmp_path / "10_b.py", "")
    assert N.sync_index(tmp_path, "estudo") == "updated"
    text = readme.read_text(encoding="utf-8")
    assert text.startswith("Nota antes.")
    assert text.rstrip().endswith("Nota depois.")
    assert "10_b.py" in text
    assert N.sync_index(tmp_path, "estudo") is None


def test_sync_index_sem_bloco_acrescenta_no_fim(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "# Meus notebooks\n\nTexto meu.\n")
    _write(tmp_path / "00_a.py", "")
    assert N.sync_index(tmp_path, "estudo") == "inserted"
    text = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert text.startswith("# Meus notebooks\n\nTexto meu.\n")
    assert N.BLOCK_BEGIN in text


def test_sync_index_dry_run_nao_escreve(tmp_path: Path) -> None:
    _write(tmp_path / "00_a.py", "")
    assert N.sync_index(tmp_path, "estudo", write=False) == "created"
    assert not (tmp_path / "README.md").exists()


def test_sync_index_delimitador_sem_par_falha_com_correcao(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", f"x\n{N.BLOCK_BEGIN}\n")
    with pytest.raises(ConfigError) as exc:
        N.sync_index(tmp_path, "estudo")
    assert "prumo update" in str(exc.value)


# --- criação -------------------------------------------------------------------


def test_create_notebook_numera_preenche_e_indexa(tmp_path: Path) -> None:
    pj = _pj(tmp_path, "01_estudo")
    path = N.create_notebook(
        pj,
        "01_estudo",
        "baseline",
        kind="model",
        question="O modelo discrimina?",
        templates=_kinds(tmp_path),
    )
    assert path == pj / "notebooks" / "estudo" / "20_baseline.py"
    text = path.read_text(encoding="utf-8")
    assert "Pergunta: O modelo discrimina?" in text
    assert "# tipo model: Baseline" in text
    assert "20_baseline.py" in (path.parent / "README.md").read_text(encoding="utf-8")


def test_create_notebook_ipynb_so_para_eda(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    kinds = _kinds(tmp_path)
    path = N.create_notebook(pj, "estudo", "herdado", kind="eda", ipynb=True, templates=kinds)
    assert path.name == "00_herdado.ipynb"
    assert "# Herdado" in path.read_text(encoding="utf-8")
    with pytest.raises(PrumoError) as exc:
        N.create_notebook(pj, "estudo", "x", kind="model", ipynb=True, templates=kinds)
    assert "--kind eda" in str(exc.value)


@pytest.mark.parametrize("name", ["Baseline", "02_x", "com-hifen", "com espaço", "", "ação"])
def test_create_notebook_nome_invalido_sugere_correcao(tmp_path: Path, name: str) -> None:
    pj = _pj(tmp_path)
    with pytest.raises(PrumoError) as exc:
        N.create_notebook(pj, "estudo", name, templates=_kinds(tmp_path))
    assert "prumo add notebook" in str(exc.value)


def test_create_notebook_nao_sobrescreve_mesmo_nome(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    kinds = _kinds(tmp_path)
    N.create_notebook(pj, "estudo", "exploracao", templates=kinds)
    with pytest.raises(PrumoError) as exc:
        N.create_notebook(pj, "estudo", "exploracao", templates=kinds)
    assert "00_exploracao.py" in str(exc.value)


def test_create_notebook_escopo_inexistente_falha(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    with pytest.raises(PrumoError) as exc:
        N.create_notebook(pj, "outro", "x", templates=_kinds(tmp_path))
    assert "prumo add study outro" in str(exc.value)


# --- modelos empacotados (templates/notebook_kinds/) ------------------------------

_ALLOWED_IMPORTS = {
    "marimo",
    "numpy",
    "pandas",
    "pandera",
    "sklearn",
    "statsmodels",
    "matplotlib",
    "seaborn",
    "__pkg__",
}


def test_modelos_empacotados_existem_fora_do_payload_dos_modulos() -> None:
    from par.core.paths import resolve_resource
    from par.core.scaffold import discover_modules

    kinds = N.default_kinds_dir()
    assert kinds.parent == resolve_resource("templates")
    assert {p.name for p in kinds.iterdir()} >= {f"{k}.py" for k in N.KINDS} | {"eda.ipynb"}
    assert all(kinds not in m.path.parents and m.path != kinds for m in discover_modules())


@pytest.mark.parametrize("kind", list(N.KINDS))
def test_modelo_compila_tem_cabecalho_e_so_importa_a_stack(kind: str) -> None:
    import ast

    path = N.default_kinds_dir() / f"{kind}.py"
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    doc = ast.get_docstring(tree) or ""
    for campo in ("Pergunta:", "Entrada:", "Saída:"):
        assert campo in doc
    assert "sys.path" not in text
    assert "__title__" in text
    roots = {
        ((node.module or "") if isinstance(node, ast.ImportFrom) else alias.name).split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    assert roots <= _ALLOWED_IMPORTS, roots - _ALLOWED_IMPORTS


@pytest.mark.parametrize("kind", list(N.KINDS))
def test_modelo_nao_define_o_mesmo_nome_em_duas_celulas(kind: str) -> None:
    """No marimo, nome global (inclusive import) só pode nascer numa célula; o
    notebook com nome repetido nem roda (`MultipleDefinitionError`)."""
    import ast

    tree = ast.parse((N.default_kinds_dir() / f"{kind}.py").read_text(encoding="utf-8"))
    vistos: dict[str, str] = {}
    for cell in tree.body:
        if not isinstance(cell, ast.FunctionDef):
            continue
        nomes: set[str] = set()
        for node in cell.body:
            if isinstance(node, ast.Import | ast.ImportFrom):
                nomes |= {(a.asname or a.name).split(".")[0] for a in node.names}
            elif isinstance(node, ast.Assign):
                for alvo in node.targets:
                    elts = alvo.elts if isinstance(alvo, ast.Tuple) else [alvo]
                    nomes |= {e.id for e in elts if isinstance(e, ast.Name)}
        for nome in nomes:
            if nome.startswith("_"):
                continue
            assert nome not in vistos, f"`{nome}` definido em {vistos[nome]} e em {cell.name}"
            vistos[nome] = cell.name


def test_create_notebook_com_modelos_reais_nao_deixa_marcador(tmp_path: Path) -> None:
    pj = _pj(tmp_path, "01_estudo")
    for kind in N.KINDS:
        path = N.create_notebook(pj, "01_estudo", f"nb_{kind}", kind=kind)
        text = path.read_text(encoding="utf-8")
        assert "__title__" not in text
        assert "__scope__" not in text
        assert "__pkg__" not in text
    model = (pj / "notebooks" / "estudo" / "20_nb_model.py").read_text(encoding="utf-8")
    assert 'ESCOPO = "estudo"' in model
    assert "from exemplo.runs import start_run" in model


# --- doctor e update -----------------------------------------------------------

_MARIMO = "import marimo\n\napp = marimo.App()\n"


def test_notebook_issues_projeto_limpo_nao_acusa_nada(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    N.create_notebook(pj, "estudo", "exploracao", question="q", templates=_kinds(tmp_path))
    nb = pj / "notebooks" / "estudo" / "00_exploracao.py"
    nb.write_text(_HEADER.format(q="q", i="i", o="o") + _MARIMO, encoding="utf-8")
    N.sync_index(nb.parent, "estudo")
    assert N.notebook_issues(pj) == ([], [])


def test_notebook_issues_fora_do_lugar_com_git_mv(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    _write(pj / "eda.ipynb", "{}")
    _write(pj / "src" / "exemplo" / "analise.py", _MARIMO)
    _write(pj / "src" / "exemplo" / "cohort.py", "def load(): ...\n")
    _write(pj / ".venv" / "lib" / "x.ipynb", "{}")
    _write(pj / "experiments" / "r1" / "x.ipynb", "{}")
    _write(pj / "content" / "01_raw" / "x.ipynb", "{}")
    issues, _ = N.notebook_issues(pj)
    assert len(issues) == 1
    assert issues[0].startswith("[notebook_fora_do_lugar]")
    assert "`git mv eda.ipynb notebooks/estudo/`" in issues[0]
    assert "src/exemplo/analise.py" in issues[0]
    assert "cohort.py" not in issues[0]


def test_notebook_issues_escopo_prefixado(tmp_path: Path) -> None:
    pj = _pj(tmp_path, "01_estudo")
    _write(pj / "notebooks" / "01_estudo" / "00_a.py", _HEADER.format(q="q", i="i", o="o"))
    N.sync_index(pj / "notebooks" / "01_estudo", "estudo")
    issues, _ = N.notebook_issues(pj)
    assert issues == [
        "[notebook_escopo_prefixado] `notebooks/01_estudo/` usa o slug com prefixo numérico; "
        "o nome de código do escopo é `estudo`. Rode: `git mv notebooks/01_estudo "
        "notebooks/estudo`."
    ]


def test_notebook_issues_sem_numero_sugere_o_nome(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    _write(pj / "notebooks" / "estudo" / "00_a.py", _HEADER.format(q="q", i="i", o="o"))
    _write(pj / "notebooks" / "estudo" / "Análise Final.py", _MARIMO)
    _write(pj / "notebooks" / "estudo" / "util.py", "x = 1\n")
    N.sync_index(pj / "notebooks" / "estudo", "estudo")
    issues, _ = N.notebook_issues(pj)
    assert len(issues) == 1
    assert "[notebook_sem_numero]" in issues[0]
    assert "notebooks/estudo/01_analise_final.py" in issues[0]


def test_notebook_issues_cabecalho_incompleto_e_aviso(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    _write(pj / "notebooks" / "estudo" / "00_a.py", '"""\nPergunta: q\n"""\n' + _MARIMO)
    N.sync_index(pj / "notebooks" / "estudo", "estudo")
    issues, warnings = N.notebook_issues(pj)
    assert issues == []
    assert len(warnings) == 1
    assert "[notebook_sem_cabecalho]" in warnings[0]
    assert "Entrada, Saída" in warnings[0]


def test_notebook_issues_indice_atrasado_e_sync_all(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    _write(pj / "notebooks" / "estudo" / "00_a.py", _HEADER.format(q="q", i="i", o="o"))
    issues, _ = N.notebook_issues(pj)
    assert any("[notebook_indice_desatualizado]" in i and "prumo update" in i for i in issues)
    assert N.sync_all_indexes(pj, write=False) == ["notebooks/estudo/README.md"]
    assert not (pj / "notebooks" / "estudo" / "README.md").exists()
    assert N.sync_all_indexes(pj) == ["notebooks/estudo/README.md"]
    assert N.notebook_issues(pj) == ([], [])
    assert N.sync_all_indexes(pj) == []


def test_notebook_issues_projeto_sem_notebooks(tmp_path: Path) -> None:
    assert N.notebook_issues(_pj(tmp_path)) == ([], [])
