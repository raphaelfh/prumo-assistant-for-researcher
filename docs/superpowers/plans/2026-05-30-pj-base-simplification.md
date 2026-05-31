# pj_base Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduzir o template `templates/pj_base/` a um núcleo mínimo genérico (bibliografia/Zotero + wiki + escrita + decisões) e mover clínico/ML para módulos opt-in, ativados por wizard no `prumo init` e por um novo comando `prumo add`.

**Architecture:** Extrair a lógica de overlay/descoberta para `core/scaffold.py` (cli.py vira fachada fina). Módulos são overlays de **conteúdo puro** em `templates/modules/<nome>/` com um `_module.toml` de metadados; `prumo add` aplica por cópia não-destrutiva. Nenhum módulo edita arquivo existente do núcleo (regras aditivas em `.claude/rules/`, alvos de Make em `.claude/make/*.mk`, grupos de deps já inertes no `pyproject.toml`).

**Tech Stack:** Python 3.13, Typer, Rich, `tomllib` (stdlib), pytest + `typer.testing.CliRunner`, ruff.

**Spec:** [`docs/superpowers/specs/2026-05-30-pj-base-simplification-design.md`](../specs/2026-05-30-pj-base-simplification-design.md)

**Ordering invariant:** cada task termina com a suíte verde. Conteúdo clínico/ML é **movido** (`git mv`) do `pj_base` para `modules/` na Fase 3, e os testes de `init` afetados são atualizados na mesma fase.

---

## Fase 1 — `core/scaffold.py` (fundação, adição pura)

### Task 1: `overlay()` — cópia não-destrutiva

**Files:**
- Create: `src/prumo_assist/core/scaffold.py`
- Test: `tests/unit/core/test_scaffold.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/core/test_scaffold.py
"""Unit tests para core/scaffold.py (overlay + descoberta de módulos)."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.core import scaffold


def test_overlay_copies_into_empty_target(tmp_path: Path) -> None:
    src = tmp_path / "src"
    (src / "docs").mkdir(parents=True)
    (src / "docs" / "a.md").write_text("A")
    (src / "root.txt").write_text("R")
    target = tmp_path / "tgt"
    target.mkdir()

    copied, skipped = scaffold.overlay(src, target)

    assert (target / "docs" / "a.md").read_text() == "A"
    assert (target / "root.txt").read_text() == "R"
    assert sorted(copied) == ["docs/a.md", "root.txt"]
    assert skipped == []


def test_overlay_does_not_clobber_existing(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "keep.txt").write_text("FROM SRC")
    target = tmp_path / "tgt"
    target.mkdir()
    (target / "keep.txt").write_text("USER OWN")

    copied, skipped = scaffold.overlay(src, target)

    assert (target / "keep.txt").read_text() == "USER OWN"
    assert copied == []
    assert skipped == ["keep.txt"]


def test_overlay_is_idempotent(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "x.txt").write_text("X")
    target = tmp_path / "tgt"
    target.mkdir()

    scaffold.overlay(src, target)
    copied, skipped = scaffold.overlay(src, target)  # segunda vez

    assert copied == []
    assert skipped == ["x.txt"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/core/test_scaffold.py -v`
Expected: FAIL with `ModuleNotFoundError: prumo_assist.core.scaffold` (ou `AttributeError: overlay`).

- [ ] **Step 3: Write minimal implementation**

```python
# src/prumo_assist/core/scaffold.py
"""Scaffold compartilhado: overlay de templates + descoberta de módulos.

Extraído do ``cli.py`` para que ``init`` e ``add`` reusem a mesma lógica
(regra da ARCHITECTURE: ``cli.py`` é fachada fina, sem lógica de negócio).
"""

from __future__ import annotations

import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

from prumo_assist.core.paths import resolve_resource


def overlay(template: Path, target: Path) -> tuple[list[str], list[str]]:
    """Copia ``template/*`` para ``target/`` sem sobrescrever arquivos existentes.

    Retorna ``(copied, skipped)`` com paths relativos ao target. Cria
    diretórios faltantes; ignora arquivos cujo destino já existe.
    """
    copied: list[str] = []
    skipped: list[str] = []
    for src in template.rglob("*"):
        rel = src.relative_to(template)
        dst = target / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        if dst.exists():
            skipped.append(str(rel))
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(str(rel))
    return copied, skipped
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/core/test_scaffold.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/core/scaffold.py tests/unit/core/test_scaffold.py
git commit -m "feat(core): scaffold.overlay — cópia não-destrutiva reusável"
```

---

### Task 2: `discover_modules()` + `ModuleInfo` + `get_module()`

**Files:**
- Modify: `src/prumo_assist/core/scaffold.py`
- Test: `tests/unit/core/test_scaffold.py:end`

- [ ] **Step 1: Write the failing test** (append to `test_scaffold.py`)

```python
import pytest


@pytest.fixture
def fake_modules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Cria templates/modules/<m>/_module.toml fake e aponta scaffold para ele."""
    root = tmp_path / "templates" / "modules"
    clin = root / "clinical"
    clin.mkdir(parents=True)
    (clin / "_module.toml").write_text(
        'description = "Camada clínica"\n'
        'when_to_use = "Estudo clínico"\n'
        'anchor = "docs/protocol.md"\n'
    )
    (clin / "docs").mkdir()
    (clin / "docs" / "protocol.md").write_text("# protocolo")
    bare = root / "bare"  # módulo sem _module.toml
    bare.mkdir()
    monkeypatch.setattr(scaffold, "_modules_root", lambda: root)
    return root


def test_discover_modules_reads_metadata(fake_modules: Path) -> None:
    mods = scaffold.discover_modules()
    names = [m.name for m in mods]
    assert names == ["bare", "clinical"]  # ordenado
    clin = scaffold.get_module("clinical")
    assert clin is not None
    assert clin.description == "Camada clínica"
    assert clin.anchor == "docs/protocol.md"


def test_discover_modules_tolerates_missing_metadata(fake_modules: Path) -> None:
    bare = scaffold.get_module("bare")
    assert bare is not None
    assert bare.description == ""
    assert bare.anchor is None


def test_get_module_unknown_returns_none(fake_modules: Path) -> None:
    assert scaffold.get_module("nope") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/core/test_scaffold.py -k discover -v`
Expected: FAIL with `AttributeError: _modules_root` / `discover_modules`.

- [ ] **Step 3: Write minimal implementation** (append to `scaffold.py`)

