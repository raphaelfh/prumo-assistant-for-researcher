---
status: implemented
verified: 2026-06-14
release: null
spec: "[[2026-06-13-researcher-pipeline-design]]"
phase: "A1 de A1–A4 (Fase A do spec)"
---

# Fase A1 — Ponte CLI das skills com `scripts/` (wiki) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir os 5 scripts de `skills/active-learning/scripts/` por subcomandos `prumo wiki` (fachadas finas sobre `domains/wiki`), deletar os scripts, e atualizar a prosa de `active-learning` e `wiki-query` para chamar o CLI — eliminando o `from prumo_assist` frágil dessas skills.

**Architecture:** Fachadas finas Typer no padrão do repo (`@wiki_app.command` + `cli_run` + `Console.emit`), sobre funções de domínio que **já existem** em `domains/wiki/{study,findings}.py`. Único componente novo de infra: `core/cli_io.py` (ler stdin), porque o repo ainda não tem precedente de payload via stdin e o spec (Seção 0.5) define corpo markdown e payloads-schema via stdin. Nenhuma lógica de domínio nova — só exposição.

**Tech Stack:** Python 3.11+, Typer, Pydantic v2, pytest + `typer.testing.CliRunner`, uv. Tudo já no projeto.

**Escopo desta fase (parte de A1–A4):** só a trilha `wiki` (active-learning + wiki-query). Protocol (A2), paper/write (A3) e o hook + release (A4) são planos seguintes. **Nenhum release nesta fase** — a versão é bumpada só no A4.

---

## File Structure

| Caminho | Ação | Responsabilidade |
|---|---|---|
| `src/prumo_assist/core/cli_io.py` | Criar | Ler stdin (texto/JSON) + parsear opção `--x` como array JSON, com erros pt-BR acionáveis |
| `tests/unit/test_cli_io.py` | Criar | Testar os 3 helpers de I/O |
| `src/prumo_assist/domains/wiki/cli.py` | Modificar | +4 subcomandos: `study-start`, `study-step`, `study-finish`, `finding` |
| `tests/unit/wiki/test_cli_study.py` | Criar | Testar os 4 subcomandos via CliRunner |
| `src/prumo_assist/domains/wiki/api.py` | Modificar | Re-exportar `create_session_log`, `append_step`, `finalize_session`, `archive_as_finding` |
| `skills/active-learning/SKILL.md` | Modificar | 5 invocações de script → `prumo wiki ...` |
| `skills/wiki-query/SKILL.md` | Modificar | snippet de finding → `prumo wiki finding` |
| `skills/active-learning/scripts/` | Deletar | 5 scripts (slug, create_log, append_step, archive_finding, finalize_session) |

Mapa script → subcomando (slug + create_log colapsam num só `study-start`, que slugifica internamente):

| Script (active-learning) | Subcomando |
|---|---|
| `slug.py` + `create_log.py` | `prumo wiki study-start <topic> --date --sources` |
| `append_step.py` | `prumo wiki study-step --log-path --step` (StepLog JSON via stdin) |
| `finalize_session.py` | `prumo wiki study-finish --log-path --duration --status --missing --finding` |
| `archive_finding.py` | `prumo wiki finding --slug --title --date --tags --sources --generator` (corpo via stdin) |
| (wiki-query snippet) | `prumo wiki finding ...` (mesmo subcomando) |

---

### Task 1: `core/cli_io.py` — helpers de stdin (TDD)

**Files:**
- Create: `src/prumo_assist/core/cli_io.py`
- Test: `tests/unit/test_cli_io.py`

- [ ] **Step 1: Escrever os testes que falham**

Create `tests/unit/test_cli_io.py`:

```python
"""Testa os helpers de I/O de CLI (leitura de stdin + parse de array JSON)."""

from __future__ import annotations

import io

import pytest

from prumo_assist import PrumoError
from prumo_assist.core import cli_io


def test_read_stdin_text_retorna_corpo() -> None:
    assert cli_io.read_stdin_text(io.StringIO("# título\n\ncorpo")) == "# título\n\ncorpo"


def test_read_stdin_text_vazio_e_permitido() -> None:
    assert cli_io.read_stdin_text(io.StringIO("")) == ""


def test_read_stdin_json_parseia_objeto() -> None:
    assert cli_io.read_stdin_json(io.StringIO('{"a": 1}')) == {"a": 1}


def test_read_stdin_json_vazio_levanta_prumoerror() -> None:
    with pytest.raises(PrumoError, match="payload JSON ausente"):
        cli_io.read_stdin_json(io.StringIO("  \n "))


def test_read_stdin_json_invalido_levanta_prumoerror() -> None:
    with pytest.raises(PrumoError, match="JSON inválido"):
        cli_io.read_stdin_json(io.StringIO("{nao é json}"))


def test_read_stdin_json_nao_objeto_levanta_prumoerror() -> None:
    with pytest.raises(PrumoError, match="objeto"):
        cli_io.read_stdin_json(io.StringIO("[1, 2, 3]"))


def test_parse_json_list_ok() -> None:
    assert cli_io.parse_json_list('["[[@a]]", "[[@b]]"]', "--sources") == ["[[@a]]", "[[@b]]"]


def test_parse_json_list_default_vazio() -> None:
    assert cli_io.parse_json_list("[]", "--tags") == []


def test_parse_json_list_nao_array_levanta_prumoerror() -> None:
    with pytest.raises(PrumoError, match="--tags deve ser um array JSON"):
        cli_io.parse_json_list('{"x": 1}', "--tags")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/test_cli_io.py -q`
Expected: erro de import (`ModuleNotFoundError: prumo_assist.core.cli_io`).

- [ ] **Step 3: Implementar `core/cli_io.py`**

Create `src/prumo_assist/core/cli_io.py`:

```python
"""Leitura de stdin para subcomandos que recebem corpo markdown ou payload-schema.

O repo não tinha precedente de payload via stdin; o spec do pipeline (Seção 0.5)
define: corpo markdown vai cru por stdin (heredoc), payload estruturado vai como
JSON por stdin quando já é schema, metadados via flags. O ``stream`` é injetável
para teste (seam) — em produção, ``None`` resolve para ``sys.stdin``.
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from prumo_assist import PrumoError


def read_stdin_text(stream: TextIO | None = None) -> str:
    """Lê o corpo (markdown) de stdin. Vazio é permitido (retorna ``''``)."""
    src = stream if stream is not None else sys.stdin
    return src.read()


def read_stdin_json(stream: TextIO | None = None) -> dict[str, Any]:
    """Lê e parseia um objeto JSON de stdin. ``PrumoError`` acionável se vazio/inválido."""
    raw = read_stdin_text(stream).strip()
    if not raw:
        raise PrumoError(
            "payload JSON ausente no stdin; passe o objeto via pipe "
            "(ex.: echo '{...}' | prumo ...)."
        )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise PrumoError(f"JSON inválido no stdin: {e}") from e
    if not isinstance(data, dict):
        raise PrumoError("payload JSON deve ser um objeto (mapping).")
    return data


def parse_json_list(raw: str, flag: str) -> list[str]:
    """Parseia uma opção ``--flag`` que carrega um array JSON de strings."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise PrumoError(f"{flag} deve ser um array JSON: {e}") from e
    if not isinstance(data, list):
        raise PrumoError(f"{flag} deve ser um array JSON.")
    return [str(x) for x in data]
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/test_cli_io.py -q`
Expected: `9 passed`.

- [ ] **Step 5: Gates + commit**

Run: `uv run ruff check src/prumo_assist/core/cli_io.py tests/unit/test_cli_io.py && uv run ruff format src/prumo_assist/core/cli_io.py tests/unit/test_cli_io.py && uv run mypy`
Expected: tudo verde.

```bash
git add src/prumo_assist/core/cli_io.py tests/unit/test_cli_io.py
git commit -m "feat(core): cli_io — leitura de stdin (texto/JSON) para subcomandos do núcleo"
```

---

### Task 2: `prumo wiki study-start` (TDD)

**Files:**
- Modify: `src/prumo_assist/domains/wiki/cli.py`
- Test: `tests/unit/wiki/test_cli_study.py`

Contexto: substitui `slug.py` + `create_log.py`. Slugifica o tópico internamente (colapsa os dois scripts). Domínio: `study.create_session_log(*, pj_path, topic, date, sources_consulted) -> Path` e `core.note_paths.slugify(text) -> str` (ambos já existem).

