---
status: implemented
verified: 2026-06-14
release: null
spec: "[[2026-06-13-researcher-pipeline-design]]"
phase: "A2 de A1–A4 (Fase A do spec)"
---

# Fase A2 — Ponte CLI da skill `formulate-picot` (protocol) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir os 3 scripts de `skills/formulate-picot/scripts/` por subcomandos `prumo protocol` (fachadas finas sobre `domains/protocol`), deletar os scripts, e atualizar a prosa de `formulate-picot` para chamar o CLI — eliminando o `from prumo_assist` frágil dessa skill.

**Architecture:** Diferente da A1 (cujas funções de domínio já existiam), os scripts de `formulate-picot` carregam **orquestração** (`init_picot`, `diff_and_adr`) e **inspeção de estado** (`detect_mode`) que hoje só vivem no script. A regra "fachadas finas" (`cli.py` faz só parsing + chamada do domínio + saída, ver `.claude/rules/code.md`) exige mover essa lógica para `domains/protocol/ops.py` como funções novas, com o CLI fino por cima. Nenhuma lógica nova é inventada — ela **migra** do script para o domínio (Princípio I; spec D1: "lógica … passa a viver em `domains/`"). `prumo protocol propagate`/`diff` já existem (migração anterior); só restam 3 scripts.

**Tech Stack:** Python 3.11+, Typer, Pydantic v2, pytest + `typer.testing.CliRunner`, uv. Reaproveita `core/cli_io.read_stdin_json` (entregue na A1).

**Escopo desta fase (parte de A1–A4):** só a trilha `protocol` (`formulate-picot`). Paper/write (A3) e o hook + release (A4) são planos seguintes. **Nenhum release nesta fase** — a versão é bumpada só no A4.

---

## File Structure

| Caminho | Ação | Responsabilidade |
|---|---|---|
| `src/prumo_assist/domains/protocol/ops.py` | Modificar | +3 funções: `detect_mode`, `init_picot_spec` (+`InitResult`), `create_picot_adr` (+`AdrResult`) |
| `src/prumo_assist/domains/protocol/cli.py` | Modificar | +3 subcomandos: `detect-mode`, `init`, `adr` |
| `src/prumo_assist/domains/protocol/api.py` | Modificar | Re-exportar as 3 funções novas + 2 result types |
| `tests/unit/protocol/test_ops.py` | Modificar | Testes de domínio das 3 funções novas |
| `tests/unit/protocol/test_cli.py` | Modificar | Testes CLI dos 3 subcomandos novos |
| `skills/formulate-picot/SKILL.md` | Modificar | 2 invocações de script → `prumo protocol …`; `allowed-tools`; Pressupostos |
| `skills/formulate-picot/references/operations-advanced.md` | Modificar | `diff_and_adr.py` → `prumo protocol adr` |
| `skills/formulate-picot/scripts/` | Deletar | 3 scripts (`detect_mode`, `init_picot`, `diff_and_adr`) |

Mapa script → subcomando:

| Script (formulate-picot) | Subcomando | Lógica migra para |
|---|---|---|
| `detect_mode.py` | `prumo protocol detect-mode` | `ops.detect_mode(pj_path) -> str` |
| `init_picot.py` | `prumo protocol init` (PicotSpec JSON via stdin) | `ops.init_picot_spec(pj_path, *, spec, motivation, date) -> InitResult` |
| `diff_and_adr.py` | `prumo protocol adr` (`--motivation --slug --date`) | `ops.create_picot_adr(pj_path, *, motivation, slug, date) -> AdrResult` |
| (já existia) | `prumo protocol propagate` / `prumo protocol diff` | `ops.propagate` / `ops.diff_against_last_adr` |

**Contrato de I/O (spec Fase A):** corpo/payload-schema via stdin JSON (heredoc, nunca escapado), metadados via flags, relatório via `--json`. `detect-mode` imprime uma palavra crua (consumida pela skill).

---

### Task 1: `prumo protocol detect-mode` (TDD)

