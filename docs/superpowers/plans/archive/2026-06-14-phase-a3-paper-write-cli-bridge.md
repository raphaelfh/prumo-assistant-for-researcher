---
status: implemented
verified: 2026-06-14
release: null
spec: "[[2026-06-13-researcher-pipeline-design]]"
phase: "A3 de A1–A4 (Fase A do spec)"
---

# Fase A3 — Ponte CLI das skills `paper-extract` e `write-paper` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir os 5 snippets inline `uv run python -c "from prumo_assist…"` das skills `paper-extract` (2) e `write-paper` (3) por subcomandos `prumo paper *` / `prumo write *` (fachadas finas), eliminando o `from prumo_assist` frágil da prosa dessas duas skills.

**Architecture:** Como na A2, `cli.py` faz só parsing → chamada de domínio → saída (regra "fachadas finas"). Diferenças por skill: **write-paper** já tem todas as 3 funções em `domains/write/api.py` (`read_inputs`, `resolve_template`, `write_output`) — só faltam fachadas + um pequeno compositor `prep`. **paper-extract** precisa: (a) re-exportar `apply_extraction` (hoje importado direto de `callout.py`); (b) absorver o snippet `load_project_config` num comando *prep* (spec Fase A: "Comandos *prep* compõem validação + leitura de contexto num só… não há `prumo config` standalone — YAGNI"), migrando os aborts de pré-requisito (hoje prosa agêntica + `Bash(test/readlink)`) para validação determinística. Nenhuma lógica de julgamento entra no CLI. Reaproveita `core/cli_io` (stdin) da A1.

**Tech Stack:** Python 3.11+, Typer, Pydantic v2, pytest + `typer.testing.CliRunner`, uv.

**Escopo desta fase (parte de A1–A4):** só a trilha `paper`/`write` (`paper-extract` + `write-paper`). O hook de enforcement + release ficam para A4. **Nenhum release nesta fase.** Estas skills **não têm `scripts/`** (aqueles eram active-learning/formulate-picot, já removidos em A1/A2) — A3 só migra snippets inline; não há "deletar scripts".

---

## File Structure

| Caminho | Ação | Responsabilidade |
|---|---|---|
| `src/prumo_assist/domains/paper/prep.py` | Criar | `extract_prep(pj_path, citekey) -> ExtractPrep` (valida pré-reqs + lê config) |
| `src/prumo_assist/domains/paper/cli.py` | Modificar | +2 subcomandos: `extract-prep`, `extract` |
| `src/prumo_assist/domains/paper/api.py` | Modificar | Re-exportar `apply_extraction`, `extract_prep`, `ExtractPrep` |
| `src/prumo_assist/domains/write/compose.py` | Modificar | +`prep(pj_path, *, kind) -> WritePrep` (compõe read_inputs + resolve_template) |
| `src/prumo_assist/domains/write/cli.py` | Modificar | +2 subcomandos: `prep`, `draft` |
| `src/prumo_assist/domains/write/api.py` | Modificar | Re-exportar `prep`, `WritePrep` |
| `tests/unit/paper/test_prep.py` | Criar | testes de domínio de `extract_prep` |
| `tests/unit/paper/test_cli.py` | Modificar | testes CLI de `extract-prep`/`extract` |
| `tests/unit/write/test_compose_prep.py` | Criar | testes de domínio de `prep` |
| `tests/unit/write/test_cli.py` | Criar | testes CLI de `prep`/`draft` |
| `skills/paper-extract/SKILL.md` | Modificar | 2 snippets → `prumo paper …`; allowed-tools; Pressupostos |
| `skills/write-paper/SKILL.md` | Modificar | 3 snippets → `prumo write …`; allowed-tools |

Mapa snippet → subcomando:

| Snippet inline | Subcomando | Função de domínio |
|---|---|---|
| `load_project_config` (paper-extract §2) + aborts de pré-req (§1) | `prumo paper extract-prep <citekey>` | `paper.prep.extract_prep` (nova) |
| `apply_extraction` (paper-extract §5) | `prumo paper extract <citekey> --model --date` (content via stdin) | `paper.callout.apply_extraction` (existe; +re-export) |
| `read_inputs` + `resolve_template` (write-paper §1,§2) | `prumo write prep --kind` | `write.compose.prep` (nova; compõe existentes) |
| `write_output` (write-paper §5) | `prumo write draft …` (content via stdin) | `write.compose.write_output` (existe) |