```python
@dataclass(frozen=True)
class ModuleInfo:
    name: str
    description: str
    when_to_use: str
    anchor: str | None
    path: Path


def _modules_root() -> Path:
    return resolve_resource("templates") / "modules"


def discover_modules() -> list[ModuleInfo]:
    """Lista módulos em ``templates/modules/`` lendo cada ``_module.toml``."""
    root = _modules_root()
    if not root.is_dir():
        return []
    out: list[ModuleInfo] = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        meta: dict = {}
        meta_path = d / "_module.toml"
        if meta_path.is_file():
            with meta_path.open("rb") as f:
                meta = tomllib.load(f)
        out.append(
            ModuleInfo(
                name=d.name,
                description=meta.get("description", ""),
                when_to_use=meta.get("when_to_use", ""),
                anchor=meta.get("anchor"),
                path=d,
            )
        )
    return out


def get_module(name: str) -> ModuleInfo | None:
    for m in discover_modules():
        if m.name == name:
            return m
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/core/test_scaffold.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/core/scaffold.py tests/unit/core/test_scaffold.py
git commit -m "feat(core): discover_modules + ModuleInfo lendo _module.toml"
```

---

### Task 3: `is_applied()`

**Files:**
- Modify: `src/prumo_assist/core/scaffold.py`
- Test: `tests/unit/core/test_scaffold.py:end`

- [ ] **Step 1: Write the failing test** (append)

```python
def test_is_applied_true_when_anchor_exists(tmp_path: Path) -> None:
    m = scaffold.ModuleInfo("clinical", "", "", "docs/protocol.md", tmp_path)
    target = tmp_path / "pj"
    (target / "docs").mkdir(parents=True)
    (target / "docs" / "protocol.md").write_text("x")
    assert scaffold.is_applied(target, m) is True


def test_is_applied_false_when_anchor_missing_or_none(tmp_path: Path) -> None:
    target = tmp_path / "pj"
    target.mkdir()
    with_anchor = scaffold.ModuleInfo("clinical", "", "", "docs/protocol.md", tmp_path)
    no_anchor = scaffold.ModuleInfo("x", "", "", None, tmp_path)
    assert scaffold.is_applied(target, with_anchor) is False
    assert scaffold.is_applied(target, no_anchor) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/core/test_scaffold.py -k is_applied -v`
Expected: FAIL with `AttributeError: is_applied`.

- [ ] **Step 3: Write minimal implementation** (append)

```python
def is_applied(target: Path, module: ModuleInfo) -> bool:
    """``True`` se o ``anchor`` declarado do módulo existe em ``target``."""
    if not module.anchor:
        return False
    return (target / module.anchor).exists()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/core/test_scaffold.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/core/scaffold.py tests/unit/core/test_scaffold.py
git commit -m "feat(core): is_applied via anchor declarado do módulo"
```

---

## Fase 2 — `init` usa scaffold + prefixo único `pj_`

### Task 4: Refatorar `init` para usar `scaffold.overlay`

**Files:**
- Modify: `src/prumo_assist/cli.py` (remover `_merge_scaffold`; importar de scaffold)

- [ ] **Step 1: Run existing init tests (baseline green)**

Run: `uv run pytest tests/unit/test_cli_init.py -v`
Expected: PASS (baseline antes do refactor).

- [ ] **Step 2: Edit `cli.py`** — adicionar import e remover o helper local

No topo, junto aos imports de core:

```python
from prumo_assist.core.scaffold import overlay as _overlay
```

Deletar a função `_merge_scaffold` inteira (linhas que começam em `def _merge_scaffold(`). Em `init_command`, no ramo `MODE_MERGE`, trocar:

```python
        if mode == MODE_MERGE:
            target.mkdir(parents=True, exist_ok=True)
            copied, skipped = _merge_scaffold(template, target)
```

por:

```python
        if mode == MODE_MERGE:
            target.mkdir(parents=True, exist_ok=True)
            copied, skipped = _overlay(template, target)
```

- [ ] **Step 3: Run init tests to verify still green**

Run: `uv run pytest tests/unit/test_cli_init.py -v`
Expected: PASS (comportamento idêntico; lógica só mudou de lugar).

- [ ] **Step 4: Run full suite + lint**

Run: `uv run pytest -q && uv run ruff check src/prumo_assist/cli.py`
Expected: PASS, sem erros de lint (sem import não usado).

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/cli.py
git commit -m "refactor(cli): init usa core/scaffold.overlay (cli.py mais fino)"
```

---

### Task 5: Prefixo único `pj_`

**Files:**
- Modify: `src/prumo_assist/cli.py:92` (`_VALID_PREFIXES`)
- Test: `tests/unit/test_cli_init.py`

- [ ] **Step 1: Write the failing test** (append to `test_cli_init.py`)

```python
def test_init_rejects_srpj_prefix(tmp_path: Path) -> None:
    """srpj_ deixou de ser aceito; só pj_."""
    target = tmp_path / "srpj_old"
    result = runner.invoke(app, ["init", str(target), "--yes"])
    assert result.exit_code != 0


