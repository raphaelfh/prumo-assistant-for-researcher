---
status: draft
spec: "[[2026-07-26-domain-errors-prumoerror-design]]"
---

# Erros de domínio sob PrumoError — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** As 19 exceções de negócio de `write` e `paper` (hoje `RuntimeError` cru) passam a herdar de `WriteError`/`PaperError(PrumoError)`, auto-capturadas por `cli_run`; as tuplas enumeradas das fachadas encolhem para builtins e `cli_run` ganha `exit_codes` declarativo (`ZoteroOfflineError` → exit 2).

**Architecture:** Base por domínio em módulo novo `domains/<X>/errors.py` (importa só a raiz `prumo_assist`, sem ciclo); folhas ficam onde estão e só trocam a base (imports de testes/consumidores intactos); `cli_run` ganha parâmetro aditivo `exit_codes: Mapping[type[Exception], int]` (primeiro match por `isinstance` na ordem de inserção). Comportamento do CLI (mensagens, exit codes) fica idêntico — a suíte existente é o lock de regressão.

**Tech Stack:** Python 3.11, Typer, pytest, mypy --strict, ruff.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-26-domain-errors-prumoerror-design.md`.
- Bateria completa ao fim de CADA task, antes do commit, NENHUM passo pulado:
  `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run python .github/scripts/gen_indexes.py --check`
- NÃO bumpar versão (ADR-0015; release é ciclo separado). NÃO editar manifests.
- Regras da casa: `from __future__ import annotations` em módulo novo; docstrings pt-BR, identificadores em inglês; testes espelham o layout (`tests/unit/<dominio>/test_<modulo>.py`); `api.py` é re-export puro.
- Comportamento do CLI NÃO muda: mensagens e exit codes idênticos. `test_paper_connect_error_contract` (tests/unit/paper/test_cli.py) NÃO é editado — é o lock.
- Intocados: `ToolNotFoundError(FileNotFoundError)` em export.py, `QmdNotFoundError(FileNotFoundError)` em wiki/index.py, `CslNotFoundError(ConfigError)` em core/csl.py, `sync_all.py` (captura builtins), `raise typer.Exit(code=2)` do doctor em `cli.py` raiz.

---

### Task 1: `cli_run` ganha `exit_codes`

**Files:**
- Modify: `src/prumo_assist/core/cli_op.py`
- Test (create): `tests/unit/core/test_cli_op.py`

**Interfaces:**
- Produces: `cli_run(*, json_mode: bool = False, catches: tuple[type[Exception], ...] = (), exit_code: int = 1, exit_codes: Mapping[type[Exception], int] | None = None)` — Tasks 3 e 5 dependem de `exit_codes`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/unit/core/test_cli_op.py`:

```python
"""Contrato de ``cli_run``: captura, exit codes e o mapa ``exit_codes`` (spec 2026-07-26)."""

from __future__ import annotations

import pytest
import typer

from prumo_assist import PrumoError
from prumo_assist.core.cli_op import cli_run


class _DomainError(PrumoError):
    """Erro de domínio fake pro contrato."""


class _ChildError(_DomainError):
    """Subclasse pra provar a semântica de primeiro-match por ordem de inserção."""


def test_exit_codes_maps_class_to_code() -> None:
    with pytest.raises(typer.Exit) as excinfo:
        with cli_run(exit_codes={_DomainError: 2}):
            raise _DomainError("zotero fechado")
    assert excinfo.value.exit_code == 2


def test_unmapped_prumo_error_uses_default_exit_code() -> None:
    with pytest.raises(typer.Exit) as excinfo:
        with cli_run(exit_codes={_ChildError: 2}):
            raise _DomainError("erro comum")
    assert excinfo.value.exit_code == 1


def test_mapped_class_is_caught_even_outside_catches() -> None:
    """Classe no mapa entra no conjunto capturado sem precisar repetir em ``catches``."""
    with pytest.raises(typer.Exit) as excinfo:
        with cli_run(exit_codes={ConnectionError: 3}):
            raise ConnectionError("rede caiu")
    assert excinfo.value.exit_code == 3


def test_first_match_wins_by_insertion_order() -> None:
    with pytest.raises(typer.Exit) as excinfo:
        with cli_run(exit_codes={_DomainError: 4, _ChildError: 3}):
            raise _ChildError("filho")
    assert excinfo.value.exit_code == 4


def test_per_command_exit_code_still_applies() -> None:
    """Caso sync-annotations: ``exit_code=2`` pro comando inteiro continua valendo."""
    with pytest.raises(typer.Exit) as excinfo:
        with cli_run(catches=(ConnectionError,), exit_code=2):
            raise ConnectionError("zotero fechado")
    assert excinfo.value.exit_code == 2


def test_unrelated_exception_leaks() -> None:
    """Exceção fora do contrato vaza — é bug, queremos traceback."""
    with pytest.raises(KeyError):
        with cli_run():
            raise KeyError("bug real")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/core/test_cli_op.py -v`