**Files:**
- Modify: `src/prumo_assist/domains/protocol/ops.py`
- Modify: `src/prumo_assist/domains/protocol/cli.py`
- Test: `tests/unit/protocol/test_ops.py`, `tests/unit/protocol/test_cli.py`

Contexto: substitui `detect_mode.py`. Inspeção determinística do estado do projeto → uma das 4 palavras (`init`/`formalize`/`propagate`/`diff`). A lógica (hoje no script) migra para `ops.detect_mode`. Funções já importadas em `ops.py`: `picot_path`, `find_last_picot_adr`. Regra de decisão (faithful ao script):
- sem `.claude/picot.toml` e `docs/protocol.md` vazio/ausente → `init`
- sem `.claude/picot.toml` mas `docs/protocol.md` com prosa → `formalize`
- com `picot.toml` mas sem ADR baseline → `propagate`
- com `picot.toml` e ADR baseline → `diff`

- [ ] **Step 1: Escrever os testes de domínio que falham**

Append to `tests/unit/protocol/test_ops.py`:

```python
def test_detect_mode_init_when_nothing(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    from prumo_assist.domains.protocol.ops import detect_mode

    assert detect_mode(pj) == "init"


def test_detect_mode_formalize_when_protocol_prose(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    (pj / "docs" / "protocol.md").write_text("# Protocolo\n\nprosa humana.\n", encoding="utf-8")
    from prumo_assist.domains.protocol.ops import detect_mode

    assert detect_mode(pj) == "formalize"


def test_detect_mode_propagate_when_picot_no_adr(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    write_picot(pj, _spec())
    from prumo_assist.domains.protocol.ops import detect_mode

    assert detect_mode(pj) == "propagate"


def test_detect_mode_diff_when_baseline_adr(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs" / "decisions").mkdir(parents=True)
    write_picot(pj, _spec())
    (pj / "docs" / "decisions" / "adr-0001-picot-v1-versao-inicial.md").write_text(
        "# adr\n", encoding="utf-8"
    )
    from prumo_assist.domains.protocol.ops import detect_mode

    assert detect_mode(pj) == "diff"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/protocol/test_ops.py -q -k detect_mode`
Expected: FAIL — `ImportError: cannot import name 'detect_mode'`.

- [ ] **Step 3: Implementar `ops.detect_mode`**

In `src/prumo_assist/domains/protocol/ops.py`, the existing import from `picot_io` already includes `picot_path`; the import from `adr` includes `find_last_picot_adr`. Add the function (after `diff_against_last_adr`):

```python
def detect_mode(pj_path: Path) -> str:
    """Detecta o modo da skill ``formulate-picot`` pelo estado do projeto.

    Retorna ``init`` | ``formalize`` | ``propagate`` | ``diff``.
    """
    toml = picot_path(pj_path)
    last_adr = find_last_picot_adr(pj_path)
    protocol_md = pj_path / "docs" / "protocol.md"
    if not toml.exists():
        has_prose = protocol_md.exists() and protocol_md.read_text(errors="ignore").strip() != ""
        return "formalize" if has_prose else "init"
    if last_adr is None:
        return "propagate"
    return "diff"
```

- [ ] **Step 4: Rodar e ver passar (domínio)**

Run: `uv run pytest tests/unit/protocol/test_ops.py -q -k detect_mode`
Expected: `4 passed`.

- [ ] **Step 5: Escrever o teste CLI que falha**

Append to `tests/unit/protocol/test_cli.py`:

```python
def test_protocol_detect_mode_init(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    result = runner.invoke(app, ["protocol", "detect-mode", str(pj)])
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "init"
```

- [ ] **Step 6: Rodar e ver falhar (CLI)**

Run: `uv run pytest tests/unit/protocol/test_cli.py -q -k detect_mode`
Expected: FAIL — `No such command 'detect-mode'`.

- [ ] **Step 7: Implementar o subcomando**

