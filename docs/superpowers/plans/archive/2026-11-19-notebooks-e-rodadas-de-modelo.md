---
status: implemented
verified: 2026-11-19
release: "0.72.2"
spec: "[[2026-11-18-notebooks-e-rodadas-de-modelo-design]]"
adr: "[[adr/adr-0047-notebooks-indexados-e-rodadas]]"
---

> **Fechamento (2026-11-19).** Tasks 1–13 implementadas em TDD. Verificação: suíte inteira,
> `ruff`, `mypy` e `gen_indexes --check` limpos; ponta a ponta num `pj_exemplo` sintético com
> Python 3.13 (`init`, `add ml`, `add notebook` dos quatro tipos e `--ipynb`, os quatro notebooks
> rodados como script, rodada gravada em `experiments/`, `doctor` sem issue). O E2E achou um
> import repetido entre células no modelo `model`, corrigido e coberto por teste. Emendas na spec.
> Não verificado: os modelos abertos no editor do marimo no navegador (só a docstring, no spike).

# Notebooks numerados com índice e rodadas de modelo — plano de implementação

**Spec:** [[2026-11-18-notebooks-e-rodadas-de-modelo-design]] · **ADR:** ADR-0047

Cada task é TDD: teste falhando, implementação, `uv run pytest`, `ruff`, `mypy`. Fixtures são
sintéticas (`pj_exemplo`); `git` e binários externos mockados nos seams.

- [x] **Task 1 — Spike do cabeçalho.** Na versão mínima de marimo do `pyproject.toml` do módulo
  `code`, criar um notebook com docstring de módulo, salvar pelo editor e conferir se ela
  sobrevive. Registrar o resultado como emenda na spec. Se não sobreviver, o cabeçalho vira bloco
  de comentários `#` e as tasks 3 e 5 usam esse formato. Nenhum código de produção nesta task.
- [x] **Task 2 — Nome de escopo.** `tests/unit/core/test_pj_layout.py`: `01_estudo` → `estudo`,
  slug sem prefixo fica igual, slug só numérico falha com a correção na mensagem. Implementar a
  função em `core/pj_layout.py` e trocar por ela os usos que hoje fazem a conversão à mão.
- [x] **Task 3 — `core/notebooks.py`.** `tests/unit/core/test_notebooks.py`: faixa por tipo,
  primeiro número livre, faixa cheia, nome inválido, não sobrescreve, leitura do cabeçalho em
  `.py` (sem executar) e `.ipynb`, render do bloco `prumo:notebooks`, sincronização preservando
  texto humano, README ausente é criado, delimitador sem par. Value objects `frozen=True`.
- [x] **Task 4 — Resolução dos modelos.** `tests/unit/core/test_paths.py` e `test_scaffold.py`:
  `templates/notebook_kinds/` resolvido pelo `core/paths.py`, presente no wheel, fora do payload
  de qualquer módulo. Conferir o force-include do `pyproject.toml` junto.
- [x] **Task 5 — Modelos por tipo.** `templates/notebook_kinds/{eda,prep,model,figures}.py` e
  `eda.ipynb`, todos com cabeçalho. Teste: cada modelo compila (`ast.parse`), tem os três campos
  e não contém `sys.path`. `model.py` usa só o que está nos grupos `tabular` e `viz`.
- [x] **Task 6 — `requires` nos módulos.** `tests/unit/core/test_scaffold.py` e
  `test_modules.py`: `ModuleInfo.requires` (default vazio), ordem de aplicação, dependência já
  aplicada é pulada, nome desconhecido falha no teste de contrato dos manifestos.
- [x] **Task 7 — Helper de rodada.** `templates/modules/ml/src/__pkg__/runs.py`, só biblioteca
  padrão. `tests/unit/templates/test_runs_template.py` importa o arquivo de um `tmp_path`:
  `run_id` e colisão, `run.json` (semente, escopo, commit, árvore suja, versões), `metrics.csv`
  acrescentado, `save_fig`, `finish` escreve o README. Sem git instalado o campo fica nulo.
- [x] **Task 8 — Módulo `ml`.** Remover `eda.ipynb`; `requires = ["code"]`; rule
  `ml_modeling.md` com `paths` em `notebooks/**` e `src/**`; `ml_stack.md` e
  `experiments/README.md` atualizados para o helper. `test_rules_scoping.py` cobre a rule nova.
- [x] **Task 9 — Módulo `notebooks`.** Remover `notebooks/__scope__/`; `anchor` vira a rule;
  rule reescrita (comando, faixas, cabeçalho, índice). `test_modules.py`: `is_applied` com o
  anchor novo, inclusive em projeto que aplicou o módulo no formato anterior.
- [x] **Task 10 — CLI `add`.** `tests/unit/test_cli_add.py`: `prumo add notebook <nome>` com
  `--kind`, `--scope`, `--ipynb`, `--json`; `prumo add notebooks` cria `00_exploracao.py` pelo
  mesmo caminho; `prumo add ml` aplica `code` antes e diz que aplicou; erros com a correção na
  mensagem. `cli.py` só faz parsing, chamada e saída, dentro de `cli_run`.
- [x] **Task 11 — `doctor` e `update`.** `test_cli_doctor.py`: as cinco issues da spec, cada uma
  com o comando de correção, e a varredura ignorando `.venv/`, `build/` e `experiments/`.
  `test_cli_update.py`: `update` regenera o bloco do índice, `--dry-run` só relata. Lógica em
  `core/notebooks.py`.
- [x] **Task 12 — Ponta a ponta.** Num `pj_exemplo` em `tmp_path`: `init`, `add ml`,
  `add notebook` dos quatro tipos, `doctor` limpo, mover um notebook para fora e ver a issue.
  Rodar o `model.py` gerado com dado sintético e conferir a rodada em `experiments/`.
- [x] **Task 13 — Docs e fechamento.** `templates/pj_base/README.md` e `CLAUDE.md`, skill `start`
  (fonte, depois `gen_indexes.py`), ARCHITECTURE, ROADMAP, CHANGELOG (ADR-0047, ADR-0009,
  ADR-0027), ADR-0047 para "aceito", emendas na spec. Release PATCH pelos 8 passos do
  `RELEASING.md`. Mover este plano para `archive/` com o frontmatter de fechamento.

## Ordem e dependências

Task 1 decide o formato do cabeçalho e trava 3 e 5. Tasks 2, 4, 6 e 7 são independentes entre
si. Tasks 8 e 9 dependem de 5, 6 e 7; 10 depende de 3, 8 e 9; 11 depende de 3.

## Fora do alcance de teste automático

- O editor do marimo abrindo cada modelo num navegador (só a Task 1 e a Task 12 tocam nisso, à mão).
- O `model.py` com dado real: o teste usa dado sintético pequeno e não diz nada sobre desempenho.
