---
title: O pj_* é um pacote instalável — código compartilhado com nome, sem sys.path
date: 2026-08-24
status: approved
tags: [layout, modules, code, notebooks, doctor, packaging, uv, breaking, adr]
---

# O pj_* é um pacote instalável — código compartilhado com nome, sem sys.path

## Resumo executivo

Três mudanças, nesta ordem de importância:

1. **O `pj_*` vira pacote instalável.** O `pyproject.toml` do módulo `code` ganha `[build-system]` com hatchling, e `uv sync` passa a instalar o projeto em editable no `.venv`. O import de código próprio deixa de depender do `cwd` e da ordem do `sys.path` e passa a resolver por instalação — igual em notebook, pytest, papermill, CI e IDE.
2. **O código compartilhado ganha nome e lugar.** `src/<pkg>/` é o pacote do projeto; a **raiz do pacote é o compartilhado** e um **subpacote por estudo** guarda o que serve a um estudo só. O caminho mais curto é o do código reutilizável, porque reuso é o caso que queremos barato.
3. **O módulo `notebooks` passa a ser por escopo.** `notebooks/<estudo>/` em vez de `notebooks/` plano, espelhando os slugs de `docs/studies/`. Com isso some o tree paralelo `studies/<slug>/{notebooks,scripts}/` que projetos reais inventaram para preencher o vazio.

Tudo entra numa fase só — **`⚠ Breaking`**, MINOR por [ADR-0015](../../adr/adr-0015-pre-1-0-patch-para-releasavel.md).

## Contexto

### O vazio que projetos reais preencheram sozinhos

O módulo `code` entrega hoje exatamente quatro arquivos:

```
templates/modules/code/
├── _module.toml
├── pyproject.toml     ← [project] name = "pj-NOME", sem [build-system]
├── src/.gitkeep       ← vazio
└── tests/.gitkeep     ← vazio
```

O plugin entrega o diretório `src/` e **cala sobre o que vai dentro dele**. Não há convenção documentada, não há placeholder de nome de pacote, e o `pyproject.toml` sem `[build-system]` faz do `pj_*` um *virtual project* do uv — o projeto nunca é instalado no próprio `.venv`.

A consequência é observável em projeto real. Quando dois notebooks do mesmo estudo precisam compartilhar código — o caso canônico é o pré-processamento determinístico de uma coorte, que precisa ser idêntico entre o notebook de descritivas e o de modelagem — o pesquisador escreve isto:

```python
PROJECT_ROOT = str(next(p for p in [Path.cwd(), *Path.cwd().parents]
                        if (p / "pyproject.toml").exists()))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "studies", "01_estudo", "scripts"))
from prep_estudo import ...   # noqa: E402
```

Roda, e cobra quatro pedágios:

- **O IDE não segue.** PyCharm e VS Code fazem análise estática; `sys.path` é runtime. O import fica marcado como unresolved para sempre, e junto com ele morrem o *go to definition*, o rename refactoring e o autocomplete no único código que é do pesquisador.
- **O `# noqa: E402` vira ruído permanente.** Todo import útil fica depois de código, então a regra dispara em toda célula, e o `noqa` treina o olho a ignorar lint naquele arquivo.
- **`papermill` e CI dependem do `cwd`.** A busca por `pyproject.toml` sobe a partir de `Path.cwd()`, que num runner não é a pasta do notebook.
- **O pickle grava o caminho do módulo.** Um bundle `joblib` serializa `prep_estudo` como `__module__`; mover o arquivo quebra a desserialização **em silêncio**, meses depois, com um `ModuleNotFoundError` que aponta para o lugar errado.

### O que o repo já decidiu, e o que ele nunca decidiu

Decidido: [ADR-0022](../../adr/adr-0022-layout-por-escopo.md) fez de `docs/` a raiz única de leitura e modelou `docs/studies/<slug>/` como unidade de **escrita** (`notes/`, `writing/`, `decisions/`). `tests/unit/test_pj_base_integration.py` trava `src`, `tests`, `notebooks`, `content` e `pyproject.toml` fora do núcleo — eles só chegam por módulo.