In `src/prumo_assist/domains/protocol/cli.py`, append (no new imports needed — `ops`, `cli_run`, `Path`, `Annotated`, `typer` are already imported):

```python
@protocol_app.command("detect-mode")
def detect_mode_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Imprime o modo da skill (init|formalize|propagate|diff) pelo estado do projeto."""
    with cli_run(json_mode=json_mode) as console:
        console.emit(ops.detect_mode(path.resolve()))
```

- [ ] **Step 8: Rodar e ver passar (CLI)**

Run: `uv run pytest tests/unit/protocol/test_cli.py -q -k detect_mode`
Expected: `1 passed`.

- [ ] **Step 9: Gates + commit**

Run: `uv run ruff check src/prumo_assist/domains/protocol/ tests/unit/protocol/ && uv run ruff format src/prumo_assist/domains/protocol/ tests/unit/protocol/ && uv run mypy`
Expected: tudo verde.

```bash
git add src/prumo_assist/domains/protocol/ops.py src/prumo_assist/domains/protocol/cli.py tests/unit/protocol/test_ops.py tests/unit/protocol/test_cli.py
git commit -m "feat(protocol): prumo protocol detect-mode (substitui detect_mode.py)"
```

---

### Task 2: `prumo protocol init` (TDD)

**Files:**
- Modify: `src/prumo_assist/domains/protocol/ops.py`
- Modify: `src/prumo_assist/domains/protocol/cli.py`
- Test: `tests/unit/protocol/test_ops.py`, `tests/unit/protocol/test_cli.py`

Contexto: substitui `init_picot.py`. Orquestração: `write_picot` + `propagate` + `next_adr_number` + `compose_adr` (diff vazio, sem supersedes) + grava `adr-{n:04d}-picot-v1-versao-inicial.md`. Migra para `ops.init_picot_spec`. O CLI lê o `PicotSpec` JSON do stdin (corpo via heredoc), separa `hypothesis`, constrói `PicotSpec`/`Hypothesis` (pode levantar `pydantic.ValidationError`).

- [ ] **Step 1: Escrever o teste de domínio que falha**

Append to `tests/unit/protocol/test_ops.py`:

```python
def test_init_picot_spec_writes_toml_and_adr(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    from prumo_assist.domains.protocol.ops import InitResult, init_picot_spec
    from prumo_assist.domains.protocol.picot_io import picot_path

    result = init_picot_spec(pj, spec=_spec(), motivation="inicial", date="2026-06-14")
    assert isinstance(result, InitResult)
    assert picot_path(pj).exists()
    assert result.adr_path.exists()
    assert "picot-v1-versao-inicial" in result.adr_path.name
    assert result.report.hash8 != ""
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/protocol/test_ops.py -q -k init_picot_spec`
Expected: FAIL — `ImportError: cannot import name 'init_picot_spec'`.

- [ ] **Step 3: Implementar `ops.init_picot_spec`**

In `ops.py`, extend the `picot_io` import to add `write_picot`, and the `adr` import to add `compose_adr` and `next_adr_number`:

```python
from prumo_assist.domains.protocol.adr import (
    compose_adr,
    extract_picot_snapshot,
    find_last_picot_adr,
    next_adr_number,
)
from prumo_assist.domains.protocol.picot_io import (
    picot_hash,
    picot_path,
    read_picot,
    write_picot,
)
```

Add the result dataclass + function (after `detect_mode`):

```python
@dataclass(frozen=True)
class InitResult:
    """Resultado de ``init_picot_spec``: relatório de propagação + caminho do ADR-0001."""

    report: PropagateReport
    adr_path: Path


def init_picot_spec(
    pj_path: Path, *, spec: PicotSpec, motivation: str, date: str
) -> InitResult:
    """Escreve o ``PicotSpec`` inicial, propaga os blocos e cria o ADR-0001."""
    write_picot(pj_path, spec)
    report = propagate(pj_path)
    n = next_adr_number(pj_path)
    body = compose_adr(
        adr_number=n,
        spec=spec,
        diff=PicotDiff(changes=[]),
        motivation=motivation,
        supersedes_path=None,
        date=date,
    )
    adr_path = pj_path / "docs" / "decisions" / f"adr-{n:04d}-picot-v1-versao-inicial.md"
    adr_path.parent.mkdir(parents=True, exist_ok=True)
    adr_path.write_text(body, encoding="utf-8")
    return InitResult(report=report, adr_path=adr_path)
```

