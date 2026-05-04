# `active-learning` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar a skill `/prumo-assist:active-learning` (tutor metacognitivo Socrático em 5 steps) com helpers Python para session log + refator DRY do `archive_as_finding` (compartilhado com `wiki-query`).

**Architecture:** Adiciona ao domínio `wiki/` existente: `findings.py` (refatorado de inline-prose do `wiki-query` SKILL.md), `study.py` (helpers de session log), `schemas/v1.py` (`SessionLog/v1`, `StepLog`). 1 SKILL.md nova (~120 linhas). Refator backward-compat do `wiki-query` SKILL.md pra chamar `findings.archive_as_finding`.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, ruff strict, mypy strict.

---

## File Structure

| Caminho | Ação | Responsabilidade |
|---|---|---|
| `src/prumo_assist/domains/wiki/findings.py` | **Create** | `archive_as_finding(pj, slug, title, body, sources, ...)` — extrai pattern do `wiki-query` SKILL.md |
| `src/prumo_assist/domains/wiki/schemas/__init__.py` | **Create** | Vazio |
| `src/prumo_assist/domains/wiki/schemas/v1.py` | **Create** | `SessionLog/v1`, `StepLog` |
| `src/prumo_assist/domains/wiki/study.py` | **Create** | `session_log_path`, `create_session_log`, `append_step`, `finalize_session` |
| `src/prumo_assist/domains/wiki/api.py` | **Modify** | Re-exports |
| `skills/wiki-query/SKILL.md` | **Modify** | Trocar prose-inline-archive por chamada a `findings.archive_as_finding` |
| `skills/active-learning/SKILL.md` | **Create** | Prompt agêntico do tutor (5 steps + context gathering + reflect+archive) |
| `tests/unit/wiki/test_findings.py` | **Create** | Tests do archive_as_finding |
| `tests/unit/wiki/test_schemas_v1.py` | **Create** | Tests SessionLog/v1 |
| `tests/unit/wiki/test_study.py` | **Create** | Tests dos helpers de log |
| `README.md` | **Modify** | Adicionar `active-learning` na tabela de skills |
| `docs/actions-by-context.md` | **Modify** | Materializar gatilho "Quero estudar conceito X usando minhas próprias fontes" (apontar pra skill) |

---

## Task 1: Refator DRY — extrair `archive_as_finding`

**Files:**
- Create: `src/prumo_assist/domains/wiki/findings.py`
- Test: `tests/unit/wiki/test_findings.py`
- Modify: `src/prumo_assist/domains/wiki/api.py`

- [ ] **Step 1: Write failing tests for `archive_as_finding`**

Create `tests/unit/wiki/test_findings.py`:

