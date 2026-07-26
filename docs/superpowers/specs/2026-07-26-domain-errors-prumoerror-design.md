---
title: Erros de domínio sob PrumoError — tuplas de catch viram builtins
date: 2026-07-26
status: draft
tags: [errors, cli_op, write, paper, refactor, simplify-follow-up]
---

# Erros de domínio sob `PrumoError`

## Resumo executivo

As 19 classes de erro de domínio que hoje herdam de `RuntimeError` cru passam a
herdar de uma base por domínio — `WriteError(PrumoError)` e
`PaperError(PrumoError)` — que `core/cli_op.cli_run` já auto-captura. As tuplas
enumeradas das fachadas (`_EXPORT_CATCHES` com 10 entradas, `_REVIEW_CATCHES`
com 7, `_CONNECT_CATCHES` com 4, `_VERIFY_CATCHES` com 2) encolhem para os
builtins que restam (`FileNotFoundError`, `ValueError`) e são inlinadas.
Adicionar um erro de domínio novo deixa de exigir lembrar de estender a tupla
certa: herdar da base do domínio basta.

O caso especial `ZoteroOfflineError → exit 2` (try/except interno em
`connect_command`) vira mecanismo declarativo: `cli_run` ganha o parâmetro
`exit_codes: Mapping[type[Exception], int]` que mapeia classe → exit code.

Origem: follow-up #9 do agente de altitude do passe `/simplify` (2026-07-25),
grande demais para aquele passe.

## Contexto e problema

- `cli_run` (`core/cli_op.py`) captura sempre `PrumoError` + o que vier em
  `catches`; converte em mensagem limpa + `typer.Exit(exit_code)`. Exceções
  fora disso vazam de propósito (são bugs, queremos traceback).
- Os erros de domínio de `write` e `paper` nasceram como `RuntimeError` cru,
  então cada fachada mantém uma tupla enumerada que precisa listar TODOS —
  10 entradas em `_EXPORT_CATCHES`, 7 em `_REVIEW_CATCHES` etc. Esquecer de
  listar = traceback cru pro usuário em erro de negócio legítimo.
- `connect_command` (`domains/paper/cli.py`) precisa de exit 2 só para
  `ZoteroOfflineError` e resolve isso com try/except interno — o mecanismo de
  tupla não expressa exit code por exceção.
- A docstring de `PrumoError` já antecipava: "Subclasses específicas por
  domínio facilitam handlers mais granulares. Quando um domínio crescer pra ≥3
  exceções próprias, extrai [...] (ainda não justifica)". Write tem 13 próprias
  e paper 6: agora justifica.

## Fatos verificados (2026-07-26, neste worktree)

- **Nenhum** `except RuntimeError` ou `except Exception` em `src/` ou `tests/`
  captura essas classes — a mudança de MRO não altera nenhum handler existente
  (pré-verificado pelo agente do /simplify e re-verificado por grep).
- Testes referenciam sempre as classes-folha específicas (nenhum
  `pytest.raises(RuntimeError)`).
- O contrato de exit code do connect está travado por teste parametrizado
  (`test_paper_connect_error_contract` em `tests/unit/paper/test_cli.py`):
  4 erros → exit 1, `ZoteroOfflineError` → exit 2, sem traceback. Esse teste é
  o lock de regressão da mudança e NÃO muda.
- Únicos handlers internos de erros de domínio em `src/`: o try/except de
  `connect_command` (substituído pelo mecanismo novo) e
  `sync_all.py` capturando `(ConnectionError, FileNotFoundError)` (builtins —
  intocado).

## Abordagens consideradas

1. **Base por domínio + `exit_codes` em `cli_run` (escolhida).** Novo módulo
   `domains/<X>/errors.py` com a base; folhas re-baseadas onde estão; parâmetro
   novo aditivo em `cli_run`. Diff mínimo nos testes (zero), imports dos
   consumidores preservados, mecanismo declarativo pro exit 2.
2. **Rebase direto em `PrumoError`, sem base intermediária.** Menor diff, mas
   perde o agrupamento semântico ("qualquer falha do write") que a própria
   docstring de `PrumoError` promete, e espalha a decisão "é capturável" por
   19 declarações sem um ponto único por domínio.
3. **`catches` vira `dict[type[Exception], int]` (união com tupla).** Expressa
   tudo num parâmetro só, mas complica a assinatura (union type, mypy --strict)
   e força mudança em todos os call sites que hoje passam tupla. O parâmetro
   separado `exit_codes` é aditivo e ortogonal.

## Decisões

1. **Bases por domínio, domain-local:** `domains/write/errors.py` define
   `WriteError(PrumoError)`; `domains/paper/errors.py` define
   `PaperError(PrumoError)`. NÃO vão para `core/` (core não conhece domínios —
   regra de layering) nem para o `__init__.py` raiz (que fica com as
   cross-cutting: `ConfigError`, `ManifestError`, `IntegrationError`). A
   docstring de `PrumoError` é atualizada para apontar o padrão novo.