(`PicotDiff` já está importado em `ops.py`.)

- [ ] **Step 4: Rodar e ver passar (domínio)**

Run: `uv run pytest tests/unit/protocol/test_ops.py -q -k init_picot_spec`
Expected: `1 passed`.

- [ ] **Step 5: Escrever o teste CLI que falha**

Append to `tests/unit/protocol/test_cli.py`:

```python
def test_protocol_init_writes_and_emits(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    payload = {
        "type": "clinical",
        "created_at": "2026-06-14",
        "last_updated": "2026-06-14",
        "version": 1,
        "population": "DS_A",
        "intervention": "IntervencaoX",
        "comparison": "best baseline",
        "outcome": "AUROC ≥ 0.85",
        "time": "retrospectivo",
        "hypothesis": {"statement": "x", "rationale": "y", "metrics": ["AUROC"]},
    }
    result = runner.invoke(
        app,
        ["protocol", "init", "--date", "2026-06-14", "--path", str(pj), "--json"],
        input=json.dumps(payload),
    )
    assert result.exit_code == 0, result.output
    out = _last_json(result.stdout)
    assert Path(str(out["adr_path"])).exists()


def test_protocol_init_invalid_payload_fails(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    result = runner.invoke(
        app, ["protocol", "init", "--date", "2026-06-14", "--path", str(pj)], input="{}"
    )
    assert result.exit_code == 1
```

- [ ] **Step 6: Rodar e ver falhar (CLI)**

Run: `uv run pytest tests/unit/protocol/test_cli.py -q -k "protocol_init"`
Expected: FAIL — `No such command 'init'`.

- [ ] **Step 7: Implementar o subcomando**

In `cli.py`, add these imports at the top (alongside the existing ones):

```python
from pydantic import ValidationError

from prumo_assist import PrumoError
from prumo_assist.core.cli_io import read_stdin_json
from prumo_assist.domains.protocol.schemas.v1 import Hypothesis, PicotSpec
```

Append the command:

```python
@protocol_app.command("init")
def init_command(
    date: Annotated[str, typer.Option("--date", help="Data ISO YYYY-MM-DD.")],
    motivation: Annotated[
        str, typer.Option("--motivation", help="Motivação do ADR-0001.")
    ] = "versão inicial — primeira formalização",
    path: Annotated[Path, typer.Option("--path", help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Cria o PicotSpec inicial (JSON via stdin), propaga blocos e grava o ADR-0001."""
    with cli_run(
        json_mode=json_mode, catches=(ValueError, FileNotFoundError, ValidationError)
    ) as console:
        payload = read_stdin_json()
        hypothesis_data = payload.pop("hypothesis", None)
        if not isinstance(hypothesis_data, dict):
            raise PrumoError("payload PicotSpec exige a chave 'hypothesis' (objeto).")
        spec = PicotSpec(**payload, hypothesis=Hypothesis(**hypothesis_data))
        result = ops.init_picot_spec(
            path.resolve(), spec=spec, motivation=motivation, date=date
        )
        console.success(f"PicotSpec v{spec.version} inicializado; ADR em {result.adr_path}")
        console.emit({"adr_path": str(result.adr_path), "propagate": asdict(result.report)})
```

(`asdict` já está importado em `cli.py`.)

- [ ] **Step 8: Rodar e ver passar (CLI)**

Run: `uv run pytest tests/unit/protocol/test_cli.py -q -k "protocol_init"`
Expected: `2 passed`.

- [ ] **Step 9: Gates + commit**

