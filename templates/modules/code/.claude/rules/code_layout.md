# Regras de código do projeto

## O projeto é um pacote instalável

`uv sync` instala este projeto em editable no `.venv`. Código próprio se importa
pelo nome, de qualquer lugar:

```python
from __pkg__.cohort import load_raw
from __pkg__.estudo.prep import build_cohort
```

**Nunca** `sys.path.insert`, nunca `PROJECT_ROOT`, nunca `# noqa: E402` para
liberar import depois de código. Se um import não resolve, o conserto é
`uv sync` — não é mexer no `sys.path`.

## Onde o código mora

| O que | Onde |
|---|---|
| Usado por mais de um estudo ou notebook | `src/__pkg__/<modulo>.py` |
| Usado por um estudo só | `src/__pkg__/<estudo>/<modulo>.py` |
| Teste | `tests/` espelhando `src/__pkg__/` |
| Notebook | `notebooks/<estudo>/` (marimo `.py` ou Jupyter `.ipynb`) |
| Prosa, draft, ADR | `docs/studies/<slug>/` |

A raiz do pacote é o compartilhado, de propósito: o caminho curto pertence ao
código reutilizável. O nome do subpacote vem do slug de `docs/studies/` sem o
prefixo numérico (`01_estudo` → `estudo`).

Não crie um diretório `scripts/` nem um segundo tree `studies/` na raiz — código
auxiliar de um estudo é `src/__pkg__/<estudo>/`.

## Bundle serializado não guarda objeto

`pickle` e `joblib` gravam o `__module__` do objeto. Um bundle que serializa uma
classe sua quebra em silêncio no dia em que o módulo mudar de lugar — e o
`ModuleNotFoundError` aparece meses depois, apontando para o lugar errado.

Bundle guarda **dado** e **versão de schema**, nunca objeto cujo caminho de
import importe:

```python
joblib.dump({"schema": 1, "X": X, "y": y, "feature_names": cols}, path)
```

Quando promover um módulo de `<estudo>/` para a raiz do pacote (o único
movimento que ainda quebra desserialização), regenere os bundles.

## Ambiente e IDE

Rode `uv sync` e aponte o interpretador do editor para o `.venv` do projeto.

- **PyCharm** — detecta o `.venv` sozinho. Não configure source root, não
  versione `.idea/`.
- **VS Code** — `python.defaultInterpreterPath` no `.venv`. **Não** use
  `python.analysis.extraPaths`.

Precisar de configuração de IDE para o import resolver é sinal de que o
`uv sync` não rodou, não de que falta configuração.
