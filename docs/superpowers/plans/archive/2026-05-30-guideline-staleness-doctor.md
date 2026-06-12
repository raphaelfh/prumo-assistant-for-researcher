---
status: implemented
verified: 2026-06-11
release: "0.61.0"
---

# Checklist Staleness in `prumo doctor` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a skill declare `prumo.guidelines_reviewed: "<ISO date>"`, parse it into `SkillManifest`, and have `prumo doctor` warn when a skill's clinical checklists haven't been reviewed in >180 days — so living guidelines (TRIPOD-LLM revises every ~3 months) don't silently rot.

**Architecture:** One new optional frontmatter field parsed by `core/skills.py` (it already preserves unknown keys in `extra`; we promote this one to a typed field). A pure, fully-tested function `stale_guideline_warnings(registry, *, today, max_age_days=180)` does the date math. `prumo doctor` (inline in `cli.py`) resolves the plugin skills dir it already knows how to find, loads the registry, and appends the warnings to its existing `issues` list.

**Tech Stack:** Python 3.11+ (`datetime.date`), Typer, pytest, `mypy --strict`, `ruff`. No new dependencies.

---

## Verified existing APIs

```python
# core/skills.py
@dataclass(frozen=True)
class SkillManifest:  # name, description, body, path, version, schema, determinism,
                      # agent_compat, cost_estimate, inputs, extra
def parse_skill_file(path) -> SkillManifest      # extra = unknown prumo.* keys
def load_skill_registry(dir, *, strict=True) -> tuple[SkillRegistry, list[str]]
class SkillRegistry: .get(name)->SkillManifest ; .names()->list[str]

# cli.py  (doctor lives HERE, not in a domains/doctor.py)
@app.command("doctor")
def doctor_command(path=Path("."), json_mode=False):
    issues: list[str] = [...]            # dirs + per-integration adapter.doctor()
    # ... builds payload, warns per issue, exits 1 if issues
def _resolve_skills_dir() -> Path | None  # finds plugin skills/ (packaged or worktree)
# load_skill_registry is already imported in cli.py
```

YAML note: an unquoted `2026-05-30` parses as a `datetime.date`; we always `str(...)` it on read and **quote it** when writing frontmatter, so parsing is stable either way.

## Files

- Modify `src/prumo_assist/core/skills.py` + `tests/unit/core/test_skills.py`.
- Modify `src/prumo_assist/cli.py` + `tests/unit/test_cli_init.py` (doctor smoke).
- Modify `skills/peer-review/SKILL.md`, `skills/write-statistics/SKILL.md` (seed the field).
- Modify `CHANGELOG.md`.

---

### Task 1: Parse `guidelines_reviewed` into `SkillManifest`

**Files:** Modify `src/prumo_assist/core/skills.py`; Test `tests/unit/core/test_skills.py`

- [ ] **Step 1: Write the failing tests** — add to `tests/unit/core/test_skills.py`:

```python
def test_parses_guidelines_reviewed(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "pr" / "SKILL.md",
        '---\nname: pr\ndescription: d\nprumo:\n  guidelines_reviewed: "2026-05-30"\n---\nbody\n',
    )
    m = parse_skill_file(skill)
    assert m.guidelines_reviewed == "2026-05-30"


def test_guidelines_reviewed_defaults_none(tmp_path: Path) -> None:
    skill = _write(tmp_path / "x" / "SKILL.md", "---\nname: x\ndescription: d\n---\nbody\n")
    assert parse_skill_file(skill).guidelines_reviewed is None


def test_guidelines_reviewed_not_in_extra(tmp_path: Path) -> None:
    skill = _write(
        tmp_path / "x" / "SKILL.md",
        '---\nname: x\ndescription: d\nprumo:\n  guidelines_reviewed: "2026-01-01"\n---\nbody\n',
    )
    assert "guidelines_reviewed" not in parse_skill_file(skill).extra
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/core/test_skills.py -k guidelines_reviewed -v`
Expected: FAIL — `AttributeError: 'SkillManifest' object has no attribute 'guidelines_reviewed'`.

- [ ] **Step 3: Implement** — three edits in `src/prumo_assist/core/skills.py`:

(a) add the field to `SkillManifest` (after `cost_estimate: str | None = None`):

```python
    guidelines_reviewed: str | None = None
```