def test_init_accepts_pj_prefix(tmp_path: Path) -> None:
    target = tmp_path / "pj_ok"
    result = runner.invoke(app, ["init", str(target), "--json"])
    assert result.exit_code == 0, result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_cli_init.py -k "srpj or pj_prefix" -v`
Expected: `test_init_rejects_srpj_prefix` FAILS (srpj_ ainda é aceito hoje).

- [ ] **Step 3: Edit `cli.py`**

Trocar:

```python
_VALID_PREFIXES = ("srpj_", "pj_")
```

por:

```python
_VALID_PREFIXES = ("pj_",)
```

E o default do wizard (`_wizard`), trocar `default=default_target or "srpj_"` por `default=default_target or "pj_"`.

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_cli_init.py -v`
Expected: PASS (incl. os 2 novos).

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/cli.py tests/unit/test_cli_init.py
git commit -m "feat(cli): prefixo único pj_ (remove srpj_)"
```

---

## Fase 3 — Overlays de módulo (`clinical`, `ml`) por `git mv`

### Task 6: Módulo `clinical`

**Files:**
- Move: `templates/pj_base/docs/protocol.md` → `templates/modules/clinical/docs/protocol.md`
- Move: `templates/pj_base/docs/templates/*` → `templates/modules/clinical/docs/templates/`
- Create: `templates/modules/clinical/_module.toml`
- Create: `templates/modules/clinical/.claude/rules/clinical_context.md`
- Modify: `tests/unit/test_cli_init.py` (assertion de docs/templates)

- [ ] **Step 1: Move conteúdo clínico para o módulo**

```bash
mkdir -p templates/modules/clinical/docs templates/modules/clinical/.claude/rules
git mv templates/pj_base/docs/protocol.md templates/modules/clinical/docs/protocol.md
git mv templates/pj_base/docs/templates templates/modules/clinical/docs/templates
```

- [ ] **Step 2: Criar `_module.toml`**

```toml
# templates/modules/clinical/_module.toml
description = "Camada clínica: protocolo, projeto CEP, plano estatístico, contexto de ética."
when_to_use = "Estudo clínico/empírico com coorte e submissão a CEP."
anchor = "docs/protocol.md"
```

- [ ] **Step 3: Criar `clinical_context.md`** (campos clínicos extraídos do `project_context.md`)

```markdown
<!-- templates/modules/clinical/.claude/rules/clinical_context.md -->
---
paths:
  - "**/pj_*/**"
---

# Contexto clínico do estudo

> Preenchido pelo módulo `clinical`. Complementa `project_context.md`.

## Desfecho e rótulos
- **Definição do label positivo/negativo:**
- **Critérios de inclusão e exclusão:**

## Dados
- **Fonte (sistema, export, versão):**
- **Identificadores-chave** (ex.: `patient_id`, `accession_number`):
- **Modalidades:** tabular / imagem / outras

## Coorte e ética
- **População e coorte:**
- **Período de coleta / janela temporal:**
- **Aprovação ética / uso restrito** (CEP/CONEP, CAAE):
- **Contato / responsável:**
```

- [ ] **Step 4: Atualizar o teste de merge que assertava `docs/templates/README.md`**

Em `tests/unit/test_cli_init.py`, na função `test_init_merge_preserves_existing_files`, trocar:

```python
    assert (target / "docs" / "templates" / "README.md").is_file()
```

por:

```python
    assert (target / "docs" / "project_guide.md").is_file()
```

> Nota: `project_guide.md` ainda não existe no template até a Fase 6. Para manter este teste verde agora, use uma asserção de núcleo já presente: `assert (target / "references" / "_references.bib").is_file()`. Será trocada para `project_guide.md` na Task 12.

Aplicar a versão segura agora:

```python
    assert (target / "references" / "_references.bib").is_file()
```

- [ ] **Step 5: Run tests + commit**

Run: `uv run pytest tests/unit/test_cli_init.py -v`
Expected: PASS.

```bash
git add templates/ tests/unit/test_cli_init.py
git commit -m "feat(modules): cria módulo clinical (protocol + templates + contexto)"
```

---

### Task 7: Módulo `ml`

**Files:**
- Move: `templates/pj_base/.claude/rules/{coding_style,code_library,data_governance}.md` → `templates/modules/ml/.claude/rules/`
- Create: `templates/modules/ml/_module.toml`, `.../ml_stack.md`, `.claude/make/ml.mk`, `eda.ipynb`

- [ ] **Step 1: Mover regras de código**

```bash
mkdir -p templates/modules/ml/.claude/rules templates/modules/ml/.claude/make
git mv templates/pj_base/.claude/rules/coding_style.md templates/modules/ml/.claude/rules/coding_style.md
git mv templates/pj_base/.claude/rules/code_library.md templates/modules/ml/.claude/rules/code_library.md
git mv templates/pj_base/.claude/rules/data_governance.md templates/modules/ml/.claude/rules/data_governance.md
```

- [ ] **Step 2: Criar `_module.toml`**

```toml
# templates/modules/ml/_module.toml
description = "Stack de ML/dados, regras de código (ruff) e notebook de EDA."
when_to_use = "Vai treinar modelos ou fazer análise tabular/de imagem."
anchor = ".claude/rules/ml_stack.md"
```

- [ ] **Step 3: Criar `ml_stack.md`** (persona/stack removida do `CLAUDE.md` na Fase 6)

```markdown
<!-- templates/modules/ml/.claude/rules/ml_stack.md -->
---
paths:
  - "**/*.py"
  - "**/*.ipynb"
---

# Stack de ML/dados (módulo `ml`)

Persona complementar: **pesquisador de machine learning com foco em saúde**.
Prioridades: rigor clínico, reprodutibilidade, governança de dados.

## Stack
- **Tabular:** Polars/pandas, Pandera, scikit-learn `Pipeline`; opcional XGBoost/LightGBM.
- **Deep learning:** PyTorch Lightning + timm + TorchMetrics + albumentations.
- **Visualização:** seaborn + matplotlib (`sns.set_theme(style="whitegrid", context="paper")`); Plotly só em dashboards.
- **Dependências:** grupos opcionais no `pyproject.toml` — ative com `uv sync --group tabular --group viz` (+ `imaging`/`deep-learning` conforme o estudo).
```

- [ ] **Step 4: Criar `ml.mk`** (alvos de dev incluídos via `-include`)

```makefile
# templates/modules/ml/.claude/make/ml.mk — incluído por `-include .claude/make/*.mk`
lint:  ## Ruff check no projeto
	uv run ruff check .

format:  ## Ruff format no projeto
	uv run ruff format .
