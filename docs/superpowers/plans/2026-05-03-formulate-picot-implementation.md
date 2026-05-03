# `formulate-picot` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar a skill `/prumo-assist:formulate-picot` ponta-a-ponta — schema canônico (`.claude/picot.toml`), renders nos 3 destinos (`protocol.md`, `project.md`, ADRs), diff de versão e modo Socrático/Formalize via SKILL.md agêntica.

**Architecture:** Domínio novo `domains/protocol/` segue o padrão de `domains/paper/`. Schema Pydantic (`PicotSpec/v1`) é fonte única; `picot_io.py` lê/escreve TOML; `render.py` produz blocos delimitados; `diff.py` compara estruturas; `adr.py` gera ADRs; `ops.py` orquestra os 4 modos (init/formalize/propagate/diff). SKILL.md fica responsável só pelo lado agêntico (Socrático + Formalize); o resto é Python determinístico.

**Tech Stack:** Python 3.11+, Pydantic v2, `tomllib` (stdlib, leitura), `tomli_w` (escrita, nova dep), Typer (CLI), pytest, ruff strict, mypy strict.

---

## File Structure

| Caminho | Ação | Responsabilidade |
|---|---|---|
| `pyproject.toml` | **Modify** | Adicionar `tomli-w>=1.0` em `dependencies` |
| `src/prumo_assist/domains/protocol/__init__.py` | **Create** | Docstring do domínio |
| `src/prumo_assist/domains/protocol/schemas/__init__.py` | **Create** | Vazio |
| `src/prumo_assist/domains/protocol/schemas/v1.py` | **Create** | `PicotSpec`, `Hypothesis` Pydantic models |
| `src/prumo_assist/domains/protocol/picot_io.py` | **Create** | `read_picot`, `write_picot`, `picot_path`, `picot_hash` |
| `src/prumo_assist/domains/protocol/render.py` | **Create** | `render_protocol_block`, `render_project_block`, `replace_block`, regex helpers |
| `src/prumo_assist/domains/protocol/diff.py` | **Create** | `PicotDiff` dataclass, `diff_picot`, `is_structural` |
| `src/prumo_assist/domains/protocol/adr.py` | **Create** | `next_adr_number`, `compose_adr`, `extract_picot_snapshot` |
| `src/prumo_assist/domains/protocol/ops.py` | **Create** | `propagate(pj)`, `diff_against_last_adr(pj)` orchestrators |
| `src/prumo_assist/domains/protocol/api.py` | **Create** | Re-exports |
| `src/prumo_assist/domains/protocol/cli.py` | **Create** | `prumo protocol propagate`, `prumo protocol diff` |
| `src/prumo_assist/cli.py` | **Modify** | Registrar `protocol_app` |
| `src/prumo_assist/api.py` | **Modify** | Adicionar `from ... import protocol` |
| `skills/formulate-picot/SKILL.md` | **Create** | Prompt do agente Socrático/Formalize |
| `tests/unit/protocol/__init__.py` | **Create** | Vazio |
| `tests/unit/protocol/test_schemas_v1.py` | **Create** | Schema validation tests |
| `tests/unit/protocol/test_picot_io.py` | **Create** | TOML round-trip + hash tests |
| `tests/unit/protocol/test_render.py` | **Create** | Render block tests |
| `tests/unit/protocol/test_diff.py` | **Create** | Deep diff tests |
| `tests/unit/protocol/test_adr.py` | **Create** | ADR generation tests |
| `tests/unit/protocol/test_ops.py` | **Create** | End-to-end orchestrator tests |
| `tests/unit/protocol/test_cli.py` | **Create** | CLI integration tests |
| `docs/actions-by-context.md` | **Modify** | Adicionar gatilho "Quero formalizar PICOT" |
| `README.md` | **Modify** | Adicionar `formulate-picot` na tabela de skills |

---

## Task 1: Dependência + schema `PicotSpec/v1`

**Files:**
- Modify: `pyproject.toml` (add `tomli-w`)
- Create: `src/prumo_assist/domains/protocol/__init__.py`
- Create: `src/prumo_assist/domains/protocol/schemas/__init__.py`
- Create: `src/prumo_assist/domains/protocol/schemas/v1.py`
- Test: `tests/unit/protocol/__init__.py` (empty)
- Test: `tests/unit/protocol/test_schemas_v1.py`

- [ ] **Step 1: Add `tomli-w` to `pyproject.toml`**

In `pyproject.toml`, find the `dependencies = [` block and append:

```toml
dependencies = [
  "typer>=0.12",
  "rich>=13.7",
  "pydantic>=2.6",
  "pydantic-settings>=2.2",
  "pyyaml>=6.0",
  "jinja2>=3.1",
  "tomli-w>=1.0",
]
```

Run: `uv sync --extra dev`
Expected: installs `tomli-w`.

- [ ] **Step 2: Create `__init__.py` files**

```bash
mkdir -p src/prumo_assist/domains/protocol/schemas
mkdir -p tests/unit/protocol
```

Create `src/prumo_assist/domains/protocol/__init__.py`:

```python
"""Domínio ``protocol`` — formalização de PICOT.

Cobre o ciclo de vida da PICOT do projeto:

- ``schemas.v1.PicotSpec`` — schema canônico (Pydantic)
- ``picot_io`` — read/write de ``.claude/picot.toml``
- ``render`` — TOML → blocos delimitados em ``protocol.md`` / ``project.md``
- ``diff`` — deep diff entre versões pra detectar mudança estrutural
- ``adr`` — gera ADRs append-only quando versão muda
- ``ops`` — orquestra ``propagate`` e ``diff_against_last_adr``

A parte agêntica (modos Socrático e Formalize) vive na skill
``skills/formulate-picot/SKILL.md``; este pacote é puro Python determinístico.
"""

from __future__ import annotations
```

Create empty `src/prumo_assist/domains/protocol/schemas/__init__.py`:

```python
```

(Just an empty file with a newline.)

Create empty `tests/unit/protocol/__init__.py`:

```python
```

- [ ] **Step 3: Write failing test for `PicotSpec` schema**

Create `tests/unit/protocol/test_schemas_v1.py`:

```python
"""Tests para PicotSpec/v1."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from prumo_assist.domains.protocol.schemas.v1 import Hypothesis, PicotSpec


def _valid_clinical() -> dict:
    return {
        "type": "clinical",
        "created_at": "2026-05-03",
        "last_updated": "2026-05-03",
        "version": 1,
        "population": "DS_A + DS_BB",
        "intervention": "intervenção X",
        "comparison": "cuidado usual",
        "outcome": "AUROC ≥ 0.85",
        "time": "retrospectivo, sem janela",
        "hypothesis": {
            "statement": "combinado supera comparador em ≥5 pontos AUC",
            "rationale": "estudos-piloto sugerem efeito relevante",
            "metrics": ["AUROC", "ECE"],
        },
    }


def test_clinical_picot_valid() -> None:
    spec = PicotSpec.model_validate(_valid_clinical())
    assert spec.type == "clinical"
    assert spec.version == 1
    assert spec.hypothesis.statement.startswith("combinado")


def test_clinical_picot_requires_picot_fields() -> None:
    data = _valid_clinical()
    data["population"] = ""
    with pytest.raises(ValidationError) as exc:
        PicotSpec.model_validate(data)
    assert "population" in str(exc.value)


def test_methodological_picot_valid() -> None:
    data = {
        "type": "methodological",
        "created_at": "2026-05-03",
        "last_updated": "2026-05-03",
        "version": 1,
        "contribution": "método estatístico M",
        "hypothesis_validity_condition": "a suposição S falha",
        "hypothesis": {
            "statement": "o método M mantém a propriedade P sob S",
            "rationale": "a correção C compensa o viés",
            "metrics": ["coverage", "set-size"],
        },
    }
    spec = PicotSpec.model_validate(data)
    assert spec.type == "methodological"
    assert spec.population is None
    assert spec.contribution is not None


def test_methodological_picot_requires_contribution() -> None:
    data = {
        "type": "methodological",
        "created_at": "2026-05-03",
        "last_updated": "2026-05-03",
        "version": 1,
        "contribution": "",
        "hypothesis_validity_condition": "X",
        "hypothesis": {
            "statement": "Y",
            "rationale": "Z",
            "metrics": ["m"],
        },
    }
    with pytest.raises(ValidationError) as exc:
        PicotSpec.model_validate(data)
    assert "contribution" in str(exc.value)


def test_hypothesis_metrics_must_be_non_empty() -> None:
    data = _valid_clinical()
    data["hypothesis"]["metrics"] = []
    with pytest.raises(ValidationError):
        PicotSpec.model_validate(data)


def test_version_must_be_positive() -> None:
    data = _valid_clinical()
    data["version"] = 0
    with pytest.raises(ValidationError):
        PicotSpec.model_validate(data)


def test_schema_version_constant() -> None:
    spec = PicotSpec.model_validate(_valid_clinical())
    assert spec.schema_version == "PicotSpec/v1"


def test_hypothesis_statement_required() -> None:
    h = {"statement": "", "rationale": "x", "metrics": ["m"]}
    with pytest.raises(ValidationError):
        Hypothesis.model_validate(h)
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/unit/protocol/test_schemas_v1.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prumo_assist.domains.protocol.schemas.v1'`

- [ ] **Step 5: Implement `PicotSpec/v1`**

Create `src/prumo_assist/domains/protocol/schemas/v1.py`:

```python
"""``PicotSpec/v1`` — schema canônico da PICOT do projeto.

Vive em ``.claude/picot.toml`` e é a fonte única de verdade. Os 3 destinos
(``docs/protocol.md``, ``docs/project.md``, ADRs) são renders.

Versionamento forward-only: nunca remover ou renomear campos; novos campos
sempre opcionais com default. ``v2`` lê ``v1``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Hypothesis(BaseModel):
    """Hipótese formal única do projeto."""

    statement: str = Field(..., min_length=1, description="Frase declarativa formal.")
    rationale: str = Field(..., min_length=1, description="Por que esperar — ok citar literatura.")
    metrics: list[str] = Field(..., min_length=1, description="Como testar — ex.: AUROC, ECE.")


class PicotSpec(BaseModel):
    """Schema canônico de PICOT por projeto.

    Em ``type = 'clinical'``, P/I/C/O/T são obrigatórios.
    Em ``type = 'methodological'``, ``contribution`` + ``hypothesis_validity_condition``
    são obrigatórios; P/I/C/O/T podem ser ``None`` (omitidos do TOML).
    """

    schema_version: Literal["PicotSpec/v1"] = "PicotSpec/v1"
    type: Literal["clinical", "methodological"]
    created_at: str = Field(..., description="ISO date YYYY-MM-DD da primeira escrita.")
    last_updated: str = Field(..., description="ISO date YYYY-MM-DD da última escrita.")
    version: int = Field(..., ge=1, description="Bump em mudança estrutural.")

    population: str | None = None
    intervention: str | None = None
    comparison: str | None = None
    outcome: str | None = None
    time: str | None = None

    contribution: str | None = None
    hypothesis_validity_condition: str | None = None

    hypothesis: Hypothesis

    @model_validator(mode="after")
    def _validate_required_by_type(self) -> PicotSpec:
        if self.type == "clinical":
            for field in ("population", "intervention", "comparison", "outcome", "time"):
                value = getattr(self, field)
                if not value:
                    raise ValueError(
                        f"type='clinical': campo '{field}' é obrigatório (não-vazio)."
                    )
        elif self.type == "methodological":
            for field in ("contribution", "hypothesis_validity_condition"):
                value = getattr(self, field)
                if not value:
                    raise ValueError(
                        f"type='methodological': campo '{field}' é obrigatório (não-vazio)."
                    )
        return self
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/protocol/test_schemas_v1.py -v`
Expected: 8 tests PASS

- [ ] **Step 7: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/protocol tests/unit/protocol`
Run: `uv run --extra dev mypy src/prumo_assist/domains/protocol`
Expected: clean

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml src/prumo_assist/domains/protocol tests/unit/protocol
git commit -m "feat(protocol): PicotSpec/v1 schema + tomli-w dep"
```

---

## Task 2: Read/Write `.claude/picot.toml` + hash

**Files:**
- Create: `src/prumo_assist/domains/protocol/picot_io.py`
- Test: `tests/unit/protocol/test_picot_io.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/protocol/test_picot_io.py`:

```python
"""Tests para read/write/hash de .claude/picot.toml."""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist.domains.protocol.picot_io import (
    picot_hash,
    picot_path,
    read_picot,
    write_picot,
)
from prumo_assist.domains.protocol.schemas.v1 import Hypothesis, PicotSpec


def _spec() -> PicotSpec:
    return PicotSpec(
        type="clinical",
        created_at="2026-05-03",
        last_updated="2026-05-03",
        version=1,
        population="DS_A + DS_BB",
        intervention="IntervencaoX",
        comparison="melhor comparador",
        outcome="AUROC ≥ 0.85",
        time="retrospectivo",
        hypothesis=Hypothesis(
            statement="combinado supera comparador em ≥5 pontos AUC",
            rationale="efeito piloto",
            metrics=["AUROC", "ECE"],
        ),
    )


def test_picot_path_returns_expected(tmp_path: Path) -> None:
    assert picot_path(tmp_path) == tmp_path / ".claude" / "picot.toml"


def test_write_creates_file(tmp_path: Path) -> None:
    spec = _spec()
    written = write_picot(tmp_path, spec)
    assert written.exists()
    assert written == picot_path(tmp_path)


def test_write_then_read_round_trip(tmp_path: Path) -> None:
    original = _spec()
    write_picot(tmp_path, original)
    loaded = read_picot(tmp_path)
    assert loaded.model_dump() == original.model_dump()


def test_read_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_picot(tmp_path)


def test_read_validates(tmp_path: Path) -> None:
    p = picot_path(tmp_path)
    p.parent.mkdir(parents=True)
    p.write_text(
        '[picot]\n'
        'type = "clinical"\n'
        'created_at = "2026-05-03"\n'
        'last_updated = "2026-05-03"\n'
        'version = 1\n'
        'population = ""\n'  # invalido
        'intervention = "X"\n'
        'comparison = "Y"\n'
        'outcome = "Z"\n'
        'time = "T"\n'
        '[picot.hypothesis]\n'
        'statement = "S"\n'
        'rationale = "R"\n'
        'metrics = ["m"]\n'
    )
    with pytest.raises(ValueError):
        read_picot(tmp_path)


def test_picot_hash_stable(tmp_path: Path) -> None:
    spec = _spec()
    write_picot(tmp_path, spec)
    h1 = picot_hash(tmp_path)
    h2 = picot_hash(tmp_path)
    assert h1 == h2
    assert len(h1) == 8


def test_picot_hash_changes_on_field_change(tmp_path: Path) -> None:
    spec = _spec()
    write_picot(tmp_path, spec)
    h1 = picot_hash(tmp_path)
    spec2 = spec.model_copy(update={"population": "NOVO"})
    write_picot(tmp_path, spec2)
    h2 = picot_hash(tmp_path)
    assert h1 != h2


def test_methodological_omits_picot_fields(tmp_path: Path) -> None:
    spec = PicotSpec(
        type="methodological",
        created_at="2026-05-03",
        last_updated="2026-05-03",
        version=1,
        contribution="X",
        hypothesis_validity_condition="Y",
        hypothesis=Hypothesis(
            statement="S",
            rationale="R",
            metrics=["m"],
        ),
    )
    written = write_picot(tmp_path, spec)
    text = written.read_text()
    # Métodológico não deve emitir population/intervention vazios.
    assert "population" not in text
    assert "intervention" not in text
    assert 'contribution = "X"' in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/protocol/test_picot_io.py -v`
Expected: FAIL — `picot_io` module not defined.

- [ ] **Step 3: Implement `picot_io.py`**

Create `src/prumo_assist/domains/protocol/picot_io.py`:

```python
"""Read/write canônico de ``.claude/picot.toml``.

Usa ``tomllib`` (stdlib) pra leitura e ``tomli_w`` pra escrita. Validação via
Pydantic (``PicotSpec/v1``) acontece no read; write pré-condiciona spec válido.

Hash sha256[:8] do conteúdo serve pra detectar drift nos blocos delimitados
dos destinos (``protocol.md``, ``project.md``).
"""

from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path
from typing import Any

import tomli_w

from prumo_assist.domains.protocol.schemas.v1 import PicotSpec


def picot_path(pj_path: Path) -> Path:
    """Retorna ``<pj>/.claude/picot.toml``."""
    return pj_path / ".claude" / "picot.toml"


def read_picot(pj_path: Path) -> PicotSpec:
    """Lê e valida ``.claude/picot.toml``. Levanta ``FileNotFoundError`` se ausente."""
    path = picot_path(pj_path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} não encontrado. Rode `/prumo-assist:formulate-picot init` primeiro."
        )
    with path.open("rb") as f:
        raw = tomllib.load(f)
    picot_block = raw.get("picot")
    if not isinstance(picot_block, dict):
        raise ValueError(f"{path}: bloco [picot] ausente ou inválido.")
    return PicotSpec.model_validate(picot_block)


def write_picot(pj_path: Path, spec: PicotSpec) -> Path:
    """Escreve ``.claude/picot.toml`` a partir de ``spec`` (já validado).

    Campos ``None`` são omitidos do TOML (TOML não tem null nativo).
    Preserva ordem dos campos do schema.
    """
    path = picot_path(pj_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = spec_to_toml_payload(spec)
    text = tomli_w.dumps(payload)
    path.write_text(text, encoding="utf-8")
    return path


def picot_hash(pj_path: Path) -> str:
    """sha256[:8] do conteúdo do TOML — usado em ``<!-- picot:begin hash=...-->``."""
    path = picot_path(pj_path)
    if not path.exists():
        raise FileNotFoundError(f"{path} não encontrado.")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest[:8]


def spec_to_toml_payload(spec: PicotSpec) -> dict[str, Any]:
    """Converte ``PicotSpec`` em dict TOML-friendly omitindo ``None``s."""
    dumped = spec.model_dump(mode="python", exclude={"schema_version"})
    hypothesis = dumped.pop("hypothesis")
    base = {k: v for k, v in dumped.items() if v is not None}
    return {"picot": {**base, "hypothesis": hypothesis}}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/protocol/test_picot_io.py -v`
Expected: 8 tests PASS

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/protocol/picot_io.py tests/unit/protocol/test_picot_io.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/protocol/picot_io.py`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/domains/protocol/picot_io.py tests/unit/protocol/test_picot_io.py
git commit -m "feat(protocol): read/write/hash .claude/picot.toml"
```

---

## Task 3: Render TOML → blocos delimitados

**Files:**
- Create: `src/prumo_assist/domains/protocol/render.py`
- Test: `tests/unit/protocol/test_render.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/protocol/test_render.py`:

```python
"""Tests para render TOML → blocos delimitados em protocol.md / project.md."""

from __future__ import annotations

from prumo_assist.domains.protocol.render import (
    BLOCK_BEGIN_RE,
    PICOT_BEGIN_PREFIX,
    PICOT_END,
    render_project_block,
    render_protocol_block,
    replace_or_insert_block,
)
from prumo_assist.domains.protocol.schemas.v1 import Hypothesis, PicotSpec


def _spec() -> PicotSpec:
    return PicotSpec(
        type="clinical",
        created_at="2026-05-03",
        last_updated="2026-05-03",
        version=2,
        population="DS_A + DS_BB",
        intervention="fusão combinado",
        comparison="melhor comparador",
        outcome="AUROC ≥ 0.85",
        time="retrospectivo",
        hypothesis=Hypothesis(
            statement="combinado supera comparador em ≥5 pts AUC",
            rationale="efeito piloto",
            metrics=["AUROC", "ECE"],
        ),
    )


def test_render_protocol_block_includes_fields() -> None:
    out = render_protocol_block(_spec(), hash8="a1b2c3d4")
    assert out.startswith(f"{PICOT_BEGIN_PREFIX}v=2 hash=a1b2c3d4 -->")
    assert out.rstrip().endswith(PICOT_END)
    assert "DS_A + DS_BB" in out
    assert "fusão combinado" in out
    assert "melhor comparador" in out
    assert "AUROC ≥ 0.85" in out
    assert "retrospectivo" in out
    assert "combinado supera comparador" in out
    assert "AUROC, ECE" in out


def test_render_project_block_includes_fields() -> None:
    out = render_project_block(_spec(), hash8="a1b2c3d4")
    assert "Pergunta de pesquisa" in out
    assert "Hipótese central" in out
    assert "combinado supera" in out


def test_render_methodological_omits_picot_fields() -> None:
    spec = PicotSpec(
        type="methodological",
        created_at="2026-05-03",
        last_updated="2026-05-03",
        version=1,
        contribution="método M",
        hypothesis_validity_condition="a suposição S falha",
        hypothesis=Hypothesis(
            statement="propriedade P mantida sob S",
            rationale="a correção C compensa",
            metrics=["coverage"],
        ),
    )
    out = render_project_block(spec, hash8="00000000")
    assert "método M" in out
    assert "suposição S" in out
    # campos clínicos não aparecem
    assert "População" not in out


def test_replace_or_insert_inserts_when_absent() -> None:
    text = "# Protocolo\n\n## Contexto\n\nProse humana.\n"
    block = render_protocol_block(_spec(), hash8="a1b2c3d4")
    out = replace_or_insert_block(text, block, anchor_pattern=r"^## Contexto.*$")
    assert PICOT_BEGIN_PREFIX in out
    assert PICOT_END in out
    assert "Prose humana." in out  # preservado


def test_replace_or_insert_replaces_existing() -> None:
    block_old = (
        f"{PICOT_BEGIN_PREFIX}v=1 hash=11111111 -->\nold content\n{PICOT_END}"
    )
    block_new = render_protocol_block(_spec(), hash8="a1b2c3d4")
    text = f"# Doc\n\n{block_old}\n\nFooter humano.\n"
    out = replace_or_insert_block(text, block_new, anchor_pattern=r"^# Doc.*$")
    assert "old content" not in out
    assert "DS_A" in out
    assert "Footer humano." in out


def test_block_begin_re_extracts_version_and_hash() -> None:
    block = render_protocol_block(_spec(), hash8="deadbeef")
    m = BLOCK_BEGIN_RE.search(block)
    assert m is not None
    assert m.group("version") == "2"
    assert m.group("hash") == "deadbeef"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/protocol/test_render.py -v`
Expected: FAIL — `render` module not defined.

- [ ] **Step 3: Implement `render.py`**

Create `src/prumo_assist/domains/protocol/render.py`:

```python
"""Renderiza ``PicotSpec`` em blocos Markdown delimitados pros 3 destinos.

Bloco padrão::

    <!-- picot:begin v=N hash=sha8 -->
    ... conteúdo ...
    <!-- picot:end -->

``v`` e ``hash`` permitem detectar drift sem reabrir o TOML canônico.
"""

from __future__ import annotations

import re

from prumo_assist.domains.protocol.schemas.v1 import PicotSpec

PICOT_BEGIN_PREFIX = "<!-- picot:begin "
PICOT_END = "<!-- picot:end -->"

BLOCK_BEGIN_RE = re.compile(
    r"<!--\s*picot:begin\s+v=(?P<version>\d+)\s+hash=(?P<hash>[a-f0-9]{8})\s*-->",
)
BLOCK_FULL_RE = re.compile(
    r"<!--\s*picot:begin\s+v=\d+\s+hash=[a-f0-9]{8}\s*-->.*?<!--\s*picot:end\s*-->",
    flags=re.DOTALL,
)


def render_protocol_block(spec: PicotSpec, *, hash8: str) -> str:
    """Render operacional pra ``docs/protocol.md`` (concreto, conferível)."""
    header = f"{PICOT_BEGIN_PREFIX}v={spec.version} hash={hash8} -->"
    lines = [header, ""]
    if spec.type == "clinical":
        lines += [
            f"**População operacional.** {spec.population}",
            "",
            f"**Intervenção (sob teste).** {spec.intervention}",
            "",
            f"**Comparação (baseline).** {spec.comparison}",
            "",
            f"**Desfecho primário.** {spec.outcome}",
            "",
            f"**Janela temporal.** {spec.time}",
            "",
        ]
    else:
        lines += [
            f"**Contribuição.** {spec.contribution}",
            "",
            f"**Condição de validade.** {spec.hypothesis_validity_condition}",
            "",
        ]
    lines += [
        f"**Hipótese formal.** {spec.hypothesis.statement}",
        "",
        f"*Métricas: {', '.join(spec.hypothesis.metrics)}.*",
        "",
        PICOT_END,
    ]
    return "\n".join(lines)


def render_project_block(spec: PicotSpec, *, hash8: str) -> str:
    """Render acadêmico pra ``docs/project.md`` (prosa formal)."""
    header = f"{PICOT_BEGIN_PREFIX}v={spec.version} hash={hash8} -->"
    lines = [header, "", "## Pergunta de pesquisa", ""]
    if spec.type == "clinical":
        lines.append(
            f"Em **{spec.population}**, a aplicação de **{spec.intervention}** comparada a "
            f"**{spec.comparison}** produz **{spec.outcome}**, no horizonte de **{spec.time}**?"
        )
    else:
        lines += [
            f"**Contribuição teórica:** {spec.contribution}.",
            "",
            f"**Condição de validade:** {spec.hypothesis_validity_condition}.",
        ]
    lines += [
        "",
        "## Hipótese central",
        "",
        spec.hypothesis.statement + ".",
        "",
        spec.hypothesis.rationale,
        "",
        PICOT_END,
    ]
    return "\n".join(lines)


def replace_or_insert_block(text: str, new_block: str, *, anchor_pattern: str) -> str:
    """Substitui bloco existente; se ausente, insere logo após ``anchor_pattern``.

    ``anchor_pattern`` é regex multiline (ex.: ``r'^## Contexto.*$'``). Se nenhum
    bloco picot existir e o anchor não casar, append no final.
    """
    if BLOCK_FULL_RE.search(text):
        return BLOCK_FULL_RE.sub(new_block, text, count=1)
    anchor = re.compile(anchor_pattern, flags=re.MULTILINE)
    m = anchor.search(text)
    if m:
        end = m.end()
        return text[:end] + "\n\n" + new_block + "\n" + text[end:]
    sep = "" if text.endswith("\n") else "\n"
    return text + sep + "\n" + new_block + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/protocol/test_render.py -v`
Expected: 6 tests PASS

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/protocol/render.py tests/unit/protocol/test_render.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/protocol/render.py`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/domains/protocol/render.py tests/unit/protocol/test_render.py
git commit -m "feat(protocol): render PicotSpec to delimited blocks"
```

---

## Task 4: Deep diff entre versões PICOT

**Files:**
- Create: `src/prumo_assist/domains/protocol/diff.py`
- Test: `tests/unit/protocol/test_diff.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/protocol/test_diff.py`:

```python
"""Tests para deep diff entre PicotSpec atual e snapshot do último ADR."""

from __future__ import annotations

from prumo_assist.domains.protocol.diff import (
    FieldChange,
    PicotDiff,
    diff_picot,
    is_structural_field,
)
from prumo_assist.domains.protocol.schemas.v1 import Hypothesis, PicotSpec


def _spec(**overrides: object) -> PicotSpec:
    base = dict(
        type="clinical",
        created_at="2026-05-03",
        last_updated="2026-05-03",
        version=1,
        population="DS_A",
        intervention="IntervencaoX",
        comparison="best baseline",
        outcome="AUROC ≥ 0.85",
        time="retrospectivo",
        hypothesis=Hypothesis(
            statement="combinado supera comparador em ≥5 pts",
            rationale="piloto",
            metrics=["AUROC"],
        ),
    )
    base.update(overrides)
    return PicotSpec(**base)  # type: ignore[arg-type]


def test_diff_no_changes() -> None:
    a, b = _spec(), _spec()
    out = diff_picot(a, b)
    assert isinstance(out, PicotDiff)
    assert out.changes == []
    assert out.has_structural is False


def test_diff_structural_field_change() -> None:
    a = _spec()
    b = _spec(population="DS_A + DS_BB")
    out = diff_picot(a, b)
    assert len(out.changes) == 1
    change = out.changes[0]
    assert change.field == "population"
    assert change.before == "DS_A"
    assert change.after == "DS_A + DS_BB"
    assert change.structural is True
    assert out.has_structural is True


def test_diff_non_structural_field_change_does_not_flag() -> None:
    a = _spec()
    b = _spec(last_updated="2026-06-01")
    out = diff_picot(a, b)
    assert any(c.field == "last_updated" for c in out.changes)
    assert out.has_structural is False


def test_diff_hypothesis_statement() -> None:
    a = _spec()
    b = _spec(
        hypothesis=Hypothesis(
            statement="combinado supera comparador em ≥7 pts",
            rationale="piloto",
            metrics=["AUROC"],
        )
    )
    out = diff_picot(a, b)
    fields = [c.field for c in out.changes]
    assert "hypothesis.statement" in fields
    statement_change = next(c for c in out.changes if c.field == "hypothesis.statement")
    assert statement_change.structural is True


def test_diff_hypothesis_rationale_not_structural() -> None:
    a = _spec()
    b = _spec(
        hypothesis=Hypothesis(
            statement=a.hypothesis.statement,
            rationale="motivo refinado",
            metrics=a.hypothesis.metrics,
        )
    )
    out = diff_picot(a, b)
    rationale_changes = [c for c in out.changes if c.field == "hypothesis.rationale"]
    assert len(rationale_changes) == 1
    assert rationale_changes[0].structural is False
    assert out.has_structural is False


def test_diff_metrics_change_is_structural() -> None:
    a = _spec()
    b = _spec(
        hypothesis=Hypothesis(
            statement=a.hypothesis.statement,
            rationale=a.hypothesis.rationale,
            metrics=["AUROC", "ECE"],
        )
    )
    out = diff_picot(a, b)
    metrics_change = next(c for c in out.changes if c.field == "hypothesis.metrics")
    assert metrics_change.structural is True


def test_is_structural_field() -> None:
    assert is_structural_field("population") is True
    assert is_structural_field("hypothesis.statement") is True
    assert is_structural_field("hypothesis.metrics") is True
    assert is_structural_field("last_updated") is False
    assert is_structural_field("hypothesis.rationale") is False
    assert is_structural_field("version") is False  # bump é consequência, não sinal
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/protocol/test_diff.py -v`
Expected: FAIL — `diff` module not defined.