Run: `uv run ruff check src/prumo_assist/domains/protocol/ tests/unit/protocol/ && uv run ruff format src/prumo_assist/domains/protocol/ tests/unit/protocol/ && uv run mypy`
Expected: tudo verde.

```bash
git add src/prumo_assist/domains/protocol/ops.py src/prumo_assist/domains/protocol/cli.py tests/unit/protocol/test_ops.py tests/unit/protocol/test_cli.py
git commit -m "feat(protocol): prumo protocol init (substitui init_picot.py; PicotSpec via stdin)"
```

---

### Task 3: `prumo protocol adr` (TDD)

**Files:**
- Modify: `src/prumo_assist/domains/protocol/ops.py`
- Modify: `src/prumo_assist/domains/protocol/cli.py`
- Test: `tests/unit/protocol/test_ops.py`, `tests/unit/protocol/test_cli.py`

Contexto: substitui `diff_and_adr.py`. Pressuposto: a versão em `.claude/picot.toml` **já foi bumpada** pela skill; este comando lê o estado atual, diffa contra o último ADR, grava `adr-{n:04d}-picot-v{version}-{slug}.md` e propaga. Migra para `ops.create_picot_adr`. Nota mypy-strict: `diff_against_last_adr` retorna `PicotDiff | None` mas `compose_adr` exige `PicotDiff`; `read_picot` já garante que o `picot.toml` existe (senão levanta `FileNotFoundError`), então o `None` não ocorre — narrar com `or PicotDiff(changes=[])`.

- [ ] **Step 1: Escrever o teste de domínio que falha**

Append to `tests/unit/protocol/test_ops.py`:

```python
def test_create_picot_adr_writes_and_propagates(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    (pj / "docs" / "protocol.md").write_text("# Protocolo\n", encoding="utf-8")
    (pj / "docs" / "project_guide.md").write_text("---\ntitle: x\n---\n\n# P\n", encoding="utf-8")
    write_picot(pj, _spec(version=2, population="DS_A + DS_BB"))
    from prumo_assist.domains.protocol.ops import AdrResult, create_picot_adr

    result = create_picot_adr(pj, motivation="novo dataset", slug="novo-dataset", date="2026-06-14")
    assert isinstance(result, AdrResult)
    assert result.adr_path.exists()
    assert "picot-v2-novo-dataset" in result.adr_path.name
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/protocol/test_ops.py -q -k create_picot_adr`
Expected: FAIL — `ImportError: cannot import name 'create_picot_adr'`.

- [ ] **Step 3: Implementar `ops.create_picot_adr`**

In `ops.py`, append (after `init_picot_spec`):

```python
@dataclass(frozen=True)
class AdrResult:
    """Resultado de ``create_picot_adr``: relatório de propagação + caminho do ADR."""

    report: PropagateReport
    adr_path: Path


def create_picot_adr(
    pj_path: Path, *, motivation: str, slug: str, date: str
) -> AdrResult:
    """Grava o ADR-N para a versão atual do ``picot.toml`` (após bump) e propaga."""
    spec = read_picot(pj_path)
    diff = diff_against_last_adr(pj_path) or PicotDiff(changes=[])
    last_adr = find_last_picot_adr(pj_path)
    n = next_adr_number(pj_path)
    body = compose_adr(
        adr_number=n,
        spec=spec,
        diff=diff,
        motivation=motivation,
        supersedes_path=last_adr,
        date=date,
    )
    adr_path = pj_path / "docs" / "decisions" / f"adr-{n:04d}-picot-v{spec.version}-{slug}.md"
    adr_path.parent.mkdir(parents=True, exist_ok=True)
    adr_path.write_text(body, encoding="utf-8")
    report = propagate(pj_path)
    return AdrResult(report=report, adr_path=adr_path)
```

- [ ] **Step 4: Rodar e ver passar (domínio)**

Run: `uv run pytest tests/unit/protocol/test_ops.py -q -k create_picot_adr`
Expected: `1 passed`.