```python
"""Tests para archive_as_finding (extraído de wiki-query SKILL.md)."""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist.domains.wiki.findings import archive_as_finding


def _bootstrap(tmp_path: Path) -> Path:
    pj = tmp_path / "pj_demo"
    docs = pj / "docs"
    docs.mkdir(parents=True)
    (docs / "_index.md").write_text("# Wiki\n\n## Findings\n\n_(vazio)_\n")
    (docs / "_log.md").write_text("# Log\n")
    return pj


def test_archive_creates_finding_in_default_location(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    out = archive_as_finding(
        pj_path=pj,
        slug="curvas-roc-limiar",
        title="Curvas ROC e escolha de limiar",
        body="Sintetiza que exchangeability quebra; a correção C compensa.",
        sources=["[[@hanley1982roc]]", "[[concepts/curvas-roc]]"],
        date="2026-05-03",
    )
    assert out.exists()
    assert out.name == "curvas-roc-limiar.md"
    text = out.read_text()
    assert text.startswith("---\n")
    assert "id: curvas-roc-limiar" in text
    assert "type: finding" in text
    assert "Curvas ROC e escolha de limiar" in text
    assert "exchangeability quebra" in text


def test_archive_uses_extended_wiki_when_dir_exists(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    (pj / "docs" / "wiki" / "findings").mkdir(parents=True)
    out = archive_as_finding(
        pj_path=pj, slug="x", title="T", body="B", sources=[], date="2026-05-03",
    )
    assert "wiki" in out.parts
    assert out == pj / "docs" / "wiki" / "findings" / "x.md"


def test_archive_falls_back_to_docs_findings(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    out = archive_as_finding(
        pj_path=pj, slug="y", title="T", body="B", sources=[], date="2026-05-03",
    )
    assert out == pj / "docs" / "findings" / "y.md"


def test_archive_updates_index(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    archive_as_finding(
        pj_path=pj, slug="my-finding", title="My Finding", body="B",
        sources=[], date="2026-05-03",
    )
    index_text = (pj / "docs" / "_index.md").read_text()
    assert "[[my-finding]]" in index_text or "[[findings/my-finding]]" in index_text


def test_archive_appends_log(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    archive_as_finding(
        pj_path=pj, slug="my-finding", title="My Finding", body="B",
        sources=["[[@a]]"], date="2026-05-03", generator="active-learning",
    )
    log_text = (pj / "docs" / "_log.md").read_text()
    assert "2026-05-03" in log_text
    assert "active-learning" in log_text
    assert "my-finding" in log_text


def test_archive_yaml_includes_tags(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    out = archive_as_finding(
        pj_path=pj, slug="z", title="T", body="B", sources=[],
        date="2026-05-03", tags=["curvas-roc", "mnar"],
    )
    assert "tags:" in out.read_text()


def test_archive_idempotent_overwrite(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    archive_as_finding(
        pj_path=pj, slug="x", title="T1", body="B1", sources=[], date="2026-05-03",
    )
    archive_as_finding(
        pj_path=pj, slug="x", title="T2", body="B2", sources=[], date="2026-05-03",
    )
    out = pj / "docs" / "findings" / "x.md"
    text = out.read_text()
    assert "T2" in text
    assert "B2" in text
    assert "T1" not in text


def test_archive_raises_when_pj_invalid(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        archive_as_finding(
            pj_path=tmp_path / "nope",
            slug="x", title="T", body="B", sources=[], date="2026-05-03",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `mkdir -p tests/unit/wiki && touch tests/unit/wiki/__init__.py && uv run pytest tests/unit/wiki/test_findings.py -v`
Expected: FAIL — module `findings` not defined.

- [ ] **Step 3: Implement `findings.py`**

Create `src/prumo_assist/domains/wiki/findings.py`:

```python
"""``archive_as_finding`` — cria docs/wiki/findings/<slug>.md (ou fallback).

Extraído da prose inline do ``wiki-query`` SKILL.md pra reuso pela skill
``active-learning``. Pattern: YAML frontmatter (id, type, title, added,
status, tags, sources) + body com seções fixas. Atualiza ``_index.md`` e
``_log.md``.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _resolve_findings_dir(pj_path: Path) -> Path:
    """Prefere ``docs/wiki/findings/`` se ``docs/wiki/`` existe; senão ``docs/findings/``."""
    extended = pj_path / "docs" / "wiki" / "findings"
    if extended.parent.exists():
        extended.mkdir(parents=True, exist_ok=True)
        return extended
    fallback = pj_path / "docs" / "findings"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def archive_as_finding(
    *,
    pj_path: Path,
    slug: str,
    title: str,
    body: str,
    sources: list[str],
    date: str,
    tags: list[str] | None = None,
    generator: str = "wiki-query",
) -> Path:
    """Cria/sobrescreve docs/.../findings/<slug>.md, atualiza _index.md e _log.md.

    ``body`` é texto markdown livre que vai abaixo do frontmatter.
    ``sources`` é lista de wikilinks (strings como ``"[[@key]]"`` ou ``"[[page]]"``).
    ``generator`` identifica quem chamou (``"wiki-query"`` ou ``"active-learning"``).
    """
    if not (pj_path / "docs").exists():
        raise FileNotFoundError(
            f"{pj_path}/docs/ não existe. Rode `prumo init` ou crie manualmente."
        )

    findings_dir = _resolve_findings_dir(pj_path)
    finding_path = findings_dir / f"{slug}.md"

    fm = {
        "id": slug,
        "type": "finding",
        "title": title,
        "added": date,
        "status": "active",
        "tags": tags or [],
        "sources": sources,
    }
    yaml_block = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
    text = f"---\n{yaml_block}\n---\n\n# {title}\n\n{body.strip()}\n"
    finding_path.write_text(text, encoding="utf-8")

    _append_to_index(pj_path, slug, title)
    _append_to_log(pj_path, slug, generator, date)

    return finding_path


def _append_to_index(pj_path: Path, slug: str, title: str) -> None:
    """Adiciona linha ``- [[<slug>]] — <title>`` em § Findings do _index.md."""
    index = pj_path / "docs" / "_index.md"
    if not index.exists():
        index.write_text("# Wiki\n\n## Findings\n\n", encoding="utf-8")

    text = index.read_text(encoding="utf-8")
    line = f"- [[{slug}]] — {title}"
    if line in text:
        return
    if "## Findings" not in text:
        text = text.rstrip() + "\n\n## Findings\n\n"
    text = text.replace("## Findings\n\n", f"## Findings\n\n{line}\n", 1)
    index.write_text(text, encoding="utf-8")


def _append_to_log(pj_path: Path, slug: str, generator: str, date: str) -> None:
    """Anexa entrada ao topo de _log.md."""
    log = pj_path / "docs" / "_log.md"
    if not log.exists():
        log.write_text("# Log\n", encoding="utf-8")

    head = log.read_text(encoding="utf-8")
    entry = (
        f"\n## [{date}] {generator} | finding arquivado\n\n"
        f"- [[{slug}]]\n"
    )
    log.write_text(head.rstrip() + "\n" + entry, encoding="utf-8")
```

- [ ] **Step 4: Run tests pass**

Run: `uv run pytest tests/unit/wiki/test_findings.py -v`
Expected: 8 tests PASS

- [ ] **Step 5: Re-export em `domains/wiki/api.py`**

Edit `src/prumo_assist/domains/wiki/api.py`. Add at top:

```python
from prumo_assist.domains.wiki.findings import archive_as_finding
```

Add `"archive_as_finding"` em `__all__` (alfabético).

- [ ] **Step 6: Update `wiki-query` SKILL.md to call helper**

Edit `skills/wiki-query/SKILL.md`. Find the section "### 5. Oferecer arquivamento" (around line 64). Replace the inline file-creation steps (lines that say "Criar `docs/findings/<slug>.md` com frontmatter:" and what follows up to "Atualizar `docs/_index.md`...") with:

```markdown
### 5. Oferecer arquivamento

Depois da resposta, perguntar **exatamente uma vez**:

> Quer arquivar essa resposta como finding? (`docs/wiki/findings/<slug>.md` ou fallback `docs/findings/<slug>.md`) — útil se a síntese for reutilizada.

Se **sim**, executar via `Bash`:

```bash
python3 -c '
from pathlib import Path
from prumo_assist.domains.wiki.findings import archive_as_finding

out = archive_as_finding(
    pj_path=Path("."),
    slug="<slug>",
    title="<pergunta ou síntese>",
    body=(
        "## Pergunta\n\n<pergunta>\n\n"
        "## Resposta consolidada\n\n<resposta>\n\n"
        "## Evidências\n\n<lista de wikilinks>\n\n"
        "## Limitações\n\n<ressalvas>\n"
    ),
    sources=["[[<page-a>]]", "[[@<citekey>]]"],
    date="<hoje ISO>",
    tags=[<tags>],
    generator="wiki-query",
)
print(f"finding: {out}")
'
```

A função cuida de criar o arquivo, atualizar `_index.md` e `_log.md` em uma operação atômica (vide ``prumo_assist.domains.wiki.findings``).

Se **não**: registrar no log com:
```bash
python3 -c '
from pathlib import Path
log = Path("docs/_log.md")
log.write_text(log.read_text() + "\n## [<data>] wiki-query | <pergunta curta>\n\n- Respondida sem arquivar.\n")
'
```
```

(Preserve all surrounding sections of the SKILL.md.)

- [ ] **Step 7: Run all tests + lint + types**

Run: `uv run pytest -q`
Expected: all PASS (count = baseline + 8 novos).

Run: `uv run ruff check src/ tests/`
Run: `uv run --extra dev mypy src/prumo_assist tests`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add src/prumo_assist/domains/wiki/findings.py src/prumo_assist/domains/wiki/api.py skills/wiki-query/SKILL.md tests/unit/wiki/__init__.py tests/unit/wiki/test_findings.py
git commit -m "refactor(wiki): extract archive_as_finding from wiki-query SKILL"
```

---

## Task 2: `SessionLog/v1` schema + `study.py` helpers

**Files:**
- Create: `src/prumo_assist/domains/wiki/schemas/__init__.py`
- Create: `src/prumo_assist/domains/wiki/schemas/v1.py`
- Create: `src/prumo_assist/domains/wiki/study.py`
- Test: `tests/unit/wiki/test_schemas_v1.py`
- Test: `tests/unit/wiki/test_study.py`

- [ ] **Step 1: Create schemas directory + write failing tests**

```bash
mkdir -p src/prumo_assist/domains/wiki/schemas
touch src/prumo_assist/domains/wiki/schemas/__init__.py
```

Create `tests/unit/wiki/test_schemas_v1.py`:

```python
"""Tests para SessionLog/v1 + StepLog."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from prumo_assist.domains.wiki.schemas.v1 import SessionLog, StepLog