- [ ] **Step 3: Implement `diff.py`**

Create `src/prumo_assist/domains/protocol/diff.py`:

```python
"""Deep diff entre dois ``PicotSpec`` (atual vs snapshot do último ADR).

Detecta quais campos mudaram e quais são "estruturais" (mudança = bump de
versão + ADR novo). Campos não-estruturais (``last_updated``, ``rationale``)
podem mudar livremente sem bump.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from prumo_assist.domains.protocol.schemas.v1 import PicotSpec

STRUCTURAL_FIELDS: frozenset[str] = frozenset(
    {
        "type",
        "population",
        "intervention",
        "comparison",
        "outcome",
        "time",
        "contribution",
        "hypothesis_validity_condition",
        "hypothesis.statement",
        "hypothesis.metrics",
    }
)


def is_structural_field(field: str) -> bool:
    """``True`` se a mudança nesse campo deve gerar bump + ADR."""
    return field in STRUCTURAL_FIELDS


@dataclass(frozen=True)
class FieldChange:
    """Mudança em 1 campo do ``PicotSpec``."""

    field: str
    before: Any
    after: Any
    structural: bool


@dataclass(frozen=True)
class PicotDiff:
    """Resultado de ``diff_picot``: lista de mudanças + flag de structural."""

    changes: list[FieldChange]

    @property
    def has_structural(self) -> bool:
        return any(c.structural for c in self.changes)


def diff_picot(before: PicotSpec, after: PicotSpec) -> PicotDiff:
    """Compara campo-a-campo. Retorna ``PicotDiff`` com lista de mudanças."""
    changes: list[FieldChange] = []
    flat_before = _flatten(before.model_dump(mode="python"))
    flat_after = _flatten(after.model_dump(mode="python"))
    all_keys = set(flat_before) | set(flat_after)
    for key in sorted(all_keys):
        if key == "schema_version":
            continue
        b = flat_before.get(key)
        a = flat_after.get(key)
        if b == a:
            continue
        changes.append(
            FieldChange(
                field=key,
                before=b,
                after=a,
                structural=is_structural_field(key),
            )
        )
    return PicotDiff(changes=changes)


def _flatten(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Achata 1 nível de nested (``hypothesis.statement`` etc.)."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        full = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, prefix=f"{full}."))
        else:
            out[full] = v
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/protocol/test_diff.py -v`
Expected: 7 tests PASS

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/protocol/diff.py tests/unit/protocol/test_diff.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/protocol/diff.py`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/domains/protocol/diff.py tests/unit/protocol/test_diff.py
git commit -m "feat(protocol): deep diff between PicotSpec versions"
```

---

## Task 5: ADR generator + parser

**Files:**
- Create: `src/prumo_assist/domains/protocol/adr.py`
- Test: `tests/unit/protocol/test_adr.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/protocol/test_adr.py`:

```python
"""Tests para geração e parsing de ADRs picot-v<N>."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from prumo_assist.domains.protocol.adr import (
    SNAPSHOT_BEGIN,
    SNAPSHOT_END,
    compose_adr,
    extract_picot_snapshot,
    find_last_picot_adr,
    next_adr_number,
)
from prumo_assist.domains.protocol.diff import FieldChange, PicotDiff
from prumo_assist.domains.protocol.schemas.v1 import Hypothesis, PicotSpec


def _spec(version: int = 1, population: str = "DS_A") -> PicotSpec:
    return PicotSpec(
        type="clinical",
        created_at="2026-05-03",
        last_updated="2026-05-03",
        version=version,
        population=population,
        intervention="IntervencaoX",
        comparison="best baseline",
        outcome="AUROC ≥ 0.85",
        time="retrospectivo",
        hypothesis=Hypothesis(
            statement="combinado supera comparador em ≥5 pts",
            rationale="piloto",
            metrics=["AUROC"],
        ),
    )


def test_next_adr_number_starts_at_1(tmp_path: Path) -> None:
    decisions = tmp_path / "docs" / "decisions"
    decisions.mkdir(parents=True)
    assert next_adr_number(tmp_path) == 1


def test_next_adr_number_increments(tmp_path: Path) -> None:
    decisions = tmp_path / "docs" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "adr-0001-foo.md").write_text("# x")
    (decisions / "adr-0003-bar.md").write_text("# x")
    (decisions / "not-an-adr.md").write_text("ignore")
    assert next_adr_number(tmp_path) == 4


def test_compose_adr_includes_diff_motivation_and_snapshot(tmp_path: Path) -> None:
    diff = PicotDiff(
        changes=[
            FieldChange(field="population", before="DS_A", after="DS_A+DS_BB", structural=True),
        ]
    )
    spec = _spec(version=2, population="DS_A+DS_BB")
    body = compose_adr(
        adr_number=2,
        spec=spec,
        diff=diff,
        motivation="adicionar coorte externa",
        supersedes_path=None,
        date="2026-05-03",
    )
    assert "ADR-0002" in body
    assert "PICOT v2" in body
    assert "population" in body
    assert "DS_A+DS_BB" in body
    assert "adicionar coorte externa" in body
    assert SNAPSHOT_BEGIN in body
    assert SNAPSHOT_END in body
    assert 'population = "DS_A+DS_BB"' in body


def test_compose_adr_supersedes_link() -> None:
    diff = PicotDiff(changes=[FieldChange("population", "A", "B", True)])
    body = compose_adr(
        adr_number=3,
        spec=_spec(version=3, population="B"),
        diff=diff,
        motivation="motivo",
        supersedes_path=Path("docs/decisions/adr-0002-picot-v2.md"),
        date="2026-05-03",
    )
    assert "supersedes: adr-0002-picot-v2" in body


def test_extract_snapshot_round_trip() -> None:
    diff = PicotDiff(changes=[FieldChange("population", "A", "B", True)])
    body = compose_adr(
        adr_number=1,
        spec=_spec(),
        diff=diff,
        motivation="motivo",
        supersedes_path=None,
        date="2026-05-03",
    )
    extracted = extract_picot_snapshot(body)
    assert extracted is not None
    assert "population" in extracted
    assert 'type = "clinical"' in extracted


def test_extract_snapshot_returns_none_when_absent() -> None:
    body = "ADR sem snapshot"
    assert extract_picot_snapshot(body) is None


def test_find_last_picot_adr(tmp_path: Path) -> None:
    decisions = tmp_path / "docs" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "adr-0001-foo.md").write_text("# foo")
    (decisions / "adr-0002-picot-v1-initial.md").write_text("# v1")
    (decisions / "adr-0003-picot-v2-coorte.md").write_text("# v2")
    found = find_last_picot_adr(tmp_path)
    assert found is not None
    assert found.name == "adr-0003-picot-v2-coorte.md"


def test_find_last_picot_adr_none(tmp_path: Path) -> None:
    decisions = tmp_path / "docs" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "adr-0001-foo.md").write_text("# foo")
    assert find_last_picot_adr(tmp_path) is None


def test_adr_number_from_filename_works_4_digits() -> None:
    decisions_dir_pat = re.compile(r"adr-(\d{4})-")
    m = decisions_dir_pat.match("adr-0042-picot-v3-foo.md")
    assert m is not None and m.group(1) == "0042"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/protocol/test_adr.py -v`
Expected: FAIL — `adr` module not defined.

- [ ] **Step 3: Implement `adr.py`**

Create `src/prumo_assist/domains/protocol/adr.py`:

```python
"""Geração e parsing de ADRs ``adr-NNNN-picot-v<N>-<slug>.md``.

ADRs são append-only event logs. Cada um inclui:

- diff humano-legível dos campos que mudaram
- motivação (perguntada na skill)
- snapshot completo do TOML em bloco delimitado, pra `diff` futuro
"""

from __future__ import annotations

import re
from pathlib import Path

import tomli_w

from prumo_assist.domains.protocol.diff import PicotDiff
from prumo_assist.domains.protocol.picot_io import spec_to_toml_payload
from prumo_assist.domains.protocol.schemas.v1 import PicotSpec

SNAPSHOT_BEGIN = "<!-- picot-snapshot:begin -->"
SNAPSHOT_END = "<!-- picot-snapshot:end -->"

_ADR_FILE_RE = re.compile(r"^adr-(\d{4})-")
_PICOT_ADR_RE = re.compile(r"^adr-\d{4}-picot-v\d+")


def next_adr_number(pj_path: Path) -> int:
    """Próximo número livre em ``docs/decisions/``."""
    decisions = pj_path / "docs" / "decisions"
    if not decisions.exists():
        return 1
    used: list[int] = []
    for child in decisions.iterdir():
        if not child.is_file():
            continue
        m = _ADR_FILE_RE.match(child.name)
        if m:
            used.append(int(m.group(1)))
    return (max(used) + 1) if used else 1


def find_last_picot_adr(pj_path: Path) -> Path | None:
    """Acha o ADR picot-v<N> mais recente (maior número), ou ``None``."""
    decisions = pj_path / "docs" / "decisions"
    if not decisions.exists():
        return None
    candidates = [c for c in decisions.iterdir() if c.is_file() and _PICOT_ADR_RE.match(c.name)]
    if not candidates:
        return None
    candidates.sort(key=lambda p: int(_ADR_FILE_RE.match(p.name).group(1)))  # type: ignore[union-attr]
    return candidates[-1]


def compose_adr(
    *,
    adr_number: int,
    spec: PicotSpec,
    diff: PicotDiff,
    motivation: str,
    supersedes_path: Path | None,
    date: str,
) -> str:
    """Renderiza o conteúdo Markdown completo de um ADR ``picot-v<N>``."""
    supersedes_field = supersedes_path.stem if supersedes_path else "—"
    slug = _slugify_motivation(motivation)
    title = f"ADR-{adr_number:04d}: PICOT v{spec.version} — {slug}"

    lines: list[str] = []
    lines.append("---")
    lines.append(f"adr: {adr_number:04d}")
    lines.append(f"title: PICOT v{spec.version} — {slug}")
    lines.append(f"date: {date}")
    lines.append(f"supersedes: {supersedes_field}")
    lines.append("status: accepted")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    lines.append("## Mudanças")
    lines.append("")
    if diff.changes:
        for change in diff.changes:
            lines.append(f"- **`{change.field}`**:")
            lines.append(f"  - antes: {_fmt(change.before)}")
            lines.append(f"  - agora: {_fmt(change.after)}")
    else:
        lines.append("_(versão inicial — nenhuma mudança a comparar)_")
    lines.append("")
    lines.append("## Motivação")
    lines.append("")
    lines.append(motivation.strip() or "_(não informado)_")
    lines.append("")
    lines.append(f"## Snapshot do PicotSpec/v1 (versão {spec.version})")
    lines.append("")
    lines.append(SNAPSHOT_BEGIN)
    lines.append("```toml")
    lines.append(tomli_w.dumps(spec_to_toml_payload(spec)).rstrip())
    lines.append("```")
    lines.append(SNAPSHOT_END)
    lines.append("")
    return "\n".join(lines)


def extract_picot_snapshot(adr_text: str) -> str | None:
    """Extrai o conteúdo TOML do bloco ``picot-snapshot``. ``None`` se ausente."""
    pattern = re.compile(
        re.escape(SNAPSHOT_BEGIN)
        + r"\s*```toml\s*(?P<toml>.+?)```\s*"
        + re.escape(SNAPSHOT_END),
        flags=re.DOTALL,
    )
    m = pattern.search(adr_text)
    if not m:
        return None
    return m.group("toml").strip()


def _slugify_motivation(motivation: str) -> str:
    """Slug curto kebab-case (≤ 30 chars) pra title de ADR."""
    text = motivation.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if not text:
        return "atualizacao"
    return text[:30].rstrip("-") or "atualizacao"


def _fmt(value: object) -> str:
    """Formata valores diff-friendly (strings com aspas, listas inline)."""
    if value is None:
        return "_null_"
    if isinstance(value, list):
        return "[" + ", ".join(repr(x) for x in value) + "]"
    return repr(value)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/protocol/test_adr.py -v`
Expected: 9 tests PASS

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/protocol/adr.py tests/unit/protocol/test_adr.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/protocol/adr.py`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/domains/protocol/adr.py tests/unit/protocol/test_adr.py
git commit -m "feat(protocol): generate and parse picot ADRs with snapshots"
```

---

## Task 6: Orquestradores `propagate` e `diff_against_last_adr`

**Files:**
- Create: `src/prumo_assist/domains/protocol/ops.py`
- Test: `tests/unit/protocol/test_ops.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/protocol/test_ops.py`:

```python
"""End-to-end tests pros orquestradores `propagate` e `diff_against_last_adr`."""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist.domains.protocol.ops import (
    PropagateReport,
    diff_against_last_adr,
    propagate,
)
from prumo_assist.domains.protocol.picot_io import write_picot
from prumo_assist.domains.protocol.schemas.v1 import Hypothesis, PicotSpec


def _spec(version: int = 1, population: str = "DS_A") -> PicotSpec:
    return PicotSpec(
        type="clinical",
        created_at="2026-05-03",
        last_updated="2026-05-03",
        version=version,
        population=population,
        intervention="IntervencaoX",
        comparison="best baseline",
        outcome="AUROC ≥ 0.85",
        time="retrospectivo",
        hypothesis=Hypothesis(
            statement="combinado supera comparador",
            rationale="piloto",
            metrics=["AUROC"],
        ),
    )


def _bootstrap_pj(tmp_path: Path) -> Path:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    (pj / "docs" / "protocol.md").write_text(
        "# Protocolo do estudo\n\n## Contexto da pesquisa\n\nProse humana inicial.\n"
    )
    (pj / "docs" / "project.md").write_text(
        "---\ntitle: Projeto\n---\n\n# Projeto\n\nIntro.\n"
    )
    (pj / "docs" / "decisions").mkdir()
    return pj


def test_propagate_inserts_blocks_when_absent(tmp_path: Path) -> None:
    pj = _bootstrap_pj(tmp_path)
    write_picot(pj, _spec())
    report = propagate(pj)
    assert isinstance(report, PropagateReport)
    assert report.protocol_status == "inserted"
    assert report.project_status == "inserted"
    protocol_text = (pj / "docs" / "protocol.md").read_text()
    project_text = (pj / "docs" / "project.md").read_text()
    assert "<!-- picot:begin" in protocol_text
    assert "<!-- picot:begin" in project_text
    assert "DS_A" in protocol_text
    assert "Pergunta de pesquisa" in project_text


def test_propagate_replaces_blocks_when_present(tmp_path: Path) -> None:
    pj = _bootstrap_pj(tmp_path)
    write_picot(pj, _spec(population="DS_A"))
    propagate(pj)
    write_picot(pj, _spec(population="DS_A + DS_BB"))
    propagate(pj)
    text = (pj / "docs" / "protocol.md").read_text()
    assert "DS_A + DS_BB" in text
    assert text.count("<!-- picot:begin") == 1


def test_propagate_unchanged_when_hash_matches(tmp_path: Path) -> None:
    pj = _bootstrap_pj(tmp_path)
    write_picot(pj, _spec())
    propagate(pj)
    report = propagate(pj)
    assert report.protocol_status == "unchanged"
    assert report.project_status == "unchanged"


def test_propagate_raises_when_picot_missing(tmp_path: Path) -> None:
    pj = _bootstrap_pj(tmp_path)
    with pytest.raises(FileNotFoundError):
        propagate(pj)


def test_diff_against_last_adr_no_baseline_returns_diff_with_no_changes(
    tmp_path: Path,
) -> None:
    pj = _bootstrap_pj(tmp_path)
    write_picot(pj, _spec())
    out = diff_against_last_adr(pj)
    assert out is not None
    assert out.changes == []
    assert out.has_structural is False


