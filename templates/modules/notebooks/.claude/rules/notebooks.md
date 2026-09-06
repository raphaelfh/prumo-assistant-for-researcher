---
paths:
  - "notebooks/**/*.py"
  - "notebooks/**/*.ipynb"
---

# Notebooks (módulo `notebooks`)

Notebook mora em `notebooks/<escopo>/`, fora de `docs/` — a raiz de leitura do
wiki é prosa, não execução. O escopo é o mesmo slug de `docs/studies/<slug>/`,
sem o prefixo numérico quando houver (`01_estudo` → `estudo`).

## Dois formatos aceitos

| Formato | Arquivo | Quando |
|---|---|---|
| **marimo** (padrão) | `notebooks/<escopo>/00_exploracao.py` | Notebook novo |
| Jupyter | `notebooks/<escopo>/00_exploracao.ipynb` | Notebook herdado, ou material que já chegou em `.ipynb` |

O padrão é marimo porque o notebook é um `.py` comum: o diff é legível, não
carrega saída embutida no arquivo e o grafo de dependência entre células elimina
o estado oculto — mudou uma célula, o marimo reexecuta as que dependem dela. O
`.ipynb` continua válido e ninguém precisa converter o que já existe.

Converter um notebook herdado quando valer a pena:

```bash
uv run marimo convert notebooks/<escopo>/velho.ipynb -o notebooks/<escopo>/velho.py
```

## Rodar

```bash
make nb-edit NB=notebooks/<escopo>/00_exploracao.py   # editor interativo
make nb-run  NB=notebooks/<escopo>/00_exploracao.py   # como app somente-leitura
```

Sem `make`: `uv run marimo edit notebooks/<escopo>/00_exploracao.py`. O marimo
vem no grupo `dev` do `pyproject.toml` (módulo `code`); num projeto sem esse
módulo, `uv add --dev marimo` ou `uvx marimo edit <arquivo>`.

## Import de código próprio

O projeto é um pacote instalável ([ADR-0027]): `uv sync` o instala em editable
e o notebook importa pelo nome — `from <pacote>.cohort import load_raw`. Nunca
`sys.path.insert`, nunca `PROJECT_ROOT`. Import que não resolve se conserta com
`uv sync`, não mexendo no `sys.path` (o `prumo doctor` acusa `sys_path_hack`).

Código usado por mais de um notebook ou estudo sobe para `src/<pacote>/`; o
notebook fica com a exploração, não com a biblioteca.

## marimo pair — o agente dentro da sessão do notebook

O [marimo pair](https://marimo.io/blog/marimo-pair) é uma agent skill que
coloca o agente **dentro da sessão em execução**: ele lê os valores das
variáveis em memória, executa código num scratchpad com esse mesmo estado e
edita células — sem que você descreva o schema do `DataFrame` na conversa.

Instalar uma vez (fora do projeto, é global do agente):

```bash
npx skills add marimo-team/marimo-pair
```

No Claude Code também dá como plugin, com auto-update:

```
/plugin marketplace add marimo-team/marimo-pair
/plugin install marimo-pair@marimo-pair
```

Usar: deixe o notebook rodando (`make nb-edit NB=...` já sobe com `--no-token`,
que é o que permite a descoberta automática do servidor) e chame

```
/marimo-pair pair with me on notebooks/<escopo>/00_exploracao.py
```

Requisitos: `bash`, `curl` e `jq` no `PATH`. Servidor com autenticação precisa
da variável `MARIMO_TOKEN`. Para não aprovar cada chamada, libere os scripts
`discover-servers.sh` e `execute-code.sh` em `.claude/settings.json`.

O pair é opt-in e não substitui as regras deste projeto: o que virar código de
verdade sai do notebook para `src/<pacote>/`, e dado bruto continua somente-leitura.

[ADR-0027]: https://github.com/raphaelfh/prumo-assist/blob/main/docs/adr/adr-0027-pj-instalavel.md