Nunca decidido: o que vai **dentro** de `src/`, se o projeto é instalável, e onde o notebook mora em relação ao estudo. O `pyproject.toml` sem `[build-system]` nunca foi escolha registrada; é o default de quem escreveu um `[project]` para declarar dependências e não pensou em packaging.

### O que já existe e pode ser reaproveitado

- `core/scaffold.py` tem `SCOPE_MARKER = "__scope__"` e `_substitute_scope`, que troca o segmento por um slug real em **qualquer** posição do caminho. Hoje só o módulo `clinical` usa. Serve para `notebooks/__scope__/` sem alteração.
- `apply_project_name` substitui `pj-NOME` / `pj_<NOME>` no **conteúdo** de arquivos recém-copiados. Não substitui em **caminho** — daí a peça que falta.
- `prumo doctor` é uma lista `issues: list[str]` montada em `cli.py`, alimentada por funções de `core/` e dos domínios. O check `legacy_layout` é precedente exato de "detecta e convida à adequação agêntica".

## Decisão

### D1 — Layout canônico

```
pj_piloto_genetica/
├── pyproject.toml
├── src/
│   └── piloto_genetica/          ← pacote de import
│       ├── __init__.py
│       ├── cohort.py                   ← COMPARTILHADO entre estudos e notebooks
│       └── estudo/               ← só deste estudo
│           ├── __init__.py
│           └── prep.py
├── tests/                              ← espelha src/
├── notebooks/
│   └── estudo/{03_*.ipynb, 04_*.ipynb}
└── docs/
    └── studies/01_estudo/{notes,writing,decisions}/
```

Import no notebook, sem preâmbulo nenhum:

```python
from piloto_genetica.cohort import load_raw
from piloto_genetica.estudo.prep import build_cohort
```

**A raiz do pacote é o compartilhado.** Um módulo só ganha subpacote de estudo quando é comprovadamente específico daquele estudo. A assimetria é deliberada: o caminho curto pertence ao caso que queremos incentivar, e a pergunta "isso é comum?" não precisa ser respondida na criação de cada arquivo — só na promoção.

### D2 — Nome do pacote

O `[project] name` continua sendo o nome do projeto (`pj_piloto_genetica`), já substituído pelo scaffold. O **pacote de import perde o prefixo**: `piloto_genetica`.

O `pj_` marca diretório de projeto para o humano e para o agente; em `import` ele é ruído repetido em toda célula. Distribution name diferente de import name é comum e explícito no `[tool.hatch.build.targets.wheel] packages`.

Regra: `pkg_name("pj_piloto_genetica") == "piloto_genetica"`. Se o resultado não for identificador Python válido, o scaffold recusa com a mensagem do renomeio.

### D3 — Slug de estudo → nome de subpacote

`docs/studies/01_estudo/` é bom slug de escrita e não é identificador Python. A normalização remove prefixo numérico e troca hífen por underscore:

| slug | subpacote |
|---|---|
| `01_estudo` | `estudo` |
| `mortalidade-uti` | `mortalidade_uti` |
| `principal` | `principal` |
| `2024` | **recusa** |

O slug da escrita **não muda**. A numeração ordena a leitura e é ruído no import.

### D4 — O projeto é instalável

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/piloto_genetica"]
```

`uv sync` passa a instalar o projeto em editable. Isso mata o `sys.path.insert`, o `# noqa: E402` e o unresolved import de uma vez, e é o que dissolve a questão de IDE: com o pacote instalado no `.venv`, PyCharm e VS Code resolvem por interpretador, sem source root, sem `python.analysis.extraPaths`, sem `.iml` versionado. O `.gitignore` do `pj_base` continua ignorando `.idea/` e `.vscode/`.

**O que isto não conserta:** o pickle. O `joblib` continua gravando `piloto_genetica.estudo.prep` no bundle, e mover o módulo continua quebrando a desserialização. O que muda é que o caminho passa a ser estável — não depende mais de `cwd` nem da ordem do `sys.path` — e que sobra **um** movimento perigoso (promover de subpacote de estudo para raiz) em vez de vários. A mitigação é orientação na rule do módulo, não código: bundle guarda dado e versão de schema, nunca objeto cujo `__module__` importa.

