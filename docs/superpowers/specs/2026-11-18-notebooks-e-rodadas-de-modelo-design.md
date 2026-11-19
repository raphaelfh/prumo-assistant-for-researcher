---
title: Notebooks numerados com índice e rodadas de modelo padronizadas
date: 2026-11-18
status: approved
tags: [notebooks, ml, marimo, experiments, scaffold, doctor, adr-0047, adr-0009, adr-0027]
---

# Notebooks numerados com índice e rodadas de modelo padronizadas

## Problema

Os módulos `notebooks` e `ml` entregam a convenção em prosa e quase nenhum mecanismo.

- `prumo add notebooks` cria um único `00_exploracao.py`. O segundo notebook é cópia manual, sem
  nome, número ou cabeçalho padronizados.
- Quem abre `notebooks/<escopo>/` não tem índice: precisa abrir cada arquivo para saber que
  pergunta ele responde e o que ele grava.
- A rule manda nomear a pasta sem o prefixo numérico do escopo (`01_estudo` → `estudo`), mas o
  overlay troca `__scope__` pelo slug cru. A pasta nasce com o nome que a rule proíbe.
- O módulo `ml` copia um `eda.ipynb` de duas células para a raiz do projeto, contra as próprias
  regras (marimo como padrão, notebook em `notebooks/<escopo>/`).
- `experiments/<run_id>/` existe só como README. Nada cria a rodada nem grava configuração,
  semente, métricas ou o resumo. Cada rodada sai num formato diferente.
- As rules de `ml` cobrem vazamento de dados, mas não o ajuste do modelo: tuning, calibração,
  incerteza, correção de otimismo, relato.
- `prumo add ml` sem o módulo `code` cita grupos de dependência que não existem no projeto.

## Decisão

Registrada na [ADR-0047](../../adr/adr-0047-notebooks-indexados-e-rodadas.md). Em resumo: um
comando cria notebooks numerados a partir de modelos por tipo, um bloco gerado lista os notebooks
do escopo, um helper copiado para o pacote do projeto padroniza a rodada, e o `doctor` acusa o
que saiu do lugar.

### 1. Layout

```
notebooks/<escopo>/
  README.md              # índice: bloco gerado + notas humanas fora do bloco
  00_exploracao.py       # 00–09 explorar
  10_preparo.py          # 10–19 preparar
  20_modelo_baseline.py  # 20–29 ajustar
  30_figuras.py          # 30–39 figuras e tabelas
src/<pkg>/<escopo>/      # o que o notebook promove a código (ADR-0027)
src/<pkg>/runs.py        # helper de rodada (módulo ml)
experiments/<run_id>/    # README.md, run.json, metrics.csv, figs/ (bundle fora do git)
```

`<escopo>` em `notebooks/` e em `src/<pkg>/` é o slug de `docs/studies/<slug>/` sem o prefixo
numérico (`^\d+_`). Uma função única em `core/pj_layout.py` faz a conversão; toda a base usa ela.

### 2. `prumo add notebook <nome>`

```
prumo add notebook <nome> [--kind eda|prep|model|figures] [--scope <slug>] [--ipynb]
```

- Segue a forma de `prumo add study <slug>`. `--kind` default `eda`. `--scope` resolvido como nos
  módulos por-escopo (obrigatório só com mais de um escopo).
- `<nome>` é `snake_case` ASCII; nome inválido falha com o exemplo corrigido na mensagem.
- O número é o primeiro livre da faixa do tipo. Faixa cheia falha e sugere consolidar notebooks
  ou promover código para `src/<pkg>/<escopo>/`.
- Nunca sobrescreve: arquivo existente com o mesmo nome falha.
- Copia o modelo do tipo, preenche o cabeçalho e regenera o índice do escopo.
- `--ipynb` cria o notebook Jupyter equivalente (só `eda`; os outros tipos são marimo).
- `prumo add notebooks` (o módulo) passa a instalar só a rule e a chamar este mesmo caminho para
  criar `00_exploracao.py`. O payload `notebooks/__scope__/` sai do módulo, e com ele a
  divergência do prefixo numérico. O `anchor` do módulo vira `.claude/rules/notebooks.md`.

Lógica em `core/notebooks.py`; `cli.py` só faz parsing, chamada e saída.

### 3. Cabeçalho do notebook

Docstring de módulo no topo do `.py` (primeira célula markdown no `.ipynb`):

```python
"""
Pergunta: <o que este notebook responde>
Entrada: <arquivo ou função que carrega o dado>
Saída: <o que ele grava, ou "nenhuma">
"""
```

O índice lê o cabeçalho com `ast.get_docstring` (o notebook não é executado) e, no `.ipynb`, do
JSON da primeira célula. Campo ausente aparece como `—` no índice e gera aviso no `doctor`.