def test_step_log_minimal() -> None:
    s = StepLog(
        step_name="recall",
        question="Defina X",
        answer="X é Y",
        feedback="correto, mas faltou Z",
    )
    assert s.citations == []
    assert s.references_missing == []


def test_step_log_invalid_step_name() -> None:
    with pytest.raises(ValidationError):
        StepLog(step_name="invented", question="q", answer="a", feedback="f")


def test_session_log_starts_in_progress() -> None:
    s = SessionLog(topic="x", date="2026-05-03")
    assert s.status == "in-progress"
    assert s.steps == []
    assert s.duration_minutes == 0
    assert s.finding_archived is None


def test_session_log_completed_status() -> None:
    s = SessionLog(topic="x", date="2026-05-03", status="completed")
    assert s.status == "completed"


def test_session_log_invalid_status() -> None:
    with pytest.raises(ValidationError):
        SessionLog(topic="x", date="2026-05-03", status="bogus")


def test_session_log_schema_version() -> None:
    s = SessionLog(topic="x", date="2026-05-03")
    assert s.schema_version == "SessionLog/v1"
```

Create `tests/unit/wiki/test_study.py`:

```python
"""Tests para helpers de session log."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.wiki.schemas.v1 import StepLog
from prumo_assist.domains.wiki.study import (
    append_step,
    create_session_log,
    finalize_session,
    session_log_path,
)


def _bootstrap(tmp_path: Path) -> Path:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    return pj


def test_session_log_path_extended_wiki(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    (pj / "docs" / "wiki").mkdir()
    out = session_log_path(pj, "curvas-roc", "2026-05-03")
    assert out == pj / "docs" / "wiki" / "study-sessions" / "curvas-roc-2026-05-03.md"


def test_session_log_path_fallback(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    out = session_log_path(pj, "curvas-roc", "2026-05-03")
    assert out == pj / "docs" / "study-sessions" / "curvas-roc-2026-05-03.md"


def test_create_session_log_writes_yaml_frontmatter(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    out = create_session_log(
        pj_path=pj,
        topic="curvas-roc",
        date="2026-05-03",
        sources_consulted=["[[@hanley1982roc]]", "[[concepts/curvas-roc]]"],
    )
    assert out.exists()
    text = out.read_text()
    assert text.startswith("---\n")
    assert "topic: curvas-roc" in text
    assert "date: '2026-05-03'" in text or 'date: "2026-05-03"' in text
    assert "schema_version: SessionLog/v1" in text
    assert "in-progress" in text
    assert "[[@hanley1982roc]]" in text


def test_append_step_adds_section(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    log_path = create_session_log(
        pj_path=pj, topic="x", date="2026-05-03", sources_consulted=[],
    )
    append_step(
        log_path,
        StepLog(
            step_name="recall",
            question="Defina X",
            answer="X é Y",
            feedback="correto",
            citations=["[[@a]]"],
        ),
    )
    text = log_path.read_text()
    assert "## 1. Recall" in text
    assert "**Pergunta:** Defina X" in text
    assert "**Resposta:** X é Y" in text
    assert "**Feedback:** correto" in text


def test_append_multiple_steps_sequentially_numbered(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    log_path = create_session_log(
        pj_path=pj, topic="x", date="2026-05-03", sources_consulted=[],
    )
    for name in ("recall", "anchor", "connect"):
        append_step(
            log_path,
            StepLog(step_name=name, question="q", answer="a", feedback="f"),
        )
    text = log_path.read_text()
    assert "## 1. Recall" in text
    assert "## 2. Anchor" in text
    assert "## 3. Connect" in text


def test_finalize_session_updates_yaml(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    log_path = create_session_log(
        pj_path=pj, topic="x", date="2026-05-03", sources_consulted=[],
    )
    finalize_session(
        log_path,
        duration_minutes=18,
        status="completed",
        references_missing=["ROC multiclasse"],
        finding_archived=Path("docs/findings/x.md"),
    )
    text = log_path.read_text()
    assert "duration_minutes: 18" in text
    assert "status: completed" in text
    assert "ROC multiclasse" in text
    assert "docs/findings/x.md" in text
```

- [ ] **Step 2: Run tests fail**

Run: `uv run pytest tests/unit/wiki/test_schemas_v1.py tests/unit/wiki/test_study.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement schemas**

Create `src/prumo_assist/domains/wiki/schemas/v1.py`:

```python
"""``SessionLog/v1`` — schema do log de sessão de active-learning."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