- [ ] **Step 5: Escrever o teste CLI que falha**

Append to `tests/unit/protocol/test_cli.py`:

```python
def test_protocol_adr_writes(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    write_picot(pj, _spec())
    result = runner.invoke(
        app,
        ["protocol", "adr", "--motivation", "novo dataset", "--slug", "novo-dataset",
         "--date", "2026-06-14", "--path", str(pj), "--json"],
    )
    assert result.exit_code == 0, result.output
    out = _last_json(result.stdout)
    assert Path(str(out["adr_path"])).exists()


def test_protocol_adr_missing_picot_fails(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)  # sem picot.toml
    result = runner.invoke(
        app,
        ["protocol", "adr", "--motivation", "x", "--slug", "y",
         "--date", "2026-06-14", "--path", str(pj)],
    )
    assert result.exit_code == 1
```

- [ ] **Step 6: Rodar e ver falhar (CLI)**

Run: `uv run pytest tests/unit/protocol/test_cli.py -q -k "protocol_adr"`
Expected: FAIL — `No such command 'adr'`.

- [ ] **Step 7: Implementar o subcomando**

In `cli.py`, append (no new imports — uses `ops`, `cli_run`, `asdict`, `Path`, `Annotated`, `typer`):

```python
@protocol_app.command("adr")
def adr_command(
    motivation: Annotated[str, typer.Option("--motivation", help="Motivação do ADR.")],
    slug: Annotated[str, typer.Option("--slug", help="Slug kebab-case curto.")],
    date: Annotated[str, typer.Option("--date", help="Data ISO YYYY-MM-DD.")],
    path: Annotated[Path, typer.Option("--path", help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Registra o ADR-N para a versão atual do picot.toml (após bump) e propaga blocos."""
    with cli_run(json_mode=json_mode, catches=(ValueError, FileNotFoundError)) as console:
        result = ops.create_picot_adr(
            path.resolve(), motivation=motivation, slug=slug, date=date
        )
        console.success(f"ADR criado: {result.adr_path}")
        console.emit({"adr_path": str(result.adr_path), "propagate": asdict(result.report)})
```

- [ ] **Step 8: Rodar e ver passar (CLI)**

Run: `uv run pytest tests/unit/protocol/test_cli.py -q -k "protocol_adr"`
Expected: `2 passed`.

- [ ] **Step 9: Gates + commit**

Run: `uv run ruff check src/prumo_assist/domains/protocol/ tests/unit/protocol/ && uv run ruff format src/prumo_assist/domains/protocol/ tests/unit/protocol/ && uv run mypy`
Expected: tudo verde.

```bash
git add src/prumo_assist/domains/protocol/ops.py src/prumo_assist/domains/protocol/cli.py tests/unit/protocol/test_ops.py tests/unit/protocol/test_cli.py
git commit -m "feat(protocol): prumo protocol adr (substitui diff_and_adr.py)"
```

---

### Task 4: Re-export em `protocol/api.py`

**Files:**
- Modify: `src/prumo_assist/domains/protocol/api.py`

Contexto: re-export puro (sem wrapper) das 3 funções novas + 2 result types, em ordem alfabética no `__all__`, para `from prumo_assist.domains.protocol import api; api.<fn>(...)` em notebooks. As funções low-level (`compose_adr`, `next_adr_number`, `find_last_picot_adr`, `PicotDiff`) **não** entram na api — passaram a ser detalhe interno de `ops` (não mais consumidas por scripts).

- [ ] **Step 1: Adicionar os re-exports**

In `src/prumo_assist/domains/protocol/api.py`, extend the `ops` import and `__all__`:

```python
from prumo_assist.domains.protocol.ops import (
    AdrResult,
    InitResult,
    PropagateReport,
    create_picot_adr,
    detect_mode,
    diff_against_last_adr,
    init_picot_spec,
    propagate,
)
```