- [ ] **Step 1: Escrever o teste que falha**

Create `tests/unit/wiki/test_cli_study.py`:

```python
"""Testa os subcomandos `prumo wiki study-*` e `finding` via CliRunner (sem rede/external)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from prumo_assist.cli import app

runner = CliRunner()


def _pj(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "wiki").mkdir(parents=True)
    return tmp_path


def test_study_start_cria_log_e_emite_path(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    result = runner.invoke(
        app,
        ["wiki", "study-start", "Insuficiência Cardíaca em Diabéticos",
         "--date", "2026-06-14", "--path", str(pj), "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["slug"] == "insuficiencia-cardiaca-em"  # slugify trunca em 30
    log_path = Path(payload["log_path"])
    assert log_path.exists()
    assert "2026-06-14" in log_path.name
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/wiki/test_cli_study.py -q`
Expected: FAIL — `No such command 'study-start'` (exit_code != 0).

- [ ] **Step 3: Implementar o subcomando**

In `src/prumo_assist/domains/wiki/cli.py`, garanta os imports no topo (adicione o que faltar):

```python
from __future__ import annotations

from pathlib import Path
from typing import Annotated, cast

import typer

from prumo_assist.core.cli_io import parse_json_list, read_stdin_json, read_stdin_text
from prumo_assist.core.cli_op import cli_run
from prumo_assist.core.note_paths import slugify
from prumo_assist.domains.wiki import findings, study
from prumo_assist.domains.wiki.schemas.v1 import StepLog
```

(Os imports de `index, lint, stats` já existentes permanecem.) Adicione o comando ao final do arquivo:

```python
@wiki_app.command("study-start")
def study_start_command(
    topic: Annotated[str, typer.Argument(help="Tópico da sessão (texto livre; vira slug).")],
    date: Annotated[str, typer.Option("--date", help="Data ISO YYYY-MM-DD.")],
    sources: Annotated[str, typer.Option("--sources", help="Array JSON de wikilinks.")] = "[]",
    path: Annotated[Path, typer.Option("--path", help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Cria o log de uma sessão de estudo (slugifica o tópico) e imprime o caminho."""
    with cli_run(json_mode=json_mode, catches=(ValueError,)) as console:
        sources_list = parse_json_list(sources, "--sources")
        slug = slugify(topic)
        log_path = study.create_session_log(
            pj_path=path.resolve(), topic=slug, date=date, sources_consulted=sources_list
        )
        console.success(f"Sessão criada: {log_path}")
        console.emit({"log_path": str(log_path), "slug": slug})
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/wiki/test_cli_study.py -q`
Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/wiki/cli.py tests/unit/wiki/test_cli_study.py
git commit -m "feat(wiki): prumo wiki study-start (substitui slug.py + create_log.py)"
```

---

### Task 3: `prumo wiki study-step` (TDD)

**Files:**
- Modify: `src/prumo_assist/domains/wiki/cli.py`
- Test: `tests/unit/wiki/test_cli_study.py`

Contexto: substitui `append_step.py`. StepLog parcial via stdin JSON; `--step` injeta `step_name` (sobrescreve o JSON). Domínio: `study.append_step(log_path: Path, step: StepLog) -> None`. `StepLog(**payload)` pode levantar `pydantic.ValidationError` (não é subclasse de `ValueError` na v2) — capturar.

- [ ] **Step 1: Escrever o teste que falha**

Append to `tests/unit/wiki/test_cli_study.py`:

```python
def test_study_step_anexa_step_do_stdin(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    start = runner.invoke(
        app, ["wiki", "study-start", "Tópico X", "--date", "2026-06-14",
               "--path", str(pj), "--json"],
    )
    log_path = json.loads(start.stdout)["log_path"]
    step_json = json.dumps({"question": "O que é PECO?", "answer": "Exposição..."})
    result = runner.invoke(
        app,
        ["wiki", "study-step", "--log-path", log_path, "--step", "recall", "--json"],
        input=step_json,
    )
    assert result.exit_code == 0, result.output
    text = Path(log_path).read_text(encoding="utf-8")
    assert "## 1. Recall" in text
    assert "O que é PECO?" in text


def test_study_step_json_invalido_falha_limpo(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    start = runner.invoke(
        app, ["wiki", "study-start", "Y", "--date", "2026-06-14", "--path", str(pj), "--json"]
    )
    log_path = json.loads(start.stdout)["log_path"]
    result = runner.invoke(
        app, ["wiki", "study-step", "--log-path", log_path, "--step", "recall"], input=""
    )
    assert result.exit_code == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/wiki/test_cli_study.py -q -k study_step`
Expected: FAIL — `No such command 'study-step'`.

- [ ] **Step 3: Implementar o subcomando**

Adicione ao topo de `wiki/cli.py` (junto aos imports): `from pydantic import ValidationError`. Adicione o comando:

```python
@wiki_app.command("study-step")
def study_step_command(
    log_path: Annotated[Path, typer.Option("--log-path", help="Caminho do log da sessão.")],
    step: Annotated[str, typer.Option("--step", help="recall|anchor|connect|apply|reflect.")],
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Anexa um step (StepLog via stdin JSON) ao log da sessão."""
    with cli_run(json_mode=json_mode, catches=(ValueError, FileNotFoundError, ValidationError)) as console:
        payload = read_stdin_json()
        payload["step_name"] = step
        step_obj = StepLog(**payload)
        study.append_step(log_path, step_obj)
        console.success(f"Step '{step}' anexado.")
        console.emit({"ok": True, "step": step})
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/wiki/test_cli_study.py -q -k study_step`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/wiki/cli.py tests/unit/wiki/test_cli_study.py
git commit -m "feat(wiki): prumo wiki study-step (substitui append_step.py; StepLog via stdin)"
```

---

### Task 4: `prumo wiki study-finish` (TDD)

**Files:**
- Modify: `src/prumo_assist/domains/wiki/cli.py`
- Test: `tests/unit/wiki/test_cli_study.py`

Contexto: substitui `finalize_session.py`. Domínio: `study.finalize_session(log_path, *, duration_minutes, status: Literal['completed','abandoned','partial'], references_missing, finding_archived: Path | None) -> None`. `status` é Literal — validar e `cast` para mypy-strict.

- [ ] **Step 1: Escrever o teste que falha**

Append to `tests/unit/wiki/test_cli_study.py`:

```python
def test_study_finish_grava_frontmatter(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    start = runner.invoke(
        app, ["wiki", "study-start", "Z", "--date", "2026-06-14", "--path", str(pj), "--json"]
    )
    log_path = json.loads(start.stdout)["log_path"]
    result = runner.invoke(
        app,
        ["wiki", "study-finish", "--log-path", log_path, "--duration", "20",
         "--status", "completed", "--json"],
    )
    assert result.exit_code == 0, result.output
    text = Path(log_path).read_text(encoding="utf-8")
    assert "duration_minutes: 20" in text
    assert "status: completed" in text


def test_study_finish_status_invalido_falha(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    start = runner.invoke(
        app, ["wiki", "study-start", "W", "--date", "2026-06-14", "--path", str(pj), "--json"]
    )
    log_path = json.loads(start.stdout)["log_path"]
    result = runner.invoke(
        app, ["wiki", "study-finish", "--log-path", log_path, "--duration", "5", "--status", "foo"]
    )
    assert result.exit_code == 1
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/wiki/test_cli_study.py -q -k study_finish`
Expected: FAIL — `No such command 'study-finish'`.

- [ ] **Step 3: Implementar o subcomando**

Adicione a `wiki/cli.py`:

```python
@wiki_app.command("study-finish")
def study_finish_command(
    log_path: Annotated[Path, typer.Option("--log-path", help="Caminho do log da sessão.")],
    duration: Annotated[int, typer.Option("--duration", help="Duração em minutos.")],
    status: Annotated[str, typer.Option("--status", help="completed|abandoned|partial.")],
    missing: Annotated[str, typer.Option("--missing", help="Array JSON de REF FALTANTE.")] = "[]",
    finding: Annotated[str, typer.Option("--finding", help="Caminho do finding (ou vazio).")] = "",
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Finaliza a sessão: grava duração/status/missing/finding no frontmatter."""
    from prumo_assist import PrumoError

    with cli_run(json_mode=json_mode, catches=(ValueError, FileNotFoundError)) as console:
        if status not in ("completed", "abandoned", "partial"):
            raise PrumoError("--status deve ser completed|abandoned|partial.")
        missing_list = parse_json_list(missing, "--missing")
        finding_path = Path(finding) if finding else None
        study.finalize_session(
            log_path,
            duration_minutes=duration,
            status=cast("typing.Literal['completed', 'abandoned', 'partial']", status),
            references_missing=missing_list,
            finding_archived=finding_path,
        )
        console.success("Sessão finalizada.")
        console.emit({"ok": True, "status": status})
```

Adicione `import typing` ao topo do arquivo (para o `cast`). (Alternativa equivalente, se preferir evitar `import typing`: importe `Literal` de `typing` e use `cast(Literal["completed", "abandoned", "partial"], status)`.)

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/wiki/test_cli_study.py -q -k study_finish`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/wiki/cli.py tests/unit/wiki/test_cli_study.py
git commit -m "feat(wiki): prumo wiki study-finish (substitui finalize_session.py)"
```

---

### Task 5: `prumo wiki finding` (TDD)

**Files:**
- Modify: `src/prumo_assist/domains/wiki/cli.py`
- Test: `tests/unit/wiki/test_cli_study.py`

Contexto: substitui `archive_finding.py` (active-learning) E o snippet de `wiki-query`. Corpo markdown via stdin. Domínio: `findings.archive_as_finding(*, pj_path, slug, title, body, sources, date, tags=None, generator='wiki-query') -> Path` (levanta `FileNotFoundError` se `pj/docs` não existe).

- [ ] **Step 1: Escrever o teste que falha**

Append to `tests/unit/wiki/test_cli_study.py`:

```python
def test_finding_arquiva_corpo_do_stdin(tmp_path: Path) -> None:
    pj = _pj(tmp_path)
    body = "## Pergunta\n\nO que é RWE?\n\n## Resposta\n\nReal-world evidence."
    result = runner.invoke(
        app,
        ["wiki", "finding", "--slug", "rwe-definicao", "--title", "RWE",
         "--date", "2026-06-14", "--generator", "active-learning",
         "--path", str(pj), "--json"],
        input=body,
    )
    assert result.exit_code == 0, result.output
    out = Path(json.loads(result.stdout)["finding_path"])
    assert out.exists()
    assert "Real-world evidence." in out.read_text(encoding="utf-8")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/wiki/test_cli_study.py -q -k finding`
Expected: FAIL — `No such command 'finding'`.

- [ ] **Step 3: Implementar o subcomando**

Adicione a `wiki/cli.py`:

```python
@wiki_app.command("finding")
def finding_command(
    slug: Annotated[str, typer.Option("--slug", help="Slug do finding.")],
    title: Annotated[str, typer.Option("--title", help="Título.")],
    date: Annotated[str, typer.Option("--date", help="Data ISO YYYY-MM-DD.")],
    tags: Annotated[str, typer.Option("--tags", help="Array JSON de tags.")] = "[]",
    sources: Annotated[str, typer.Option("--sources", help="Array JSON de wikilinks.")] = "[]",
    generator: Annotated[str, typer.Option("--generator", help="Skill geradora.")] = "wiki-query",
    path: Annotated[Path, typer.Option("--path", help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Arquiva um finding (corpo markdown via stdin) em docs/wiki/findings/."""
    with cli_run(json_mode=json_mode, catches=(ValueError, FileNotFoundError)) as console:
        body = read_stdin_text()
        tags_list = parse_json_list(tags, "--tags")
        sources_list = parse_json_list(sources, "--sources")
        out = findings.archive_as_finding(
            pj_path=path.resolve(), slug=slug, title=title, body=body,
            sources=sources_list, date=date, tags=tags_list, generator=generator,
        )
        console.success(f"Finding arquivado: {out}")
        console.emit({"finding_path": str(out)})
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/wiki/test_cli_study.py -q`
Expected: todos os testes do arquivo passam (`7 passed`).

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/wiki/cli.py tests/unit/wiki/test_cli_study.py
git commit -m "feat(wiki): prumo wiki finding (substitui archive_finding.py; corpo via stdin)"
```

---

### Task 6: Re-export em `wiki/api.py`

**Files:**
- Modify: `src/prumo_assist/domains/wiki/api.py`

Contexto: re-export puro (sem wrapper), em ordem alfabética no `__all__`, para `from prumo_assist import api; api.wiki.<fn>(...)` em notebooks.

- [ ] **Step 1: Adicionar os re-exports**

Em `src/prumo_assist/domains/wiki/api.py`, adicione (mantendo os existentes):

```python
from prumo_assist.domains.wiki.findings import archive_as_finding
from prumo_assist.domains.wiki.study import (
    append_step,
    create_session_log,
    finalize_session,
)
```

E inclua os 4 nomes no `__all__` existente, em ordem alfabética (ex.: `"append_step"`, `"archive_as_finding"`, `"create_session_log"`, `"finalize_session"` junto aos que já estão lá — `index`, `lint`, `stats`, etc.).

- [ ] **Step 2: Verificar import e mypy**

Run: `uv run python -c "from prumo_assist.domains.wiki import api; print(sorted(api.__all__))" && uv run mypy`
Expected: lista inclui os 4 nomes novos; mypy verde.

- [ ] **Step 3: Commit**

```bash
git add src/prumo_assist/domains/wiki/api.py
git commit -m "feat(wiki): re-exporta study/findings na api pública"
```

---

### Task 7: Atualizar a prosa de `active-learning` (5 invocações → `prumo wiki`)

**Files:**
- Modify: `skills/active-learning/SKILL.md`

Contexto: trocar cada `uv run python ${CLAUDE_SKILL_DIR}/scripts/<x>.py ...` pela chamada `prumo wiki ...`. NÃO alterar a lógica do fluxo dos 5 steps, só o comando. As substituições exatas:

- [ ] **Step 1: Substituir as 5 invocações**

(a) § Resolver tópico — a chamada a `slug.py` deixa de existir como passo separado: o slug agora vem no `--json` de `study-start`. Substituir o bloco do `slug.py` + o bloco do `create_log.py` por um único bloco:

```bash
prumo wiki study-start "<topic raw>" \
    --date "<hoje ISO>" \
    --sources '[<lista JSON de wikilinks>]' --json
```

Instrução acompanhante: "Capture `slug` e `log_path` do JSON impresso para os passos seguintes."

(b) § Loop dos 5 steps — substituir o bloco do `append_step.py` por:

```bash
echo '{"question":"...","answer":"...","feedback":"...","citations":["[[@k]]"],"references_missing":[]}' \
  | prumo wiki study-step --log-path "<log_path>" --step <recall|anchor|connect|apply|reflect> --json
```

(c) § Step 5 Reflect — substituir o bloco `archive_finding.py` (heredoc BODY) por:

```bash
cat <<'BODY' | prumo wiki finding \
    --slug "<slug-derivado>" \
    --title "<título-do-insight>" \
    --date "<hoje ISO>" \
    --tags '[<tags JSON>]' \
    --sources '[<wikilinks JSON>]' \
    --generator active-learning --json
## Pergunta

<pergunta sintetizada>

## Resposta consolidada

<síntese da definição/insight>

## Evidências

<wikilinks>

## Limitações

<ressalvas>
BODY
```

Instrução: "Capture `finding_path` do JSON para o `study-finish`."

(d) § Finalizar — substituir o bloco `finalize_session.py` por:

```bash
prumo wiki study-finish \
    --log-path "<log_path>" \
    --duration <elapsed_minutes> \
    --status completed \
    --missing '[<lista JSON de REF FALTANTE>]' \
    --finding "<finding_path ou string vazia>" --json
```

- [ ] **Step 2: Verificar que não sobrou referência a scripts/**

Run: `grep -n "CLAUDE_SKILL_DIR\|scripts/\|from prumo_assist\|python -c" skills/active-learning/SKILL.md || echo "limpo"`
Expected: `limpo`.

- [ ] **Step 3: Atualizar Pressupostos (lar único da checagem de CLI)**

Na seção Pressupostos de `skills/active-learning/SKILL.md`, adicione a linha:
`- O CLI \`prumo\` precisa estar no PATH (rode \`prumo doctor\`; se ausente: \`uv tool install git+https://github.com/raphaelfh/prumo-assist\`).`

- [ ] **Step 4: Commit**

```bash
git add skills/active-learning/SKILL.md
git commit -m "refactor(active-learning): chama prumo wiki em vez de scripts/ (ponte CLI)"
```

---

### Task 8: Atualizar a prosa de `wiki-query` (finding → `prumo wiki finding`)

**Files:**
- Modify: `skills/wiki-query/SKILL.md`

Contexto: `wiki-query` importa `from prumo_assist.domains.wiki.findings import archive_as_finding` num snippet `python3 -c`. Trocar pelo subcomando.

- [ ] **Step 1: Substituir o snippet de arquivamento**

Localize o bloco `python3 -c '...archive_as_finding...'` (≈ linha 86) e substitua por:

```bash
cat <<'BODY' | prumo wiki finding \
    --slug "<slug>" \
    --title "<título>" \
    --date "<hoje ISO>" \
    --sources '[<wikilinks JSON>]' \
    --generator wiki-query --json
<corpo markdown da resposta a arquivar>
BODY
```

(O `--generator` default já é `wiki-query`, mas explicitamos para clareza.)

- [ ] **Step 2: Verificar e adicionar Pressuposto do CLI**

Run: `grep -n "from prumo_assist\|python3 -c\|python -c" skills/wiki-query/SKILL.md || echo "limpo"`
Expected: `limpo`.

Adicione a mesma linha de Pressuposto do CLI (Task 7 Step 3) à seção de Pressupostos de `skills/wiki-query/SKILL.md`.

- [ ] **Step 3: Commit**

```bash
git add skills/wiki-query/SKILL.md
git commit -m "refactor(wiki-query): chama prumo wiki finding em vez de import inline"
```

---

### Task 9: Deletar `skills/active-learning/scripts/` + gates finais

**Files:**
- Delete: `skills/active-learning/scripts/` (5 arquivos)

Contexto: a lógica foi para `prumo wiki`. Os scripts de `formulate-picot` permanecem (são tratados na Fase A2). `wiki-query` não tinha scripts.

- [ ] **Step 1: Remover os scripts**

```bash
git rm skills/active-learning/scripts/slug.py \
       skills/active-learning/scripts/create_log.py \
       skills/active-learning/scripts/append_step.py \
       skills/active-learning/scripts/archive_finding.py \
       skills/active-learning/scripts/finalize_session.py
```

- [ ] **Step 2: Confirmar que active-learning não tem mais scripts**

Run: `ls skills/active-learning/scripts/ 2>/dev/null || echo "scripts/ removido"`
Expected: `scripts/ removido` (ou diretório vazio — então `rmdir skills/active-learning/scripts`).

- [ ] **Step 3: Suíte completa + gates**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run python .github/scripts/gen_indexes.py --check`
Expected: tudo verde (370+ testes; o `test_guidelines_present.py` e o índice de skills continuam passando — nenhum skill foi removido, só scripts).

- [ ] **Step 4: Commit**

```bash
git add -A skills/active-learning/
git commit -m "chore(active-learning): remove scripts/ (lógica migrada para prumo wiki)"
```

---

## Self-Review

**Cobertura do escopo A1:** os 5 scripts de active-learning → 4 subcomandos `prumo wiki` (slug+create_log colapsados em study-start) ✓; wiki-query finding → `prumo wiki finding` ✓; scripts deletados ✓; prosa das 2 skills atualizada ✓; Pressuposto de CLU num lar único (`prumo doctor`) ✓. Fora de A1 (planos A2–A4): protocol, paper, write, hook, release.

**Placeholders:** nenhum — todo passo tem código/comando completo e saída esperada.

**Consistência de tipos:** `slugify(str)->str`, `create_session_log(*, pj_path, topic, date, sources_consulted)->Path`, `append_step(log_path, step)->None` com `StepLog(**payload)`, `finalize_session(log_path, *, duration_minutes, status: Literal, references_missing, finding_archived)->None` (status validado + `cast`), `archive_as_finding(*, pj_path, slug, title, body, sources, date, tags, generator)->Path` — todas batem com as assinaturas reais do domínio (workflow `gather-phase-a-facts`). Helpers `read_stdin_text`/`read_stdin_json`/`parse_json_list` consistentes entre Task 1 e os subcomandos.

**Nota de design honrada:** nenhuma lógica de domínio nova — só fachadas + 1 helper de I/O. `count_records`/`template_artifact` (núcleo fechado da Seção 0.5) ficam para a Fase C, com consumidor (Princípio VI).
