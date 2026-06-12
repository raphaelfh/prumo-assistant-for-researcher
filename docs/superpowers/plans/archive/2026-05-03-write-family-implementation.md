---
status: implemented
verified: 2026-06-11
release: "0.5.0"
---

# `write-*` Family Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar família de 4 skills agênticas (`write-paper`, `write-projeto-cep`, `write-statistics`, `write-scientific`) com backend Python compartilhado em `domains/write/compose.py`. 4 templates default. Citação strict (só citekeys do acervo + `[REF FALTANTE]`). Output em 3 modos (drafts gerenciados / bloco delimitado / arquivo livre).

**Architecture:** Anexa ao domínio `write/` existente (que já tem `export.py` Pandoc + `comments.py` extract-from-docx). Não cria domínio novo. Schemas Pydantic em `domains/write/schemas/v1.py` (`ComposeInputs/v1`, `WriteOutput/v1`, `PaperSummary`, `FindingSummary`). Templates em `templates/writing/<kind>.md` ship no plugin; project pode override em `.claude/writing_templates/`. 4 SKILL.md (~80 linhas cada) chamam o backend via Bash + Python -c.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, ruff strict, mypy strict. Reusa `domains/protocol/picot_io` (formulate-picot, depende de PR-P1+P2 já estarem mergeados) e `domains/paper` (paper-extract layout α; depende de PR-N1 mergeado).

---

## Dependências externas

- **PR-N1 (zotero-notes layout α)**: precisa estar mergeado pra `read_inputs` ler `references/notes/<key>/_meta.md` e `<key>/_extract.md`. Se não estiver, código tem fallback pra `<key>.md` legado, mas com warning.
- **PR-P1+P2 (formulate-picot schema + IO)**: precisa estar mergeado pra `read_inputs` carregar `PicotSpec` via `prumo_assist.domains.protocol.picot_io.read_picot`. Se não estiver, `compose_inputs.picot = None`.

Ambos já têm specs+plans mergeados; basta executar antes desse PR.

---

## File Structure

| Caminho | Ação | Responsabilidade |
|---|---|---|
| `src/prumo_assist/domains/write/schemas/__init__.py` | **Create** | Vazio |
| `src/prumo_assist/domains/write/schemas/v1.py` | **Create** | `ComposeInputs/v1`, `PaperSummary`, `FindingSummary`, `WriteOutput/v1` |
| `src/prumo_assist/domains/write/compose.py` | **Create** | `read_inputs`, `resolve_template`, `compose_path`, `write_output`, `extract_missing_refs` |
| `src/prumo_assist/domains/write/api.py` | **Modify** | Re-exports |
| `src/prumo_assist/domains/write/cli.py` | **Modify** | Adicionar `prumo write list-templates` (opcional) |
| `templates/writing/__init__.py` | (não — Markdown templates) | — |
| `templates/writing/paper.md` | **Create** | Template IMRaD venue-aware |
| `templates/writing/projeto-cep.md` | **Create** | Template projeto CEP brasileiro |
| `templates/writing/statistics.md` | **Create** | Template plano de análise estatística |
| `templates/writing/scientific.md` | **Create** | Template scientific genérico |
| `skills/write-paper/SKILL.md` | **Create** | Prompt agêntico paper IMRaD venue-aware |
| `skills/write-projeto-cep/SKILL.md` | **Create** | Prompt agêntico CEP brasileiro |
| `skills/write-statistics/SKILL.md` | **Create** | Prompt agêntico plano estatístico |
| `skills/write-scientific/SKILL.md` | **Create** | Prompt agêntico scientific genérico |
| `tests/unit/write/__init__.py` | **Create** | Vazio |
| `tests/unit/write/test_schemas_v1.py` | **Create** | Tests dos schemas |
| `tests/unit/write/test_compose_inputs.py` | **Create** | Tests de `read_inputs` |
| `tests/unit/write/test_compose_paths.py` | **Create** | Tests de `resolve_template` + `compose_path` |
| `tests/unit/write/test_compose_output.py` | **Create** | Tests de `write_output` (3 modos) |
| `tests/unit/write/test_compose_refs.py` | **Create** | Tests de `extract_missing_refs` + validação citekey |
| `pyproject.toml` | **Modify** | `force-include` `templates/writing/` no wheel |
| `README.md` | **Modify** | Adicionar 4 skills `write-*` na tabela |
| `docs/actions-by-context.md` | **Modify** | Materializar gatilhos (já têm placeholder) |

---

## Task 1: Schemas (`ComposeInputs/v1`, `WriteOutput/v1`)

**Files:**
- Create: `src/prumo_assist/domains/write/schemas/__init__.py`
- Create: `src/prumo_assist/domains/write/schemas/v1.py`
- Test: `tests/unit/write/__init__.py` (empty)
- Test: `tests/unit/write/test_schemas_v1.py`

- [ ] **Step 1: Create schema dirs and write tests**

```bash
mkdir -p src/prumo_assist/domains/write/schemas tests/unit/write
touch src/prumo_assist/domains/write/schemas/__init__.py tests/unit/write/__init__.py
```

Create `tests/unit/write/test_schemas_v1.py`:

```python
"""Tests para ComposeInputs/v1 + WriteOutput/v1."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from prumo_assist.domains.write.schemas.v1 import (
    ComposeInputs,
    FindingSummary,
    PaperSummary,
    WriteOutput,
)


def test_paper_summary_minimal() -> None:
    p = PaperSummary(citekey="smith2024", title="X", authors="Smith, J.")
    assert p.year is None
    assert p.extract_content is None


def test_paper_summary_requires_citekey() -> None:
    with pytest.raises(ValidationError):
        PaperSummary(citekey="", title="X", authors="Smith")


def test_compose_inputs_default_empty() -> None:
    c = ComposeInputs()
    assert c.picot is None
    assert c.citekeys == []
    assert c.papers == {}
    assert c.protocol is None
    assert c.findings == []
    assert c.schema_version == "ComposeInputs/v1"


def test_compose_inputs_with_data() -> None:
    paper = PaperSummary(citekey="a", title="T", authors="A")
    finding = FindingSummary(path=Path("docs/findings/x.md"), title="F", body="B")
    c = ComposeInputs(
        citekeys=["a"],
        papers={"a": paper},
        protocol="contexto",
        project="proj",
        findings=[finding],
    )
    assert c.papers["a"].citekey == "a"
    assert len(c.findings) == 1


def test_write_output_minimal() -> None:
    out = WriteOutput(
        output_path=Path("docs/drafts/paper-2026-05-03-x.md"),
        mode="drafts",
        kind="paper",
        sections_filled=["Introduction", "Methods"],
        sections_skipped=[],
        citations_used=["smith2024"],
        references_missing=["validação externa"],
        words_generated=1500,
    )
    assert out.schema_version == "WriteOutput/v1"


def test_write_output_invalid_mode() -> None:
    with pytest.raises(ValidationError):
        WriteOutput(
            output_path=Path("x.md"), mode="bogus", kind="paper",
            sections_filled=[], sections_skipped=[], citations_used=[],
            references_missing=[], words_generated=0,
        )


def test_write_output_invalid_kind() -> None:
    with pytest.raises(ValidationError):
        WriteOutput(
            output_path=Path("x.md"), mode="drafts", kind="bogus",
            sections_filled=[], sections_skipped=[], citations_used=[],
            references_missing=[], words_generated=0,
        )
```