Add `"AdrResult"`, `"InitResult"`, `"create_picot_adr"`, `"detect_mode"`, `"init_picot_spec"` to the existing `__all__`, keeping it alphabetically sorted (capitals first, then lowercase — matching the existing order):

```python
__all__ = [
    "AdrResult",
    "Hypothesis",
    "InitResult",
    "PicotSpec",
    "PropagateReport",
    "create_picot_adr",
    "detect_mode",
    "diff_against_last_adr",
    "init_picot_spec",
    "picot_hash",
    "picot_path",
    "propagate",
    "read_picot",
    "write_picot",
]
```

- [ ] **Step 2: Verificar import e mypy**

Run: `uv run python -c "from prumo_assist.domains.protocol import api; print(sorted(api.__all__))" && uv run mypy`
Expected: lista inclui `detect_mode`, `init_picot_spec`, `create_picot_adr`, `InitResult`, `AdrResult`; mypy verde.

- [ ] **Step 3: Commit**

```bash
git add src/prumo_assist/domains/protocol/api.py
git commit -m "feat(protocol): re-exporta detect_mode/init/adr na api pública"
```

---

### Task 5: Atualizar a prosa de `formulate-picot`

**Files:**
- Modify: `skills/formulate-picot/SKILL.md`
- Modify: `skills/formulate-picot/references/operations-advanced.md`

Contexto: trocar as 3 invocações de script por `prumo protocol …`. NÃO alterar a lógica do fluxo dos modos (init/formalize/propagate/diff), só os comandos. `allowed-tools` já tem `Bash(prumo protocol *)`; remover `Bash(uv run python *)` e `Bash(python3 *)` (mortos após a migração), manter `Bash(cat *)`.

- [ ] **Step 1: `allowed-tools` (SKILL.md, linha 9)**

Current:
```
allowed-tools: Read Write Edit Glob Grep Bash(uv run python *) Bash(python3 *) Bash(cat *) Bash(prumo protocol *)
```
Replace with:
```
allowed-tools: Read Write Edit Glob Grep Bash(cat *) Bash(prumo protocol *)
```

- [ ] **Step 2: § Auto-detect (SKILL.md)**

Replace:
```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/detect_mode.py
```
with:
```bash
prumo protocol detect-mode
```

- [ ] **Step 3: § Operação 1: init, passo 7 (SKILL.md)**

Replace:
```bash
cat <<'JSON' | uv run python ${CLAUDE_SKILL_DIR}/scripts/init_picot.py --date "<hoje ISO>"
<PicotSpec JSON aprovado>
JSON
```
with:
```bash
cat <<'JSON' | prumo protocol init --date "<hoje ISO>" --json
<PicotSpec JSON aprovado>
JSON
```

- [ ] **Step 4: § Operação 4 — diff, Passo 5 (references/operations-advanced.md)**

Replace:
```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/diff_and_adr.py \
    --motivation "<motivação capturada>" \
    --slug "<slug>" \
    --date "<hoje ISO>"
```
with:
```bash
prumo protocol adr \
    --motivation "<motivação capturada>" \
    --slug "<slug>" \
    --date "<hoje ISO>" --json
```

- [ ] **Step 5: § Pressupostos (SKILL.md) — reword + add CLI bullet**

Replace:
```
- A parte determinística (read/write TOML, render, diff, ADR) vive em `prumo_assist.domains.protocol`. A skill **só** cuida do agêntico (Socrático e Formalize).
```
with:
```
- A parte determinística (read/write TOML, render, diff, ADR) é exposta via `prumo protocol *` (detect-mode/init/adr/propagate/diff). A skill **só** cuida do agêntico (Socrático e Formalize).
- O CLI `prumo` precisa estar no PATH (rode `prumo doctor`; se ausente:
  `uv tool install git+https://github.com/raphaelfh/prumo-assist`).