**Contrato de I/O (spec Fase A):** corpo/draft markdown via stdin (heredoc); payload-schema (dict de extração) via stdin JSON; metadados via flags; relatório via `--json`.

---

### Task 1: `prumo paper extract-prep` (TDD)

**Files:**
- Create: `src/prumo_assist/domains/paper/prep.py`
- Modify: `src/prumo_assist/domains/paper/cli.py`, `src/prumo_assist/domains/paper/api.py`
- Test: `tests/unit/paper/test_prep.py`, `tests/unit/paper/test_cli.py`

Contexto: substitui o snippet `load_project_config` (§2) e absorve os aborts de pré-requisito (§1, hoje agênticos com `Bash(test/readlink)`). `load_project_config(pj_path) -> dict` vive em `core/config.py` e valida `paper_extract.language` (levanta `ConfigError`, subclasse de `PrumoError`). Pré-reqs validados (todos `.exists()`; symlink quebrado → `exists()==False`): `.claude/paper_extraction.md`, `references/_references.bib`, `references/pdfs/<citekey>.pdf`, `references/notes/<citekey>/_meta.md`.

- [ ] **Step 1: Escrever os testes de domínio que falham** — Create `tests/unit/paper/test_prep.py`:

```python
"""Testa `paper.prep.extract_prep` (validação de pré-req + leitura de config)."""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist import ConfigError
from prumo_assist.domains.paper.prep import ExtractPrep, extract_prep


def _bootstrap(tmp_path: Path, citekey: str = "smith2020") -> Path:
    pj = tmp_path / "pj_demo"
    (pj / ".claude").mkdir(parents=True)
    (pj / ".claude" / "paper_extraction.md").write_text("# Template\n", encoding="utf-8")
    refs = pj / "references"
    (refs / "pdfs").mkdir(parents=True)
    (refs / "_references.bib").write_text("@article{smith2020,}\n", encoding="utf-8")
    (refs / "pdfs" / f"{citekey}.pdf").write_text("%PDF-1.4\n", encoding="utf-8")
    notes = refs / "notes" / citekey
    notes.mkdir(parents=True)
    (notes / "_meta.md").write_text("---\nid: smith2020\n---\n", encoding="utf-8")
    return pj


def test_extract_prep_returns_language_and_paths(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    prep = extract_prep(pj, "smith2020")
    assert isinstance(prep, ExtractPrep)
    assert prep.language == "pt-BR"  # default em DEFAULTS
    assert prep.template_path.name == "paper_extraction.md"
    assert prep.pdf_path.exists()
    assert prep.meta_path.exists()


def test_extract_prep_missing_meta_raises(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    (pj / "references" / "notes" / "smith2020" / "_meta.md").unlink()
    with pytest.raises(FileNotFoundError, match="_meta.md"):
        extract_prep(pj, "smith2020")


def test_extract_prep_invalid_language_raises_configerror(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    (pj / ".claude" / "pj_config.toml").write_text(
        '[paper_extract]\nlanguage = "fr"\n', encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="language"):
        extract_prep(pj, "smith2020")
```

- [ ] **Step 2: Rodar e ver falhar** — `uv run pytest tests/unit/paper/test_prep.py -q` → `ModuleNotFoundError: prumo_assist.domains.paper.prep`.

- [ ] **Step 3: Implementar `paper/prep.py`** — Create `src/prumo_assist/domains/paper/prep.py`:

```python
"""``extract_prep`` — valida pré-requisitos de extração + lê config, num só passo.

Absorve o snippet inline ``load_project_config`` e os aborts de pré-requisito
que viviam na prosa de ``paper-extract`` (spec Fase A: comando *prep* compõe
validação + leitura de contexto). Tudo determinístico (checagem de path + config).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from prumo_assist.core.config import load_project_config


@dataclass(frozen=True)
class ExtractPrep:
    """Contexto pronto pra extração: idioma + caminhos validados."""

    language: str
    template_path: Path
    pdf_path: Path
    meta_path: Path


def extract_prep(pj_path: Path, citekey: str) -> ExtractPrep:
    """Valida os pré-requisitos de extração de ``citekey`` e devolve idioma + caminhos.

    Levanta ``FileNotFoundError`` (pré-req ausente, com comando de correção) ou
    ``ConfigError`` (``paper_extract.language`` inválido).
    """
    template_path = pj_path / ".claude" / "paper_extraction.md"
    bib_path = pj_path / "references" / "_references.bib"
    pdf_path = pj_path / "references" / "pdfs" / f"{citekey}.pdf"
    meta_path = pj_path / "references" / "notes" / citekey / "_meta.md"

    checks: list[tuple[str, Path, str]] = [
        ("template .claude/paper_extraction.md", template_path, "rode o scaffold do pj_*"),
        ("references/_references.bib", bib_path, "exporte pelo BBT"),
        (f"PDF references/pdfs/{citekey}.pdf", pdf_path, "rode `make sync-pdfs`"),
        (f"_meta.md de {citekey}", meta_path, "rode `prumo paper sync`"),
    ]
    for label, p, fix in checks:
        if not p.exists():
            raise FileNotFoundError(f"pré-requisito ausente: {label} ({p}); {fix}.")

    config = load_project_config(pj_path)  # valida paper_extract.language
    language = str(config["paper_extract"]["language"])
    return ExtractPrep(
        language=language, template_path=template_path, pdf_path=pdf_path, meta_path=meta_path
    )
```