2. **Folhas ficam onde estão** (imports de testes e consumidores intactos);
   só a base muda:
   - `domains/write/export.py` (8): `ZoteroNotRunningError`,
     `PandocFailedError`, `ZoteroCitekeyNotFoundError`,
     `MissingBibliographyPlaceholderError`, `MissingZoteroPrefsError`,
     `MissingFieldLockError`, `CiteMapMismatchError`, `CorruptDocxError`
     → `WriteError`.
   - `domains/write/review.py` (5): `SourceChangedError`,
     `StructuralChangeError`, `MarkLostError`, `CitationConservationError`,
     `AdeuUnavailableError` → `WriteError`.
   - `domains/paper/connect.py` (5): `ZoteroOfflineError`,
     `CollectionNotFoundError`, `AmbiguousCollectionError`,
     `AlreadyConnectedError`, `UnsupportedCollectionNameError` → `PaperError`.
   - `domains/paper/verify.py` (1): `RefcheckerUnavailableError` → `PaperError`.
3. **Intocados de propósito:** `ToolNotFoundError(FileNotFoundError)` e
   `QmdNotFoundError(FileNotFoundError)` — herdam de builtin deliberadamente
   (são capturados pelos `catches=(FileNotFoundError,)` das fachadas e
   carregam a semântica "arquivo/binário ausente");
   `CslNotFoundError(ConfigError)` — já é `PrumoError`.
4. **`cli_run` ganha `exit_codes: Mapping[type[Exception], int] | None`.**
   Classes do mapa são adicionadas ao conjunto capturado; no except, o
   primeiro match por `isinstance` na ordem de inserção define o código;
   sem match, vale `exit_code` (default 1). `catches` e `exit_code` continuam
   exatamente como são.
5. **Fachadas encolhem para builtins inlinados** (padrão que `draft_command`
   já usa): `_EXPORT_CATCHES` e `_REVIEW_CATCHES` → `catches=(FileNotFoundError,
   ValueError)` inline nos 6 call sites (incluindo `zettlr_export_entry`);
   `_CONNECT_CATCHES` some (as 4 classes agora são `PrumoError`) e
   `connect_command` troca o try/except interno por
   `exit_codes={connect.ZoteroOfflineError: 2}`; `_VERIFY_CATCHES` →
   `catches=(FileNotFoundError,)` inline. As 4 constantes de módulo somem.
6. **API pública:** `domains/write/api.py` re-exporta `WriteError`;
   `domains/paper/api.py` re-exporta `PaperError` (re-export puro, padrão da
   casa). Folhas continuam importáveis dos módulos de domínio, como hoje.
7. **Sem bump de versão** (release é ciclo separado, ADR-0015). CHANGELOG
   ganha entrada em "Não publicado / Alterado" documentando o rebase (nota
   para consumidores da API Python que porventura capturassem `RuntimeError`).

## Efeito colateral deliberado

Hoje um erro de domínio "fora do lugar" (ex.: `SourceChangedError` vazando num
comando de export, que só enumera os erros de export) escaparia como traceback.
Com o rebase, qualquer erro de domínio vira mensagem limpa + exit 1 em qualquer
comando. É um afrouxamento intencional: erro de domínio é, por definição,
user-facing; traceback fica reservado a bugs reais (TypeError, KeyError, ...).

## Testes

- **Novos** (espelham o layout, regra da casa):
  - `tests/unit/core/test_cli_op.py` — comportamento de `exit_codes`: classe
    mapeada sai com o código dela; `PrumoError` não mapeado sai com
    `exit_code` default; classe no mapa é capturada mesmo fora de `catches`;
    primeiro match por ordem de inserção; `exit_code` por comando continua
    valendo (caso sync-annotations).
  - `tests/unit/write/test_errors.py` — parametrizado: as 13 folhas de write
    são `WriteError` e `PrumoError`; `ToolNotFoundError` continua
    `FileNotFoundError` e NÃO `PrumoError`.
  - `tests/unit/paper/test_errors.py` — parametrizado: as 6 folhas de paper
    são `PaperError` e `PrumoError`.
- **Locks existentes (não mudam):** `test_paper_connect_error_contract`
  (exit 1/2 + mensagem + sem traceback), toda a suíte de CLI de write/paper
  (mensagens e exit codes idênticos antes/depois).

## Riscos e mitigação

- **MRO:** nenhum handler em src/tests depende de `RuntimeError` (verificado).
  Consumidor externo pré-1.0 que capture `RuntimeError` quebra silenciosamente
  → nota no CHANGELOG.
- **Toca todas as fachadas:** a bateria completa roda antes de cada commit
  (`uv run pytest` && `uv run ruff check .` && `uv run ruff format --check .`
  && `uv run mypy` && `uv run python .github/scripts/gen_indexes.py --check`).
- **Import circular:** `domains/<X>/errors.py` importa só de `prumo_assist`
  (raiz), que não importa domínios — sem ciclo (mesmo padrão do
  `from prumo_assist import PrumoError` já usado nas fachadas).

## Fora de escopo

- Auditar quais builtins (`ValueError`, `FileNotFoundError`) ainda são de fato
  levantados por cada operação — as tuplas encolhidas preservam o
  comportamento atual.
- Re-exportar as classes-folha em `api.py`.
- Mover `CorruptDocxError` (definida no meio de `export.py`) para junto das
  irmãs — churn sem ganho funcional.
- `raise typer.Exit(code=2)` do doctor (`cli.py` raiz) — outro mecanismo,
  outro contexto.