- [ ] **Step 2: Run tests fail**

Run: `uv run pytest tests/unit/write/test_schemas_v1.py -v`
Expected: FAIL — `ComposeInputs` not defined.

- [ ] **Step 3: Implement schemas**

Create `src/prumo_assist/domains/write/schemas/__init__.py` (empty).

Create `src/prumo_assist/domains/write/schemas/v1.py`:

```python
"""``ComposeInputs/v1`` + ``WriteOutput/v1`` — schemas pra família ``write-*``.

Versionamento forward-only (vN+1 lê vN; nunca remove campo).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from prumo_assist.domains.protocol.schemas.v1 import PicotSpec


class PaperSummary(BaseModel):
    """Resumo de 1 paper do acervo (metadata + extract callout)."""

    citekey: str = Field(..., min_length=1)
    title: str
    year: int | None = None
    authors: str = ""
    extract_content: str | None = None


class FindingSummary(BaseModel):
    """Achado canônico (``docs/wiki/findings/*.md`` ou ``docs/findings/*.md``)."""

    path: Path
    title: str
    body: str


class ComposeInputs(BaseModel):
    """Tudo que skill ``write-*`` precisa pra gerar prose."""

    schema_version: Literal["ComposeInputs/v1"] = "ComposeInputs/v1"
    picot: PicotSpec | None = None
    citekeys: list[str] = []
    papers: dict[str, PaperSummary] = {}
    protocol: str | None = None
    project: str | None = None
    findings: list[FindingSummary] = []


WriteKind = Literal["paper", "projeto-cep", "statistics", "scientific"]
WriteMode = Literal["drafts", "into", "out"]


class WriteOutput(BaseModel):
    """Resultado da geração — reportado e usável programaticamente."""

    schema_version: Literal["WriteOutput/v1"] = "WriteOutput/v1"
    output_path: Path
    mode: WriteMode
    kind: WriteKind
    sections_filled: list[str]
    sections_skipped: list[str]
    citations_used: list[str]
    references_missing: list[str]
    words_generated: int
```

- [ ] **Step 4: Run tests pass**

Run: `uv run pytest tests/unit/write/test_schemas_v1.py -v`
Expected: 7 PASS.

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/write/schemas tests/unit/write/test_schemas_v1.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/write/schemas`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/domains/write/schemas tests/unit/write/__init__.py tests/unit/write/test_schemas_v1.py
git commit -m "feat(write): ComposeInputs/v1 + WriteOutput/v1 schemas"
```

---

## Task 2: `read_inputs` — carrega tudo do `pj_*`

**Files:**
- Create: `src/prumo_assist/domains/write/compose.py` (parte 1: `read_inputs`)
- Test: `tests/unit/write/test_compose_inputs.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/write/test_compose_inputs.py`:

```python
"""Tests para read_inputs (carrega ComposeInputs do pj_*)."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.write.compose import read_inputs


def _bootstrap(tmp_path: Path) -> Path:
    pj = tmp_path / "pj_demo"
    refs = pj / "references"
    refs.mkdir(parents=True)
    (refs / "_references.bib").write_text(
        "@article{smith2024,\n  title = {Combinado Fusion},\n"
        "  author = \"Smith, J.\",\n  year = 2024\n}\n"
        "@article{doe2025,\n  title = {Other},\n"
        "  author = \"Doe, A.\",\n  year = 2025\n}\n"
    )
    (refs / "notes" / "smith2024").mkdir(parents=True)
    (refs / "notes" / "smith2024" / "_meta.md").write_text(
        "---\nid: smith2024\ntitle: Combinado Fusion\nauthor:\n"
        "  - { family: Smith, given: J. }\nissued: { date-parts: [[2024]] }\n---\n\n"
        "## Notas\n"
    )
    (refs / "notes" / "smith2024" / "_extract.md").write_text(
        "---\npaper: smith2024\nsource: prumo-paper-extract\n---\n\n"
        "<!-- paper-extract:begin -->\n"
        "> ### TL;DR\n> resumo bom\n"
        "<!-- paper-extract:end -->\n"
    )
    docs = pj / "docs"
    docs.mkdir()
    (docs / "protocol.md").write_text("# Protocolo\n\nContexto operacional.\n")
    (docs / "project.md").write_text("# Projeto\n\nProse formal.\n")
    return pj


def test_read_inputs_minimal_pj(tmp_path: Path) -> None:
    pj = tmp_path / "pj_empty"
    pj.mkdir()
    out = read_inputs(pj)
    assert out.picot is None
    assert out.citekeys == []
    assert out.papers == {}
    assert out.protocol is None
    assert out.findings == []


def test_read_inputs_picot_loaded_when_exists(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    (pj / ".claude").mkdir()
    (pj / ".claude" / "picot.toml").write_text(
        '[picot]\n'
        'type = "clinical"\n'
        'created_at = "2026-05-03"\n'
        'last_updated = "2026-05-03"\n'
        'version = 1\n'
        'population = "DS_A"\n'
        'intervention = "IntervencaoX"\n'
        'comparison = "best baseline"\n'
        'outcome = "AUROC ≥ 0.85"\n'
        'time = "retrospectivo"\n'
        '[picot.hypothesis]\n'
        'statement = "combinado supera comparador"\n'
        'rationale = "piloto"\n'
        'metrics = ["AUROC"]\n'
    )
    out = read_inputs(pj)
    assert out.picot is not None
    assert out.picot.population == "DS_A"


def test_read_inputs_citekeys_and_papers(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    out = read_inputs(pj)
    assert "smith2024" in out.citekeys
    assert "doe2025" in out.citekeys
    assert "smith2024" in out.papers
    smith = out.papers["smith2024"]
    assert smith.title == "Combinado Fusion"
    assert smith.year == 2024
    assert "resumo bom" in (smith.extract_content or "")


def test_read_inputs_paper_without_extract(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    # doe2025 não tem _meta.md/_extract.md
    out = read_inputs(pj)
    assert "doe2025" in out.citekeys
    # PaperSummary deve existir mesmo sem _meta.md (vem do .bib direto)
    assert "doe2025" in out.papers
    assert out.papers["doe2025"].extract_content is None


def test_read_inputs_protocol_and_project(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    out = read_inputs(pj)
    assert out.protocol is not None
    assert "Contexto operacional" in out.protocol
    assert out.project is not None
    assert "Prose formal" in out.project


def test_read_inputs_findings_extended_wiki(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    findings_dir = pj / "docs" / "wiki" / "findings"
    findings_dir.mkdir(parents=True)
    (findings_dir / "calibration.md").write_text(
        "---\nid: calibration\ntitle: Calibration matters\n---\n\nConclusion.\n"
    )
    out = read_inputs(pj)
    assert len(out.findings) == 1
    assert out.findings[0].title == "Calibration matters"


def test_read_inputs_findings_fallback(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    findings_dir = pj / "docs" / "findings"
    findings_dir.mkdir(parents=True)
    (findings_dir / "calibration.md").write_text(
        "---\nid: calibration\ntitle: Calibration matters\n---\n\nC.\n"
    )
    out = read_inputs(pj)
    assert len(out.findings) == 1
```

- [ ] **Step 2: Run tests fail**

