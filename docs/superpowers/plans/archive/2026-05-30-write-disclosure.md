---
status: implemented
verified: 2026-06-11
release: "0.61.0"
---

# `prumo write disclosure` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `prumo write disclosure`, which harvests the provenance signals artifacts already carry and emits a publisher-ready "AI use" declaration (PT + EN) plus a structured `AIDisclosure/v1` JSON; add `human_reviewed` to the canonical provenance `Meta`; and make findings stamp their `generator` into frontmatter so the disclosure can name them.

**Architecture:** A deterministic op `domains/write/disclosure.py` walks the project for Markdown frontmatter, normalizes the *heterogeneous* provenance that exists today — paper extracts write `extracted_model`/`extracted_at` into `references/notes/<key>/_meta.md`; findings write a `generator` — into `ProvRecord`s, aggregates by `(skill, model)`, and renders the statement. Thin CLI (`write_app`) over the pure function (Constitution Principle I). `Meta`/`build_meta` gain an additive `human_reviewed` field (Principle IV+V).

**Tech Stack:** Python 3.11+, Typer, Pydantic v2, PyYAML, pytest, `mypy --strict`, `ruff`.

---

## Reality check (read before coding)

The `core/provenance.py` module (`Meta`, `build_meta`, `TraceWriter`) is **defined but not yet wired into any domain** — `grep -rn "build_meta\|TraceWriter" src | grep -v core/provenance.py` returns nothing. So there is **no universal `_meta:` block** in artifacts today. What exists:

- **Paper extract** → `references/notes/<key>/_meta.md` gets flat keys `extracted_model`, `extracted_at`, `extracted_template_hash` (see `domains/paper/callout.py:122-124`).
- **Findings** → `docs/**/findings/<slug>.md` frontmatter has `id,type,title,added,status,tags,sources` but **not** `generator` (it only reaches `_log.md`; see `domains/wiki/findings.py:52-60`).

This plan therefore (a) harvests those real signals, (b) makes findings stamp `generator` (one-line fix, the right thing per Principle V), and (c) stays forward-compatible with a future canonical `_meta:` block. **Out of scope (YAGNI-gated):** retrofitting `build_meta` into every producer — note it as a follow-up, don't do it here.

## Verified existing APIs (use exactly these — do not invent)

```python
# core/provenance.py
@dataclass(frozen=True)
class Meta:  # fields: run_id, timestamp_utc, prumo_version, schema, skill, skill_version,
             #         model, input_hash, cost_usd, extra   →  .to_dict() drops None/{}/[]
def build_meta(*, schema, skill=None, skill_version=None, model=None, input_hash=None,
               cost_usd=None, run_id=None, extra=None) -> Meta
def now_utc() -> str   # "YYYY-MM-DDTHH:MM:SSZ"

# core/output.py     Console: .info/.success/.warn/.error/.emit(payload)   (NO print_* family)
#                    emit(dict)→json.dumps when json_mode else key:value; emit(str)→rich.print
# core/cli_op.py     cli_run(*, json_mode=False, catches=(), exit_code=1) -> Console
# domains/write/cli.py   write_app = typer.Typer(name="write", ...); Annotated-style options
# domains/write/api.py   re-exports compose/export/list_styles/... + schemas
# __init__.py            PrumoError (base)
# domains/wiki/findings.py  archive_as_finding(*, pj_path, slug, title, body, sources, date,
#                           tags=None, generator="wiki-query") -> Path
```

## Files

- Modify `src/prumo_assist/core/provenance.py` + `tests/unit/core/test_provenance.py` — `human_reviewed`.
- Modify `src/prumo_assist/domains/wiki/findings.py` + `tests/unit/wiki/test_findings.py` — stamp `generator`.
- Modify `src/prumo_assist/domains/write/schemas/v1.py` — `AIToolUse` + `AIDisclosure`.
- Create `src/prumo_assist/domains/write/disclosure.py` + `tests/unit/write/test_disclosure.py`.
- Modify `src/prumo_assist/domains/write/api.py` — re-export.
- Modify `src/prumo_assist/domains/write/cli.py` — `disclosure` subcommand.
- Modify `CHANGELOG.md`.