StepName = Literal["recall", "anchor", "connect", "apply", "reflect"]
SessionStatus = Literal["in-progress", "completed", "abandoned", "partial"]


class StepLog(BaseModel):
    """Log de 1 dos 5 steps da sessão."""

    step_name: StepName
    question: str = Field(..., min_length=1)
    answer: str = ""
    feedback: str = ""
    citations: list[str] = []
    references_missing: list[str] = []


class SessionLog(BaseModel):
    """Log canônico de uma sessão."""

    schema_version: Literal["SessionLog/v1"] = "SessionLog/v1"
    topic: str = Field(..., min_length=1)
    date: str = Field(..., description="ISO YYYY-MM-DD")
    duration_minutes: int = 0
    status: SessionStatus = "in-progress"
    sources_consulted: list[str] = []
    steps: list[StepLog] = []
    references_missing: list[str] = []
    finding_archived: Path | None = None
```

- [ ] **Step 4: Implement `study.py`**

Create `src/prumo_assist/domains/wiki/study.py`:

```python
"""Helpers para session log de ``active-learning``.

Mantém o log em Markdown com YAML frontmatter (``SessionLog/v1``). Cada
step vira seção ``## N. <Step Name>`` com pergunta/resposta/feedback/citations.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml

from prumo_assist.domains.wiki.schemas.v1 import SessionLog, StepLog

_STEP_TITLES = {
    "recall": "Recall",
    "anchor": "Anchor",
    "connect": "Connect",
    "apply": "Apply",
    "reflect": "Reflect",
}
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def session_log_path(pj_path: Path, topic: str, date: str) -> Path:
    """``docs/wiki/study-sessions/<topic>-<date>.md`` ou fallback ``docs/study-sessions/...``."""
    extended = pj_path / "docs" / "wiki"
    if extended.exists():
        out = extended / "study-sessions" / f"{topic}-{date}.md"
    else:
        out = pj_path / "docs" / "study-sessions" / f"{topic}-{date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def create_session_log(
    *,
    pj_path: Path,
    topic: str,
    date: str,
    sources_consulted: list[str],
) -> Path:
    """Cria arquivo com YAML + heading; corpo aguarda ``append_step``."""
    log = SessionLog(topic=topic, date=date, sources_consulted=sources_consulted)
    path = session_log_path(pj_path, topic, date)
    path.write_text(_render_skeleton(log), encoding="utf-8")
    return path


def append_step(log_path: Path, step: StepLog) -> None:
    """Anexa seção ``## N. <Step Name>`` ao final do log com p/r/f/citations."""
    text = log_path.read_text(encoding="utf-8")
    n = _count_existing_steps(text) + 1
    title = _STEP_TITLES[step.step_name]
    block = [
        f"## {n}. {title}",
        "",
        f"**Pergunta:** {step.question}",
        "",
        f"**Resposta:** {step.answer or '_(sem resposta)_'}",
        "",
        f"**Feedback:** {step.feedback or '_(sem feedback)_'}",
        "",
    ]
    if step.citations:
        block.append("**Citações:** " + " ".join(step.citations))
        block.append("")
    if step.references_missing:
        block.append("**Refs faltando:**")
        for r in step.references_missing:
            block.append(f"- {r}")
        block.append("")
    appended = text.rstrip() + "\n\n" + "\n".join(block) + "\n"
    log_path.write_text(appended, encoding="utf-8")