(b) in `parse_skill_file`, add `"guidelines_reviewed",` to the `extra_keys` exclusion set:

```python
    extra_keys = set(prumo_block) - {
        "version",
        "schema",
        "determinism",
        "agent_compat",
        "cost_estimate",
        "inputs",
        "guidelines_reviewed",
    }
```

(c) add the field to the `SkillManifest(...)` return (after `cost_estimate=...`):

```python
        guidelines_reviewed=(
            str(prumo_block["guidelines_reviewed"])
            if prumo_block.get("guidelines_reviewed")
            else None
        ),
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/core/test_skills.py -v`
Expected: PASS (all — `test_parses_full_prumo_block` still sees `custom_field` in `extra`).

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/core/skills.py tests/unit/core/test_skills.py
git commit -m "feat(skills): parse prumo.guidelines_reviewed"
```

---

### Task 2: Pure checker `stale_guideline_warnings`

**Files:** Modify `src/prumo_assist/core/skills.py`; Test `tests/unit/core/test_skills.py`

- [ ] **Step 1: Write the failing tests** — add to `tests/unit/core/test_skills.py`:

```python
def test_stale_guideline_warnings_flags_old(tmp_path: Path) -> None:
    from datetime import date

    from prumo_assist.core.skills import stale_guideline_warnings

    _write(
        tmp_path / "old" / "SKILL.md",
        '---\nname: old\ndescription: d\nprumo:\n  guidelines_reviewed: "2026-01-01"\n---\nb\n',
    )
    _write(
        tmp_path / "fresh" / "SKILL.md",
        '---\nname: fresh\ndescription: d\nprumo:\n  guidelines_reviewed: "2026-05-30"\n---\nb\n',
    )
    _write(tmp_path / "nodate" / "SKILL.md", "---\nname: nodate\ndescription: d\n---\nb\n")
    reg, _ = load_skill_registry(tmp_path)
    warns = stale_guideline_warnings(reg, today=date(2026, 6, 1), max_age_days=180)
    joined = " ".join(warns)
    assert "old" in joined
    assert "fresh" not in joined
    assert "nodate" not in joined