Expected: FAIL — `TypeError: cli_run() got an unexpected keyword argument 'exit_codes'` nos 4 testes que passam `exit_codes`; os 2 restantes PASSAM (contrato atual).

- [ ] **Step 3: Implementar**

Em `src/prumo_assist/core/cli_op.py`, trocar o import de `contextlib` e a função inteira:

```python
from collections.abc import Generator, Mapping
from contextlib import contextmanager

import typer

from prumo_assist import PrumoError
from prumo_assist.core.output import Console


@contextmanager
def cli_run(
    *,
    json_mode: bool = False,
    catches: tuple[type[Exception], ...] = (),
    exit_code: int = 1,
    exit_codes: Mapping[type[Exception], int] | None = None,
) -> Generator[Console, None, None]:
    """Context manager: cria ``Console`` e converte exceções em ``Exit``.

    Captura sempre ``PrumoError`` (base de todo erro de domínio) e,
    adicionalmente, qualquer classe listada em ``catches`` ou em
    ``exit_codes``. Outras exceções vazam (são bugs, queremos traceback).

    ``exit_codes`` mapeia classe → exit code (primeiro match por
    ``isinstance`` na ordem de inserção); sem match, vale ``exit_code``
    (default 1).
    """
    console = Console(json_mode=json_mode)
    handled: tuple[type[Exception], ...] = (PrumoError, *catches, *(exit_codes or ()))
    try:
        yield console
    except handled as e:
        console.error(str(e))
        code = next(
            (mapped for cls, mapped in (exit_codes or {}).items() if isinstance(e, cls)),
            exit_code,
        )
        raise typer.Exit(code=code) from e
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/core/test_cli_op.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Bateria completa**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run python .github/scripts/gen_indexes.py --check`
Expected: tudo verde.

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/core/cli_op.py tests/unit/core/test_cli_op.py
git commit -m "feat(core): cli_run aceita exit_codes por classe de exceção"
```

---

### Task 2: Hierarquia do write — `WriteError`

**Files:**
- Create: `src/prumo_assist/domains/write/errors.py`
- Modify: `src/prumo_assist/domains/write/export.py` (8 classes + import)
- Modify: `src/prumo_assist/domains/write/review.py` (5 classes + import)
- Modify: `src/prumo_assist/domains/write/api.py` (re-export)
- Modify: `src/prumo_assist/__init__.py` (docstring de `PrumoError`)
- Test (create): `tests/unit/write/test_errors.py`

**Interfaces:**
- Produces: `prumo_assist.domains.write.errors.WriteError` (subclasse de `PrumoError`); as 13 folhas de write passam a ser `WriteError`. Task 3 depende disso pra encolher as tuplas.

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/unit/write/test_errors.py`:

```python
"""Contrato da hierarquia de erros do domínio write (spec 2026-07-26)."""

from __future__ import annotations

import pytest

from prumo_assist import PrumoError
from prumo_assist.domains.write import export, review
from prumo_assist.domains.write.errors import WriteError

_WRITE_LEAVES = (
    export.ZoteroNotRunningError,
    export.PandocFailedError,
    export.ZoteroCitekeyNotFoundError,
    export.MissingBibliographyPlaceholderError,
    export.MissingZoteroPrefsError,
    export.MissingFieldLockError,
    export.CiteMapMismatchError,
    export.CorruptDocxError,
    review.SourceChangedError,
    review.StructuralChangeError,
    review.MarkLostError,
    review.CitationConservationError,
    review.AdeuUnavailableError,
)


@pytest.mark.parametrize("leaf", _WRITE_LEAVES)
def test_leaf_is_write_error_and_prumo_error(leaf: type[Exception]) -> None:
    assert issubclass(leaf, WriteError)
    assert issubclass(leaf, PrumoError)


def test_tool_not_found_stays_builtin() -> None:
    """``ToolNotFoundError`` herda de builtin DE PROPÓSITO — capturada via
    ``catches=(FileNotFoundError,)`` nas fachadas."""
    assert issubclass(export.ToolNotFoundError, FileNotFoundError)
    assert not issubclass(export.ToolNotFoundError, PrumoError)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/write/test_errors.py -v`