def finalize_session(
    log_path: Path,
    *,
    duration_minutes: int,
    status: Literal["completed", "abandoned", "partial"],
    references_missing: list[str],
    finding_archived: Path | None,
) -> None:
    """Atualiza YAML frontmatter com fechamento da sessão."""
    text = log_path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"{log_path}: sem frontmatter YAML.")
    fm: dict = yaml.safe_load(m.group(1)) or {}
    fm["duration_minutes"] = duration_minutes
    fm["status"] = status
    fm["references_missing"] = references_missing
    fm["finding_archived"] = str(finding_archived) if finding_archived else None
    new_yaml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
    body = text[m.end():]
    log_path.write_text(f"---\n{new_yaml}\n---\n{body}", encoding="utf-8")


def _render_skeleton(log: SessionLog) -> str:
    fm = log.model_dump(mode="python", exclude={"steps"})
    fm["finding_archived"] = None  # explicito no YAML
    yaml_block = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
    body = [
        f"# Study session — {log.topic} ({log.date})",
        "",
        "## Fontes consultadas",
        "",
    ]
    body.extend(f"- {s}" for s in log.sources_consulted)
    body.append("")
    return f"---\n{yaml_block}\n---\n\n" + "\n".join(body) + "\n"


def _count_existing_steps(text: str) -> int:
    return len(re.findall(r"^## \d+\. ", text, flags=re.MULTILINE))