```

- [ ] **Step 5: Criar `eda.ipynb`** (1 stub genérico)

```bash
cat > templates/modules/ml/eda.ipynb <<'EOF'
{
 "cells": [
  {"cell_type": "markdown", "metadata": {}, "source": ["# EDA\n", "\n", "Análise exploratória inicial."]},
  {"cell_type": "code", "execution_count": null, "metadata": {}, "outputs": [], "source": ["import pandas as pd\n"]}
 ],
 "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
 "nbformat": 4,
 "nbformat_minor": 5
}
EOF
```

- [ ] **Step 6: Run tests + commit**

Run: `uv run pytest tests/unit/test_cli_init.py -v`
Expected: PASS (pj_base perdeu as 3 rules; nenhum teste assertava elas).

```bash
git add templates/
git commit -m "feat(modules): cria módulo ml (stack, rules, ml.mk, eda.ipynb)"
```

---

## Fase 4 — Comando `prumo add`

### Task 8: `prumo add <módulo>` (aplicação direta)

**Files:**
- Modify: `src/prumo_assist/cli.py` (novo comando `add`)
- Test: `tests/unit/test_cli_add.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_cli_add.py
"""Integration test: `prumo add` aplica overlays de módulo."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from prumo_assist.cli import app

runner = CliRunner()


def _init(target: Path) -> None:
    res = runner.invoke(app, ["init", str(target), "--json"])
    assert res.exit_code == 0, res.output


def test_add_clinical_restores_protocol(tmp_path: Path) -> None:
    target = tmp_path / "pj_demo"
    _init(target)
    assert not (target / "docs" / "protocol.md").exists()  # núcleo não tem

    res = runner.invoke(app, ["add", "clinical", "--target", str(target), "--json"])
    assert res.exit_code == 0, res.output
    assert (target / "docs" / "protocol.md").is_file()
    assert (target / "docs" / "templates" / "projeto-cep.md").is_file()
    payload = json.loads(res.stdout)
    assert payload["module"] == "clinical"
    assert payload["files_copied"] > 0


def test_add_ml_restores_stack(tmp_path: Path) -> None:
    target = tmp_path / "pj_demo"
    _init(target)
    res = runner.invoke(app, ["add", "ml", "--target", str(target), "--json"])
    assert res.exit_code == 0, res.output
    assert (target / ".claude" / "rules" / "ml_stack.md").is_file()
    assert (target / ".claude" / "make" / "ml.mk").is_file()


def test_add_unknown_module_errors(tmp_path: Path) -> None:
    target = tmp_path / "pj_demo"
    _init(target)
    res = runner.invoke(app, ["add", "nope", "--target", str(target)])
    assert res.exit_code != 0


def test_add_is_non_destructive(tmp_path: Path) -> None:
    target = tmp_path / "pj_demo"
    _init(target)
    runner.invoke(app, ["add", "clinical", "--target", str(target)])
    (target / "docs" / "protocol.md").write_text("EDITADO PELO USUÁRIO")
    runner.invoke(app, ["add", "clinical", "--target", str(target)])  # reaplica
    assert (target / "docs" / "protocol.md").read_text() == "EDITADO PELO USUÁRIO"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_cli_add.py -v`
Expected: FAIL (comando `add` não existe → exit code 2 / "No such command").

- [ ] **Step 3: Implement `add` in `cli.py`**

Adicionar imports no topo:

```python
from prumo_assist.core.scaffold import discover_modules, get_module, is_applied
from prumo_assist.core.scaffold import overlay as _overlay  # (já adicionado na Task 4)
```

Adicionar o comando (após `skills_command`):

```python
@app.command("add")
def add_command(
    module: Annotated[
        str | None,
        typer.Argument(help="Módulo a ativar (ex.: clinical, ml). Omita para listar/escolher."),
    ] = None,
    target: Annotated[
        Path, typer.Option("--target", "-t", help="Projeto alvo (default: cwd).")
    ] = Path("."),
    list_only: Annotated[
        bool, typer.Option("--list", help="Só lista módulos disponíveis.")
    ] = False,
    json_mode: Annotated[bool, typer.Option("--json", help="Saída JSON.")] = False,
) -> None:
    """Ativa um módulo no projeto (overlay não-destrutivo)."""
    console = Console(json_mode=json_mode)
    target = target.resolve()
    modules = discover_modules()

    # Sem módulo + não-interativo (ou --list/--json) → listar e sair.
    if list_only or (module is None and (json_mode or not sys.stdin.isatty())):
        _emit_module_list(console, modules, target)
        return

    if module is None:
        module = _pick_module_interactive(console, modules, target)
        if module is None:
            console.warn("Nenhum módulo selecionado.")
            raise typer.Exit(code=130)

    info = get_module(module)
    if info is None:
        console.error(f"Módulo '{module}' não encontrado. Use `prumo add --list`.")
        raise typer.Exit(code=1)

    copied, skipped = _overlay(info.path, target)
    payload = {
        "module": module,
        "target": str(target),
        "files_copied": len(copied),
        "files_skipped": len(skipped),
    }
    console.success(f"Módulo '{module}' aplicado em {target}")
    if not json_mode and skipped:
        console.info(f"  [dim]{len(skipped)} arquivo(s) já existiam (preservados).[/dim]")
    console.emit(payload)


def _emit_module_list(console: Console, modules: list, target: Path) -> None:
    payload = {
        "modules": [
            {
                "name": m.name,
                "description": m.description,
                "when_to_use": m.when_to_use,
                "applied": is_applied(target, m),
            }
            for m in modules
        ]
    }
    if not console.json_mode:
        for m in modules:
            mark = " [green][aplicado][/green]" if is_applied(target, m) else ""
            console._rich.print(f"  [cyan]{m.name}[/cyan]{mark} — {m.description}")  # type: ignore[attr-defined]
    console.emit(payload)
```

> `_pick_module_interactive` é implementado na Task 10. Para a Task 8 ficar verde sem ele, adicione um stub temporário agora e substitua na Task 10:

```python
def _pick_module_interactive(console: Console, modules: list, target: Path) -> str | None:
    return None  # substituído na Task 10
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_cli_add.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/cli.py tests/unit/test_cli_add.py
git commit -m "feat(cli): comando `prumo add <módulo>` (overlay não-destrutivo)"
```

---

### Task 9: `prumo add --list` e no-arg não-interativo

**Files:**
- Test: `tests/unit/test_cli_add.py:end`

- [ ] **Step 1: Write the failing test** (append)

```python
def test_add_list_marks_applied(tmp_path: Path) -> None:
    target = tmp_path / "pj_demo"
    _init(target)
    runner.invoke(app, ["add", "clinical", "--target", str(target)])
    res = runner.invoke(app, ["add", "--list", "--target", str(target), "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.stdout)
    by = {m["name"]: m for m in payload["modules"]}
    assert by["clinical"]["applied"] is True
    assert by["ml"]["applied"] is False
    assert by["ml"]["description"]


def test_add_no_arg_non_tty_lists(tmp_path: Path) -> None:
    target = tmp_path / "pj_demo"
    _init(target)
    # CliRunner não é TTY → no-arg deve listar, não travar em prompt.
    res = runner.invoke(app, ["add", "--target", str(target), "--json"])
    assert res.exit_code == 0, res.output
    assert "modules" in json.loads(res.stdout)
```

- [ ] **Step 2: Run test to verify behavior**

Run: `uv run pytest tests/unit/test_cli_add.py -k "list or non_tty" -v`
Expected: PASS já (a lógica da Task 8 cobre `--list` e no-arg não-TTY). Se falhar, ajustar `_emit_module_list`.

- [ ] **Step 3: (se necessário) ajustar implementação** — nenhuma mudança esperada.

- [ ] **Step 4: Run full add suite**

Run: `uv run pytest tests/unit/test_cli_add.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_cli_add.py
git commit -m "test(cli): add --list marca aplicados; no-arg não-TTY lista"
```

---

### Task 10: Seletor interativo (TTY)

**Files:**
- Modify: `src/prumo_assist/cli.py` (`_pick_module_interactive`)
- Test: `tests/unit/test_cli_add.py:end`

- [ ] **Step 1: Write the failing test** (append)

```python
def test_add_interactive_picks_by_number(tmp_path: Path, monkeypatch) -> None:
    import prumo_assist.cli as climod

    monkeypatch.setattr(climod.sys.stdin, "isatty", lambda: True)
    target = tmp_path / "pj_demo"
    _init(target)
    # módulos ordenados: clinical(1), ml(2). Input "2" → ml.
    res = runner.invoke(app, ["add", "--target", str(target)], input="2\n")
    assert res.exit_code == 0, res.output
    assert (target / ".claude" / "rules" / "ml_stack.md").is_file()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_cli_add.py -k interactive -v`
Expected: FAIL (stub retorna `None` → exit 130).

- [ ] **Step 3: Replace the stub in `cli.py`**

```python
def _pick_module_interactive(console: Console, modules: list, target: Path) -> str | None:
    if not modules:
        console.warn("Nenhum módulo disponível.")
        return None
    console._rich.print("[bold]Módulos disponíveis:[/bold]")  # type: ignore[attr-defined]
    for i, m in enumerate(modules, 1):
        mark = " [green][aplicado][/green]" if is_applied(target, m) else ""
        console._rich.print(  # type: ignore[attr-defined]
            f"  [cyan]{i})[/cyan] {m.name}{mark} — {m.description}"
        )
    raw = typer.prompt("Número do módulo (vazio para cancelar)", default="")
    raw = raw.strip()
    if not raw:
        return None
    try:
        idx = int(raw) - 1
    except ValueError:
        return None
    if 0 <= idx < len(modules):
        return modules[idx].name
    return None
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/unit/test_cli_add.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/cli.py tests/unit/test_cli_add.py
git commit -m "feat(cli): seletor interativo de módulos em `prumo add`"
```

---

## Fase 5 — Wizard de módulos no `init` + `--with`

### Task 11: `prumo init --with` e etapa de módulos no wizard

**Files:**
- Modify: `src/prumo_assist/cli.py` (`init_command`, `_wizard`)
- Test: `tests/unit/test_cli_init.py:end`

- [ ] **Step 1: Write the failing test** (append to `test_cli_init.py`)

```python
def test_init_with_modules_applies_them(tmp_path: Path) -> None:
    target = tmp_path / "pj_full"
    result = runner.invoke(
        app, ["init", str(target), "--with", "clinical,ml", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert (target / "docs" / "protocol.md").is_file()          # clinical
    assert (target / ".claude" / "rules" / "ml_stack.md").is_file()  # ml
    payload = json.loads(result.stdout)
    assert sorted(payload["modules_applied"]) == ["clinical", "ml"]


def test_init_without_modules_is_minimal(tmp_path: Path) -> None:
    target = tmp_path / "pj_min"
    result = runner.invoke(app, ["init", str(target), "--json"])
    assert result.exit_code == 0, result.output
    assert not (target / "docs" / "protocol.md").exists()
    assert not (target / ".claude" / "rules" / "ml_stack.md").exists()
    assert json.loads(result.stdout)["modules_applied"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_cli_init.py -k "with_modules or minimal" -v`
Expected: FAIL (`--with` não existe; `modules_applied` ausente).

- [ ] **Step 3: Edit `init_command`**

Adicionar a opção (junto às demais de `init_command`):

```python
    with_modules: Annotated[
        str | None,
        typer.Option(
            "--with",
            help="Módulos a ativar na criação, separados por vírgula (ex.: clinical,ml).",
        ),
    ] = None,
```

No bloco interativo, capturar do wizard; no não-interativo, parsear a flag. Após o scaffold base e a instalação de integrations, antes de montar `payload`, aplicar os módulos:

```python
    # Decide módulos a aplicar.
    if interactive:
        module_names = list(answers.get("modules", []))  # type: ignore[arg-type]
    else:
        module_names = (
            [m.strip() for m in with_modules.split(",") if m.strip()]
            if with_modules
            else []
        )

    modules_applied: list[str] = []
    for name in module_names:
        info = get_module(name)
        if info is None:
            console.warn(f"Módulo '{name}' desconhecido; ignorado.")
            continue
        _overlay(info.path, target)
        modules_applied.append(name)
```

Incluir `"modules_applied": modules_applied` no dict `payload`.

- [ ] **Step 4: Edit `_wizard`** — adicionar etapa de multi-select (após integrações)

```python
    # Módulos opcionais (à la carte, todos desmarcados).
    modules = discover_modules()
    selected_modules: list[str] = []
    if modules:
        console._rich.print("\n[bold]Módulos opcionais (Enter para nenhum):[/bold]")  # type: ignore[attr-defined]
        for i, m in enumerate(modules, 1):
            console._rich.print(f"  [cyan]{i})[/cyan] {m.name} — {m.description}")  # type: ignore[attr-defined]
        raw = typer.prompt("Quais ativar? (números separados por vírgula)", default="")
        for tok in raw.split(","):
            tok = tok.strip()
            if not tok:
                continue
            try:
                idx = int(tok) - 1
            except ValueError:
                continue
            if 0 <= idx < len(modules):
                selected_modules.append(modules[idx].name)
```

E incluir `"modules": selected_modules` no dict retornado pelo `_wizard`.

- [ ] **Step 5: Run tests + lint, commit**

Run: `uv run pytest tests/unit/test_cli_init.py -v && uv run ruff check src/prumo_assist/cli.py`
Expected: PASS.

```bash
git add src/prumo_assist/cli.py tests/unit/test_cli_init.py
git commit -m "feat(cli): init --with + etapa de módulos no wizard (à la carte)"
```

---

## Fase 6 — Finalização do núcleo (conteúdo)

### Task 12: Remover wiki-dirs; adicionar `project_guide.md`, `canvas`, `.claude/make/`

**Files:**
- Delete: `templates/pj_base/docs/{concepts,entities,findings,sources}/`
- Create: `templates/pj_base/docs/project_guide.md`
- Create: `templates/pj_base/docs/canvas/project.canvas`
- Create: `templates/pj_base/.claude/make/.gitkeep`
- Modify: `tests/unit/test_cli_init.py` (troca a asserção da Task 6 para `project_guide.md`)

- [ ] **Step 1: Remover pastas wiki (nascem on-demand)**

```bash
git rm -r templates/pj_base/docs/concepts templates/pj_base/docs/entities \
          templates/pj_base/docs/findings templates/pj_base/docs/sources
```

- [ ] **Step 2: Criar `project_guide.md`**

```markdown
<!-- templates/pj_base/docs/project_guide.md -->
# pj_<NOME>

## Objetivo
_(1–3 linhas)_

## Hipótese
_(a tese central do estudo)_

## Research Questions
- RQ1:
- RQ2:
```

- [ ] **Step 3: Criar `canvas/project.canvas` (canvas Obsidian vazio válido)**

```bash
mkdir -p templates/pj_base/docs/canvas
printf '{"nodes":[],"edges":[]}\n' > templates/pj_base/docs/canvas/project.canvas
mkdir -p templates/pj_base/.claude/make
touch templates/pj_base/.claude/make/.gitkeep
```

- [ ] **Step 4: Atualizar asserção do teste de merge (agora `project_guide.md` existe)**

Em `tests/unit/test_cli_init.py::test_init_merge_preserves_existing_files`, trocar:

```python
    assert (target / "references" / "_references.bib").is_file()
```

por:

```python
    assert (target / "docs" / "project_guide.md").is_file()
```

- [ ] **Step 5: Run tests + commit**

Run: `uv run pytest tests/unit/test_cli_init.py -v`
Expected: PASS.

```bash
git add templates/ tests/unit/test_cli_init.py
git commit -m "feat(pj_base): núcleo ganha project_guide.md + canvas + .claude/make; remove wiki-dirs"
```

---

### Task 13: `CLAUDE.md` genérico + `project_context.md` genérico + `pyproject` comentado + `Makefile` enxuto

**Files:**
- Rewrite: `templates/pj_base/CLAUDE.md`
- Rewrite: `templates/pj_base/.claude/rules/project_context.md`
- Modify: `templates/pj_base/pyproject.toml` (comentar grupos)
- Rewrite: `templates/pj_base/Makefile` (12 alvos + `-include` + help abrange `.mk`)

- [ ] **Step 1: Reescrever `CLAUDE.md`** (genérico + bloco "Início rápido")

```markdown
<!-- templates/pj_base/CLAUDE.md -->
# Persona e filosofia

Você é um **assistente de pesquisa acadêmica**. Prioridades: rigor, reprodutibilidade,
citações sempre ancoradas em fontes do acervo, escrita formal. Idioma: **pt-BR**.

## Início rápido (no Claude Code)

| Quero… | Invoque |
|---|---|
| não sei por onde começar | `/prumo-assist:start` |
| adicionar papers do Zotero ao acervo | `/prumo-assist:paper-manager` |
| extrair um PDF → resumo estruturado | `/prumo-assist:paper-extract` |
| guardar uma fonte (URL/DOI/PDF) no wiki | `/prumo-assist:wiki-ingest <fonte>` |
| perguntar ao meu acervo, com citações | `/prumo-assist:wiki-query "..."` |
| revisar / escrever um texto | `/prumo-assist:scientific-writing` · `:peer-review` · `:write-paper` |

## Dependência: plugin `prumo-assist`

Instale no Claude Code: `/plugin install prumo-assist`. Ele fornece as skills acima,
os agents e o MCP `qmd` (busca no wiki).

## Estrutura do projeto (núcleo)

```text
pj_<nome>/
├── docs/{_index.md, _log.md, project_guide.md, decisions/, canvas/}
├── references/{_index.md, _references.bib, notes/, pdfs/, templates/, views/}
└── .claude/{rules/, make/, pj_config.toml, paper_extraction.md}
```

Pastas de wiki (`concepts/`, `entities/`, `findings/`, `sources/`) nascem quando você
ingere a primeira fonte. Para mais estrutura: `prumo add <módulo>` (ex.: `clinical`, `ml`).

## Hierarquia de instruções

1. `CLAUDE.md` (este arquivo).
2. `.claude/rules/` — carregadas automaticamente (`documentation.md`, `project_context.md`, e o que os módulos adicionarem).
3. `.claude/skills/` — skills específicas do projeto (as globais vêm do plugin).

## Como operar

- **Bibliografia:** Zotero é a fonte única; Better BibTeX auto-export regrava `references/_references.bib`. Paper principal marcado `role: primary` (máx. 1).
- **Caminhos:** relativos ao projeto.
- **Evoluir o projeto:** `prumo add` (sem argumento) lista e ativa módulos.
```

- [ ] **Step 2: Reescrever `project_context.md`** (genérico)

```markdown
<!-- templates/pj_base/.claude/rules/project_context.md -->
---
paths:
  - "**/pj_*/**"
---

# Contexto do projeto

> Preencha conforme o estudo evoluir. Campos clínicos (coorte, desfecho, ética) são
> adicionados pelo módulo `clinical` (`prumo add clinical`).

## Estudo
- **Objetivo principal:**
- **Hipótese:**

## Escopo do wiki
- **Entidades principais** (datasets, ferramentas, instituições):
- **Conceitos centrais** (métodos, abordagens):
- **Decisões já tomadas** (viram ADR em `docs/decisions/`):
```

- [ ] **Step 3: Comentar os grupos do `pyproject.toml`**

No `templates/pj_base/pyproject.toml`, inserir acima de `[dependency-groups]`:

```toml
# Grupos opcionais — não instalam nada até `uv sync --group <nome>`.
# Para a stack de ML/dados, ative o módulo: `prumo add ml` (guia + regras),
# e instale: `uv sync --group tabular --group viz`.
```

(Os grupos permanecem inalterados; só ganham o comentário-cabeçalho.)

- [ ] **Step 4: Reescrever `Makefile`** (12 alvos do núcleo + `-include` + help abrangente)

Manter apenas os alvos do núcleo e ajustar `help` para varrer também os `.mk`. Remover `lint`/`format` (vão no `ml.mk`), `watch`, `compose`/`export-doc`, `extract-comments`. Conteúdo final:

```makefile
.PHONY: wiki-index wiki-search sync-pdfs sync-paper sync-pdf-paper sync-annotations extract-paper-all cite cite-styles export preview help

# === Wiki / busca (qmd) ===
wiki-index:  ## Indexa docs/ + references/ via qmd
	@qmd collection add . --name $(notdir $(CURDIR)) 2>/dev/null || true
	@qmd embed

wiki-search:  ## Busca híbrida no wiki (uso: make wiki-search Q="termo")
	@test -n "$(Q)" || (echo "Uso: make wiki-search Q=\"...\"" && exit 1)
	@qmd query "$(Q)"

# === Bibliografia (Zotero + Better BibTeX) ===
sync-pdfs:  ## Cria symlinks references/pdfs/<citekey>.pdf -> Zotero
	@prumo paper sync-pdfs

sync-paper:  ## Sync .bib -> notas + grafo passivo de citação
	@prumo paper sync
	@prumo paper graph

sync-pdf-paper: sync-pdfs sync-paper  ## Atalho: sync-pdfs + sync-paper

sync-annotations:  ## Sync annotations + child notes do Zotero
	@prumo paper sync-annotations

extract-paper-all:  ## Roda /paper-extract-all via Claude Code headless ([LIMIT=N] [STALE=1])
	@command -v claude >/dev/null || (echo "Claude Code CLI não encontrado no PATH." && exit 1)
	@claude -p "Invoque a skill paper-extract em modo batch para todos os papers elegíveis$(if $(LIMIT), (--limit $(LIMIT)),)$(if $(STALE), (--stale-only),)."

cite:  ## Fuzzy lookup de citekey (uso: make cite Q="autor titulo")
	@test -n "$(Q)" || (echo 'Uso: make cite Q="termo"' && exit 1)
	@prumo paper find "$(Q)"

# === Export bibliográfico (Pandoc + CSL) ===
cite-styles:  ## Lista estilos CSL disponíveis
	@prumo write list-styles

export:  ## Exporta uma página (uso: make export PAGE=docs/foo.md [STYLE=apa] [TO=docx])
	@test -n "$(PAGE)" || (echo 'Uso: make export PAGE=docs/<arquivo>.md [STYLE=apa] [TO=docx|typst|pdf|html]' && exit 1)
	@prumo write export "$(PAGE)" $(if $(STYLE),--style $(STYLE),) $(if $(TO),--to $(TO),)

preview:  ## Exporta para HTML e abre no browser (uso: make preview PAGE=docs/foo.md)
	@test -n "$(PAGE)" || (echo 'Uso: make preview PAGE=docs/<arquivo>.md' && exit 1)
	@out=$$(prumo write export "$(PAGE)" --to html $(if $(STYLE),--style $(STYLE),) --json | python3 -c 'import json,sys; print(json.loads(sys.stdin.read().splitlines()[-1])["output"])') && \
	    echo "Abrindo $$out" && open "$$out"

help:  ## Lista comandos disponíveis (núcleo + módulos)
	@grep -hE '^[a-zA-Z_-]+:.*##' Makefile .claude/make/*.mk 2>/dev/null | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

-include .claude/make/*.mk

.DEFAULT_GOAL := help
```

- [ ] **Step 5: Run tests + commit**

Run: `uv run pytest tests/unit/test_cli_init.py tests/unit/test_cli_add.py -v`
Expected: PASS (init cria CLAUDE.md genérico; add ml deposita ml.mk que o help passa a varrer).

```bash
git add templates/pj_base/
git commit -m "feat(pj_base): CLAUDE.md + project_context genéricos; pyproject comentado; Makefile enxuto"
```

---

### Task 14: `README.md` do núcleo

**Files:**
- Rewrite: `templates/pj_base/README.md`

- [ ] **Step 1: Reescrever `README.md`** (curto, genérico, sem ML)

```markdown
<!-- templates/pj_base/README.md -->
# pj_<NOME>

Projeto de pesquisa: bibliografia (Zotero), wiki e escrita.

## Setup

```bash
uv sync                 # ambiente Python base
/plugin install prumo-assist   # no Claude Code: skills + agents + MCP qmd
```

## Estrutura

```
pj_<nome>/
├── docs/         Wiki + project_guide.md + decisions/ + canvas/
├── references/   Acervo bibliográfico (notas, .bib, pdfs) — Zotero
└── .claude/      Rules, config, make/
```

## Evoluir o projeto

```bash
prumo add            # lista e ativa módulos (clinical, ml, ...)
prumo add clinical   # protocolo, CEP, plano estatístico
prumo add ml         # stack de ML/dados + notebook
```

## Workflow (no Claude Code)

Veja a tabela "Início rápido" em [`CLAUDE.md`](CLAUDE.md) — ou rode `/prumo-assist:start`.

## Objetivo
_(preencher em `docs/project_guide.md`)_
```

- [ ] **Step 2: Run init test (smoke) + commit**

Run: `uv run pytest tests/unit/test_cli_init.py -k structure -v`
Expected: PASS.

```bash
git add templates/pj_base/README.md
git commit -m "docs(pj_base): README genérico e curto"
```

---

## Fase 7 — Skill `start`

### Task 15: `skills/start/SKILL.md`

**Files:**
- Create: `skills/start/SKILL.md`
- Test: `tests/unit/core/test_skills.py` (carrega o registry — garantir que `start` parseia)

- [ ] **Step 1: Verificar o frontmatter exigido pelo parser**

Run: `uv run python -c "from prumo_assist.core.skills import load_skill_registry; from prumo_assist.core.paths import resolve_resource; r,w=load_skill_registry(resolve_resource('skills'), strict=False); print(sorted(r.names())); print('warnings:', w)"`
Expected: imprime as skills atuais; anote os campos do frontmatter (`name`, `description`, `prumo:` etc.) usados por uma skill existente (ex.: `skills/peer-review/SKILL.md`) para copiar o formato.

- [ ] **Step 2: Criar `skills/start/SKILL.md`** (copie o shape de frontmatter de uma skill existente; conteúdo abaixo)

```markdown
---
name: start
description: Porta de entrada do prumo-assist. Use quando o pesquisador não sabe por onde começar; lista as capacidades e roteia para a skill certa (paper-manager, paper-extract, wiki-ingest, wiki-query, write-*).
prumo:
  version: 1
  determinism: agentic
---

# prumo-assist: por onde começar

Você é o guia de entrada. Pergunte ao usuário, em 1 linha, o que ele quer fazer e
roteie para a skill adequada (não execute a tarefa você mesmo — apenas oriente/inicie):

- **Bibliografia / Zotero** → `/prumo-assist:paper-manager` (sincronizar acervo),
  `/prumo-assist:paper-extract` (PDF → resumo estruturado).
- **Conhecimento / wiki** → `/prumo-assist:wiki-ingest <fonte>` (guardar),
  `/prumo-assist:wiki-query "..."` (perguntar com citações),
  `/prumo-assist:wiki-lint` (auditar).
- **Escrita** → `/prumo-assist:scientific-writing` (passe editorial),
  `/prumo-assist:peer-review` (revisão crítica), `/prumo-assist:write-paper` (draft).

Se o projeto precisar de mais estrutura (protocolo clínico, stack de ML), informe que
isso vem de módulos: `prumo add clinical` ou `prumo add ml` no terminal.

Comece perguntando: **"O que você quer fazer agora — bibliografia, wiki ou escrita?"**
```

- [ ] **Step 3: Verificar parsing + listagem**

Run: `uv run python -c "from prumo_assist.core.skills import load_skill_registry; from prumo_assist.core.paths import resolve_resource; r,w=load_skill_registry(resolve_resource('skills'), strict=False); assert 'start' in r.names(), r.names(); print('ok start', 'warnings:', w)"`
Expected: `ok start`, sem warnings sobre `start`. Se houver warning, ajustar o frontmatter ao formato detectado no Step 1.

- [ ] **Step 4: Run skills tests**

Run: `uv run pytest tests/unit/core/test_skills.py -v && uv run prumo skills --json`
Expected: PASS; `start` aparece na lista JSON.

- [ ] **Step 5: Commit**

```bash
git add skills/start/SKILL.md
git commit -m "feat(skills): start — porta de entrada/roteador no Claude Code"
```

---

## Fase 8 — Reconciliação de docs

### Task 16: Atualizar `Research Project Structure.md` e referências a `project.md`

**Files:**
- Modify: `docs/Research Project Structure.md`
- Modify: skills `write-*` que leiam `docs/project.md` (descobrir via grep)

- [ ] **Step 1: Localizar referências a `project.md` e data-pipeline**

Run: `grep -rn "project\.md" skills/ docs/Research\ Project\ Structure.md`
Expected: lista de ocorrências. Anote quais skills `write-*` usam `docs/project.md` como input.

- [ ] **Step 2: Atualizar `docs/Research Project Structure.md`**

- Trocar `project.md` por `project_guide.md` na descrição do núcleo (mantendo a nota de que é guia, não a entrega final).
- Mover `data-pipeline`/notebooks da descrição para refletir o módulo `ml`; citar `clinical` como módulo.
- Ajustar a tabela do núcleo para: `_index.md`, `_log.md`, `project_guide.md`, `decisions/`, `canvas/`.

- [ ] **Step 3: Atualizar skills `write-*`** — onde lerem `docs/project.md`, aceitar `docs/project_guide.md` (ou ambos). Para cada arquivo achado no Step 1, trocar a referência por `docs/project_guide.md`.

- [ ] **Step 4: Verificar que nada quebrou**

Run: `uv run pytest -q && grep -rn "docs/project\.md" skills/ || echo "sem referências antigas"`
Expected: testes PASS; nenhuma referência antiga remanescente (ou só intencionais).

- [ ] **Step 5: Commit**

```bash
git add docs/Research\ Project\ Structure.md skills/
git commit -m "docs: reconcilia estrutura (project_guide.md; ml/clinical como módulos)"
```

---

## Fase 9 — Teste de integração ponta-a-ponta

### Task 17: Integração — núcleo mínimo + `add` reconstrói

**Files:**
- Test: `tests/unit/test_cli_add.py:end` (ou novo `tests/unit/test_pj_base_integration.py`)

- [ ] **Step 1: Write the integration test**

```python
# tests/unit/test_pj_base_integration.py
"""Integração: init cria núcleo mínimo; add reconstrói camadas."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from prumo_assist.cli import app

