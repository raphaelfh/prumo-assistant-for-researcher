---
paths:
  - "notebooks/**"
---

# Notebooks (módulo `notebooks`)

Notebook mora em `notebooks/<escopo>/`, fora de `docs/` — a raiz de leitura do
wiki é prosa, não execução. O escopo é o slug de `docs/studies/<slug>/` sem o
prefixo numérico e com `-` virando `_` (`01_estudo` → `estudo`,
`mortalidade-uti` → `mortalidade_uti`), o mesmo nome do subpacote em `src/<pacote>/`.

## Criar: sempre pelo comando

```bash
prumo add notebook <nome> --kind eda|prep|model|figures [--scope <slug>] [--question "..."]
```

O comando escolhe o número, copia o modelo do tipo e atualiza o índice. Não copie
notebook à mão: o número e o índice saem errados.

| Faixa | Tipo | Para quê |
|---|---|---|
| 00–09 | `eda` | Explorar: esquema, agregados, distribuições |
| 10–19 | `prep` | Preparar: `content/01_raw/` → contrato → `content/02_processed/` |
| 20–29 | `model` | Ajustar modelo e gravar a rodada em `experiments/` (módulo `ml`) |
| 30–39 | `figures` | Figuras e tabelas do manuscrito, a partir de uma rodada |

A ordem dos números é a ordem de execução: quem chega à pasta lê de cima para baixo.

## Cabeçalho: o topo de todo notebook

```python
"""
Pergunta: qual a distribuição da idade por desfecho?
Entrada: content/02_processed/coorte.parquet
Saída: nenhuma
"""
```

No `.ipynb`, as mesmas três linhas na primeira célula markdown. O cabeçalho é o que
aparece no índice; ao mudar o que o notebook faz, mude o cabeçalho junto.

## Índice: `notebooks/<escopo>/README.md`

O bloco entre `<!-- prumo:notebooks:begin -->` e `<!-- prumo:notebooks:end -->` é
gerado a partir dos cabeçalhos por `prumo add notebook` e `prumo update`. Não edite
dentro dele; notas suas ficam fora. `prumo doctor` acusa notebook fora do lugar, sem
número, sem cabeçalho ou com o índice atrasado, sempre com o comando que conserta.

## Dois formatos aceitos

| Formato | Quando |
|---|---|
| **marimo** `.py` (padrão) | Notebook novo |
| Jupyter `.ipynb` | Notebook herdado, ou material que já chegou em `.ipynb` (`--kind eda --ipynb`) |

O padrão é marimo porque o notebook é um `.py` comum: o diff é legível, não
carrega saída embutida no arquivo e o grafo de dependência entre células elimina
o estado oculto — mudou uma célula, o marimo reexecuta as que dependem dela. O
`.ipynb` continua válido e ninguém precisa converter o que já existe.

Converter um notebook herdado quando valer a pena:

```bash
uv run marimo convert notebooks/<escopo>/00_velho.ipynb -o notebooks/<escopo>/01_velho.py
```

## Rodar

```bash
uv run marimo edit --no-token notebooks/<escopo>/00_exploracao.py   # editor interativo
uv run marimo run notebooks/<escopo>/00_exploracao.py               # como app somente-leitura
```

O marimo vem no grupo `dev` do `pyproject.toml` (módulo `code`); num projeto sem esse
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

Usar: deixe o notebook rodando com `uv run marimo edit --no-token <arquivo>` (o
`--no-token` é o que permite a descoberta automática do servidor) e chame

```
/marimo-pair pair with me on notebooks/<escopo>/00_exploracao.py
```

Requisitos: `bash`, `curl` e `jq` no `PATH`. Servidor com autenticação precisa
da variável `MARIMO_TOKEN`. Para não aprovar cada chamada, libere os scripts
`discover-servers.sh` e `execute-code.sh` em `.claude/settings.json`.

O pair é opt-in e não substitui as regras deste projeto: o que virar código de
verdade sai do notebook para `src/<pacote>/`, e dado bruto continua somente-leitura.

[ADR-0027]: https://github.com/raphaelfh/prumo-assistant-for-researcher/blob/main/docs/adr/adr-0027-pj-instalavel.md