---

### Task 1: `human_reviewed` on `Meta` + `build_meta`

**Files:** Modify `src/prumo_assist/core/provenance.py`; Test `tests/unit/core/test_provenance.py`

- [ ] **Step 1: Write the failing tests** — add to `tests/unit/core/test_provenance.py`:

```python
def test_build_meta_human_reviewed_default_false() -> None:
    m = build_meta(schema="X/v1")
    assert m.human_reviewed is False
    assert m.to_dict()["human_reviewed"] is False


def test_build_meta_records_human_reviewed() -> None:
    m = build_meta(schema="X/v1", human_reviewed=True)
    assert m.to_dict()["human_reviewed"] is True
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/core/test_provenance.py -k human_reviewed -v`
Expected: FAIL — `build_meta() got an unexpected keyword argument 'human_reviewed'`.

- [ ] **Step 3: Implement** — in `Meta` (after `cost_usd: float | None = None`, before `extra`) add:

```python
    human_reviewed: bool = False
```

In `build_meta`, add `human_reviewed: bool = False,` to the signature (after `run_id`) and pass `human_reviewed=human_reviewed,` into the `Meta(...)` constructor.

Note: `Meta.to_dict()` drops values in `(None, {}, [])`; `False` is **not** dropped, so `human_reviewed` always appears. Good.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/core/test_provenance.py -v`
Expected: PASS (all, incl. existing `test_build_meta_omits_none_in_dict`).

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/core/provenance.py tests/unit/core/test_provenance.py
git commit -m "feat(provenance): add human_reviewed to Meta/build_meta"
```

---

### Task 2: findings stamp `generator` into frontmatter

**Files:** Modify `src/prumo_assist/domains/wiki/findings.py`; Test `tests/unit/wiki/test_findings.py`

- [ ] **Step 1: Write the failing test** — add to `tests/unit/wiki/test_findings.py`:

```python
def test_archive_stamps_generator_in_frontmatter(tmp_path: Path) -> None:
    import yaml

    from prumo_assist.domains.wiki.findings import archive_as_finding

    (tmp_path / "docs").mkdir()
    out = archive_as_finding(
        pj_path=tmp_path,
        slug="q1",
        title="Q1",
        body="body",
        sources=["[[@a]]"],
        date="2026-05-30",
        generator="wiki-query",
    )
    text = out.read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("---", 2)[1])
    assert fm["generator"] == "wiki-query"
```