Risco a fechar na primeira tarefa do plano: confirmar, na versão mínima de marimo do
`pyproject.toml` do módulo `code`, que o editor preserva a docstring de módulo ao salvar. Se não
preservar, o cabeçalho passa para um bloco de comentários `#` no topo, com o mesmo parser.

### 4. Índice do escopo

`notebooks/<escopo>/README.md` com o bloco `<!-- prumo:notebooks:begin -->` /
`<!-- prumo:notebooks:end -->` (ADR-0009):

| Nº | Notebook | Pergunta | Entrada | Saída |
|---|---|---|---|---|

Uma linha por `NN_*.py` e `NN_*.ipynb`, em ordem. Texto fora do bloco é da pesquisadora e é
preservado. Regeneram o bloco: `prumo add notebook` e `prumo update`.

### 5. Modelos por tipo

Ficam em `templates/notebook_kinds/<kind>.py`, fora do payload dos módulos (o overlay não os
copia). `core/paths.py` ganha o resolvedor; `templates/` já é force-included no wheel.

| Tipo | Conteúdo |
|---|---|
| `eda` | O `00_exploracao.py` atual, com cabeçalho. |
| `prep` | Lê de `content/01_raw/`, valida schema, grava Parquet em `content/02_processed/`. |
| `model` | `Pipeline` + `ColumnTransformer`, split por paciente, CV aninhada para tuning, discriminação e calibração com IC por bootstrap, e a célula final que grava a rodada via `start_run`. |
| `figures` | Lê `metrics.csv` de uma rodada e gera as figuras do manuscrito. |

Os modelos são sintéticos: nenhum nome de variável, desfecho ou dataset de estudo real.

### 6. Helper de rodada

`templates/modules/ml/src/__pkg__/runs.py`, copiado para o projeto. É código do projeto: o
projeto não passa a depender do `prumo` em tempo de execução, e a pesquisadora pode editar.

```python
run = start_run("baseline", seed=42, scope="estudo")
run.log_params({...})
run.log_metrics(rows)        # acrescenta em metrics.csv
run.save_fig(fig, "calibracao")
run.finish("O que mudou e o que a rodada mostrou.")
```

- `run_id = <AAAA-MM-DD>_<nome>`; colisão recebe sufixo `_2`, `_3`.
- `run.json`: parâmetros, semente, escopo, commit do git e se a árvore estava suja, versões de
  Python e das bibliotecas de ajuste.
- `finish` escreve o `README.md` da rodada a partir do resumo e do `run.json`.
- Só biblioteca padrão; sem dependência nova.
- O helper grava métrica agregada, nunca linha por paciente. A regra de célula mínima do projeto
  (ADR-0046) continua valendo para o que vai em `metrics.csv`.

`experiments/` continua plano (`experiments/<run_id>/`): o escopo vai no `run.json` e no README.
Projetos existentes não migram nada.

### 7. Módulo `ml`

- Sai `eda.ipynb`. Projeto que já o tem fica com ele.
- Entra `.claude/rules/ml_modeling.md` (paths `notebooks/**` e `src/**`), o checklist de ajuste:
  1. A análise segue o plano de análise do módulo `protocol`; desvio é registrado na rodada.
  2. Modelo de referência simples primeiro (regressão logística ou linear).
  3. Split por paciente antes de qualquer transformação; pré-processamento dentro do `Pipeline`.
  4. Tuning por CV aninhada ou conjunto de validação próprio; o teste é usado uma vez.
  5. Relatar discriminação, calibração (intercepto, inclinação, curva) e utilidade clínica.
  6. Incerteza por bootstrap; só validação interna pede correção de otimismo.
  7. Semente fixa e registrada.
  8. Todo ajuste que informa uma decisão é uma rodada em `experiments/`.
  9. Relato pelo TRIPOD+AI.
- `_module.toml` ganha `requires = ["code"]`. `prumo add ml` aplica antes o que falta e diz que
  aplicou. `ModuleInfo` ganha o campo `requires` (default vazio).
- `ml_stack.md` deixa de citar o `eda.ipynb`.

### 8. `prumo doctor`

| Issue | Quando | Correção na mensagem |
|---|---|---|
| `[notebook_fora_do_lugar]` | `.ipynb` ou `.py` marimo fora de `notebooks/<escopo>/` | `git mv <arquivo> notebooks/<escopo>/` |
| `[notebook_escopo_prefixado]` | `notebooks/01_estudo/` com prefixo numérico | `git mv notebooks/01_estudo notebooks/estudo` |
| `[notebook_sem_numero]` | arquivo sem `NN_` no nome | `git mv` com o número sugerido |
| `[notebook_sem_cabecalho]` | cabeçalho ausente ou incompleto (aviso) | o bloco a colar |
| `[notebook_indice_desatualizado]` | bloco do README difere do disco | `prumo update` |