- [ ] **Step 4: Rodar e ver passar (domínio)** — `uv run pytest tests/unit/paper/test_prep.py -q` → `3 passed`.

- [ ] **Step 5: Escrever o teste CLI que falha** — Append to `tests/unit/paper/test_cli.py` (reusa `runner`, `_last_json`):

```python
def test_paper_extract_prep_emits_language(tmp_path: Path) -> None:
    from tests.unit.paper.test_prep import _bootstrap

    pj = _bootstrap(tmp_path)
    result = runner.invoke(app, ["paper", "extract-prep", "smith2020", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    out = _last_json(result.stdout)
    assert out["language"] == "pt-BR"
    assert Path(str(out["meta_path"])).exists()
```

- [ ] **Step 6: Rodar e ver falhar (CLI)** — `uv run pytest tests/unit/paper/test_cli.py -q -k extract_prep` → `No such command 'extract-prep'`.

- [ ] **Step 7: Implementar o subcomando** — In `src/prumo_assist/domains/paper/cli.py`, add to the top imports:
```python
from prumo_assist.domains.paper import prep as paper_prep
```
Append the command:
```python
@paper_app.command("extract-prep")
def extract_prep_command(
    citekey: Annotated[str, typer.Argument(help="Citekey do paper.")],
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Valida pré-requisitos de extração e imprime idioma + caminhos."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError,)) as console:
        prep = paper_prep.extract_prep(path.resolve(), citekey)
        console.success(f"Pronto pra extrair {citekey} (idioma {prep.language}).")
        console.emit(
            {
                "language": prep.language,
                "template_path": str(prep.template_path),
                "pdf_path": str(prep.pdf_path),
                "meta_path": str(prep.meta_path),
            }
        )
```
(`ConfigError` é `PrumoError`, sempre capturado por `cli_run`; `FileNotFoundError` adicionado em `catches`.)

- [ ] **Step 8: Re-export em `api.py`** — In `src/prumo_assist/domains/paper/api.py`, add imports + `__all__` entries (alphabetical): `from prumo_assist.domains.paper.prep import ExtractPrep, extract_prep` and add `"ExtractPrep"`, `"extract_prep"` to `__all__`.

- [ ] **Step 9: Rodar e ver passar (CLI)** — `uv run pytest tests/unit/paper/test_cli.py -q -k extract_prep` → `1 passed`.

- [ ] **Step 10: Gates + commit**
```bash
uv run ruff check src/prumo_assist/domains/paper/ tests/unit/paper/ && uv run ruff format src/prumo_assist/domains/paper/ tests/unit/paper/ && uv run mypy
git add src/prumo_assist/domains/paper/prep.py src/prumo_assist/domains/paper/cli.py src/prumo_assist/domains/paper/api.py tests/unit/paper/test_prep.py tests/unit/paper/test_cli.py
git commit -m "feat(paper): prumo paper extract-prep (absorve load_project_config + valida pré-req)"
```

---

### Task 2: `prumo paper extract` (TDD)

**Files:**
- Modify: `src/prumo_assist/domains/paper/cli.py`, `src/prumo_assist/domains/paper/api.py`
- Test: `tests/unit/paper/test_cli.py`

Contexto: substitui o snippet `apply_extraction` (§5). `apply_extraction(pj_path, citekey, template_path, content: dict[str, str], model, date) -> bool` vive em `callout.py` (existe; falta re-export). O `content` (dict produzido pela LLM) chega via stdin JSON. `template_path` é o default `.claude/paper_extraction.md` (faithful ao snippet, que o hardcoda).