(If `tests/unit/wiki/test_findings.py` lacks `from pathlib import Path`, add it at the top.)

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/wiki/test_findings.py -k generator -v`
Expected: FAIL — `KeyError: 'generator'`.

- [ ] **Step 3: Implement** — in `archive_as_finding`, add `"generator": generator,` to the `fm` dict (after `"status": "active",`):

```python
    fm = {
        "id": slug,
        "type": "finding",
        "title": title,
        "added": date,
        "status": "active",
        "generator": generator,
        "tags": tags or [],
        "sources": sources,
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/wiki/test_findings.py -v`
Expected: PASS (all — existing tests don't assert an exact key set, so adding a key is safe; if one does a strict equality on `fm`, update it to include `generator`).

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/wiki/findings.py tests/unit/wiki/test_findings.py
git commit -m "feat(wiki): stamp generator into finding frontmatter for provenance"
```

---

### Task 3: `AIToolUse` + `AIDisclosure` schemas

**Files:** Modify `src/prumo_assist/domains/write/schemas/v1.py`; Test `tests/unit/write/test_disclosure.py` (created here)

- [ ] **Step 1: Write the failing test** — create `tests/unit/write/test_disclosure.py`:

```python
"""Testes do gerador de declaração de uso de IA."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.write.schemas.v1 import AIDisclosure, AIToolUse


def test_aitooluse_defaults() -> None:
    u = AIToolUse(tool="prumo-assist:paper-extract", task="t")
    assert u.count == 1
    assert u.human_reviewed is False
    assert u.model is None


def test_aidisclosure_schema_version() -> None:
    d = AIDisclosure(generated_at="t", statement_pt="p", statement_en="e")
    assert d.schema_version == "AIDisclosure/v1"
    assert d.tools == []
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/write/test_disclosure.py -v`
Expected: FAIL — `ImportError: cannot import name 'AIDisclosure'`.

- [ ] **Step 3: Implement** — append to `src/prumo_assist/domains/write/schemas/v1.py`:

```python
class AIToolUse(BaseModel):
    """Um uso agregado de ferramenta de IA (uma skill + um modelo)."""

    tool: str
    model: str | None = None
    task: str
    count: int = 1
    human_reviewed: bool = False


class AIDisclosure(BaseModel):
    """AIDisclosure/v1 — declaração de uso de IA derivada da proveniência."""

    schema_version: Literal["AIDisclosure/v1"] = "AIDisclosure/v1"
    generated_at: str
    date_from: str | None = None
    date_to: str | None = None
    tools: list[AIToolUse] = Field(default_factory=list)
    statement_pt: str
    statement_en: str
```

(`BaseModel`, `Field`, `Literal` are already imported at the top of this file.)

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/write/test_disclosure.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/write/schemas/v1.py tests/unit/write/test_disclosure.py
git commit -m "feat(write): add AIDisclosure/v1 schema"
```

---

### Task 4: provenance harvesting — `_read_frontmatter` + `_record_from_fm` + `collect_records`

**Files:** Create `src/prumo_assist/domains/write/disclosure.py`; Test `tests/unit/write/test_disclosure.py`

- [ ] **Step 1: Write the failing tests** — add to `tests/unit/write/test_disclosure.py`:

```python
def test_record_from_paper_meta() -> None:
    from prumo_assist.domains.write.disclosure import _record_from_fm

    rec = _record_from_fm({"extracted_model": "claude-opus-4", "extracted_at": "2026-05-01"})
    assert rec is not None
    assert rec.skill == "paper-extract"
    assert rec.model == "claude-opus-4"


def test_record_from_finding_generator() -> None:
    from prumo_assist.domains.write.disclosure import _record_from_fm

    rec = _record_from_fm({"type": "finding", "generator": "wiki-query", "added": "2026-05-02"})
    assert rec is not None
    assert rec.skill == "wiki-query"
    assert rec.model is None


def test_record_from_plain_frontmatter_is_none() -> None:
    from prumo_assist.domains.write.disclosure import _record_from_fm

    assert _record_from_fm({"title": "just a note"}) is None


def test_collect_records_walks_and_skips_dotdirs(tmp_path: Path) -> None:
    from prumo_assist.domains.write.disclosure import collect_records

    (tmp_path / "references" / "notes" / "a").mkdir(parents=True)
    (tmp_path / "references" / "notes" / "a" / "_meta.md").write_text(
        "---\nextracted_model: m1\nextracted_at: 2026-05-01\n---\n", encoding="utf-8"
    )
    (tmp_path / ".prumo").mkdir()
    (tmp_path / ".prumo" / "leak.md").write_text(
        "---\nextracted_model: leak\n---\n", encoding="utf-8"
    )
    recs = collect_records(tmp_path)
    assert [r.model for r in recs] == ["m1"]
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/write/test_disclosure.py -k "record or collect" -v`
Expected: FAIL — `ModuleNotFoundError: ...disclosure`.

- [ ] **Step 3: Implement** — create `src/prumo_assist/domains/write/disclosure.py`:

```python
"""Gera declaração de uso de IA a partir da proveniência dos artefatos.

Determinístico. Hoje a proveniência é heterogênea (o módulo
``core.provenance`` existe mas ainda não está ligado em todos os produtores):
extrações de paper gravam ``extracted_model``/``extracted_at`` em
``references/notes/<key>/_meta.md``; findings gravam ``generator`` no
frontmatter. Esta op colhe esses sinais (e qualquer bloco ``_meta:`` canônico
futuro), agrega por (skill, modelo) e renderiza o parágrafo de disclosure
exigido por periódicos e pelo EU AI Act.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from prumo_assist import PrumoError
from prumo_assist.core.provenance import now_utc
from prumo_assist.domains.write.schemas.v1 import AIDisclosure, AIToolUse

__all__ = ["collect_records", "generate_disclosure"]

_SKIP_PARTS = {".prumo", ".git", "build", "node_modules", ".venv"}

_TASK_BY_SKILL = {
    "paper-extract": "structured extraction of key information from source documents",
    "wiki-query": "synthesis of answers grounded in the project knowledge base",
    "active-learning": "synthesis of study-session findings",
    "peer-review": "critical review of draft sections",
    "write-paper": "drafting of manuscript sections",
    "write-scientific": "drafting of prose sections",
    "write-statistics": "drafting of the statistical analysis plan",
    "write-projeto-cep": "drafting of the research ethics submission",
}
_DEFAULT_TASK = "assistive text generation"


@dataclass(frozen=True)
class ProvRecord:
    skill: str
    model: str | None
    date: str | None
    human_reviewed: bool


def _read_frontmatter(md: Path) -> dict[str, Any] | None:
    text = md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        fm = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None
    return fm if isinstance(fm, dict) else None


def _record_from_fm(fm: dict[str, Any]) -> ProvRecord | None:
    meta = fm.get("_meta") if isinstance(fm.get("_meta"), dict) else {}
    reviewed = bool(meta.get("human_reviewed", fm.get("human_reviewed", False)))
    if meta.get("skill") or meta.get("model"):  # future canonical block
        return ProvRecord(
            skill=str(meta.get("skill") or "prumo-assist"),
            model=str(meta["model"]) if meta.get("model") else None,
            date=str(meta["timestamp_utc"]) if meta.get("timestamp_utc") else None,
            human_reviewed=reviewed,
        )
    if fm.get("extracted_model"):  # paper-extract note metadata
        return ProvRecord(
            skill="paper-extract",
            model=str(fm["extracted_model"]),
            date=str(fm["extracted_at"]) if fm.get("extracted_at") else None,
            human_reviewed=reviewed,
        )
    if fm.get("generator"):  # finding frontmatter
        return ProvRecord(
            skill=str(fm["generator"]),
            model=str(fm["model"]) if fm.get("model") else None,
            date=str(fm["added"]) if fm.get("added") else None,
            human_reviewed=reviewed,
        )
    return None


def collect_records(root: Path) -> list[ProvRecord]:
    records: list[ProvRecord] = []
    for md in sorted(root.rglob("*.md")):
        if _SKIP_PARTS & set(md.parts):
            continue
        fm = _read_frontmatter(md)
        if fm is None:
            continue
        rec = _record_from_fm(fm)
        if rec is not None:
            records.append(rec)
    return records
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/write/test_disclosure.py -k "record or collect" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/write/disclosure.py tests/unit/write/test_disclosure.py
git commit -m "feat(write): harvest heterogeneous provenance for disclosure"
```

---

### Task 5: `generate_disclosure` — aggregate + render

**Files:** Modify `src/prumo_assist/domains/write/disclosure.py`; Test `tests/unit/write/test_disclosure.py`

- [ ] **Step 1: Write the failing tests** — add to `tests/unit/write/test_disclosure.py`:

```python
def _paper(p: Path, model: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\nextracted_model: {model}\nextracted_at: 2026-05-01\n---\n", encoding="utf-8")


def test_generate_disclosure_names_tool_and_model(tmp_path: Path) -> None:
    from prumo_assist.domains.write.disclosure import generate_disclosure

    _paper(tmp_path / "references/notes/a/_meta.md", "claude-opus-4")
    _paper(tmp_path / "references/notes/b/_meta.md", "claude-opus-4")
    disc = generate_disclosure(root=tmp_path)
    assert len(disc.tools) == 1
    assert disc.tools[0].count == 2
    assert disc.tools[0].tool == "prumo-assist:paper-extract"
    assert "claude-opus-4" in disc.statement_en
    assert "responsibility" in disc.statement_en
    assert "responsabilidade" in disc.statement_pt


def test_generate_disclosure_empty(tmp_path: Path) -> None:
    from prumo_assist.domains.write.disclosure import generate_disclosure

    disc = generate_disclosure(root=tmp_path)
    assert disc.tools == []
    assert "No generative AI" in disc.statement_en


def test_generate_disclosure_missing_root_raises() -> None:
    import pytest

    from prumo_assist import PrumoError
    from prumo_assist.domains.write.disclosure import generate_disclosure

    with pytest.raises(PrumoError):
        generate_disclosure(root=Path("/no/such/dir/xyz123"))
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/write/test_disclosure.py -k generate -v`
Expected: FAIL — `ImportError: cannot import name 'generate_disclosure'`.

- [ ] **Step 3: Implement** — append to `src/prumo_assist/domains/write/disclosure.py`:

```python
def _aggregate(records: list[ProvRecord]) -> list[AIToolUse]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for r in records:
        slot = grouped.setdefault((r.skill, r.model or ""), {"count": 0, "reviewed": True})
        slot["count"] = int(slot["count"]) + 1
        slot["reviewed"] = bool(slot["reviewed"]) and r.human_reviewed
    uses: list[AIToolUse] = []
    for (skill, model), slot in sorted(grouped.items()):
        tool = skill if skill.startswith("prumo-assist") else f"prumo-assist:{skill}"
        uses.append(
            AIToolUse(
                tool=tool,
                model=model or None,
                task=_TASK_BY_SKILL.get(skill, _DEFAULT_TASK),
                count=int(slot["count"]),
                human_reviewed=bool(slot["reviewed"]),
            )
        )
    return uses


def _phrase(use: AIToolUse) -> str:
    head = f"{use.tool} ({use.model})" if use.model else use.tool
    return f"{head} for {use.task}"


def _render(uses: list[AIToolUse], lang: str) -> str:
    if not uses:
        if lang == "pt":
            return "Nenhuma ferramenta de IA generativa foi usada na preparação deste trabalho."
        return "No generative AI tools were used in the preparation of this work."
    items = "; ".join(_phrase(u) for u in uses)
    if lang == "pt":
        return (
            f"Durante a preparação deste trabalho, o(s) autor(es) utilizaram {items}. "
            "Após o uso dessas ferramentas, o(s) autor(es) revisaram e editaram o "
            "conteúdo conforme necessário e assumem total responsabilidade pelo "
            "conteúdo da publicação."
        )
    return (
        f"During the preparation of this work, the author(s) used {items}. "
        "After using these tools, the author(s) reviewed and edited the content as "
        "needed and take full responsibility for the content of the publication."
    )


def generate_disclosure(*, root: Path | None = None) -> AIDisclosure:
    """Varre ``root`` (default: cwd) e devolve uma ``AIDisclosure``."""
    root = root or Path.cwd()
    if not root.exists():
        raise PrumoError(f"diretório não encontrado: {root}")
    records = collect_records(root)
    uses = _aggregate(records)
    dates = sorted(r.date for r in records if r.date)
    return AIDisclosure(
        generated_at=now_utc(),
        date_from=dates[0] if dates else None,
        date_to=dates[-1] if dates else None,
        tools=uses,
        statement_pt=_render(uses, "pt"),
        statement_en=_render(uses, "en"),
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/write/test_disclosure.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/write/disclosure.py tests/unit/write/test_disclosure.py
git commit -m "feat(write): aggregate + render AI-use disclosure"
```

---

### Task 6: re-export + CLI subcommand

**Files:** Modify `src/prumo_assist/domains/write/api.py`, `src/prumo_assist/domains/write/cli.py`; Test `tests/unit/write/test_disclosure.py`

- [ ] **Step 1: Write the failing tests** — add to `tests/unit/write/test_disclosure.py`:

```python
def test_reexported() -> None:
    from prumo_assist.domains.write.api import generate_disclosure

    assert callable(generate_disclosure)


def test_cli_disclosure_json(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from prumo_assist.domains.write.cli import write_app

    (tmp_path / "references" / "notes" / "a").mkdir(parents=True)
    (tmp_path / "references" / "notes" / "a" / "_meta.md").write_text(
        "---\nextracted_model: claude-opus-4\nextracted_at: 2026-05-01\n---\n", encoding="utf-8"
    )
    result = CliRunner().invoke(write_app, ["disclosure", str(tmp_path), "--json"])
    assert result.exit_code == 0
    assert "AIDisclosure/v1" in result.stdout
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/write/test_disclosure.py -k "reexported or cli" -v`
Expected: FAIL — import error, then unknown command.

- [ ] **Step 3: Implement**

In `src/prumo_assist/domains/write/api.py`, add the import (near the other `from prumo_assist.domains.write.*` imports) and the `__all__` entry:

```python
from prumo_assist.domains.write.disclosure import generate_disclosure
```

Add `"generate_disclosure",` to the `__all__` list (keep it alphabetically sorted).

In `src/prumo_assist/domains/write/cli.py`, append:

```python
@write_app.command("disclosure")
def disclosure_command(
    path: Annotated[Path, typer.Argument(help="Raiz do pj_* a escanear.")] = Path("."),
    lang: Annotated[str, typer.Option("--lang", help="Idioma da declaração: en | pt.")] = "en",
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Gera a declaração de uso de IA a partir da proveniência dos artefatos."""
    with cli_run(json_mode=json_mode) as console:
        from prumo_assist.domains.write.disclosure import generate_disclosure

        disc = generate_disclosure(root=path.resolve())
        if json_mode:
            console.emit(disc.model_dump())
        else:
            console.emit(disc.statement_pt if lang == "pt" else disc.statement_en)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/write/test_disclosure.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/write/api.py src/prumo_assist/domains/write/cli.py tests/unit/write/test_disclosure.py
git commit -m "feat(write): wire 'prumo write disclosure' subcommand + API"
```

---

### Task 7: full gate + changelog

**Files:** Modify `CHANGELOG.md`

- [ ] **Step 1: Run the full gate**

Run: `uv run pytest -q && uv run ruff check src tests && uv run mypy --strict src`
Expected: all green.

- [ ] **Step 2: Changelog** — under `## [Não publicado]` → `### Adicionado` add:

```markdown
- **`prumo write disclosure`** — gera a declaração de uso de IA (PT/EN) a partir
  da proveniência dos artefatos (`extracted_model` em `_meta.md`, `generator` em
  findings, e blocos `_meta:` canônicos futuros), no formato exigido por
  periódicos (Elsevier, Springer Nature, Wiley, T&F, SAGE) e pelo EU AI Act.
  Schema `AIDisclosure/v1`.
- **`Meta.human_reviewed`** (provenance) — registra verificação humana; aditivo,
  Princípio IV. Findings agora gravam `generator` no frontmatter.
```

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): note write disclosure"
```

---

## Self-Review

- **Spec coverage:** `prumo write disclosure` (Tasks 4-6) + `human_reviewed` no provenance `Meta` (Task 1). Findings `generator` (Task 2) makes the disclosure able to name wiki artifacts. ✅
- **Placeholders:** none — every step shows complete code. ✅
- **Type consistency:** `generate_disclosure(*, root=None)` identical across api/cli/tests; `AIToolUse.model: str | None` matches `_aggregate`'s `model or None` and `_phrase`'s `if use.model`; `ProvRecord` fields (`skill,model,date,human_reviewed`) consistent across `_record_from_fm`/`_aggregate`/`generate_disclosure`. Uses real APIs (`build_meta`, `Console.emit`, `cli_run(json_mode=...)`, `write_app`, `now_utc`). ✅
- **Honesty note for executor:** disclosure is only as complete as the provenance artifacts carry. Today that's paper extracts (model) + findings (generator). Retrofitting `build_meta` into every producer is a deliberate follow-up, intentionally out of scope.