Expected: FAIL no import — `ModuleNotFoundError: No module named 'prumo_assist.domains.write.errors'`.

- [ ] **Step 3: Criar `errors.py` e re-basear as folhas**

Criar `src/prumo_assist/domains/write/errors.py`:

```python
"""Base das exceções do domínio write.

Toda exceção de negócio do domínio herda de :class:`WriteError` — capturada
automaticamente por ``core/cli_op.cli_run`` nas fachadas (mensagem limpa +
exit code). Erro novo no domínio: herde daqui; nenhuma tupla de catch
precisa ser estendida.
"""

from __future__ import annotations

from prumo_assist import PrumoError


class WriteError(PrumoError):
    """Falha de negócio do domínio write (export, review, compose)."""
```

Em `src/prumo_assist/domains/write/export.py`, adicionar o import (junto dos
imports de `prumo_assist` existentes, ordem alfabética do ruff):

```python
from prumo_assist.domains.write.errors import WriteError
```

e trocar a base das 8 classes — SOMENTE a linha `class` muda, docstrings ficam:

```python
class ZoteroNotRunningError(WriteError):
class PandocFailedError(WriteError):
class ZoteroCitekeyNotFoundError(WriteError):
class MissingBibliographyPlaceholderError(WriteError):
class MissingZoteroPrefsError(WriteError):
class MissingFieldLockError(WriteError):
class CiteMapMismatchError(WriteError):
class CorruptDocxError(WriteError):      # linha ~296, longe das irmãs — fica onde está
```

(`ToolNotFoundError(FileNotFoundError)` NÃO muda.)

Em `src/prumo_assist/domains/write/review.py`, adicionar o mesmo import e trocar as 5:

```python
class SourceChangedError(WriteError):
class StructuralChangeError(WriteError):
class MarkLostError(WriteError):
class CitationConservationError(WriteError):
class AdeuUnavailableError(WriteError):
```

Em `src/prumo_assist/domains/write/api.py`, adicionar o import:

```python
from prumo_assist.domains.write.errors import WriteError
```

e `"WriteError",` no `__all__` (ordem alfabética: entre `"WritePrep"`… não —
ASCII: `"WriteError"` vem ANTES de `"WriteOutput"`).

Em `src/prumo_assist/__init__.py`, atualizar a docstring de `PrumoError`
(a nota "extrai pra core/errors.py (ainda não justifica)" está resolvida
de outro jeito):

```python
class PrumoError(Exception):
    """Raiz da hierarquia de exceções de prumo-assist.

    ``core/cli_op.cli_run`` captura qualquer ``PrumoError`` nas fachadas
    (mensagem limpa + exit code). Aqui na raiz vivem as cross-cutting
    (ConfigError, ManifestError, IntegrationError); domínio com exceções
    próprias define sua base em ``domains/<X>/errors.py`` (WriteError,
    PaperError)."""
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/write/test_errors.py -v`
Expected: 14 PASS (13 parametrizados + builtin).

- [ ] **Step 5: Bateria completa**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run python .github/scripts/gen_indexes.py --check`
Expected: tudo verde (a suíte inteira prova que o rebase não muda comportamento).

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/domains/write/errors.py src/prumo_assist/domains/write/export.py src/prumo_assist/domains/write/review.py src/prumo_assist/domains/write/api.py src/prumo_assist/__init__.py tests/unit/write/test_errors.py
git commit -m "refactor(write): erros de export/review herdam de WriteError(PrumoError)"
```

---

### Task 3: Fachada write dispensa as tuplas

**Files:**
- Modify: `src/prumo_assist/domains/write/cli.py`

**Interfaces:**
- Consumes: as 13 folhas de write já são `PrumoError` (Task 2) — auto-capturadas por `cli_run`.
- Produces: nada novo; `_EXPORT_CATCHES` e `_REVIEW_CATCHES` deixam de existir.

- [ ] **Step 1: Encolher**

Em `src/prumo_assist/domains/write/cli.py`:

1. Deletar os blocos `_EXPORT_CATCHES = (...)` e `_REVIEW_CATCHES = (...)`
   (linhas ~32–53).