Run: `uv run pytest tests/unit/write/test_compose_inputs.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `compose.py` part 1 (`read_inputs`)**

Create `src/prumo_assist/domains/write/compose.py`:

```python
"""Backend compartilhado da família ``write-*``.

Funções:

- ``read_inputs`` — carrega ``ComposeInputs`` lendo ``.claude/picot.toml``,
  ``references/_references.bib``, callouts ``_extract.md``, ``protocol.md``,
  ``project.md``, ``findings/*.md``.
- ``resolve_template`` — chain ``--template`` > ``.claude/writing_templates/`` > plugin default.
- ``compose_path`` — resolve output path por modo (drafts/into/out).
- ``write_output`` — escreve conteúdo no destino + retorna ``WriteOutput``.
- ``extract_missing_refs`` — varre texto pra ``[REF FALTANTE: ...]``.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from prumo_assist.core.bib import extract_field, parse_bib
from prumo_assist.core.note_paths import (
    extract_path,
    iter_note_meta_files,
    meta_path,
)
from prumo_assist.domains.write.schemas.v1 import (
    ComposeInputs,
    FindingSummary,
    PaperSummary,
)


def read_inputs(pj_path: Path) -> ComposeInputs:
    """Carrega ``ComposeInputs`` lendo ``pj_path``. Cada parte é graceful (None/empty)."""
    return ComposeInputs(
        picot=_read_picot(pj_path),
        citekeys=_read_citekeys(pj_path),
        papers=_read_papers(pj_path),
        protocol=_read_text(pj_path / "docs" / "protocol.md"),
        project=_read_text(pj_path / "docs" / "project.md"),
        findings=_read_findings(pj_path),
    )


def _read_picot(pj_path: Path):  # type: ignore[no-untyped-def]
    """Tenta carregar PicotSpec; ``None`` se ausente ou inválido."""
    try:
        from prumo_assist.domains.protocol.picot_io import read_picot
    except ImportError:
        return None
    try:
        return read_picot(pj_path)
    except (FileNotFoundError, ValueError):
        return None


def _read_citekeys(pj_path: Path) -> list[str]:
    bib = pj_path / "references" / "_references.bib"
    if not bib.exists():
        return []
    return [e.citekey for e in parse_bib(bib.read_text(encoding="utf-8"))]


def _read_papers(pj_path: Path) -> dict[str, PaperSummary]:
    """Combina ``.bib`` (metadata) + ``_extract.md`` (callout body) por citekey."""
    bib = pj_path / "references" / "_references.bib"
    if not bib.exists():
        return {}
    out: dict[str, PaperSummary] = {}
    for entry in parse_bib(bib.read_text(encoding="utf-8")):
        title = (extract_field(entry.body, "title") or "").strip()
        year_raw = (extract_field(entry.body, "year") or "").strip()
        year = int(year_raw) if year_raw.isdigit() else None
        authors = (extract_field(entry.body, "author") or "").strip()
        extract_content = _read_text(extract_path(pj_path, entry.citekey))
        out[entry.citekey] = PaperSummary(
            citekey=entry.citekey,
            title=title,
            year=year,
            authors=authors,
            extract_content=extract_content,
        )
    return out


def _read_findings(pj_path: Path) -> list[FindingSummary]:
    """Tenta ``docs/wiki/findings/`` primeiro, fallback ``docs/findings/``."""
    candidates = [
        pj_path / "docs" / "wiki" / "findings",
        pj_path / "docs" / "findings",
    ]
    findings_dir = next((c for c in candidates if c.exists()), None)
    if findings_dir is None:
        return []
    out: list[FindingSummary] = []
    for md in sorted(findings_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        title = _extract_yaml_field(text, "title") or md.stem
        body = _strip_frontmatter(text)
        out.append(FindingSummary(path=md, title=title, body=body))
    return out


def _read_text(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def _extract_yaml_field(text: str, key: str) -> str | None:
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return None
    parsed = yaml.safe_load(m.group(1)) or {}
    if isinstance(parsed, dict):
        v = parsed.get(key)
        return str(v) if v is not None else None
    return None


def _strip_frontmatter(text: str) -> str:
    return re.sub(r"\A---\n.*?\n---\n+", "", text, count=1, flags=re.DOTALL).strip()
```

- [ ] **Step 4: Run tests pass**

Run: `uv run pytest tests/unit/write/test_compose_inputs.py -v`
Expected: 7 PASS.

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/write/compose.py tests/unit/write/test_compose_inputs.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/write/compose.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/domains/write/compose.py tests/unit/write/test_compose_inputs.py
git commit -m "feat(write): read_inputs — load ComposeInputs from pj_*"
```

---

## Task 3: `resolve_template` + `compose_path` + `write_output` (3 modos)

**Files:**
- Modify: `src/prumo_assist/domains/write/compose.py` (acrescentar funções)
- Test: `tests/unit/write/test_compose_paths.py`
- Test: `tests/unit/write/test_compose_output.py`

- [ ] **Step 1: Write failing tests for path resolution**

Create `tests/unit/write/test_compose_paths.py`:

```python
"""Tests para resolve_template + compose_path."""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist.domains.write.compose import compose_path, resolve_template


def test_resolve_template_default_from_plugin(tmp_path: Path) -> None:
    """Plugin ships templates/writing/<kind>.md; deve ser default."""
    out = resolve_template(pj_path=tmp_path, kind="paper")
    assert out is not None
    assert out.name == "paper.md"
    assert "templates/writing" in str(out) or "_templates/writing" in str(out)


def test_resolve_template_project_override(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    over = pj / ".claude" / "writing_templates"
    over.mkdir(parents=True)
    (over / "paper.md").write_text("# Project Paper\n")
    out = resolve_template(pj_path=pj, kind="paper")
    assert out == over / "paper.md"


def test_resolve_template_explicit_override(tmp_path: Path) -> None:
    custom = tmp_path / "custom.md"
    custom.write_text("# Custom\n")
    out = resolve_template(
        pj_path=tmp_path, kind="paper", explicit=custom,
    )
    assert out == custom


def test_resolve_template_explicit_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        resolve_template(
            pj_path=tmp_path, kind="paper", explicit=tmp_path / "nope.md",
        )


def test_resolve_template_invalid_kind(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="kind"):
        resolve_template(pj_path=tmp_path, kind="bogus")  # type: ignore[arg-type]


def test_compose_path_drafts_default(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    (pj / "docs").mkdir(parents=True)
    out = compose_path(
        pj_path=pj, kind="paper", date="2026-05-03", slug="combinado",
    )
    assert out == pj / "docs" / "drafts" / "paper-2026-05-03-combinado.md"


def test_compose_path_into_uses_path_arg(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    (pj / "docs").mkdir(parents=True)
    target = pj / "docs" / "project.md"
    target.write_text("# Projeto\n")
    out = compose_path(
        pj_path=pj, kind="paper", date="2026-05-03", slug="x", into=target,
    )
    assert out == target


def test_compose_path_out_uses_path_arg(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    target = tmp_path / "any" / "place.md"
    out = compose_path(
        pj_path=pj, kind="paper", date="2026-05-03", slug="x", out=target,
    )
    assert out == target


def test_compose_path_into_and_out_conflict(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        compose_path(
            pj_path=tmp_path, kind="paper", date="2026-05-03", slug="x",
            into=tmp_path / "a.md", out=tmp_path / "b.md",
        )
```

Create `tests/unit/write/test_compose_output.py`:

```python
"""Tests para write_output (3 modos: drafts, into, out)."""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist.domains.write.compose import write_output


def test_write_output_drafts_creates_file(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    (pj / "docs" / "drafts").mkdir(parents=True)
    out = write_output(
        content="# Draft\n\nbody\n",
        pj_path=pj,
        kind="paper",
        mode="drafts",
        date="2026-05-03",
        slug="x",
    )
    assert out.output_path == pj / "docs" / "drafts" / "paper-2026-05-03-x.md"
    assert out.output_path.exists()
    assert out.mode == "drafts"
    assert "body" in out.output_path.read_text()


def test_write_output_into_replaces_block(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    (pj / "docs").mkdir(parents=True)
    target = pj / "docs" / "project.md"
    target.write_text(
        "# Projeto\n\n"
        "<!-- write:begin kind=paper section=intro -->\n"
        "old content\n"
        "<!-- write:end -->\n\n"
        "Footer humano.\n"
    )
    out = write_output(
        content="new content",
        pj_path=pj,
        kind="paper",
        mode="into",
        date="2026-05-03",
        slug="x",
        into=target,
        section="intro",
    )
    text = target.read_text()
    assert "new content" in text
    assert "old content" not in text
    assert "Footer humano." in text  # preservado
    assert out.mode == "into"


def test_write_output_into_inserts_when_block_absent(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    (pj / "docs").mkdir(parents=True)
    target = pj / "docs" / "project.md"
    target.write_text("# Projeto\n\nIntro existente.\n")
    write_output(
        content="generated",
        pj_path=pj, kind="paper", mode="into", date="2026-05-03", slug="x",
        into=target, section="methods",
    )
    text = target.read_text()
    assert "<!-- write:begin kind=paper section=methods -->" in text
    assert "generated" in text
    assert "Intro existente." in text


def test_write_output_out_writes_to_path(tmp_path: Path) -> None:
    pj = tmp_path / "pj"
    target = tmp_path / "anywhere" / "file.md"
    out = write_output(
        content="# X\n",
        pj_path=pj, kind="paper", mode="out", date="2026-05-03", slug="x",
        out=target,
    )
    assert target.exists()
    assert out.mode == "out"


def test_write_output_out_refuses_overwrite_without_force(tmp_path: Path) -> None:
    target = tmp_path / "f.md"
    target.write_text("existing")
    with pytest.raises(FileExistsError):
        write_output(
            content="new",
            pj_path=tmp_path, kind="paper", mode="out", date="2026-05-03", slug="x",
            out=target,
        )


def test_write_output_out_force_overwrites(tmp_path: Path) -> None:
    target = tmp_path / "f.md"
    target.write_text("existing")
    write_output(
        content="new",
        pj_path=tmp_path, kind="paper", mode="out", date="2026-05-03", slug="x",
        out=target, force=True,
    )
    assert target.read_text() == "new"
```

- [ ] **Step 2: Run tests fail**

Run: `uv run pytest tests/unit/write/test_compose_paths.py tests/unit/write/test_compose_output.py -v`
Expected: FAIL.

- [ ] **Step 3: Append to `compose.py`**

Append to `src/prumo_assist/domains/write/compose.py`:

```python
from prumo_assist.core.paths import find_resource
from prumo_assist.domains.write.schemas.v1 import WriteKind, WriteMode, WriteOutput

_VALID_KINDS = ("paper", "projeto-cep", "statistics", "scientific")
_BLOCK_FULL_RE = re.compile(
    r"<!--\s*write:begin\s+kind=(?P<kind>[\w-]+)\s+section=(?P<section>[\w-]+)\s*-->"
    r".*?"
    r"<!--\s*write:end\s*-->",
    flags=re.DOTALL,
)


def resolve_template(
    *,
    pj_path: Path,
    kind: WriteKind,
    explicit: Path | None = None,
) -> Path:
    """Resolve template via fallback chain ``explicit > project > plugin``."""
    if kind not in _VALID_KINDS:
        raise ValueError(
            f"kind inválido '{kind}'; esperado um de {list(_VALID_KINDS)}"
        )
    if explicit is not None:
        if not explicit.exists():
            raise FileNotFoundError(f"--template {explicit} não existe.")
        return explicit
    project_override = pj_path / ".claude" / "writing_templates" / f"{kind}.md"
    if project_override.exists():
        return project_override
    plugin_root = find_resource("templates")
    if plugin_root is not None:
        plugin_template = plugin_root / "writing" / f"{kind}.md"
        if plugin_template.exists():
            return plugin_template
    raise FileNotFoundError(
        f"Nenhum template '{kind}' encontrado. Crie "
        f".claude/writing_templates/{kind}.md ou passe --template."
    )


def compose_path(
    *,
    pj_path: Path,
    kind: WriteKind,
    date: str,
    slug: str,
    into: Path | None = None,
    out: Path | None = None,
) -> Path:
    """Resolve output path por modo. ``into``/``out`` mutuamente exclusivos."""
    if into is not None and out is not None:
        raise ValueError("--into e --out são mutuamente exclusivos.")
    if into is not None:
        return into
    if out is not None:
        return out
    drafts = pj_path / "docs" / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    return drafts / f"{kind}-{date}-{slug}.md"


def write_output(
    *,
    content: str,
    pj_path: Path,
    kind: WriteKind,
    mode: WriteMode,
    date: str,
    slug: str,
    into: Path | None = None,
    out: Path | None = None,
    section: str | None = None,
    force: bool = False,
    sections_filled: list[str] | None = None,
    sections_skipped: list[str] | None = None,
) -> WriteOutput:
    """Escreve ``content`` no destino conforme ``mode`` e retorna ``WriteOutput``."""
    target = compose_path(
        pj_path=pj_path, kind=kind, date=date, slug=slug, into=into, out=out,
    )

    if mode == "into":
        if not target.exists():
            raise FileNotFoundError(f"--into {target} não existe.")
        if section is None:
            raise ValueError("--into requer --section <name>.")
        new_block = (
            f"<!-- write:begin kind={kind} section={section} -->\n"
            f"{content.rstrip()}\n"
            f"<!-- write:end -->"
        )
        existing = target.read_text(encoding="utf-8")
        # Substituir bloco kind+section específico se existe; senão inserir no fim
        block_specific_re = re.compile(
            rf"<!--\s*write:begin\s+kind={re.escape(kind)}\s+section={re.escape(section)}\s*-->"
            r".*?<!--\s*write:end\s*-->",
            flags=re.DOTALL,
        )
        if block_specific_re.search(existing):
            updated = block_specific_re.sub(new_block, existing, count=1)
        else:
            sep = "\n\n" if not existing.endswith("\n\n") else ""
            updated = existing.rstrip() + "\n\n" + new_block + "\n"
        target.write_text(updated, encoding="utf-8")
    elif mode == "out":
        if target.exists() and not force:
            raise FileExistsError(
                f"{target} já existe. Use force=True pra sobrescrever."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    else:  # drafts
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    return WriteOutput(
        output_path=target,
        mode=mode,
        kind=kind,
        sections_filled=sections_filled or [],
        sections_skipped=sections_skipped or [],
        citations_used=_extract_citekeys_used(content),
        references_missing=extract_missing_refs(content),
        words_generated=len(content.split()),
    )


def extract_missing_refs(text: str) -> list[str]:
    """Captura `[REF FALTANTE: <descrição>]` em ``text``."""
    pattern = re.compile(r"\[REF FALTANTE:\s*(?P<desc>[^\]]+)\]")
    return [m.group("desc").strip() for m in pattern.finditer(text)]


def _extract_citekeys_used(text: str) -> list[str]:
    """Captura `[[@<citekey>]]` em ``text``; retorna lista única ordenada."""
    pattern = re.compile(r"\[\[@(?P<key>[a-zA-Z0-9._+-]+)(?:\|[^\]]+)?\]\]")
    return sorted({m.group("key") for m in pattern.finditer(text)})
```

- [ ] **Step 4: Run tests pass**

Run: `uv run pytest tests/unit/write/test_compose_paths.py tests/unit/write/test_compose_output.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/write/compose.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/write/compose.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/domains/write/compose.py tests/unit/write/test_compose_paths.py tests/unit/write/test_compose_output.py
git commit -m "feat(write): resolve_template + compose_path + write_output (3 modes)"
```

---

## Task 4: Test `extract_missing_refs` + utility helpers

**Files:**
- Test: `tests/unit/write/test_compose_refs.py`

- [ ] **Step 1: Write tests**

Create `tests/unit/write/test_compose_refs.py`:

```python
"""Tests para extract_missing_refs e validação de citekey."""

from __future__ import annotations

from prumo_assist.domains.write.compose import (
    _extract_citekeys_used,
    extract_missing_refs,
)


def test_extract_missing_refs_finds_one() -> None:
    text = "Claim X [REF FALTANTE: difusão latente]."
    assert extract_missing_refs(text) == ["difusão latente"]


def test_extract_missing_refs_finds_multiple() -> None:
    text = "[REF FALTANTE: a]. Outra. [REF FALTANTE: b multi-word]."
    assert extract_missing_refs(text) == ["a", "b multi-word"]


def test_extract_missing_refs_strips_whitespace() -> None:
    text = "[REF FALTANTE:  with spaces  ]"
    assert extract_missing_refs(text) == ["with spaces"]


def test_extract_missing_refs_empty() -> None:
    assert extract_missing_refs("texto sem placeholders") == []


def test_extract_citekeys_simple() -> None:
    text = "...claim [[@smith2024]]. Outro [[@doe2025]]."
    assert _extract_citekeys_used(text) == ["doe2025", "smith2024"]


def test_extract_citekeys_with_alias() -> None:
    text = "[[@smith2024|Smith et al., 2024]] mostra X."
    assert _extract_citekeys_used(text) == ["smith2024"]


def test_extract_citekeys_dedup() -> None:
    text = "[[@a]] foo [[@a]] bar [[@b]]."
    assert _extract_citekeys_used(text) == ["a", "b"]


def test_extract_citekeys_empty() -> None:
    assert _extract_citekeys_used("sem citekeys") == []
```

- [ ] **Step 2: Tests should already pass** (functions já implementadas em Task 3)

Run: `uv run pytest tests/unit/write/test_compose_refs.py -v`
Expected: 8 PASS.

- [ ] **Step 3: Commit (sanity test gate)**

```bash
git add tests/unit/write/test_compose_refs.py
git commit -m "test(write): coverage for extract_missing_refs + citekey extractor"
```

---

## Task 5: Templates default (4 arquivos Markdown)

**Files:**
- Create: `templates/writing/paper.md`
- Create: `templates/writing/projeto-cep.md`
- Create: `templates/writing/statistics.md`
- Create: `templates/writing/scientific.md`
- Modify: `pyproject.toml` (force-include `templates/writing/` no wheel)

- [ ] **Step 1: Create directory + 4 templates**

```bash
mkdir -p templates/writing
```

Create `templates/writing/paper.md`:

```markdown
---
title: ""
target_venue: "general"
authors: []
---

# Title

<!-- 1 frase, ≤180 caracteres, declarativa.
     Use PicotSpec.hypothesis.statement como base. -->

# Abstract

<!-- IMRaD em 250-300 palavras (ajustar pra venue):
     Background (PicotSpec.population + gap), Methods (PicotSpec.intervention),
     Results (placeholders [RESULTADO N=...] se ainda não temos), Conclusion
     (hipótese + implicação clínica). Sem citações no abstract. -->

# Introduction

<!-- 4-6 parágrafos:
     1. Contexto clínico (PicotSpec.population). Cite ≥2 papers do acervo.
     2. Gap metodológico/clínico. Cite ≥3 papers que mostram limites.
     3. Nossa abordagem (PicotSpec.intervention). Cite trabalhos correlatos.
     4. Hipótese formal (PicotSpec.hypothesis.statement). Sem citação.
     Tom: presente pra SOTA, futuro pra "this study will". -->

# Methods

<!-- Subsections:
     - Population (PicotSpec.population + protocol.md § Coorte)
     - Data (datasets, protocol.md § Modalidades)
     - Model architecture (PicotSpec.intervention)
     - Training
     - Evaluation (PicotSpec.outcome + métricas)
     - Statistical analysis (protocol.md § Splits) -->

# Results

<!-- Placeholders [RESULTADO ...] se ainda em desenho.
     Caso já tenha valores em docs/findings/, reutilizar. -->

# Discussion

<!-- 4-6 parágrafos: principais achados, comparação com literatura,
     limitações (use protocol.md § Limitações), implicações,
     trabalho futuro. -->

# Limitations

<!-- Lista numerada, derivada de protocol.md ou ADRs. -->

# References

<!-- NÃO gerar; lista é responsabilidade do export Pandoc + CSL. -->
```

Create `templates/writing/projeto-cep.md`:

```markdown
---
title: ""
authors: []
ciaap: ""             # CAAE quando aprovado
plataforma_brasil: "" # link ou ID
---

# Resumo

<!-- 1-2 parágrafos. Use PicotSpec.population + intervention + outcome.
     Sem citações. Linguagem acessível (Comitê de Ética não-técnico). -->

# Pergunta de pesquisa

<!-- 1 parágrafo formalizando PicotSpec em prosa. -->

# Justificativa

<!-- 3-5 parágrafos: relevância clínica, gap, contribuição esperada.
     Cite ≥3 papers do acervo justificando importância. -->

# Hipótese

<!-- PicotSpec.hypothesis.statement em prosa. -->

# Coorte e critérios

<!-- Use protocol.md § Coorte + Critérios.
     - Fonte dos dados
     - Critérios de inclusão
     - Critérios de exclusão
     - Tamanho previsto (n) -->

# Métodos

<!-- PicotSpec.intervention + comparison + outcome em detalhe operacional.
     Sub-seções: Coleta de dados, Análise, Métricas. -->

# Riscos e benefícios

<!-- - Riscos (mínimos pra estudo retrospectivo de dados públicos)
     - Benefícios (acadêmicos + indiretos pra paciente futuro)
     - Mitigações dos riscos -->

# TCLE (Termo de Consentimento Livre e Esclarecido)

<!-- Aplicável apenas se há contato com participantes.
     Para estudo retrospectivo com dados anonimizados públicos:
     marcar como N/A com justificativa via Resolução CNS 510/2016 Art 1. -->

# Cronograma

<!-- 12-36 meses dependendo do escopo. Marcos:
     - Mês 0-3: Aprovação CEP, ingest acervo
     - ... -->

# Orçamento

<!-- Itens com justificativa. Vincular cada gasto a um marco. -->

# Conformidade ética

<!-- - Resolução CNS 466/2012, 510/2016
     - LGPD (Lei 13.709/2018)
     - HIPAA / GDPR se aplicável
     - DUAs (Data Use Agreements) das coortes
     - Conflitos de interesse -->
```

Create `templates/writing/statistics.md`:

```markdown
---
title: "Plano de análise estatística"
revisao: 1
---

# Plano de análise estatística (PAE)

<!-- 2-3 frases sobre escopo do plano (qual estudo, hipótese central). -->

## Definição operacional do outcome

<!-- PicotSpec.outcome formalizado:
     - Variável dependente: tipo (binária / contínua / time-to-event)
     - Definição clínica
     - Janela de mensuração
     - Critérios de exclusão por outcome ausente -->

## Sample size justification

<!-- Cálculo formal:
     - Métrica primária + threshold (PicotSpec.hypothesis.metrics)
     - Effect size esperado
     - Power (geralmente 0.8)
     - Alpha (geralmente 0.05)
     - Cite ≥1 paper metodológico sustentando o cálculo. -->

## Métricas primárias e secundárias

<!-- Lista detalhada:
     - Primária: ... (com IC 95% via bootstrap)
     - Secundárias: ECE, Brier, calibração por subgrupo -->

## Análises de sensibilidade

<!-- - Sensitivity to MNAR mechanism
     - Subgroup analysis
     - Influence diagnostics -->

## Splits e anti-leakage

<!-- protocol.md § Splits:
     - Estratégia (GroupKFold/temporal/...)
     - Seeds reportadas
     - Validação externa cross-cohort -->

## Software e reprodutibilidade

<!-- Bibliotecas + versões; código liberado em <repo>; seeds reportadas. -->
```

Create `templates/writing/scientific.md`:

```markdown
---
title: ""
section: ""
---

# {{ title or "Seção" }}

<!-- Genérico. Adapte conforme `--section` ou contexto.
     Use PicotSpec se relevante. Cite acervo strict. -->
```

- [ ] **Step 2: Update `pyproject.toml` to include templates/writing in wheel**

Find the `[tool.hatch.build.targets.wheel.force-include]` section. It already has `"templates" = "prumo_assist/_templates"`. The new `templates/writing/` is automatically included since it's under `templates/`. Verify with:

```bash
grep -A 3 'force-include' pyproject.toml
```
Expected: `"templates" = "prumo_assist/_templates"` line present (no edit needed).

- [ ] **Step 3: Verify resolve_template encontra os 4 templates**

Run an inline check:
```bash
uv run python -c '
from pathlib import Path
from prumo_assist.domains.write.compose import resolve_template
for kind in ("paper", "projeto-cep", "statistics", "scientific"):
    p = resolve_template(pj_path=Path("/tmp/nope"), kind=kind)
    print(f"{kind}: {p}")
'
```
Expected: cada um aponta pra `templates/writing/<kind>.md`.

- [ ] **Step 4: Commit**

```bash
git add templates/writing
git commit -m "feat(write): default templates (paper, projeto-cep, statistics, scientific)"
```

---

## Task 6: 4 SKILL.md + API + CLI list-templates

**Files:**
- Create: `skills/write-paper/SKILL.md`
- Create: `skills/write-projeto-cep/SKILL.md`
- Create: `skills/write-statistics/SKILL.md`
- Create: `skills/write-scientific/SKILL.md`
- Modify: `src/prumo_assist/domains/write/api.py` (re-exports)
- Modify: `src/prumo_assist/domains/write/cli.py` (`list-templates` command)

- [ ] **Step 1: Create SKILL.md for write-paper**

Create `skills/write-paper/SKILL.md`:

```markdown
---
name: write-paper
description: "Gera draft de paper acadêmico IMRaD (Introduction-Methods-Results-Discussion) venue-aware a partir do PICOT do projeto, callouts _extract.md dos papers cited, protocol.md e project.md. Citação strict — só citekeys do acervo + [REF FALTANTE]. Default: docs/drafts/paper-<data>-<slug>.md; --into <path> insere bloco delimitado em arquivo existente; --out <path> escreve livre. Invocar quando o usuário pedir 'escreve um draft do meu paper', 'gera o paper sobre X', 'rascunho IMRaD pra Y', 'me ajuda a começar o draft'..."
prumo:
  version: 1.0.0
  schema: WriteOutput/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~10-30k tokens
  inputs:
    venue: optional
    section: optional
    template: optional
    into: optional
    out: optional
    slug: optional
---

# Write Paper — IMRaD venue-aware

Você é um pesquisador clínico de ML escrevendo paper acadêmico. Use o template
default (ou o que o usuário passar via `--template`). Para cada section,
preencha conforme as instruções HTML comments dentro do template, usando os
inputs estruturados do projeto.

## Regras invioláveis

1. **Citação strict.** Só `[[@citekey]]` que existe em `references/_references.bib`. Se a claim precisa de paper fora do acervo, escreva `[REF FALTANTE: <descrição curta>]`. Nunca invente citekey ou escreva `[Smith et al., 2024]` sem wikilink.
2. **Não toca `## References`.** Lista bibliográfica é gerada por export Pandoc.
3. **Use PicotSpec do projeto** se existir (`.claude/picot.toml`). Population = coorte; Intervention = método; Comparison = baseline; Outcome = métrica primária; Hypothesis.statement = hipótese formal.
4. **Use callouts `_extract.md`** dos papers como insumo. Extract content tem PICOT/Método/Resultados/Limitações estruturados.
5. **Modo de output**: default `drafts/`; `--into` requer `--section`; `--out` ad-hoc.

## Fluxo

### 1. Carregar inputs

```bash
uv run python -c '
import json
from pathlib import Path
from prumo_assist.domains.write.api import read_inputs
inputs = read_inputs(Path("."))
print(inputs.model_dump_json(indent=2))
' > /tmp/compose_inputs.json
```

Ler o JSON; identificar:
- `picot` (se None, abortar com mensagem "rode `/prumo-assist:formulate-picot` primeiro")
- `citekeys` (lista pra validação de citação)
- `papers` (citekey → metadata + extract_content)
- `protocol`, `project` (raw text)
- `findings` (insights consolidados)

### 2. Resolver template

```bash
uv run python -c '
from pathlib import Path
from prumo_assist.domains.write.api import resolve_template
print(resolve_template(pj_path=Path("."), kind="paper"))
'
```

Ler conteúdo via `Read`. Identificar sections (cabeçalhos `#`).

### 3. Gerar prose por section

Para cada section do template (ou só `--section` se passado), formule prose seguindo:
- Instruções dos HTML comments dentro do template
- Inputs estruturados (PicotSpec, papers extract_content, protocol, project)
- Citação strict (validar contra `inputs.citekeys` antes de escrever)

Tom de cada section:
- **Title**: declarativo, ≤180 chars
- **Abstract**: IMRaD 250-300 palavras, sem citações
- **Introduction**: presente pra SOTA, futuro pra "this study will"
- **Methods**: presente impessoal ("é avaliado") ou passivo ("foi avaliado")
- **Results**: pretérito; placeholders `[RESULTADO N=...]` quando ainda não temos dado
- **Discussion**: presente pra interpretação, comparação com literatura
- **Limitations**: lista numerada, derivada de `protocol.md § Limitações` ou ADRs

### 4. Validar citação antes de gravar

Cada `[[@<key>]]` deve estar em `inputs.citekeys`. Se não está, substituir por `[REF FALTANTE: <descrição>]`.

### 5. Escrever output

Modos:
- **drafts** (default): `docs/drafts/paper-<data>-<slug>.md`
- **into** (`--into <path> --section <name>`): bloco delimitado em arquivo existente
- **out** (`--out <path>`): caminho livre

Comando:
```bash
uv run python -c '
from pathlib import Path
from prumo_assist.domains.write.api import write_output

content = """<draft completo gerado>"""
out = write_output(
    content=content,
    pj_path=Path("."),
    kind="paper",
    mode="drafts",   # ou "into" ou "out"
    date="<hoje ISO>",
    slug="<slug derivado>",
    sections_filled=["Introduction", "Methods", ...],
)
print(out.model_dump_json(indent=2))
'
```

### 6. Reportar

```
✓ Paper draft gerado em <output_path>
  Modo: <mode>
  Citações usadas: <N>
  Refs faltando: <M>
    - <descrição 1>
    - <descrição 2>
  Sections preenchidas: <list>
  Sugestão: rode `/prumo-assist:scientific-writing` no draft, depois `/prumo-assist:peer-review`.
```

## Boundaries

- **Não invente citekey.** Use `[REF FALTANTE]` quando incerto.
- **Não toque** em `## References`.
- **Não rode** Pandoc nem export — outras skills cuidam.
- **Não corrija** estilo editorial — papel do `scientific-writing` (depois).
- **Não critique** conteúdo — papel do `peer-review` (depois).
```

- [ ] **Step 2: Create SKILL.md for write-projeto-cep**

Create `skills/write-projeto-cep/SKILL.md`:

```markdown
---
name: write-projeto-cep
description: "Gera projeto pra Comitê de Ética em Pesquisa (CEP) brasileiro a partir do PICOT, protocol.md e papers do acervo. Estrutura formal: Resumo, Pergunta, Justificativa, Hipótese, Coorte e critérios, Métodos, Riscos e benefícios, TCLE, Cronograma, Orçamento, Conformidade ética. Citação strict (só citekeys do acervo). Linguagem acessível pra revisor não-técnico no Resumo. Invocar quando o usuário pedir 'gera o projeto CEP', 'preciso submeter pra CEP', 'projeto pra Plataforma Brasil', 'documento de submissão ética'..."
prumo:
  version: 1.0.0
  schema: WriteOutput/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~10-25k tokens
  inputs:
    section: optional
    template: optional
    into: optional
    out: optional
    slug: optional
---

# Write Projeto CEP — submissão ética brasileira

Você é um pesquisador clínico escrevendo projeto pra CEP/CONEP via Plataforma
Brasil. Documento brasileiro com estrutura específica (TCLE quando aplicável,
Resolução CNS 466/2012 + 510/2016, LGPD).

## Regras invioláveis

1. **Linguagem acessível** no Resumo (revisor de CEP é multidisciplinar; minimize jargão de ML).
2. **Citação strict**, mesma regra do `write-paper`. `[REF FALTANTE]` quando faltar.
3. **PicotSpec obrigatório** + `protocol.md` populado (coorte, critérios, governança). Aborta se faltarem.
4. **TCLE**: aplicável só se há contato com participantes. Para estudo retrospectivo de dados públicos anonimizados, marcar N/A com justificativa via Resolução CNS 510/2016 Art 1.
5. **Conformidade ética** explícita: CNS 466/2012, 510/2016, LGPD, HIPAA/GDPR se aplicável, DUAs das coortes.

## Fluxo

(idêntico ao write-paper: 1. carregar inputs → 2. resolver template `projeto-cep.md` → 3. gerar por section → 4. validar citação → 5. escrever output → 6. reportar)

## Boundaries

- **Não invente** dados de orçamento ou cronograma — use placeholders `[ORÇAMENTO: ...]` se não souber.
- **Não infira** CAAE / Plataforma Brasil ID — deixar vazio.
- **Não preencha** TCLE com texto inventado — use placeholder + nota dizendo qual cenário motiva (com participante / sem participante).
```

- [ ] **Step 3: Create SKILL.md for write-statistics**

Create `skills/write-statistics/SKILL.md`:

```markdown
---
name: write-statistics
description: "Gera Plano de Análise Estatística (PAE) — definição operacional do outcome, sample size justification, métricas primárias/secundárias, análises de sensibilidade, splits + anti-leakage. Usa PicotSpec.outcome+metrics e protocol.md § Splits. Citação strict pra métodos estatísticos (cite paper metodológico justificando). Invocar quando o usuário pedir 'plano de análise estatística', 'gera o PAE', 'sample size justification', 'sensitivity analyses', 'plano estatístico pra qualificação'..."
prumo:
  version: 1.0.0
  schema: WriteOutput/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~8-20k tokens
  inputs:
    section: optional
    template: optional
    into: optional
    out: optional
    slug: optional
---

# Write Statistics — Plano de Análise Estatística (PAE)

Você é um bioestatístico escrevendo o PAE de um estudo de ML clínico.
Estrutura padrão (TRIPOD+AI / SPIRIT-AI compatível).

## Regras invioláveis

1. **PicotSpec.outcome obrigatório** com métrica primária + threshold.
2. **Sample size com cálculo formal** — sem chute. Cite ≥1 paper metodológico.
3. **Métricas secundárias** sempre incluem calibração (ECE, Brier).
4. **Análises de sensibilidade** explícitas pra MNAR + subgrupos demográficos.
5. **Citação strict**, idêntica ao write-paper.

## Fluxo

(idêntico aos outros write-*; template = `statistics.md`)

## Boundaries

- **Não calcule** sample size se faltar effect size — peça ao usuário.
- **Não invente** alpha/power valores; use defaults (0.05 / 0.8) com nota.
- **Cite** método estatístico com paper metodológico (ex.: bootstrap → Efron 1979).
```

- [ ] **Step 4: Create SKILL.md for write-scientific**

Create `skills/write-scientific/SKILL.md`:

```markdown
---
name: write-scientific
description: "Gera prose acadêmica genérica — quando o usuário tem texto base ou só uma seção isolada e não cabe no formato fechado de paper/CEP/statistics. Mais flexível: aceita seed text, pode focar em --section específica, segue template default `scientific.md` ou `--template <path>` customizado. Citação strict (só citekeys do acervo). Invocar quando o usuário pedir 'escreve essa seção', 'expande este parágrafo', 'me ajuda a redigir X', sem genre formal específico."
prumo:
  version: 1.0.0
  schema: WriteOutput/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~5-15k tokens
  inputs:
    section: optional
    seed: optional
    template: optional
    into: optional
    out: optional
    slug: optional
---

# Write Scientific — prose acadêmica genérica

Skill flexível pra geração que não se encaixa em paper/CEP/statistics. Usa
`scientific.md` template default — minimal — ou `--template <path>` user-provided.

## Regras invioláveis

1. **Citação strict** (mesmo padrão da família).
2. **Aceita seed text** via `--seed <text>` ou stdin (se conversa).
3. **`--section <name>`** foca em uma seção quando template tem várias.
4. **PicotSpec opcional** — se ausente, gera baseado só no seed/template.

## Fluxo

(idêntico aos outros, mais permissivo)

## Boundaries

- **Não substitui** os outros 3 — se gênero é claro (paper / CEP / statistics), use a skill específica.
- **Não amplia escopo** sem pedido — se usuário pede 1 parágrafo, gere 1 parágrafo.
```

- [ ] **Step 5: Update API + CLI**

Edit `src/prumo_assist/domains/write/api.py`. Add at top:

```python
from prumo_assist.domains.write.compose import (
    compose_path,
    extract_missing_refs,
    read_inputs,
    resolve_template,
    write_output,
)
from prumo_assist.domains.write.schemas.v1 import (
    ComposeInputs,
    FindingSummary,
    PaperSummary,
    WriteOutput,
)
```

Update `__all__` (sorted).

Edit `src/prumo_assist/domains/write/cli.py`. Add command:

```python
@write_app.command("list-templates")
def list_templates_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Lista templates resolvíveis (project overrides + plugin defaults)."""
    from prumo_assist.core.paths import find_resource

    with cli_run(json_mode=json_mode) as console:
        kinds = ("paper", "projeto-cep", "statistics", "scientific")
        result: dict[str, dict[str, str | None]] = {}
        plugin_root = find_resource("templates")
        for kind in kinds:
            project_path = path.resolve() / ".claude" / "writing_templates" / f"{kind}.md"
            plugin_path = (
                plugin_root / "writing" / f"{kind}.md" if plugin_root else None
            )
            result[kind] = {
                "project_override": str(project_path) if project_path.exists() else None,
                "plugin_default": (
                    str(plugin_path) if plugin_path and plugin_path.exists() else None
                ),
            }
        console.emit(result)