### D5 — `notebooks` vira módulo por escopo

`notebooks/__scope__/.gitkeep` no template, `anchor` idem. `is_applied` já substitui o escopo antes de checar o anchor.

### D6 — Quatro checks no `doctor`

| Check | Dispara quando |
|---|---|
| `projeto_nao_instalavel` | há `pyproject.toml` **e** `.py` sob `src/`, mas falta `[build-system]` |
| `pacote_sem_nome` | `src/` tem `.py` solto na raiz, ou existe `src/src/` |
| `sys_path_hack` | `sys.path.insert`/`append` em `notebooks/**/*.ipynb` ou `src/**/*.py` |
| `projeto_nao_sincronizado` | há `[build-system]` mas o pacote não está no `.venv` |

Todos determinísticos, sem LLM ([Princípio II](../../constitution.md)), todos como `issues` (exit 1), todos com o comando de correção embutido na mensagem.

**Corte deliberado:** o check "import top-level de módulo que não é dependência declarada nem pacote do projeto" **não entra**. Exigiria resolver o grafo de imports contra os `[dependency-groups]`, que são opt-in por design (`uv sync --group tabular`); num projeto que ativou só `viz`, `pandas` apareceria como não-declarado. Falso-positivo seria o caso comum. Isso é trabalho de `deptry` ou de regra do `ruff`, não do `doctor`.

### D7 — Migração dos pj_* existentes

Detecção determinística pelo `doctor`, adequação pelo agente — o molde exato do check `legacy_layout` da ADR-0022. Não há comando de migração: o estado de partida de cada projeto é arbitrário (nome de pacote inventado, `src` como namespace, scripts espalhados), e um migrador determinístico erraria onde o agente acerta lendo o projeto.

## Não-objetivos

- **Migrador automático.** Ver D7.
- **Config de IDE versionada.** Se a convenção precisasse dela, a convenção estaria errada.
- **`src/` no núcleo.** Continua exclusivo do módulo `code`; `test_pj_base_integration.py` segue verde.
- **Tornar o `pj_*` publicável em índice.** Instalável em editable no próprio `.venv` é o alvo; wheel para PyPI não é caso de uso de projeto de pesquisa.
- **Mexer no layout de escrita.** `docs/studies/<slug>/` é intocado.

## Consequências

Notebooks do mesmo estudo passam a compartilhar código por import de verdade, com navegação de IDE e sem `noqa`. `papermill` e CI param de depender do `cwd`.

**Dois breaks concretos:**

1. `prumo add code` muda de forma — passa a criar `src/<pkg>/__init__.py` em vez de `src/` vazio, e o `pyproject.toml` gerado ganha `[build-system]`. Projetos que já rodaram `add code` não são tocados (overlay não sobrescreve), mas passam a acusar `projeto_nao_instalavel` no `doctor`.
2. O `anchor` do módulo `notebooks` muda de `notebooks/.gitkeep` para `notebooks/__scope__/.gitkeep`. Projeto que já rodou `add notebooks` volta a aparecer como **não-aplicado** em `prumo add --list`, e um `prumo add notebooks` novo criaria `notebooks/<escopo>/` ao lado do `notebooks/` plano existente. Isso é ruído, não perda — o `doctor` não reclama e nada é sobrescrito — mas precisa estar dito na mensagem de release.

O `doctor` fica mais barulhento em projetos legados, por desenho: os quatro checks existem para que o pesquisador descubra o problema antes do `ModuleNotFoundError` de daqui a três meses.

`uv sync` passa a ser pré-requisito para importar código próprio. Em projeto que já usa o `.venv` como kernel do notebook isso é invisível; em projeto que importava por `sys.path` sem nunca ter sincronizado, é um passo novo — e o check `projeto_nao_sincronizado` existe exatamente para nomeá-lo.