Detecção de marimo por texto (`marimo.App(`), sem importar o arquivo. `.venv/`, `build/` e
`experiments/` ficam fora da varredura. O `doctor` nunca move arquivo.

## Alternativas rejeitadas

- **Helper de rodada dentro do `prumo`**: o código de análise passaria a importar a ferramenta de
  scaffolding, e a versão do plugin entraria na reprodutibilidade do estudo.
- **MLflow ou similar**: servidor e banco para um projeto de uma pesquisadora; o README da rodada
  versionado já é o registro que o `experiments/README.md` do módulo pede.
- **Índice escrito à mão**: envelhece no segundo notebook.
- **`experiments/<escopo>/<run_id>/`**: mais simétrico, mas quebra o layout dos projetos que já
  têm rodadas, por um ganho que o `run.json` entrega.
- **Segundo marcador de overlay (`__scope_pkg__`)** para corrigir o prefixo: mantém dois caminhos
  de criação de notebook; um só é mais simples.

## Fora deste corte

- Rodar notebook em lote (`marimo export`) e anexar o HTML à rodada.
- Tipo `model` para deep learning (Lightning).
- Índice de `experiments/` gerado a partir dos `run.json`.
- Converter `.ipynb` herdado automaticamente.

## Versão

PATCH (ADR-0015): invocável novo, sem quebra. `uv.lock` e `shims/prumo` não mudam, então ninguém
baixa o ambiente de novo.

## Testes

- `tests/unit/core/test_notebooks.py`: número por faixa, faixa cheia, nome inválido, não
  sobrescreve, cabeçalho lido de `.py` e `.ipynb`, bloco regenerado preservando texto humano,
  escopo com prefixo numérico vira pasta sem prefixo.
- `tests/unit/core/test_scaffold.py`: `requires` aplicado em ordem, `anchor` novo do módulo
  `notebooks`, modelos de tipo fora do payload.
- `tests/unit/core/test_doctor_notebooks.py` (ou o módulo do `doctor` que já existir): as cinco
  issues, com a correção na mensagem.
- `tests/unit/templates/test_runs_template.py`: o `runs.py` do template importado de um `tmp_path`
  grava `run.json`, `metrics.csv` e `README.md`; colisão de `run_id`; `git` mockado no seam.
- Teste de CLI: `prumo add notebook` e `prumo add ml` em projeto sintético (`pj_exemplo`).

## Emenda (2026-11-19): spike do cabeçalho

Notebook com docstring de módulo antes do `import marimo`, aberto em `marimo edit` 0.24.0 (a
versão mínima do grupo `dev`), célula editada e salva pelo editor com Cmd+S. A docstring ficou
intacta; o editor só acrescentou `__generated_with` e regravou a célula editada. O cabeçalho fica
em docstring de módulo, como na seção 3; a alternativa por comentário `#` não é necessária.

## Emenda (2026-11-19): o que a implementação acertou

- **Nome de código do escopo** (`core/pj_layout.py::code_scope_name`): além de tirar o prefixo
  numérico, `-` vira `_` e o resultado precisa ser identificador Python, porque é o mesmo nome do
  subpacote em `src/<pkg>/` (`mortalidade-uti` → `mortalidade_uti`).
- **`--question`** no `prumo add notebook` preenche a Pergunta do cabeçalho. Campo com `<...>`
  conta como não preenchido: é o exemplo do modelo.
- **Os modelos trocam `__scope__` e `__pkg__`** pelo nome de código do escopo e pelo pacote do
  projeto, como o overlay faz nos módulos.
- **O tipo `model` grava a rodada no clique de um botão** (`mo.ui.run_button`) ou sempre que o
  notebook roda como script. O E2E achou um import repetido entre células, que o marimo recusa;
  um teste agora impede nome global definido em duas células de um modelo.
- **Cópia de módulo virou `scaffold.apply_module`**, usada por `init --with` e `add`; o `init`
  também respeita `requires`. A semente do primeiro notebook é `notebooks.seed_scope`.
- **`templates/notebook_kinds/*.py` libera o B018 do ruff**: expressão solta no fim da célula é
  como o marimo exibe um valor.
- **Fora do escopo, achado no E2E:** o grupo `viz` do módulo `code` traz `ydata-profiling`, que
  puxa `numba`, sem suporte a Python 3.14. Com `requires-python >= 3.13`, o uv pode escolher 3.14
  e o `uv sync --group viz` falha. O E2E rodou com `--python 3.13`.