runner = CliRunner()


def test_core_is_minimal_and_modules_rebuild(tmp_path: Path) -> None:
    target = tmp_path / "pj_e2e"
    assert runner.invoke(app, ["init", str(target), "--json"]).exit_code == 0

    # Núcleo: presentes
    for rel in [
        "CLAUDE.md", "README.md", "Makefile", "pyproject.toml",
        "docs/project_guide.md", "docs/canvas/project.canvas",
        ".claude/rules/documentation.md", ".claude/rules/project_context.md",
        ".claude/make", "references/_references.bib",
    ]:
        assert (target / rel).exists(), f"faltou núcleo: {rel}"

    # Núcleo: ausentes (são módulo)
    for rel in [
        "docs/protocol.md", "docs/templates",
        ".claude/rules/ml_stack.md", ".claude/rules/coding_style.md",
        "docs/concepts", "docs/findings",
    ]:
        assert not (target / rel).exists(), f"núcleo não deveria ter: {rel}"

    # CLAUDE.md genérico (sem ML), com Início rápido
    claude = (target / "CLAUDE.md").read_text()
    assert "Início rápido" in claude
    assert "PyTorch" not in claude and "timm" not in claude

    # add reconstrói
    assert runner.invoke(app, ["add", "clinical", "-t", str(target)]).exit_code == 0
    assert runner.invoke(app, ["add", "ml", "-t", str(target)]).exit_code == 0
    assert (target / "docs" / "protocol.md").is_file()
    assert (target / ".claude" / "rules" / "ml_stack.md").is_file()
    assert (target / ".claude" / "make" / "ml.mk").is_file()
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/unit/test_pj_base_integration.py -v`
Expected: PASS.

- [ ] **Step 3: Full suite + lint + doctor smoke**

Run: `uv run pytest -q && uv run ruff check . && uv run prumo doctor --help`
Expected: tudo PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_pj_base_integration.py
git commit -m "test: integração núcleo mínimo + add reconstrói clinical/ml"
```