def test_stale_guideline_warnings_flags_malformed_date(tmp_path: Path) -> None:
    from datetime import date

    from prumo_assist.core.skills import stale_guideline_warnings

    _write(
        tmp_path / "bad" / "SKILL.md",
        '---\nname: bad\ndescription: d\nprumo:\n  guidelines_reviewed: "not-a-date"\n---\nb\n',
    )
    reg, _ = load_skill_registry(tmp_path)
    warns = stale_guideline_warnings(reg, today=date(2026, 6, 1))
    assert any("bad" in w and "inválid" in w for w in warns)
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/core/test_skills.py -k stale_guideline -v`
Expected: FAIL — `ImportError: cannot import name 'stale_guideline_warnings'`.

- [ ] **Step 3: Implement** — add `from datetime import date` to the imports of `src/prumo_assist/core/skills.py`, then append at module end:

```python
def stale_guideline_warnings(
    registry: SkillRegistry,
    *,
    today: date,
    max_age_days: int = 180,
) -> list[str]:
    """Avisos para skills cujo ``guidelines_reviewed`` está velho ou inválido.

    Só considera skills que **declaram** o campo — é opt-in por skill. Mantém o
    julgamento de validade fora do LLM (Princípio II): living guidelines como
    TRIPOD-LLM mudam a cada ~3 meses; sem revisão a prose envelhece em silêncio.
    """
    out: list[str] = []
    for name in registry.names():
        raw = registry.get(name).guidelines_reviewed
        if not raw:
            continue
        try:
            reviewed = date.fromisoformat(raw)
        except ValueError:
            out.append(f"skill '{name}': prumo.guidelines_reviewed inválido ({raw!r}); use ISO YYYY-MM-DD.")
            continue
        age = (today - reviewed).days
        if age > max_age_days:
            out.append(
                f"skill '{name}': checklists revisados há {age} dias "
                f"(> {max_age_days}); revalide os reporting guidelines e atualize guidelines_reviewed."
            )
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/core/test_skills.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/core/skills.py tests/unit/core/test_skills.py
git commit -m "feat(skills): stale_guideline_warnings checker"
```

---

### Task 3: Wire the check into `prumo doctor`

**Files:** Modify `src/prumo_assist/cli.py`; Test `tests/unit/test_cli_init.py`

- [ ] **Step 1: Write the failing test** — add to `tests/unit/test_cli_init.py` (it already uses Typer's `CliRunner`; reuse the same import style already present in the file):

```python
def test_doctor_runs_with_guideline_check(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from typer.testing import CliRunner

    from prumo_assist.cli import app

    # Minimal valid project so doctor's dir checks pass:
    for d in (".claude", "docs", "references"):
        (tmp_path / d).mkdir()
    result = CliRunner().invoke(app, ["doctor", str(tmp_path), "--json"])
    # Real plugin skills are fresh today, so the guideline path adds no issue;
    # the assertion is that the new code path runs without crashing.
    assert result.exit_code in (0, 1)
    assert "\"project\"" in result.stdout
```

- [ ] **Step 2: Run to verify fail (or pass-trivially)**

Run: `uv run pytest tests/unit/test_cli_init.py -k guideline_check -v`
Expected: FAIL only if the doctor code path raises; if it already passes, proceed (the real assertion is "no crash with the new path"). Implement Step 3 regardless.

- [ ] **Step 3: Implement** — in `src/prumo_assist/cli.py`, inside `doctor_command`, after the integration loop:

```python
    for adapter_cls in INTEGRATIONS.values():
        adapter = adapter_cls()
        issues.extend(adapter.doctor(target))

    # Staleness das checklists clínicas (Princípio II: validade sem LLM).
    skills_dir = _resolve_skills_dir()
    if skills_dir is not None:
        from datetime import UTC, datetime

        from prumo_assist.core.skills import stale_guideline_warnings

        registry, _warns = load_skill_registry(skills_dir, strict=False)
        issues.extend(
            stale_guideline_warnings(registry, today=datetime.now(UTC).date())
        )
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/test_cli_init.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/cli.py tests/unit/test_cli_init.py
git commit -m "feat(doctor): warn on stale clinical guideline reviews"
```

---

### Task 4: Seed the two clinical skills + changelog

**Files:** Modify `skills/peer-review/SKILL.md`, `skills/write-statistics/SKILL.md`, `CHANGELOG.md`

- [ ] **Step 1: Add the field to both frontmatters**

In each skill's `prumo:` block, add (immediately under the `version:` line):

```yaml
  guidelines_reviewed: "2026-05-30"
```

(Quoted, so YAML keeps it a string regardless of parser.)

- [ ] **Step 2: Changelog** — under `## [Não publicado]` → `### Adicionado` add:

```markdown
- **`prumo.guidelines_reviewed`** (frontmatter de skill) + aviso no
  `prumo doctor` quando os reporting guidelines de uma skill não são
  revisados há > 180 dias. Living guidelines (ex.: TRIPOD-LLM, revisado a cada
  ~3 meses) deixam de envelhecer em silêncio. `peer-review` e
  `write-statistics` já declaram o campo.
```

- [ ] **Step 3: Full gate**

Run: `uv run pytest -q && uv run ruff check src tests && uv run mypy --strict src`
Expected: green. (The skills still parse; `guidelines_reviewed` is now a typed field.)

- [ ] **Step 4: Commit**

```bash
git add skills/peer-review/SKILL.md skills/write-statistics/SKILL.md CHANGELOG.md
git commit -m "chore(skills): declare guidelines_reviewed on clinical skills"
```

---

## Self-Review

- **Spec coverage:** `guidelines_reviewed` parsed (Task 1), staleness checker (Task 2), `aviso no doctor` (Task 3), seeded on real skills (Task 4). ✅
- **Placeholders:** none. ✅
- **Type consistency:** `stale_guideline_warnings(registry, *, today: date, max_age_days=180) -> list[str]` used identically in tests (Task 2) and doctor (Task 3, passing `datetime.now(UTC).date()` — a `date`). `SkillManifest.guidelines_reviewed: str | None` matches the `str(...)` parse and the `if not raw` guard. ✅
- **Honesty note:** the doctor *unit* smoke test can't force a stale warning because doctor reads the real (fresh) plugin skills dir; staleness logic is fully covered by the pure-function tests in Task 2. This is an accepted, documented limitation rather than a hidden gap.
