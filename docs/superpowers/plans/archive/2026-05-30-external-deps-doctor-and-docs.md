---
status: implemented
verified: 2026-06-11
release: "0.61.0"
---

# External Dependency Discoverability (`doctor` + docs) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar visíveis e verificáveis as dependências externas que o plugin assume mas não documenta: o servidor MCP `qmd` (skills `wiki-query`, `wiki-ingest`, `active-learning` dependem dele) e o Zotero + Better BibTeX em `127.0.0.1:23119` (comandos `paper sync-annotations`/`sync-notes` dependem dele). Hoje quem instala o plugin recebe skills que referenciam um MCP que pode não estar no PATH, sem nenhum aviso.

**Architecture:**
- Um módulo novo `core/deps.py` centraliza a detecção de dependências externas (binários no PATH + portas TCP), retornando uma lista de `DepStatus` puramente declarativa e testável.
- O comando existente `prumo doctor` (em `cli.py`) ganha uma seção "External dependencies" alimentada por `core/deps.py`. Dependência ausente vira warning informativo — **não** quebra o doctor (exit code só muda para erros estruturais que já existem).
- O README ganha uma seção "Pré-requisitos" documentando `qmd` (repo `https://github.com/tobi/qmd`, install `bun install -g @tobilu/qmd`) e o Zotero+BBT, mais a nota de que `prumo doctor` checa isso.

**Tech Stack:** Python 3.11+ stdlib (`shutil.which`, `socket`), Typer, pytest, ruff, mypy strict. `uv` como runner.

---

## File Structure

| Caminho | Ação | Responsabilidade |
|---|---|---|
| `src/prumo_assist/core/deps.py` | **Create** | `check_external_deps()` → lista de `DepStatus`; helpers `_binary_on_path`, `_port_open` |
| `src/prumo_assist/cli.py` | **Modify** | `doctor_command` chama `check_external_deps` e reporta |
| `tests/unit/core/test_deps.py` | **Create** | tests de `check_external_deps` com PATH/porta mockados |
| `tests/unit/test_cli_doctor.py` | **Create** | integration test do `doctor` mostrando deps |
| `README.md` | **Modify** | seção "Pré-requisitos" |

---

## Task 1: `core/deps.py` — detecção declarativa de dependências

**Files:**
- Create: `src/prumo_assist/core/deps.py`
- Create: `tests/unit/core/test_deps.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/core/test_deps.py`:

```python
"""Tests para detecção de dependências externas."""

from __future__ import annotations

from unittest.mock import patch

from prumo_assist.core.deps import DepStatus, check_external_deps


def test_qmd_present_when_on_path() -> None:
    with (
        patch("prumo_assist.core.deps._binary_on_path", return_value="/usr/local/bin/qmd"),
        patch("prumo_assist.core.deps._port_open", return_value=False),
    ):
        statuses = check_external_deps()
    qmd = _by_name(statuses, "qmd")
    assert qmd.present is True
    assert qmd.detail and "qmd" in qmd.detail


def test_qmd_absent_includes_install_hint() -> None:
    with (
        patch("prumo_assist.core.deps._binary_on_path", return_value=None),
        patch("prumo_assist.core.deps._port_open", return_value=False),
    ):
        statuses = check_external_deps()
    qmd = _by_name(statuses, "qmd")
    assert qmd.present is False
    assert "bun install -g @tobilu/qmd" in qmd.hint
    assert "github.com/tobi/qmd" in qmd.hint


def test_zotero_present_when_port_open() -> None:
    with (
        patch("prumo_assist.core.deps._binary_on_path", return_value=None),
        patch("prumo_assist.core.deps._port_open", return_value=True),
    ):
        statuses = check_external_deps()
    zot = _by_name(statuses, "zotero")
    assert zot.present is True


def test_zotero_absent_hint_mentions_port_and_bbt() -> None:
    with (
        patch("prumo_assist.core.deps._binary_on_path", return_value=None),
        patch("prumo_assist.core.deps._port_open", return_value=False),
    ):
        statuses = check_external_deps()
    zot = _by_name(statuses, "zotero")
    assert zot.present is False
    assert "23119" in zot.hint
    assert "Better BibTeX" in zot.hint


def test_dep_status_is_serializable() -> None:
    s = DepStatus(name="x", present=True, required_by=["foo"], detail="d", hint="h")
    assert s.as_dict() == {
        "name": "x",
        "present": True,
        "required_by": ["foo"],
        "detail": "d",
        "hint": "h",
    }


def _by_name(statuses: list[DepStatus], name: str) -> DepStatus:
    for s in statuses:
        if s.name == name:
            return s
    raise AssertionError(f"dep {name!r} não encontrada em {[s.name for s in statuses]}")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/core/test_deps.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prumo_assist.core.deps'`