- [ ] **Step 1: Escrever o teste CLI que falha** — Append to `tests/unit/paper/test_cli.py`:

```python
def test_paper_extract_applies_content_from_stdin(tmp_path: Path) -> None:
    import json

    from tests.unit.paper.test_prep import _bootstrap

    pj = _bootstrap(tmp_path)
    # template com 1 seção pra apply_extraction popular:
    (pj / ".claude" / "paper_extraction.md").write_text(
        "## Resumo\n<!-- instrução -->\n", encoding="utf-8"
    )
    body = json.dumps({"Resumo": "Estudo de coorte sobre RWE."})
    result = runner.invoke(
        app,
        ["paper", "extract", "smith2020", "--model", "claude-x", "--date", "2026-06-14",
         str(pj), "--json"],
        input=body,
    )
    assert result.exit_code == 0, result.output
    out = _last_json(result.stdout)
    assert out["changed"] is True
    extract_md = pj / "references" / "notes" / "smith2020" / "_extract.md"
    assert extract_md.exists()
    assert "Estudo de coorte" in extract_md.read_text(encoding="utf-8")
```

- [ ] **Step 2: Rodar e ver falhar** — `uv run pytest tests/unit/paper/test_cli.py -q -k "paper_extract_applies"` → `No such command 'extract'`.

- [ ] **Step 3: Implementar o subcomando** — In `src/prumo_assist/domains/paper/cli.py`, add to the top imports:
```python
from prumo_assist.core.cli_io import read_stdin_json
from prumo_assist.domains.paper.callout import apply_extraction
```
Append the command:
```python
@paper_app.command("extract")
def extract_command(
    citekey: Annotated[str, typer.Argument(help="Citekey do paper.")],
    model: Annotated[str, typer.Option("--model", help="Modelo que gerou a extração.")],
    date: Annotated[str, typer.Option("--date", help="Data ISO YYYY-MM-DD.")],
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Aplica a extração (dict via stdin JSON) ao callout do paper; grava _extract.md."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError,)) as console:
        content = read_stdin_json()
        template_path = path.resolve() / ".claude" / "paper_extraction.md"
        changed = apply_extraction(
            pj_path=path.resolve(),
            citekey=citekey,
            template_path=template_path,
            content=content,
            model=model,
            date=date,
        )
        console.success("MUDOU" if changed else "IDÊNTICO")
        console.emit({"changed": changed})
```

- [ ] **Step 4: Re-export em `api.py`** — Add `from prumo_assist.domains.paper.callout import apply_extraction` and `"apply_extraction"` to `__all__` (alphabetical) in `src/prumo_assist/domains/paper/api.py`.

- [ ] **Step 5: Rodar e ver passar** — `uv run pytest tests/unit/paper/test_cli.py -q` → todos passam.

- [ ] **Step 6: Gates + commit**
```bash
uv run ruff check src/prumo_assist/domains/paper/ tests/unit/paper/ && uv run ruff format src/prumo_assist/domains/paper/ tests/unit/paper/ && uv run mypy
git add src/prumo_assist/domains/paper/cli.py src/prumo_assist/domains/paper/api.py tests/unit/paper/test_cli.py
git commit -m "feat(paper): prumo paper extract (substitui snippet apply_extraction; content via stdin)"
```

---

### Task 3: `prumo write prep` (TDD)

**Files:**
- Modify: `src/prumo_assist/domains/write/compose.py`, `src/prumo_assist/domains/write/cli.py`, `src/prumo_assist/domains/write/api.py`
- Test: `tests/unit/write/test_compose_prep.py`, `tests/unit/write/test_cli.py`

Contexto: substitui os snippets `read_inputs` (§1) + `resolve_template` (§2) num só comando *prep* (spec: "leitura de contexto num só"). Ambas as funções já existem em `compose.py`; `prep` apenas as compõe. `WriteKind = Literal["paper","projeto-cep","statistics","scientific"]`. Nota de layering: `read_inputs` usa o import guardado `write → protocol` (try/except ImportError em `compose.py`) — não adicionar import top-level de `protocol` em `write/cli.py` nem `write/api.py`.

- [ ] **Step 1: Escrever o teste de domínio que falha** — Create `tests/unit/write/test_compose_prep.py`:

```python
"""Testa `write.compose.prep` (compõe read_inputs + resolve_template)."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.write.compose import WritePrep, prep
from prumo_assist.domains.write.schemas.v1 import ComposeInputs


def test_prep_returns_inputs_and_template(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    result = prep(pj, kind="paper")
    assert isinstance(result, WritePrep)
    assert isinstance(result.inputs, ComposeInputs)
    assert result.template_path.name.endswith(".md")
```

(`resolve_template(kind="paper")` cai no template do bundle da skill quando o pj não tem override — ver `test_resolve_template_default_from_skill_bundle`.)

- [ ] **Step 2: Rodar e ver falhar** — `uv run pytest tests/unit/write/test_compose_prep.py -q` → `ImportError: cannot import name 'WritePrep'`.

- [ ] **Step 3: Implementar `prep` em `compose.py`** — Add (near `read_inputs`/`resolve_template`); `dataclass`/`Path` already imported there, add `WriteKind` from schemas if not present:

```python
@dataclass(frozen=True)
class WritePrep:
    """Contexto de escrita: inputs compostos + template resolvido."""

    inputs: ComposeInputs
    template_path: Path


def prep(pj_path: Path, *, kind: WriteKind) -> WritePrep:
    """Compõe ``read_inputs`` + ``resolve_template`` num só passo de contexto."""
    return WritePrep(inputs=read_inputs(pj_path), template_path=resolve_template(pj_path=pj_path, kind=kind))
```

(Confirme os imports no topo de `compose.py`: `from dataclasses import dataclass`; `ComposeInputs`, `WriteKind` de `schemas.v1`. Adicione o que faltar.)

- [ ] **Step 4: Rodar e ver passar (domínio)** — `uv run pytest tests/unit/write/test_compose_prep.py -q` → `1 passed`.

- [ ] **Step 5: Escrever o teste CLI que falha** — Create `tests/unit/write/test_cli.py`:

```python
"""Integration tests para `prumo write *` (prep/draft)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from prumo_assist.cli import app

runner = CliRunner()


def _last_json(stdout: str) -> dict[str, object]:
    last: dict[str, object] | None = None
    for line in stdout.splitlines():
        try:
            last = json.loads(line)
        except json.JSONDecodeError:
            continue
    assert last is not None, f"nenhum JSON na saída: {stdout!r}"
    return last


def test_write_prep_emits_inputs_and_template(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    result = runner.invoke(app, ["write", "prep", "--kind", "paper", "--path", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    out = _last_json(result.stdout)
    assert "inputs" in out
    assert "template_path" in out


def test_write_prep_invalid_kind_fails(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    result = runner.invoke(app, ["write", "prep", "--kind", "bogus", "--path", str(pj)])
    assert result.exit_code == 1
    assert "--kind" in result.output
```

- [ ] **Step 6: Rodar e ver falhar (CLI)** — `uv run pytest tests/unit/write/test_cli.py -q -k write_prep` → `No such command 'prep'`.

- [ ] **Step 7: Implementar o subcomando** — In `src/prumo_assist/domains/write/cli.py`, add to the top imports:
```python
from typing import cast

from prumo_assist import PrumoError
from prumo_assist.domains.write import compose
from prumo_assist.domains.write.schemas.v1 import WriteKind

_WRITE_KINDS = ("paper", "projeto-cep", "statistics", "scientific")
```
Append the command:
```python
@write_app.command("prep")
def prep_command(
    kind: Annotated[str, typer.Option("--kind", help="paper|projeto-cep|statistics|scientific.")] = "paper",
    path: Annotated[Path, typer.Option("--path", help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Lê inputs do projeto + resolve o template (contexto pra escrita) num só passo."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError,)) as console:
        if kind not in _WRITE_KINDS:
            raise PrumoError(f"--kind deve ser um de {list(_WRITE_KINDS)}.")
        result = compose.prep(path.resolve(), kind=cast(WriteKind, kind))
        console.success(f"Contexto pronto (template {result.template_path.name}).")
        console.emit(
            {"inputs": result.inputs.model_dump(mode="json"), "template_path": str(result.template_path)}
        )
```

- [ ] **Step 8: Re-export em `api.py`** — In `src/prumo_assist/domains/write/api.py`, add `WritePrep`, `prep` to the `compose` import and to `__all__` (alphabetical).

- [ ] **Step 9: Rodar e ver passar (CLI)** — `uv run pytest tests/unit/write/test_cli.py -q -k write_prep` → `2 passed`.