2. Nos 6 call sites, inlinar os builtins que restam (padrão que
   `draft_command` já usa):
   - `export_command`: `catches=_EXPORT_CATCHES` → `catches=(FileNotFoundError, ValueError)`
   - `compose_command`: idem
   - `review_ingest_command`: `catches=_REVIEW_CATCHES` → `catches=(FileNotFoundError, ValueError)`
   - `review_events_command`: idem
   - `review_apply_command`: idem
   - `zettlr_export_entry`: `catches=_EXPORT_CATCHES` → `catches=(FileNotFoundError, ValueError)`

- [ ] **Step 2: Rodar os locks de comportamento**

Run: `uv run pytest tests/unit/write/ -v`
Expected: tudo PASS sem editar nenhum teste — mensagens e exit codes idênticos.

- [ ] **Step 3: Bateria completa**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run python .github/scripts/gen_indexes.py --check`
Expected: tudo verde (ruff acusaria import não usado se sobrasse).

- [ ] **Step 4: Commit**

```bash
git add src/prumo_assist/domains/write/cli.py
git commit -m "refactor(write): fachada dispensa tuplas enumeradas de catch"
```

---

### Task 4: Hierarquia do paper — `PaperError`

**Files:**
- Create: `src/prumo_assist/domains/paper/errors.py`
- Modify: `src/prumo_assist/domains/paper/connect.py` (5 classes + import)
- Modify: `src/prumo_assist/domains/paper/verify.py` (1 classe + import)
- Modify: `src/prumo_assist/domains/paper/api.py` (re-export)
- Test (create): `tests/unit/paper/test_errors.py`

**Interfaces:**
- Produces: `prumo_assist.domains.paper.errors.PaperError` (subclasse de `PrumoError`); as 6 folhas de paper passam a ser `PaperError`. Task 5 depende disso.

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/unit/paper/test_errors.py`:

```python
"""Contrato da hierarquia de erros do domínio paper (spec 2026-07-26)."""

from __future__ import annotations

import pytest

from prumo_assist import PrumoError
from prumo_assist.domains.paper import connect, verify
from prumo_assist.domains.paper.errors import PaperError

_PAPER_LEAVES = (
    connect.ZoteroOfflineError,
    connect.CollectionNotFoundError,
    connect.AmbiguousCollectionError,
    connect.AlreadyConnectedError,
    connect.UnsupportedCollectionNameError,
    verify.RefcheckerUnavailableError,
)


@pytest.mark.parametrize("leaf", _PAPER_LEAVES)
def test_leaf_is_paper_error_and_prumo_error(leaf: type[Exception]) -> None:
    assert issubclass(leaf, PaperError)
    assert issubclass(leaf, PrumoError)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/paper/test_errors.py -v`
Expected: FAIL no import — `ModuleNotFoundError: No module named 'prumo_assist.domains.paper.errors'`.

- [ ] **Step 3: Criar `errors.py` e re-basear as folhas**

Criar `src/prumo_assist/domains/paper/errors.py`:

```python
"""Base das exceções do domínio paper.

Toda exceção de negócio do domínio herda de :class:`PaperError` — capturada
automaticamente por ``core/cli_op.cli_run`` nas fachadas (mensagem limpa +
exit code). Erro novo no domínio: herde daqui; nenhuma tupla de catch
precisa ser estendida.
"""

from __future__ import annotations

from prumo_assist import PrumoError


class PaperError(PrumoError):
    """Falha de negócio do domínio paper (sync, connect, verify, ...)."""
```

Em `src/prumo_assist/domains/paper/connect.py`, adicionar o import e trocar a base das 5:

```python
from prumo_assist.domains.paper.errors import PaperError
```

```python
class ZoteroOfflineError(PaperError):
class CollectionNotFoundError(PaperError):
class AmbiguousCollectionError(PaperError):
class AlreadyConnectedError(PaperError):
class UnsupportedCollectionNameError(PaperError):
```

Em `src/prumo_assist/domains/paper/verify.py`, idem para 1:

```python
class RefcheckerUnavailableError(PaperError):
```

Em `src/prumo_assist/domains/paper/api.py`, adicionar o import:

```python
from prumo_assist.domains.paper.errors import PaperError
```

e `"PaperError",` no `__all__` (ASCII: depois de `"ExtractPrep"`, antes das minúsculas).

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/paper/test_errors.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Bateria completa**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run python .github/scripts/gen_indexes.py --check`
Expected: tudo verde — em particular `test_paper_connect_error_contract` intacto.

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/domains/paper/errors.py src/prumo_assist/domains/paper/connect.py src/prumo_assist/domains/paper/verify.py src/prumo_assist/domains/paper/api.py tests/unit/paper/test_errors.py
git commit -m "refactor(paper): erros de connect/verify herdam de PaperError(PrumoError)"
```