- [ ] **Step 3: Implement `core/deps.py`**

Create `src/prumo_assist/core/deps.py`:

```python
"""Detecção de dependências externas do ecossistema prumo.

prumo orquestra ferramentas que vivem fora do pacote Python:

- **qmd** — servidor MCP de busca (BM25+vector+rerank) que as skills
  ``wiki-query``, ``wiki-ingest`` e ``active-learning`` consomem. Binário no PATH.
- **Zotero + Better BibTeX** — fonte de bibliografia/anotações. Expõe API local
  HTTP em ``127.0.0.1:23119`` quando o app está aberto.

Este módulo é puramente declarativo: retorna ``DepStatus`` por dependência.
Quem decide o que fazer (warning, erro, JSON) é o ``doctor``. Centralizar aqui
evita espalhar ``shutil.which`` e checagem de porta pelo CLI.
"""

from __future__ import annotations

import shutil
import socket
from dataclasses import dataclass

ZOTERO_HOST = "127.0.0.1"
ZOTERO_PORT = 23119


@dataclass
class DepStatus:
    """Estado de uma dependência externa."""

    name: str
    present: bool
    required_by: list[str]
    detail: str
    hint: str

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "present": self.present,
            "required_by": self.required_by,
            "detail": self.detail,
            "hint": self.hint,
        }


def _binary_on_path(name: str) -> str | None:
    """Caminho do binário no PATH, ou ``None``. Seam testável."""
    return shutil.which(name)


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """``True`` se há algo escutando em ``host:port``. Seam testável."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_external_deps() -> list[DepStatus]:
    """Audita dependências externas. Nunca levanta — sempre retorna a lista."""
    statuses: list[DepStatus] = []

    qmd_path = _binary_on_path("qmd")
    statuses.append(
        DepStatus(
            name="qmd",
            present=qmd_path is not None,
            required_by=["wiki-query", "wiki-ingest", "active-learning"],
            detail=f"qmd em {qmd_path}" if qmd_path else "qmd não está no PATH",
            hint=(
                "Instale o qmd (servidor MCP de busca): `bun install -g @tobilu/qmd` "
                "— repo https://github.com/tobi/qmd. Depois confirme que está no PATH."
            ),
        )
    )

    zotero_up = _port_open(ZOTERO_HOST, ZOTERO_PORT)
    statuses.append(
        DepStatus(
            name="zotero",
            present=zotero_up,
            required_by=["paper sync-annotations", "paper sync-notes", "write export --to docx"],
            detail=(
                f"API local respondendo em {ZOTERO_HOST}:{ZOTERO_PORT}"
                if zotero_up
                else f"nada escutando em {ZOTERO_HOST}:{ZOTERO_PORT}"
            ),
            hint=(
                f"Abra o Zotero 9 (com Better BibTeX instalado) — ele expõe a API "
                f"local em {ZOTERO_HOST}:{ZOTERO_PORT}. Só é necessário pros comandos "
                f"que leem anotações/notas; o resto do prumo funciona sem ele."
            ),
        )
    )

    return statuses
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/core/test_deps.py -v`
Expected: 5 tests PASS

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check src/prumo_assist/core/deps.py tests/unit/core/test_deps.py`
Run: `uv run --extra dev mypy src/prumo_assist/core/deps.py`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/core/deps.py tests/unit/core/test_deps.py
git commit -m "feat(core): external dependency detection (qmd, zotero)"
```

---

## Task 2: Integrar deps no `prumo doctor`

**Files:**
- Modify: `src/prumo_assist/cli.py:477-513` (`doctor_command`)
- Create: `tests/unit/test_cli_doctor.py`

- [ ] **Step 1: Write the failing integration tests**

Create `tests/unit/test_cli_doctor.py`:

```python
"""Integration tests do prumo doctor com seção de dependências externas."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from prumo_assist.cli import app
from prumo_assist.core.deps import DepStatus

runner = CliRunner()


def _project(tmp_path: Path) -> Path:
    pj = tmp_path / "pj_x"
    for d in (".claude", "docs", "references"):
        (pj / d).mkdir(parents=True)
    (pj / ".claude" / "skills").mkdir()
    return pj


def test_doctor_json_includes_external_deps(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    fake = [
        DepStatus(name="qmd", present=True, required_by=["wiki-query"], detail="ok", hint=""),
        DepStatus(name="zotero", present=False, required_by=["paper sync-annotations"],
                  detail="down", hint="abra o Zotero"),
    ]
    with patch("prumo_assist.cli.check_external_deps", return_value=fake):
        result = runner.invoke(app, ["doctor", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    names = {d["name"] for d in payload["external_deps"]}
    assert names == {"qmd", "zotero"}


def test_doctor_missing_dep_does_not_fail_exit_code(tmp_path: Path) -> None:
    """Dep externa ausente é informativa: não derruba o exit code (só estrutura derruba)."""
    pj = _project(tmp_path)
    fake = [
        DepStatus(name="qmd", present=False, required_by=["wiki-query"],
                  detail="missing", hint="instale"),
    ]
    with patch("prumo_assist.cli.check_external_deps", return_value=fake):
        result = runner.invoke(app, ["doctor", str(pj), "--json"])
    # estrutura do projeto está OK → exit 0 mesmo com qmd ausente
    assert result.exit_code == 0, result.output


def test_doctor_human_output_shows_missing_dep_hint(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    fake = [
        DepStatus(name="qmd", present=False, required_by=["wiki-query"],
                  detail="qmd não está no PATH", hint="bun install -g @tobilu/qmd"),
    ]
    with patch("prumo_assist.cli.check_external_deps", return_value=fake):
        result = runner.invoke(app, ["doctor", str(pj)])
    assert "qmd" in result.output
    assert "bun install -g @tobilu/qmd" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_cli_doctor.py -v`
Expected: FAIL — `external_deps` key absent; `check_external_deps` not imported in `cli.py`.

- [ ] **Step 3: Add the import in `cli.py`**

In `src/prumo_assist/cli.py`, after line 38 (`from prumo_assist.core.paths import ...`), add:

```python
from prumo_assist.core.deps import check_external_deps
```

- [ ] **Step 4: Extend `doctor_command`**

In `src/prumo_assist/cli.py`, replace the body of `doctor_command` (lines 485-513) with:

```python
    """Health-check do projeto: estrutura, skills instaladas, integrations OK?

    Também reporta dependências externas (qmd, Zotero). Dependência externa
    ausente é informativa — não muda o exit code; só problemas estruturais
    (diretórios/skills faltando) retornam 1.
    """
    console = Console(json_mode=json_mode)
    target = path.resolve()
    issues: list[str] = []

    expected = [".claude", "docs", "references"]
    for name in expected:
        if not (target / name).is_dir():
            issues.append(f"Diretório esperado ausente: {name}/")

    for adapter_cls in INTEGRATIONS.values():
        adapter = adapter_cls()
        issues.extend(adapter.doctor(target))

    deps = check_external_deps()

    payload = {
        "project": str(target),
        "ok": not issues,
        "issues": issues,
        "external_deps": [d.as_dict() for d in deps],
        "version": __version__,
    }
    if issues:
        console.warn(f"{len(issues)} problema(s) estrutural(is) encontrado(s).")
        for i in issues:
            console.info(f"  • {i}")
    else:
        console.success("Estrutura do projeto OK.")

    console.info("")
    console.info("Dependências externas:")
    for d in deps:
        mark = "✓" if d.present else "○"
        console.info(f"  {mark} {d.name} — {d.detail}")
        if not d.present:
            console.info(f"      ↳ {d.hint}")

    console.emit(payload)
    if issues:
        raise typer.Exit(code=1)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_cli_doctor.py -v`
Expected: 3 tests PASS

- [ ] **Step 6: Lint + types**

Run: `uv run ruff check src/prumo_assist/cli.py tests/unit/test_cli_doctor.py`
Run: `uv run --extra dev mypy src/prumo_assist/cli.py`
Expected: clean

- [ ] **Step 7: Commit**