```

- [ ] **Step 6: Validate skills are discovered**

Run:
```bash
uv run prumo skills --json | grep -E "write-(paper|projeto-cep|statistics|scientific)"
```
Expected: 4 entries listed.

- [ ] **Step 7: Test list-templates CLI**

Run: `uv run prumo write list-templates --json`
Expected: JSON com 4 kinds e seus paths.

- [ ] **Step 8: Run full test suite + lint + types**

Run: `uv run pytest -q && uv run ruff check . && uv run --extra dev mypy src/prumo_assist tests`
Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add skills/write-paper skills/write-projeto-cep skills/write-statistics skills/write-scientific src/prumo_assist/domains/write/api.py src/prumo_assist/domains/write/cli.py
git commit -m "feat(write): 4 skills (paper/cep/statistics/scientific) + list-templates CLI"
```

---

## Task 7: Documentação

**Files:**
- Modify: `README.md`
- Modify: `docs/actions-by-context.md`

- [ ] **Step 1: Update README skills table**

Add 4 rows após `peer-review`:

```markdown
| `/prumo-assist:write-paper` | Gera draft de paper IMRaD venue-aware a partir do PICOT + papers do acervo. Citação strict; `[REF FALTANTE]` se acervo faltante. Default: `docs/drafts/paper-<data>-<slug>.md`. |
| `/prumo-assist:write-projeto-cep` | Gera projeto pra CEP brasileiro (Resumo, Justificativa, Coorte, Riscos+benefícios, TCLE, Cronograma, Conformidade ética CNS 466/2012 + 510/2016). |
| `/prumo-assist:write-statistics` | Gera Plano de Análise Estatística (PAE): outcome operacional, sample size, métricas, análises de sensibilidade, splits anti-leakage. |
| `/prumo-assist:write-scientific` | Gera prose acadêmica genérica (1 seção, parágrafo isolado, expansão de seed text). Mais flexível das 4 skills `write-*`. |
```