- [ ] **Step 10: Gates + commit**
```bash
uv run ruff check src/prumo_assist/domains/write/ tests/unit/write/ && uv run ruff format src/prumo_assist/domains/write/ tests/unit/write/ && uv run mypy
git add src/prumo_assist/domains/write/compose.py src/prumo_assist/domains/write/cli.py src/prumo_assist/domains/write/api.py tests/unit/write/test_compose_prep.py tests/unit/write/test_cli.py
git commit -m "feat(write): prumo write prep (compõe read_inputs + resolve_template)"
```

---

### Task 4: `prumo write draft` (TDD)

**Files:**
- Modify: `src/prumo_assist/domains/write/cli.py`
- Test: `tests/unit/write/test_cli.py`

Contexto: substitui o snippet `write_output` (§5). `write_output(*, content, pj_path, kind, mode, date, slug, into=None, out=None, section=None, force=False, sections_filled=None, sections_skipped=None) -> WriteOutput` (existe em `compose.py`, já em `api.py`). Draft markdown via stdin; `--sections` como array JSON; `mode`/`kind` validados + `cast`. `WriteMode = Literal["drafts","into","out"]`.

- [ ] **Step 1: Escrever o teste CLI que falha** — Append to `tests/unit/write/test_cli.py`:

```python
def test_write_draft_drafts_mode_writes_file(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    draft = "# Paper\n\n## Introduction\n\nReal-world evidence."
    result = runner.invoke(
        app,
        ["write", "draft", "--kind", "paper", "--mode", "drafts", "--date", "2026-06-14",
         "--slug", "rwe-paper", "--sections", '["Introduction"]', "--path", str(pj), "--json"],
        input=draft,
    )
    assert result.exit_code == 0, result.output
    out = _last_json(result.stdout)
    written = Path(str(out["output_path"]))
    assert written.exists()
    assert "Real-world evidence." in written.read_text(encoding="utf-8")


def test_write_draft_invalid_mode_fails(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    result = runner.invoke(
        app,
        ["write", "draft", "--kind", "paper", "--mode", "bogus", "--date", "2026-06-14",
         "--slug", "x", "--path", str(pj)],
        input="conteúdo",
    )
    assert result.exit_code == 1
    assert "--mode" in result.output
```

- [ ] **Step 2: Rodar e ver falhar** — `uv run pytest tests/unit/write/test_cli.py -q -k write_draft` → `No such command 'draft'`.

- [ ] **Step 3: Implementar o subcomando** — In `src/prumo_assist/domains/write/cli.py`, extend the top imports to add `read_stdin_text`, `parse_json_list`, and `WriteMode`:
```python
from prumo_assist.core.cli_io import parse_json_list, read_stdin_text
from prumo_assist.domains.write.schemas.v1 import WriteKind, WriteMode

_WRITE_MODES = ("drafts", "into", "out")
```
Append the command:
```python
@write_app.command("draft")
def draft_command(
    kind: Annotated[str, typer.Option("--kind", help="paper|projeto-cep|statistics|scientific.")],
    date: Annotated[str, typer.Option("--date", help="Data ISO YYYY-MM-DD.")],
    slug: Annotated[str, typer.Option("--slug", help="Slug do output.")],
    mode: Annotated[str, typer.Option("--mode", help="drafts|into|out.")] = "drafts",
    sections: Annotated[str, typer.Option("--sections", help="Array JSON de seções preenchidas.")] = "[]",
    into: Annotated[str, typer.Option("--into", help="Caminho destino (modo into).")] = "",
    out: Annotated[str, typer.Option("--out", help="Caminho destino (modo out).")] = "",
    force: Annotated[bool, typer.Option("--force", help="Sobrescreve no modo out.")] = False,
    path: Annotated[Path, typer.Option("--path", help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Grava o draft (markdown via stdin) conforme o modo; reporta o WriteOutput."""
    with cli_run(json_mode=json_mode, catches=(ValueError, FileNotFoundError, FileExistsError)) as console:
        if kind not in _WRITE_KINDS:
            raise PrumoError(f"--kind deve ser um de {list(_WRITE_KINDS)}.")
        if mode not in _WRITE_MODES:
            raise PrumoError(f"--mode deve ser um de {list(_WRITE_MODES)}.")
        content = read_stdin_text()
        sections_list = parse_json_list(sections, "--sections")
        result = compose.write_output(
            content=content,
            pj_path=path.resolve(),
            kind=cast(WriteKind, kind),
            mode=cast(WriteMode, mode),
            date=date,
            slug=slug,
            into=Path(into) if into else None,
            out=Path(out) if out else None,
            force=force,
            sections_filled=sections_list,
        )
        console.success(f"Draft gravado em {result.output_path} ({result.words_generated} palavras).")
        console.emit(result.model_dump(mode="json"))
```