```bash
git add src/prumo_assist/cli.py tests/unit/test_cli_doctor.py
git commit -m "feat(doctor): report external deps (qmd, zotero)"
```

---

## Task 3: Documentar pré-requisitos no README

**Files:**
- Modify: `README.md` (inserir seção "Pré-requisitos" após "Instalação", antes de "Pressupostos de projeto")

- [ ] **Step 1: Insert the prerequisites section**

In `README.md`, after the "Instalação" code block (after the `/plugin install ...` block, line ~51) and before "## Pressupostos de projeto", insert:

```markdown
## Pré-requisitos externos

O plugin orquestra duas ferramentas que vivem fora do pacote Python. Rode
`prumo doctor` a qualquer momento para checar o estado delas.

| Dependência | Necessária para | Como instalar / habilitar |
|---|---|---|
| **`qmd`** (MCP de busca) | `/prumo-assist:wiki-query`, `/prumo-assist:wiki-ingest`, `/prumo-assist:active-learning` | `bun install -g @tobilu/qmd` (repo: [github.com/tobi/qmd](https://github.com/tobi/qmd)). Precisa estar no `PATH`. Declarado em `.mcp.json` como servidor `qmd`. |
| **Zotero 9 + Better BibTeX** | `paper sync-annotations`, `paper sync-notes`, `write export --to docx` (citações vivas) | Abra o Zotero 9 com o [Better BibTeX](https://retorque.re/zotero-better-bibtex/) instalado. Ele expõe a API local em `127.0.0.1:23119`. Só é necessário para os comandos que leem anotações/notas — o resto do prumo funciona sem ele. |

> [!tip]
> `prumo doctor` lista o estado de cada dependência (`✓` presente / `○` ausente)
> com a dica de instalação. Dependência ausente é apenas um aviso — não impede
> o uso das partes do plugin que não dependem dela.
```

- [ ] **Step 2: Update the bare `### MCP` bullet to cross-reference**

In `README.md`, the existing `### MCP` section (line ~40) says only `- **qmd** — servidor MCP ...`. Append a pointer so the reader knows it must be installed:

```markdown
- **`qmd`** — servidor MCP para busca BM25 + vector + rerank local no wiki dos projetos. **Requer instalação** — ver [Pré-requisitos externos](#pré-requisitos-externos).
```

- [ ] **Step 3: Verify markdown renders (no broken anchors)**

Run: `uv run python -c "import pathlib; t = pathlib.Path('README.md').read_text(); assert 'Pré-requisitos externos' in t; assert 'bun install -g @tobilu/qmd' in t; assert '127.0.0.1:23119' in t; print('README OK')"`
Expected: `README OK`

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): document external prerequisites (qmd, zotero)"
```

---

## Task 4: Suíte completa + sanity manual

**Files:** none (verification only)

- [ ] **Step 1: Full test suite**

Run: `uv run pytest -q`
Expected: all PASS

- [ ] **Step 2: Lint + types whole tree**

Run: `uv run ruff check src tests`
Run: `uv run --extra dev mypy src tests`
Expected: clean

- [ ] **Step 3: Run doctor live (real environment)**

Run: `uv run prumo doctor .`
Expected: human output ends with a "Dependências externas:" section listing `qmd` and `zotero` with `✓`/`○`. (Result depends on your machine — the point is the section renders.)

---

## Self-Review notes (for the implementer)

- **Scope:** This plan covers gaps #2 (qmd packaging/discoverability) and #3 (Zotero prerequisites in README) from the audit. It does **not** install qmd or change `.mcp.json` — that file already declares the `qmd` server; the gap was *discoverability*, which `doctor` + README now close.
- **Exit-code policy:** external deps are informative only. `doctor` keeps returning `1` solely for the pre-existing structural checks (missing `.claude`/`docs`/`references` or uninstalled skills). This is asserted by `test_doctor_missing_dep_does_not_fail_exit_code`.
- **Why `127.0.0.1` not `localhost`:** matches the Lua filters and the CHANGELOG wording, and dodges IPv6 `::1` resolution surprises. (Plan C — harden `zotero.py` — unifies the Python client constant on the same host with an env override.)
- **Type consistency:** `DepStatus.as_dict()` is the single serialization path used by both `doctor`'s JSON payload and the tests.