```

- [ ] **Step 5: Re-export em `api.py`**

Edit `src/prumo_assist/domains/wiki/api.py`. Add imports:

```python
from prumo_assist.domains.wiki.schemas.v1 import SessionLog, StepLog
from prumo_assist.domains.wiki.study import (
    append_step,
    create_session_log,
    finalize_session,
    session_log_path,
)
```

Add to `__all__` em ordem alfabética.

- [ ] **Step 6: Tests pass + lint**

Run: `uv run pytest tests/unit/wiki/ -v`
Expected: all PASS.

Run: `uv run ruff check src/prumo_assist/domains/wiki tests/unit/wiki`
Run: `uv run --extra dev mypy src/prumo_assist/domains/wiki`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add src/prumo_assist/domains/wiki/schemas src/prumo_assist/domains/wiki/study.py src/prumo_assist/domains/wiki/api.py tests/unit/wiki/test_schemas_v1.py tests/unit/wiki/test_study.py
git commit -m "feat(wiki): SessionLog/v1 schema + study.py helpers"
```

---

## Task 3: SKILL.md `active-learning`

**Files:**
- Create: `skills/active-learning/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

Create `skills/active-learning/SKILL.md`:

```markdown
---
name: active-learning
description: "Conduz uma sessão de estudo Socrática estruturada em 5 steps (Recall → Anchor → Connect → Apply → Reflect) sobre um tópico específico, ancorada nas fontes do projeto (wiki + acervo). Sessão ad-hoc curta (15-25 min). Citação strict (só citekeys do acervo + [REF FALTANTE]). Log estruturado em docs/wiki/study-sessions/<topic>-<data>.md (ou fallback). No Reflect step, oferece arquivar insight como finding. Invocar quando o usuário pedir 'me ensina X', 'estudar curvas ROC', 'me coloca à prova sobre Y', 'preciso fixar Z', '/active-learning <topic>', ou ao terminar de ler papers e querer consolidar entendimento."
prumo:
  version: 1.0.0
  schema: SessionLog/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~8-15k tokens
  inputs:
    topic: optional (positional; senão skill pergunta)
---

# Active Learning — tutor metacognitivo Socrático

Você é um tutor especializado em pesquisa clínica/ML conduzindo uma sessão de
estudo do pesquisador. Use a estrutura fixa de 5 steps abaixo. **Toda
afirmação que você fizer deve estar ancorada num citekey do acervo do projeto
ou num wikilink interno**. Se a fonte não está no acervo, emita
`[REF FALTANTE: <descrição>]` ao invés de inventar.

## Pressupostos

- cwd é um `pj_*` com `docs/_index.md` e `references/_references.bib` (mesmo que vazios).
- A parte determinística (criar log, anexar steps, arquivar finding) vive em
  `prumo_assist.domains.wiki.{study,findings}`. Você só cuida do agêntico.

## Fluxo

### 0. Resolver tópico

Se foi passado positional `<topic>`, use direto. Senão pergunte (1 vez):

> Qual tópico vamos estudar?

Slugify o tópico via:

```bash
python3 -c '
from prumo_assist.core.note_paths import slugify
print(slugify("'"$TOPIC_RAW"'"))
'
```

### 1. Context gathering (pré-sessão)