```

- [ ] **Step 6: Verificar que não sobrou referência a scripts/ ou import frágil**

Run: `grep -rnE "CLAUDE_SKILL_DIR|scripts/|from prumo_assist|python -c|uv run python|python3" skills/formulate-picot/ || echo "limpo"`
Expected: `limpo`.

- [ ] **Step 7: Commit**

```bash
git add skills/formulate-picot/SKILL.md skills/formulate-picot/references/operations-advanced.md
git commit -m "refactor(formulate-picot): chama prumo protocol em vez de scripts/ (ponte CLI)"
```

---

### Task 6: Deletar `skills/formulate-picot/scripts/` + gates finais

**Files:**
- Delete: `skills/formulate-picot/scripts/` (3 arquivos)

Contexto: a lógica migrou para `prumo protocol`. Esta era a última skill com `scripts/` — depois desta fase, `skills/*/scripts/` não existe mais (critério de sucesso #1 do spec, parcial: A2 fecha a parte de scripts; os snippets `from prumo_assist` de paper/write ficam para A3).

- [ ] **Step 1: Remover os scripts**

```bash
git rm skills/formulate-picot/scripts/detect_mode.py \
       skills/formulate-picot/scripts/init_picot.py \
       skills/formulate-picot/scripts/diff_and_adr.py
```

- [ ] **Step 2: Confirmar que não há mais `scripts/` em nenhum skill**

Run: `ls -d skills/*/scripts/ 2>/dev/null || echo "nenhum scripts/ restante"`
Expected: `nenhum scripts/ restante` (A1 já removeu o de active-learning; este remove o de formulate-picot).

- [ ] **Step 3: Suíte completa + gates**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run python .github/scripts/gen_indexes.py --check`
Expected: tudo verde.

- [ ] **Step 4: Commit**

```bash
git add -A skills/formulate-picot/
git commit -m "chore(formulate-picot): remove scripts/ (lógica migrada para prumo protocol)"
```

---

## Self-Review

**Cobertura do escopo A2:** os 3 scripts de formulate-picot → 3 subcomandos `prumo protocol` (`detect-mode`, `init`, `adr`) ✓; lógica migrada para `ops` (não inlinada no CLI — fachadas finas) ✓; scripts deletados ✓; prosa da skill atualizada (SKILL.md + references) ✓; `allowed-tools` limpo + Pressuposto de CLI ✓; re-export em api.py ✓. `propagate`/`diff` já existiam (migração anterior) — fora do escopo desta fase. Fora de A2: paper/write (A3), hook + release (A4).

**Placeholders:** nenhum — todo passo tem código/comando completo e saída esperada.

**Consistência de tipos:** `detect_mode(pj_path)->str`; `init_picot_spec(pj_path, *, spec: PicotSpec, motivation: str, date: str)->InitResult`; `create_picot_adr(pj_path, *, motivation, slug, date)->AdrResult`; `InitResult`/`AdrResult` ambos `(report: PropagateReport, adr_path: Path)`. As funções de domínio chamadas (`write_picot`, `propagate`, `next_adr_number`, `compose_adr`, `read_picot`, `diff_against_last_adr`, `find_last_picot_adr`, `PicotDiff`) batem com as assinaturas reais (verificadas em `ops.py`/`adr.py`/`picot_io.py`/`diff.py`). `read_stdin_json` reaproveitado da A1. Narrowing mypy do `PicotDiff | None` tratado com `or PicotDiff(changes=[])`.

**Grafo de imports:** as 3 funções novas vivem em `ops.py`, que já importa de `adr`/`diff`/`picot_io`/`render` (sentido único — sem ciclo). `cli.py` ganha imports de `schemas.v1` (PicotSpec/Hypothesis), `cli_io` (read_stdin_json), `pydantic` (ValidationError) e `PrumoError` — todos sem ciclo.

**Nota de design honrada:** nenhuma lógica de domínio inventada — só **migra** dos scripts para `ops` + fachadas + re-export. Coerente com a A1 e com a fronteira determinístico/agêntico da Seção 0.5 do spec (detect-mode/init/adr são operações exatas/auditáveis; o julgamento Socrático/Formalize fica na skill).