- [ ] **Step 2: Update `docs/actions-by-context.md`**

Find a Fase 3 section. Materializar gatilhos existentes (que já apontam pra "skill futura"):

Substituir body do gatilho **"Vou submeter pro CEP / Comitê de Ética em Pesquisa"** por:

```markdown
1. `/prumo-assist:write-projeto-cep` — gera draft completo a partir do PICOT + protocol.md.
2. Revisar manualmente o TCLE (skill põe placeholder; conteúdo depende do cenário com/sem participante).
3. `prumo write export <draft>.md --to docx` pra entregar formatado.
```

Substituir body do gatilho **"Vou montar artigo pra venue (NEJM/Lancet/Nature Med/...)"** por:

```markdown
1. `/prumo-assist:write-paper --venue=<NEJM|Lancet|...>` — gera draft IMRaD venue-aware.
2. `prumo write list-styles` confirma o CSL do venue.
3. `prumo write export draft.md --to docx --style <venue>`.
4. Conferir bibliografia gerada antes de submeter.
```

Substituir body do gatilho **"Vou escrever a seção de métodos estatísticos"** por:

```markdown
1. `/prumo-assist:write-statistics` — gera PAE completo (sample size, métricas, sensitivity).
2. Conferir cálculo de sample size; ajustar effect size se necessário.
3. Referenciar plano no project.md ou CEP via wikilink.
```