def test_diff_against_last_adr_detects_structural_change(tmp_path: Path) -> None:
    """Após ADR inicial, mudar campo estrutural produz diff structural."""
    from prumo_assist.domains.protocol.adr import compose_adr, next_adr_number
    from prumo_assist.domains.protocol.diff import PicotDiff

    pj = _bootstrap_pj(tmp_path)
    spec_v1 = _spec(version=1, population="DS_A")
    write_picot(pj, spec_v1)
    decisions = pj / "docs" / "decisions"
    body = compose_adr(
        adr_number=next_adr_number(pj),
        spec=spec_v1,
        diff=PicotDiff(changes=[]),
        motivation="versão inicial",
        supersedes_path=None,
        date="2026-05-03",
    )
    (decisions / "adr-0001-picot-v1-versao-inicial.md").write_text(body)

    spec_v2 = _spec(version=2, population="DS_A + DS_BB")
    write_picot(pj, spec_v2)
    diff = diff_against_last_adr(pj)
    assert diff is not None
    assert diff.has_structural is True
    assert any(c.field == "population" for c in diff.changes)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/protocol/test_ops.py -v`
Expected: FAIL — `ops` module not defined.

- [ ] **Step 3: Implement `ops.py`**

Create `src/prumo_assist/domains/protocol/ops.py`:

```python
"""Orquestradores para ``propagate`` e ``diff_against_last_adr``.

Lado determinístico Python das operações. A skill ``formulate-picot`` usa
estas funções via Python -c após coletar inputs do usuário.

``init`` e ``formalize`` (modos agênticos) ficam no SKILL.md — escrevem
``.claude/picot.toml`` via ``write_picot`` e chamam ``propagate``.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from prumo_assist.domains.protocol.adr import (
    extract_picot_snapshot,
    find_last_picot_adr,
)
from prumo_assist.domains.protocol.diff import PicotDiff, diff_picot
from prumo_assist.domains.protocol.picot_io import (
    picot_hash,
    picot_path,
    read_picot,
)
from prumo_assist.domains.protocol.render import (
    render_project_block,
    render_protocol_block,
    replace_or_insert_block,
)
from prumo_assist.domains.protocol.schemas.v1 import PicotSpec

PropagateStatus = Literal["inserted", "updated", "unchanged", "missing"]


@dataclass(frozen=True)
class PropagateReport:
    """Resultado de ``propagate``: status por destino."""

    protocol_status: PropagateStatus
    project_status: PropagateStatus
    hash8: str


def propagate(pj_path: Path) -> PropagateReport:
    """Lê ``picot.toml``, regenera blocos delimitados em protocol.md e project.md.

    Status por destino:

    - ``missing``: arquivo destino não existe (humano precisa criar)
    - ``inserted``: bloco não existia, foi inserido após anchor
    - ``updated``: bloco existia, foi substituído (hash mudou)
    - ``unchanged``: bloco já tem o hash atual, nada a fazer
    """
    spec = read_picot(pj_path)
    h = picot_hash(pj_path)

    protocol_status = _propagate_one(
        target=pj_path / "docs" / "protocol.md",
        block=render_protocol_block(spec, hash8=h),
        anchor=r"^# .+$",
        new_hash8=h,
    )
    project_status = _propagate_one(
        target=pj_path / "docs" / "project.md",
        block=render_project_block(spec, hash8=h),
        anchor=r"^---\n.*?\n---",
        new_hash8=h,
    )
    return PropagateReport(
        protocol_status=protocol_status,
        project_status=project_status,
        hash8=h,
    )


def _propagate_one(
    *,
    target: Path,
    block: str,
    anchor: str,
    new_hash8: str,
) -> PropagateStatus:
    if not target.exists():
        return "missing"
    text = target.read_text(encoding="utf-8")
    from prumo_assist.domains.protocol.render import BLOCK_BEGIN_RE

    existing = BLOCK_BEGIN_RE.search(text)
    if existing and existing.group("hash") == new_hash8:
        return "unchanged"
    new_text = replace_or_insert_block(text, block, anchor_pattern=anchor)
    target.write_text(new_text, encoding="utf-8")
    return "updated" if existing else "inserted"


def diff_against_last_adr(pj_path: Path) -> PicotDiff | None:
    """Compara ``picot.toml`` atual contra snapshot do último ADR ``picot-v<N>``.

    Retorna ``None`` se ``picot.toml`` ausente. Retorna ``PicotDiff`` com
    ``changes=[]`` quando não há ADR baseline (caller decide criar v1).
    """
    if not picot_path(pj_path).exists():
        return None
    current = read_picot(pj_path)
    last_adr = find_last_picot_adr(pj_path)
    if last_adr is None:
        return PicotDiff(changes=[])
    snapshot_text = extract_picot_snapshot(last_adr.read_text(encoding="utf-8"))
    if snapshot_text is None:
        return PicotDiff(changes=[])
    parsed = tomllib.loads(snapshot_text)
    baseline = PicotSpec.model_validate(parsed["picot"])
    return diff_picot(baseline, current)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/protocol/test_ops.py -v`
Expected: 6 tests PASS

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/protocol/ops.py tests/unit/protocol/test_ops.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/protocol/ops.py`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/domains/protocol/ops.py tests/unit/protocol/test_ops.py
git commit -m "feat(protocol): orchestrate propagate + diff_against_last_adr"
```

---

## Task 7: CLI `prumo protocol propagate|diff` + API re-export

**Files:**
- Create: `src/prumo_assist/domains/protocol/api.py`
- Create: `src/prumo_assist/domains/protocol/cli.py`
- Modify: `src/prumo_assist/cli.py` (registrar protocol_app)
- Modify: `src/prumo_assist/api.py` (expor protocol)
- Test: `tests/unit/protocol/test_cli.py`

- [ ] **Step 1: Create `api.py`**

Create `src/prumo_assist/domains/protocol/api.py`:

```python
"""Python API pra ``protocol``."""

from __future__ import annotations

from prumo_assist.domains.protocol.ops import (
    PropagateReport,
    diff_against_last_adr,
    propagate,
)
from prumo_assist.domains.protocol.picot_io import (
    picot_hash,
    picot_path,
    read_picot,
    write_picot,
)
from prumo_assist.domains.protocol.schemas.v1 import Hypothesis, PicotSpec

__all__ = [
    "Hypothesis",
    "PicotSpec",
    "PropagateReport",
    "diff_against_last_adr",
    "picot_hash",
    "picot_path",
    "propagate",
    "read_picot",
    "write_picot",
]
```

- [ ] **Step 2: Write failing tests for CLI**

Create `tests/unit/protocol/test_cli.py`:

```python
"""Integration tests para ``prumo protocol *``."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from prumo_assist.cli import app
from prumo_assist.domains.protocol.picot_io import write_picot
from prumo_assist.domains.protocol.schemas.v1 import Hypothesis, PicotSpec

runner = CliRunner()


def _bootstrap(tmp_path: Path) -> Path:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    (pj / "docs" / "protocol.md").write_text("# Protocolo\n")
    (pj / "docs" / "project.md").write_text("---\ntitle: x\n---\n\n# Projeto\n")
    (pj / "docs" / "decisions").mkdir()
    return pj


def _spec() -> PicotSpec:
    return PicotSpec(
        type="clinical",
        created_at="2026-05-03",
        last_updated="2026-05-03",
        version=1,
        population="DS_A",
        intervention="IntervencaoX",
        comparison="best baseline",
        outcome="AUROC ≥ 0.85",
        time="retrospectivo",
        hypothesis=Hypothesis(
            statement="combinado supera comparador",
            rationale="piloto",
            metrics=["AUROC"],
        ),
    )