1. Buscar tópico no wiki via:
   - `mcp__qmd__query "<topic>"` se MCP disponível, senão `Grep` em `docs/`
   - `prumo paper find "<topic>"` para papers
   - `Read docs/_index.md`
2. Listar top 5-8 candidates ao usuário:

   > Encontrei N páginas e M papers sobre `<topic>`. Vou usar:
   > - [[concepts/curvas-roc]]
   > - [[@hanley1982roc]]
   > - ...
   >
   > Prosseguir? (Y/n)

3. Se >8 candidates, oferecer filtrar (1 rodada).

### 2. Criar log skeleton

Via `Bash`:

```bash
python3 -c '
from pathlib import Path
from prumo_assist.domains.wiki.study import create_session_log

p = create_session_log(
    pj_path=Path("."),
    topic="<slug>",
    date="<hoje ISO>",
    sources_consulted=[<lista de wikilinks>],
)
print(p)
'
```

Capture o path retornado para os append_step subsequentes.

### 3. Loop dos 5 steps

Para cada step, formule a pergunta usando o context, aguarde resposta do
usuário, avalie com citação strict, e anexe via `study.append_step`.

#### Step 1: Recall

> De memória, defina `<topic>` em 2-3 frases.

Avalie:
- O que estava correto? Cite `[[@key]]` que confirma.
- O que faltou? Aponte com citação.
- O que estava impreciso? Corrija com citação.

Anexar com `step_name="recall"`.

#### Step 2: Anchor

> Qual paper/página do wiki ancora cada parte da sua definição?

Avalie:
- Se o usuário citou fonte certa, valide.
- Se errou, mostre a fonte correta `[[@key]]` ou `[[page]]`.
- Se omitiu fonte de algo essencial, aponte.

Anexar com `step_name="anchor"`.

#### Step 3: Connect

Escolha um conceito-vizinho do wiki (proximidade no graph, ou tópico
relacionado encontrado no context gathering). Pergunte:

> Como `<topic>` se relaciona com `<conceito-vizinho>`? Onde divergem? Onde se complementam?

Avalie a conexão; aponte ligação faltando se houver.

Anexar com `step_name="connect"`.

#### Step 4: Apply

Crie um cenário hipotético plausível. Se PicotSpec do projeto existe
(`.claude/picot.toml`), use a `population`/`intervention` como base do
cenário. Senão invente plausível pra área.

> Cenário: <X concreto>. Como `<topic>` se comporta aqui? Quais resultados esperar?

Avalie o raciocínio aplicado.

Anexar com `step_name="apply"`.

#### Step 5: Reflect

> O que ainda está confuso? O que você gostaria de aprofundar numa próxima sessão?

Aguarde resposta do usuário.

Em seguida, ofereça arquivamento (1 vez):

> Quer arquivar a definição operacional/insight desta sessão como finding em `docs/wiki/findings/<sugestao-de-slug>.md`?

Se **sim**, executar via `Bash`:

```bash
python3 -c '
from pathlib import Path
from prumo_assist.domains.wiki.findings import archive_as_finding

out = archive_as_finding(
    pj_path=Path("."),
    slug="<slug-derivado>",
    title="<título-do-insight>",
    body=(
        "## Pergunta\n\n<pergunta sintetizada>\n\n"
        "## Resposta consolidada\n\n<síntese da definição/insight>\n\n"
        "## Evidências\n\n<wikilinks>\n\n"
        "## Limitações\n\n<ressalvas>\n"
    ),
    sources=[<lista de wikilinks>],
    date="<hoje>",
    tags=[<tags>],
    generator="active-learning",
)
print(out)
'
```

Capture o path para `finalize_session`.

Anexar step Reflect com `step_name="reflect"` antes do finalize.

### 4. Finalizar

Via `Bash`:

```bash
python3 -c '
from pathlib import Path
from prumo_assist.domains.wiki.study import finalize_session

finalize_session(
    Path("<log_path>"),
    duration_minutes=<elapsed>,
    status="completed",
    references_missing=[<lista de [REF FALTANTE]>],
    finding_archived=Path("<finding_path>") if "<finding_path>" else None,
)
'
```

### 5. Reportar ao usuário

```
Sessão concluída — `<topic>`
- Log: docs/wiki/study-sessions/<slug>-<data>.md
- Citações usadas: N
- Refs faltando: M (sugiro `prumo paper sync` em <descrições>)
- Finding arquivado: <path ou —>
```