(`compose` já importado na Task 3; `PrumoError`/`cast`/`_WRITE_KINDS` idem. `write_output` pode levantar `FileExistsError` (modo out sem `--force`); incluído em `catches`.)

- [ ] **Step 4: Rodar e ver passar** — `uv run pytest tests/unit/write/test_cli.py -q` → todos passam.

- [ ] **Step 5: Gates + commit**
```bash
uv run ruff check src/prumo_assist/domains/write/ tests/unit/write/ && uv run ruff format src/prumo_assist/domains/write/ tests/unit/write/ && uv run mypy
git add src/prumo_assist/domains/write/cli.py tests/unit/write/test_cli.py
git commit -m "feat(write): prumo write draft (substitui snippet write_output; draft via stdin)"
```

---

### Task 5: Atualizar a prosa de `paper-extract`

**Files:**
- Modify: `skills/paper-extract/SKILL.md`

Contexto: trocar os 2 snippets inline por `prumo paper …`; mover a validação de pré-req pro `extract-prep`. NÃO alterar a lógica agêntica de leitura/extração do PDF.

- [ ] **Step 1: `allowed-tools` (linha 9)** — Replace:
```
allowed-tools: Read Write Edit Glob Grep Bash(python3 *) Bash(uv run python *) Bash(test *) Bash(readlink *) Agent
```
with (remove python + test + readlink — a validação foi pro `extract-prep`; adiciona `Bash(prumo paper *)` e `Bash(cat *)` para o heredoc):
```
allowed-tools: Read Write Edit Glob Grep Bash(prumo paper *) Bash(cat *) Agent
```

- [ ] **Step 2: § 1 (validação) + § 2 (config) → `extract-prep`** — Substituir os passos de checagem de pré-requisito e o bloco `uv run python -c "... load_project_config ..."` por um único bloco no início do fluxo single:
```bash
prumo paper extract-prep <citekey> --json
```
Instrução acompanhante: "Capture `language`, `template_path`, `pdf_path` e `meta_path` do JSON. Se falhar (exit≠0), aborte mostrando a mensagem (ela traz o comando de correção)."

- [ ] **Step 3: § 5 (apply) → `prumo paper extract`** — Substituir o bloco `uv run python -c '... apply_extraction ...'` por:
```bash
cat <<'JSON' | prumo paper extract <citekey> --model "<modelo_atual>" --date "<hoje>" --json
{ "<Seção>": "<conteúdo extraído>", "...": "..." }
JSON
```

- [ ] **Step 4: Pressupostos** — Atualizar a seção Pressupostos: substituir os bullets de pré-requisito (agora checados por `extract-prep`) por uma nota de que `prumo paper extract-prep` valida tudo, e adicionar o bullet do CLI:
```
- A validação de pré-requisitos (template, .bib, PDF, _meta.md) e a leitura de
  config são feitas por `prumo paper extract-prep <citekey>` (aborta com correção).
- O CLI `prumo` precisa estar no PATH (rode `prumo doctor`; se ausente:
  `uv tool install git+https://github.com/raphaelfh/prumo-assist`).
```

- [ ] **Step 5: Verificar** — `grep -nE "from prumo_assist|python -c|uv run python|python3|load_project_config|apply_extraction" skills/paper-extract/SKILL.md || echo "limpo"` → `limpo`.

- [ ] **Step 6: Commit**
```bash
git add skills/paper-extract/SKILL.md
git commit -m "refactor(paper-extract): chama prumo paper em vez de snippets inline (ponte CLI)"
```

---

### Task 6: Atualizar a prosa de `write-paper`

**Files:**
- Modify: `skills/write-paper/SKILL.md`

Contexto: trocar os 3 snippets inline por `prumo write …`. NÃO alterar a lógica agêntica de composição da prose.

- [ ] **Step 1: `allowed-tools` (linha 9)** — Replace:
```
allowed-tools: Read Write Edit Glob Grep Bash(uv run python *) Bash(python3 *)
```
with:
```
allowed-tools: Read Write Edit Glob Grep Bash(prumo write *) Bash(cat *)
```

- [ ] **Step 2: § 1 (read_inputs) + § 2 (resolve_template) → `prumo write prep`** — Substituir os dois blocos `uv run python -c '...'` por um único:
```bash
prumo write prep --kind paper --json > /tmp/compose_prep.json
```
Instrução: "Leia `inputs` (contexto: picot, papers, protocolo, findings) e `template_path` do JSON; faça `Read <template_path>`."

- [ ] **Step 3: § 5 (write_output) → `prumo write draft`** — Substituir o bloco `uv run python -c '... write_output ...'` por:
```bash
cat <<'DRAFT' | prumo write draft \
    --kind paper \
    --mode drafts \
    --date "<hoje ISO>" \
    --slug "<slug derivado>" \
    --sections '["Introduction","Methods", "..."]' --json