def test_protocol_propagate_inserts_blocks(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    write_picot(pj, _spec())
    result = runner.invoke(app, ["protocol", "propagate", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = _last_json(result.stdout)
    assert payload["protocol_status"] == "inserted"
    assert payload["project_status"] == "inserted"


def test_protocol_diff_no_baseline(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    write_picot(pj, _spec())
    result = runner.invoke(app, ["protocol", "diff", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = _last_json(result.stdout)
    assert payload["changes"] == []
    assert payload["has_structural"] is False


def test_protocol_propagate_missing_picot(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)  # sem picot.toml
    result = runner.invoke(app, ["protocol", "propagate", str(pj), "--json"])
    assert result.exit_code != 0
    assert "picot.toml" in result.output or "picot.toml" in result.stderr


def _last_json(stdout: str) -> dict[str, object]:
    last: dict[str, object] | None = None
    for line in stdout.splitlines():
        try:
            last = json.loads(line)
        except json.JSONDecodeError:
            continue
    assert last is not None, f"nenhum JSON na saída: {stdout!r}"
    return last
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/protocol/test_cli.py -v`
Expected: FAIL — `protocol` sub-app não registrada.

- [ ] **Step 4: Implement `cli.py`**

Create `src/prumo_assist/domains/protocol/cli.py`:

```python
"""Subcomandos ``prumo protocol *`` — Typer fachada."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Annotated

import typer

from prumo_assist.core.cli_op import cli_run
from prumo_assist.domains.protocol import ops

protocol_app = typer.Typer(
    name="protocol",
    help="PICOT: propagate (regenerar blocos) + diff (comparar contra último ADR).",
    no_args_is_help=True,
)


@protocol_app.command("propagate")
def propagate_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Regenera blocos ``<!-- picot:begin -->`` em ``protocol.md`` e ``project.md``."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError,)) as console:
        report = ops.propagate(path.resolve())
        console.success(
            f"protocol.md: {report.protocol_status} · project.md: {report.project_status} "
            f"(hash {report.hash8})"
        )
        console.emit(asdict(report))


@protocol_app.command("diff")
def diff_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Compara ``picot.toml`` atual contra snapshot do último ADR ``picot-v<N>``."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError,)) as console:
        diff = ops.diff_against_last_adr(path.resolve())
        if diff is None:
            console.warn("`.claude/picot.toml` não encontrado.")
            console.emit({"changes": [], "has_structural": False, "missing": True})
            return
        if not diff.changes:
            console.success("Sem mudanças desde o último ADR (ou sem baseline).")
        else:
            console.info(
                f"{len(diff.changes)} campo(s) mudaram "
                f"(estrutural: {diff.has_structural})."
            )
            for c in diff.changes:
                console.info(
                    f"  • {c.field}: {c.before!r} → {c.after!r} "
                    f"({'estrutural' if c.structural else 'cosmético'})"
                )
        console.emit(
            {
                "changes": [_change_to_dict(c) for c in diff.changes],
                "has_structural": diff.has_structural,
            }
        )


def _change_to_dict(change: object) -> dict[str, object]:
    if is_dataclass(change):
        return asdict(change)  # type: ignore[arg-type]
    return {"field": "?", "before": None, "after": None, "structural": False}
```

- [ ] **Step 5: Register `protocol_app` in `cli.py`**

Edit `src/prumo_assist/cli.py`. Add import after the existing domain imports:

```python
from prumo_assist.domains.protocol.cli import protocol_app
```

And after the existing `app.add_typer(...)` calls, add:

```python
app.add_typer(protocol_app)
```

- [ ] **Step 6: Re-export in root `api.py`**

Edit `src/prumo_assist/api.py`. Add to imports:

```python
from prumo_assist.domains.protocol import api as protocol
```

Add `"protocol"` to `__all__` (sorted alphabetical: between `paper` and `skills`).

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/unit/protocol/test_cli.py -v`
Expected: 3 tests PASS

Run full suite: `uv run pytest -q`
Expected: all tests pass.

- [ ] **Step 8: Lint + types**

Run: `uv run ruff check src/prumo_assist tests`
Run: `uv run --extra dev mypy src/prumo_assist tests`
Expected: clean

- [ ] **Step 9: Commit**

```bash
git add src/prumo_assist/domains/protocol/api.py src/prumo_assist/domains/protocol/cli.py src/prumo_assist/cli.py src/prumo_assist/api.py tests/unit/protocol/test_cli.py
git commit -m "feat(protocol): wire prumo protocol propagate|diff CLI + api"
```

---

## Task 8: SKILL.md `formulate-picot` (modos Socrático e Formalize)

**Files:**
- Create: `skills/formulate-picot/SKILL.md`

- [ ] **Step 1: Verify existing skill patterns**

Run: `cat skills/paper-extract/SKILL.md | head -40`
Note the structure: `---` frontmatter (`name`, `description`, `prumo:` block) → markdown body with operations.

- [ ] **Step 2: Create the skill file**

Create `skills/formulate-picot/SKILL.md`:

```markdown
---
name: formulate-picot
description: Formaliza, propaga e versiona a PICOT do projeto (Population, Intervention, Comparison, Outcome, Time + Hipótese formal única). Invocar quando o usuário pedir "fechar PICOT", "formalizar pergunta de pesquisa", "propagar PICOT pra protocol/project/ADR", "PICOT mudou — gera novo ADR", "/formulate-picot", ou quando estiver na transição de busca ampla pra busca focada (Fase 1 da journey). Auto-detecta modo (Socrático / Formalize / Propagate / Diff) pelo estado do `.claude/picot.toml` e dos 3 destinos (`docs/protocol.md`, `docs/project.md`, `docs/decisions/adr-*-picot-*.md`).
prumo:
  version: 1.0.0
  schema: PicotSpec/v1
  determinism: hybrid
  agent_compat: [claude-code]
  cost_estimate: ~6k tokens (Socrático), ~2k (Formalize/Propagate/Diff)
  inputs:
    pj_path: optional (default cwd)
    mode: optional ('init' | 'formalize' | 'propagate' | 'diff'; default = auto-detect)
---

# Formulate PICOT — formalização canônica + propagação versionada

Skill que mantém a PICOT do projeto consistente em **três destinos**:

- `.claude/picot.toml` — canônico (machine-readable, validado por `PicotSpec/v1`)
- `docs/protocol.md` — render operacional (concreto, conferível)
- `docs/project.md` — render acadêmico (prosa formal)
- `docs/decisions/adr-NNNN-picot-v<N>-<slug>.md` — ADR append-only quando versão muda

## Pressupostos

- cwd é um `pj_*` com `docs/protocol.md` e `docs/project.md` (mesmo que vazios) e `docs/decisions/`.
- A parte determinística (read/write TOML, render, diff, ADR) vive em `prumo_assist.domains.protocol`. A skill **só** cuida do agêntico (Socrático e Formalize).

## Auto-detect

A skill escolhe o modo baseado no estado, executando este check em `Bash`:

```bash
python3 -c '
from pathlib import Path
from prumo_assist.domains.protocol.picot_io import picot_path
from prumo_assist.domains.protocol.adr import find_last_picot_adr

pj = Path(".")
toml = picot_path(pj)
last_adr = find_last_picot_adr(pj)
protocol_md = pj / "docs" / "protocol.md"
project_md = pj / "docs" / "project.md"

if not toml.exists():
    print("init" if not protocol_md.read_text(errors="ignore").strip() else "formalize")
elif last_adr is None:
    print("propagate")
else:
    # delegar diff: pode retornar zero changes (= já em dia) ou detectar mudança
    print("diff")
'
```

A saída (`init` / `formalize` / `propagate` / `diff`) define qual operação seguir.

## Operação 1: `init` — modo Socrático (greenfield)

Pré-condição: `.claude/picot.toml` ausente, `docs/protocol.md` vazio (ou só template).

Passos:

1. **Reunir contexto via wiki-query**: invocar `wiki-query` (ou `Read` em `docs/_index.md`/`_log.md`) pra entender o que já existe de tema. Citações livres ok.

2. **Perguntar `type`** (escolha):
   - "É um estudo **clínico** (PICOT padrão: Population/Intervention/Comparison/Outcome/Time) ou **metodológico** (Contribution + Hypothesis-validity-condition)?"

3. **Para `clinical`**, perguntar uma de cada vez (sugerindo do wiki sempre que possível):
   - **P (Population)**: "Quem é a coorte/dataset principal?" Ex.: "Coorte A + Coorte B, ~1500 participantes."
   - **I (Intervention)**: "Qual o método sob teste?" Ex.: "Intervenção X em dose padrão."
   - **C (Comparison)**: "Qual o baseline canônico?" Ex.: "Cuidado usual."
   - **O (Outcome)**: "Métrica primária + threshold?" Ex.: "AUROC ≥ 0.85, IC bootstrap; ECE ≤ 0.05 como secundária."
   - **T (Time)**: "Janela temporal?" Ex.: "Retrospectivo, sem janela prospectiva; cross-cohort split."

4. **Para `methodological`**, perguntar:
   - **Contribution**: "Qual a contribuição teórica/metodológica?" Ex.: "Método estatístico M."
   - **Hypothesis-validity-condition**: "Sob qual condição a contribuição vale?" Ex.: "Quando a suposição S falha."

5. **Hipótese formal única** (sempre):
   - **Statement**: frase declarativa testável. Ex.: "A intervenção X supera o comparador em ≥5 pts no desfecho primário."
   - **Rationale**: por que esperar isso. Ex.: "Estudos-piloto sugerem efeito clinicamente relevante."
   - **Metrics**: lista de métricas pra testar. Ex.: `["AUROC", "ECE", "coverage"]`.

6. **Mostrar TOML proposto pro usuário e pedir confirmação**:

```python
from prumo_assist.domains.protocol.schemas.v1 import PicotSpec, Hypothesis
spec = PicotSpec(
    type="clinical",
    created_at="<hoje ISO>",
    last_updated="<hoje ISO>",
    version=1,
    population="...",
    intervention="...",
    comparison="...",
    outcome="...",
    time="...",
    hypothesis=Hypothesis(statement="...", rationale="...", metrics=["..."]),
)
```

Mostrar o output de `tomli_w.dumps(spec.model_dump(...))` e perguntar "OK assim?".

7. **Após confirmação, escrever** via `Bash`:

```bash
python3 -c '
import sys
sys.path.insert(0, ".")
from pathlib import Path
from prumo_assist.domains.protocol.api import (
    PicotSpec, Hypothesis, write_picot, propagate
)
from prumo_assist.domains.protocol.adr import compose_adr, next_adr_number
from prumo_assist.domains.protocol.diff import PicotDiff

pj = Path(".")
spec = PicotSpec(...)  # campos preenchidos pela conversa
write_picot(pj, spec)
report = propagate(pj)

# ADR-0001 inicial
n = next_adr_number(pj)
body = compose_adr(
    adr_number=n,
    spec=spec,
    diff=PicotDiff(changes=[]),
    motivation="versão inicial — primeira formalização",
    supersedes_path=None,
    date="<hoje ISO>",
)
adr_path = pj / "docs" / "decisions" / f"adr-{n:04d}-picot-v1-versao-inicial.md"
adr_path.write_text(body, encoding="utf-8")
print(f"ok: {report}, adr={adr_path}")
'
```

8. **Reportar ao usuário**: arquivos criados (`.claude/picot.toml`, `docs/decisions/adr-NNNN-picot-v1-*.md`) e blocos atualizados em `protocol.md`/`project.md`.

## Operação 2: `formalize` — extrair de prosa existente

Pré-condição: `.claude/picot.toml` ausente, mas `docs/protocol.md` ou `docs/project.md` têm prose com sinais de PICOT.

Passos:

1. **Ler `protocol.md` e `project.md`**, identificar candidatos pra cada campo (heurística: parágrafo após heading "## Contexto" / "## Coorte" / "## Desfecho").

2. **Apresentar tabela**:

| Campo | Candidato extraído | Fonte |
|---|---|---|
| `population` | "..." | `protocol.md § Coorte` |
| `intervention` | "..." | `project.md § Hipótese` |
| ... | ... | ... |

3. **Confirmar/editar campo a campo** com o usuário.

4. **Resto idêntico ao `init` passos 5–8** (hipótese, write, propagate, ADR-0001).

## Operação 3: `propagate` — apenas regenerar destinos

Quando: `.claude/picot.toml` existe e os blocos delimitados em `protocol.md`/`project.md` estão stale (hash mismatch). Sem mudança estrutural.

Executar via `Bash`:

```bash
prumo protocol propagate --json
```

Reportar status por destino (`inserted`/`updated`/`unchanged`/`missing`).

## Operação 4: `diff` — detectar mudança e gerar ADR

Quando: usuário editou `.claude/picot.toml` (manualmente ou via outra invocação) e quer registrar a mudança.

Passos:

1. **Rodar diff** via `Bash`:

```bash
prumo protocol diff --json
```

Captura JSON da última linha; campo `changes` é lista, `has_structural` é bool.

2. **Se `changes == []`**: nada mudou. Sair informando o usuário.

3. **Se `has_structural == false`** (só campos cosméticos como `last_updated` ou `hypothesis.rationale`): chamar `prumo protocol propagate` e sair sem ADR.

4. **Se `has_structural == true`**:
   - Mostrar diff campo-a-campo.
   - **Perguntar motivação** (livre ou multipla escolha):
     - "novo dataset disponível"
     - "refinamento conceitual após leitura"
     - "feedback de orientador/revisor"
     - "consolidação pré-banca/submissão"
     - "outro: ___"
   - **Bumpar versão** em `picot.toml` (`[picot] version += 1`, `last_updated = hoje`).
   - **Gerar ADR** via `Bash`:

```bash
python3 -c '
from pathlib import Path
from prumo_assist.domains.protocol.api import read_picot, propagate
from prumo_assist.domains.protocol.adr import (
    compose_adr, next_adr_number, find_last_picot_adr,
)
from prumo_assist.domains.protocol.ops import diff_against_last_adr

pj = Path(".")
spec = read_picot(pj)
diff = diff_against_last_adr(pj)
last_adr = find_last_picot_adr(pj)
n = next_adr_number(pj)
body = compose_adr(
    adr_number=n,
    spec=spec,
    diff=diff,
    motivation="<motivação capturada do usuário>",
    supersedes_path=last_adr,
    date="<hoje ISO>",
)
slug = "<slug do motivo>"
adr_path = pj / "docs" / "decisions" / f"adr-{n:04d}-picot-v{spec.version}-{slug}.md"
adr_path.write_text(body, encoding="utf-8")
report = propagate(pj)
print(f"adr={adr_path}, propagate={report}")
'
```

5. **Reportar**: ADR criado, blocos atualizados.

## Boundaries

- Skill **nunca** edita `.claude/picot.toml` sem confirmação do usuário.
- Skill **nunca** edita ADR existente (append-only).
- Skill **nunca** edita prose fora dos blocos `<!-- picot:begin/end -->` em protocol.md/project.md.
- Skill **não** invoca LLM para validar PICOT semanticamente — só estrutura.
- Para escrita acadêmica do `project.md` § não delimitado, delegar à família `write-*` (spec separada).

## Erros comuns

- `picot.toml` corrompido (não-parseable) → reportar erro do `tomllib`, sugerir `git diff .claude/picot.toml`.
- `docs/protocol.md` ou `docs/project.md` ausentes → reportar `missing` e seguir; humano cria depois.
- Nenhum ADR baseline mas `picot.toml` existe → tratar como ADR-0001 inicial; criar.
- `type` mudou (`clinical` → `methodological`) → ADR especial com warning explícito sobre campos abandonados.
```

- [ ] **Step 3: Validate skill registry parses the new SKILL.md**

Run: `uv run prumo skills --json | grep formulate-picot`
Expected: skill listed with `version: 1.0.0`, `schema: PicotSpec/v1`, `determinism: hybrid`.

- [ ] **Step 4: Commit**

```bash
git add skills/formulate-picot/SKILL.md
git commit -m "feat(skill): formulate-picot — Socratic + Formalize agentic modes"
```

---

## Task 9: Documentação + listagem do plugin

**Files:**
- Modify: `README.md` (tabela de skills)
- Modify: `docs/actions-by-context.md` (gatilho "Quero formalizar PICOT")
- Modify: `docs/_index.md` (não muda — spec já listada)
- Modify: `docs/Research Project Structure.md` (se houver mention de protocol.md sem PICOT)

- [ ] **Step 1: Update README.md skills table**

Find the skills table in `README.md` and add a row for `formulate-picot`. Place it after `peer-review` (last row currently). The new row:

```markdown
| `/prumo-assist:formulate-picot` | Formaliza/propaga/versiona PICOT do projeto. Mantém canônico em `.claude/picot.toml` e renderiza blocos delimitados em `protocol.md`, `project.md`. Gera ADR `adr-NNNN-picot-v<N>` quando hipótese ou campo estrutural muda. Auto-detecta modo Socrático/Formalize/Propagate/Diff. |
```

- [ ] **Step 2: Update `docs/actions-by-context.md`**

Find the section "## Fase 1 · Pergunta  *(Discover + Define)*" (around the line `### "Preciso fechar um PICOT antes de prosseguir"`) and update its body. Replace the existing manual-steps body with:

```markdown
### "Preciso fechar um PICOT antes de prosseguir"
*Pivô da Fase 1: da busca ampla → busca focada.*
1. `/prumo-assist:formulate-picot` — auto-detecta modo:
   - greenfield → Socrático (perguntas P/I/C/O/T ancoradas em `wiki-query`)
   - prose existente → Formalize (extrai de `protocol.md`/`project.md`, confirma)
2. Skill grava `.claude/picot.toml` (canônico), regenera blocos delimitados em `protocol.md` e `project.md`, e cria `adr-NNNN-picot-v1-versao-inicial.md`.
3. (Manual quando preferir) editar `docs/protocol.md`/`docs/project.md` na prose ao redor dos blocos delimitados; depois rodar `prumo protocol propagate` pra realinhar caso edite `picot.toml`.
```

Then add a new context immediately after:

```markdown
### "PICOT mudou — preciso registrar"
*Sub-fluxo de versão: bumpa picot.toml e gera ADR.*
1. Editar `.claude/picot.toml` à mão (ou via `/prumo-assist:formulate-picot`).
2. `prumo protocol diff` — mostra campos mudados; classifica estrutural vs cosmético.
3. Se estrutural: `/prumo-assist:formulate-picot diff` (skill pergunta motivação) → cria `adr-NNNN-picot-v<N+1>-<slug>.md` + atualiza blocos delimitados.
4. Se cosmético (apenas `last_updated` ou `hypothesis.rationale`): `prumo protocol propagate` basta.
```

- [ ] **Step 3: Run full check**

Run: `uv run pytest -q`
Expected: all tests pass.

Run: `uv run ruff check .`
Run: `uv run --extra dev mypy src/prumo_assist tests`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/actions-by-context.md
git commit -m "docs: list formulate-picot in skills + add gatilhos in actions-by-context"
```

---

## Final Verification

- [ ] **Full test suite**

Run: `uv run pytest -q`
Expected: all tests PASS, count = baseline + 47 new tests across protocol/.

- [ ] **Lint + types clean**

Run: `uv run ruff check .`
Expected: All checks passed!

Run: `uv run --extra dev mypy src/prumo_assist tests`
Expected: Success: no issues.

- [ ] **Manifest validation**

Run: `uv run python .github/scripts/validate_manifests.py`
Expected: ok.

- [ ] **Smoke-test end-to-end via CLI**

Use a tmp project:

```bash
cd /tmp && rm -rf pj_picot_smoke
uv --project <repo> run prumo init pj_picot_smoke
cd pj_picot_smoke
mkdir -p .claude
cat > .claude/picot.toml <<'EOF'
[picot]
type = "clinical"
created_at = "2026-05-03"
last_updated = "2026-05-03"
version = 1
population = "DS_A"
intervention = "IntervencaoX"
comparison = "best baseline"
outcome = "AUROC ≥ 0.80"
time = "retrospectivo"

[picot.hypothesis]
statement = "combinado supera comparador em ≥3 pts AUC"
rationale = "efeito piloto"
metrics = ["AUROC"]
EOF
uv --project <repo> run prumo protocol propagate
cat docs/protocol.md  # confere bloco delimitado
uv --project <repo> run prumo protocol diff
```

Expected:
- `propagate` reporta `inserted` ou `missing` pros 2 destinos
- `diff` reporta "no baseline" ou "0 changes"
- bloco `<!-- picot:begin v=1 hash=... -->` aparece em `protocol.md` com população e hipótese.

- [ ] **Bump version (optional)**

Esta entrega é uma skill nova → MINOR bump (per RELEASING.md).

Edit `src/prumo_assist/_version.py`: `0.4.0` → `0.5.0`.

Run: `uv run python .github/scripts/sync_manifest_version.py`
Expected: `Sincronizados em v0.5.0`.

Update `CHANGELOG.md` with a `## [0.5.0] - <today>` entry summarizing this PR.

```bash
git add src/prumo_assist/_version.py .claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md
git commit -m "release: 0.5.0 — formulate-picot skill"
```

---

## Self-review notes

**Spec coverage**:
- [x] D1 auto-detect 4 modos: covered by SKILL.md auto-detect snippet (Task 8) + `ops.diff_against_last_adr` (Task 6) handles `diff` mode mecânico
- [x] D2 canônico `.claude/picot.toml`: Tasks 1+2 (schema + io)
- [x] D3 PicotSpec/v1: Task 1
- [x] D4 render delimitado + hash: Task 3
- [x] D5 diff campo-a-campo gera ADR: Tasks 4+5+6
- [x] Modo `init` Socrático: Task 8 (SKILL.md)
- [x] Modo `formalize`: Task 8 (SKILL.md)
- [x] Modo `propagate`: Task 6+7 (ops + CLI)
- [x] Modo `diff`: Task 6+7 (ops + CLI) + Task 8 (SKILL.md envolve com motivação)
- [x] Plano de implementação 5 PRs do spec colapsado em 9 tasks bite-sized neste plano

**Type consistency**:
- `PicotSpec` — usado em todo lugar com mesmos campos (verified)
- `Hypothesis` — sub-modelo, consistente
- `PicotDiff` / `FieldChange` — diff types, consistentes
- `PropagateReport` / `PropagateStatus` — ops return type, consistente
- `picot_path`, `picot_hash`, `read_picot`, `write_picot` — assinaturas consistentes
- `find_last_picot_adr`, `next_adr_number`, `compose_adr`, `extract_picot_snapshot` — adr helpers, consistentes
- `propagate`, `diff_against_last_adr` — ops, consistentes
- `BLOCK_BEGIN_RE`, `BLOCK_FULL_RE`, `PICOT_BEGIN_PREFIX`, `PICOT_END` — render constants, consistentes (notar que tests/ops.py usa `BLOCK_BEGIN_RE` importado)

**Placeholder scan**: nenhum TBD/TODO. Códigos completos. Comandos exatos.

**Out of scope (per spec, deferred)**:
- Multi-PICOT / multi-hypothesis cardinality
- Status tracking de hipótese (a-priori → confirmada)
- Render por venue (família `write-*`)
- Validação semântica via LLM