---

### Task 5: Fachada paper — `exit_codes` declarativo, tuplas somem

**Files:**
- Modify: `src/prumo_assist/domains/paper/cli.py`

**Interfaces:**
- Consumes: `exit_codes` de `cli_run` (Task 1); folhas de paper como `PrumoError` (Task 4).
- Produces: nada novo; `_CONNECT_CATCHES` e `_VERIFY_CATCHES` deixam de existir.

- [ ] **Step 1: Encolher**

Em `src/prumo_assist/domains/paper/cli.py`:

1. Deletar `_VERIFY_CATCHES = (...)` e `_CONNECT_CATCHES = (...)` (linhas ~37–44).
2. `verify_refs_command`: `catches=_VERIFY_CATCHES` → `catches=(FileNotFoundError,)`.
3. `connect_command`: o try/except interno vira mapa declarativo — o corpo do
   `with` passa a ser:

```python
    with cli_run(
        json_mode=json_mode, exit_codes={connect.ZoteroOfflineError: 2}
    ) as console:
        r = connect.connect_collection(path.resolve(), collection, library=library)
        console.success(
            f"coleção '{r.collection.path}' ({r.collection.library}) conectada → {r.bib_path}"
        )
        if not r.exported:
            console.info(
                "export agendado no BBT — o arquivo aparece em instantes; confira com "
                "`prumo paper sync` em seguida."
            )
        console.emit(
            {
                "library": r.collection.library,
                "path": r.collection.path,
                "bbt_path": r.collection.bbt_path,
                "bib_path": str(r.bib_path),
                "exported": r.exported,
                "next": "prumo paper sync",
            }
        )
```

(`sync_annotations_command` e `sync_notes_command` NÃO mudam — `exit_code=2`
por comando continua sendo o mecanismo certo pra elas.)

- [ ] **Step 2: Rodar os locks de comportamento**

Run: `uv run pytest tests/unit/paper/ -v`
Expected: tudo PASS sem editar nenhum teste — em particular
`test_paper_connect_error_contract`: 4 erros → exit 1, offline → exit 2, sem traceback.

- [ ] **Step 3: Bateria completa**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run python .github/scripts/gen_indexes.py --check`
Expected: tudo verde.

- [ ] **Step 4: Commit**

```bash
git add src/prumo_assist/domains/paper/cli.py
git commit -m "refactor(paper): fachada usa exit_codes declarativo; tuplas somem"
```

---

### Task 6: Docs — CHANGELOG e ARCHITECTURE

**Files:**
- Modify: `CHANGELOG.md` (seção "Não publicado")
- Modify: `ARCHITECTURE.md` (2 linhas do mapa)

**Interfaces:**
- Consumes: tudo implementado (Tasks 1–5).

- [ ] **Step 1: CHANGELOG**

Em `CHANGELOG.md`, sob `## [Não publicado]`: se não existir `### Alterado`,
criar a seção após o bloco `### Adicionado`; acrescentar:

```markdown
- **Erros de domínio sob `PrumoError`** — as 19 exceções de negócio de `write`
  e `paper` (antes `RuntimeError` cru) herdam de `WriteError`/`PaperError`
  (`domains/<X>/errors.py`), auto-capturadas por `cli_run`; as tuplas de catch
  enumeradas das fachadas viraram builtins e `cli_run` ganhou `exit_codes`
  declarativo (`ZoteroOfflineError` → exit 2). Comportamento do CLI (mensagens
  e exit codes) inalterado; consumidor da API Python que capturava
  `RuntimeError` deve capturar `PrumoError` (spec 2026-07-26).
```

- [ ] **Step 2: ARCHITECTURE.md**

No mapa de `src/prumo_assist/`:

- linha do `__init__.py`:
  `│   ├── __init__.py            ← hierarquia de exceções (PrumoError + cross-cutting; bases por domínio em domains/<X>/errors.py)`
- linha do `domains/<X>/`:
  `│   └── <X>/               ← cli.py + api.py + <op>.py + schemas/v1.py + errors.py (ADR-0006);`

- [ ] **Step 3: Bateria completa**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run python .github/scripts/gen_indexes.py --check && uv run mypy`
Expected: tudo verde.

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md ARCHITECTURE.md
git commit -m "docs: CHANGELOG + ARCHITECTURE refletem hierarquia de erros por domínio"
```