## Boundaries

- **Nunca** invente citekey ou se sustente em conhecimento próprio sem fonte
  do projeto. Se a fonte não está no acervo, use `[REF FALTANTE: <desc>]`.
- **Nunca** ultrapasse 5 steps. Se a sessão precisa de mais, sugira segunda sessão.
- **Não** faça grade automatizado de "respondeu certo" — feedback é qualitativo.
- **Não** edite arquivo fora de `docs/wiki/study-sessions/` e (se autorizado)
  `docs/wiki/findings/`. `_index.md` e `_log.md` são atualizados pelo helper.

## Erros comuns

- `mcp__qmd__query` indisponível → fallback `Grep` + `Read`. Aviso no log: cobertura semântica reduzida.
- Acervo vazio → todas as citations viram `[REF FALTANTE]`. Avise no início e ofereça abortar.
- Mais de 50% das respostas precisam `[REF FALTANTE]` no Recall+Anchor → aborta com sugestão de ingest.
- Usuário abandona sessão → status = `partial`, `finalize_session` captura quantos steps completaram.
```

- [ ] **Step 2: Validate skill registry parses it**

Run: `uv run prumo skills --json | grep active-learning`
Expected: skill listed com `version: 1.0.0`, `determinism: agentic`.

- [ ] **Step 3: Commit**

```bash
git add skills/active-learning/SKILL.md
git commit -m "feat(skill): active-learning Socratic 5-step tutor"
```

---

## Task 4: Documentação

**Files:**
- Modify: `README.md`
- Modify: `docs/actions-by-context.md`

- [ ] **Step 1: Update README skills table**

Add row in `README.md` skills table (após `peer-review`):

```markdown
| `/prumo-assist:active-learning` | Tutor Socrático em 5 steps (recall → anchor → connect → apply → reflect) ancorado nas fontes do projeto. Sessão ad-hoc 15-25 min. Log estruturado em `docs/wiki/study-sessions/`. Pode arquivar insight como finding. |
```

- [ ] **Step 2: Update `docs/actions-by-context.md`**

Find a seção de Fase 2 com gatilho **"Quero estudar conceito X usando minhas próprias fontes"** (já existe, aponta pra skill futura). Substituir o body atual por:

```markdown
### "Quero estudar conceito X usando minhas próprias fontes"
*Claude como tutor metacognitivo. Sessão Socrática em 5 steps ancorada no acervo.*
1. `/prumo-assist:active-learning <topic>` — skill conduz: Recall → Anchor → Connect → Apply → Reflect.
2. Skill cria log em `docs/wiki/study-sessions/<topic>-<data>.md`.
3. No step Reflect, skill oferece arquivar insight como finding.
4. Citação strict — só citekeys do acervo. Refs faltantes viram `[REF FALTANTE]`.
```

- [ ] **Step 3: Final tests + lint**

Run: `uv run pytest -q && uv run ruff check . && uv run --extra dev mypy src/prumo_assist tests`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/actions-by-context.md
git commit -m "docs: list active-learning in README + actions-by-context"
```

---

## Final Verification

- [ ] Tests: `uv run pytest -q` (count = baseline + ~14 novos)
- [ ] Lint: `uv run ruff check .`
- [ ] Types: `uv run --extra dev mypy src/prumo_assist tests`
- [ ] Skill discoverable: `uv run prumo skills --json | grep active-learning`

---

## Self-review notes

**Spec coverage**:
- [x] D1 sessão ad-hoc on-demand: SKILL.md fluxo todo
- [x] D2 5 steps fixos: Step 3 do fluxo + StepLog schema constrains step_name
- [x] D3 log + arquivamento opcional: study.create_session_log + findings.archive_as_finding
- [x] D4 strict citation + [REF FALTANTE]: SKILL.md prompt + references_missing field
- [x] D5 helpers em domains/wiki + refator DRY: Task 1 + Task 2

**Type consistency**:
- `SessionLog`, `StepLog`, `StepName`, `SessionStatus` — consistent throughout
- `archive_as_finding` signature consistente (kwargs only) entre Task 1 e SKILL.md callsites
- `session_log_path`, `create_session_log`, `append_step`, `finalize_session` — assinaturas batem

**Out of scope (deferred per spec)**:
- Spaced repetition / scheduling
- Gamificação
- Multi-session por tópico
- `--method` flag adaptativo