- [ ] **Step 3: Final tests + lint**

Run: `uv run pytest -q && uv run ruff check . && uv run --extra dev mypy src/prumo_assist tests`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/actions-by-context.md
git commit -m "docs: list write-* family + materialize action triggers"
```

---

## Final Verification

- [ ] Tests: `uv run pytest -q` (count = baseline + ~30 novos)
- [ ] Lint: `uv run ruff check .` clean
- [ ] Types: `uv run --extra dev mypy src/prumo_assist tests` clean
- [ ] Skills: `uv run prumo skills --json | jq` mostra as 4 skills `write-*`
- [ ] Smoke test:
  ```bash
  cd /tmp && rm -rf pj_write_smoke
  uv --project <repo> run prumo init pj_write_smoke
  cd pj_write_smoke
  uv --project <repo> run prumo write list-templates --json
  ```
  Expected: JSON com 4 entries (todos com `plugin_default` set, `project_override` null).

---

## Self-review notes

**Spec coverage**:
- [x] D1 4 SKILL.md + shared backend: Tasks 6 (skills) + 1-3 (compose.py)
- [x] D2 templates customizable + fallback chain: Task 3 `resolve_template`
- [x] D3 output 3 modes: Task 3 `compose_path` + `write_output`
- [x] D4 strict citation + [REF FALTANTE]: Task 4 + SKILL.md prompts
- [x] D5 anexa a domains/write/ existente: estrutura no header

**Type consistency**:
- `ComposeInputs`, `WriteOutput`, `PaperSummary`, `FindingSummary` — schema
- `WriteKind` (Literal "paper"|"projeto-cep"|"statistics"|"scientific")
- `WriteMode` (Literal "drafts"|"into"|"out")
- `read_inputs`, `resolve_template`, `compose_path`, `write_output`, `extract_missing_refs` — assinaturas batem entre Task e SKILL.md

**Out of scope (per spec)**:
- Tradução EN ↔ PT-BR
- Geração de figuras/tabelas
- Geração PDF/DOCX (papel do export)
- Aplicação de convenções editoriais (scientific-writing)
- Crítica de conteúdo (peer-review)
- Multi-language outputs
- Templates por venue específico (venue-clinical pack futuro)