---

## Self-Review (preenchido)

**1. Spec coverage:**
- Núcleo genérico (D1) → Tasks 12–14. Camada clínica módulo (D2) → Task 6. Ativação wizard+add (D3) → Tasks 8–11. `project_guide.md` (D4) → Task 12. Canvas (D5) → Task 12. Só clinical+ml (D6) → Tasks 6–7. Arquivos aditivos (D7) → Tasks 6,7,13 (rules/.mk; CLAUDE.md não editado por módulo). Grupos inertes (D8) → Task 13 Step 3. Remoção on-demand (D9) → Tasks 6,12. doctor não reporta (D10) → nenhuma mudança em doctor (ok). scaffold.py (D11) → Tasks 1–4. notebook único (D12) → Task 7. Prefixo pj_ (D13) → Task 5. Wizard à la carte (D14) → Task 11. add guiado (D15) → Tasks 8–10. Cheat-sheet + start (D16) → Tasks 13,15. Makefile 17→12 → Task 13. Reconciliação docs → Task 16. Critérios de sucesso 1–6 → cobertos por Tasks 5,11,8–10,13,15,1–4,17.
- **Gap revisado:** `prumo doctor` valida `[".claude","docs","references"]` — segue válido no núcleo (todos existem). Nenhum ajuste necessário.

**2. Placeholder scan:** Sem "TBD/TODO". Os dois stubs explícitos (`_pick_module_interactive` na Task 8; asserção temporária na Task 6) têm substituição definida em Task 10 e Task 12 respectivamente — não são placeholders abertos.

**3. Type consistency:** `overlay`, `discover_modules`, `get_module`, `is_applied`, `ModuleInfo(name, description, when_to_use, anchor, path)` usados de forma idêntica em scaffold, cli e testes. `_overlay` é alias de `scaffold.overlay`. `--target/-t`, `--with`, `--list`, `modules_applied`, `files_copied/skipped` consistentes entre implementação e testes.