<draft completo gerado>
DRAFT
```
(Para `--mode into`/`out`, acrescente `--into <path>` ou `--out <path>` e `--force` quando aplicável.)

- [ ] **Step 4: Verificar** — `grep -nE "from prumo_assist|python -c|uv run python|python3|read_inputs|resolve_template|write_output" skills/write-paper/SKILL.md || echo "limpo"` → `limpo`.

- [ ] **Step 5: Commit**
```bash
git add skills/write-paper/SKILL.md
git commit -m "refactor(write-paper): chama prumo write em vez de snippets inline (ponte CLI)"
```

---

### Task 7: Gates finais

**Files:** (nenhum — só verificação)

Contexto: não há `scripts/` a deletar nesta trilha (paper/write nunca tiveram). Critério de sucesso #1 do spec (`grep -rn "from prumo_assist" skills/` vazio) deve agora valer **repo-wide** (A1+A2+A3 cobriram os 5 skills afetados).

- [ ] **Step 1: Confirmar trilha limpa repo-wide**

Run: `grep -rn "from prumo_assist" skills/ || echo "limpo repo-wide"`
Expected: `limpo repo-wide`.

- [ ] **Step 2: Suíte completa + gates**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run python .github/scripts/gen_indexes.py --check`
Expected: tudo verde.

- [ ] **Step 3: Commit (se algo ficou pendente de format) ou nenhum**

Se `ruff format` mudou algo nos passos anteriores e não foi commitado, commit; senão, esta task não gera commit (é só verificação). Não modificar CHANGELOG (sem release nesta fase).

---

## Self-Review

**Cobertura do escopo A3:** os 5 snippets inline → 4 subcomandos (`paper extract-prep`, `paper extract`, `write prep`, `write draft`) ✓; `apply_extraction` re-exportado em paper/api.py ✓; `extract_prep`/`prep` novas funções de domínio (validação + composição de contexto, sem julgamento) ✓; prosa das 2 skills migrada + allowed-tools limpo + Pressuposto de CLI ✓; sem `scripts/` a deletar (paper/write nunca tiveram) ✓. Fora de A3: hook de enforcement + release (A4).

**Placeholders:** nenhum — todo passo tem código/comando completo e saída esperada.

**Consistência de tipos:** `extract_prep(pj_path, citekey) -> ExtractPrep(language, template_path, pdf_path, meta_path)`; `apply_extraction(pj_path, citekey, template_path, content: dict[str,str], model, date) -> bool` (content via `read_stdin_json` → `dict[str, Any]`, compatível com `dict[str,str]` por Any); `prep(pj_path, *, kind: WriteKind) -> WritePrep(inputs: ComposeInputs, template_path)`; `write_output(*, content, pj_path, kind, mode, date, slug, into, out, force, sections_filled) -> WriteOutput`. `--kind`/`--mode` validados contra `_WRITE_KINDS`/`_WRITE_MODES` + `cast` (padrão da A2). `WriteKind`/`WriteMode` Literals de `schemas/v1.py`.

**Layering:** `paper/prep.py` importa `core/config` (domain→core, ok). `write/compose.prep` reusa `read_inputs` (que carrega `read_picot` via import guardado `try/except ImportError` — não adicionar import top-level de `protocol` em `write/cli.py`/`write/api.py`, preservando a única exceção justificada do code.md). `cli.py` permanece fachada fina.

**Nota de design honrada:** `load_project_config` absorvido no `extract-prep` (sem `prumo config` standalone — YAGNI, spec). A validação de pré-req (determinística) migra da prosa agêntica pro núcleo; o julgamento (ler PDF, extrair, compor prose) fica nas skills. write-paper não precisou de lógica nova (3 funções já no api.py) — só fachadas + 1 compositor `prep`.
