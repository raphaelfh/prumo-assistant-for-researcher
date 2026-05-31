# Wiki-Lint Deterministic Checks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the *deterministic* checks the `wiki-lint` skill already specifies — broken `_log.md` prefixes, multiple `role: primary` notes, dead frontmatter links, and concept candidates — from LLM-budget into the cheap, reproducible `prumo wiki lint` (`domains/wiki/lint.py`), so the agentic skill only spends tokens on the genuinely semantic checks (contradictions, stale claims).

**Architecture:** Each check is a small pure helper appended to `domains/wiki/lint.py`, returning `WikiIssue`s the existing `lint()` aggregates. No new files, no new deps — extends the existing dataclass/report shape (`{"ok", "summary", "issues"}`). We add an `"info"` severity for advisory items (concept candidates) that must **not** flip `ok` to false. This is Constitution Principle II (determinístico antes de agêntico) in action.

**Tech Stack:** Python 3.11+ (`re`, `yaml`), pytest, `mypy --strict`, `ruff`.

---

## Honest framing (read first)

The item was "wiki-lint: contradictions/stale OU alinhar README". After reading the code, **contradictions/stale are correctly LLM-only**: `domains/wiki/lint.py`'s own docstring says it deliberately defers semantic work to the agentic skill, and `skills/wiki-lint/SKILL.md` §6-7 already implement contradictions/stale as LLM steps. The README describes the *skill* (hybrid), which does include them — so the README is **not** lying. No README change needed.

The real, low-complexity, high-value gap is different: the skill's §3, §4, §8, §9 describe **deterministic** checks that the cheap CLI layer does *not* implement, so today they cost LLM tokens (or get skipped). Implementing them in `lint.py` is the Principle-II win and lets the skill call `prumo wiki lint` and reserve the LLM for §6-7 only.

## Verified existing code (`domains/wiki/lint.py`)

```python
WIKILINK_RE   = re.compile(r"\[\[@([A-Za-z0-9_-]+)\]\]")          # citekey links
PAGE_LINK_RE  = re.compile(r"\[\[([^\]@\|]+)(?:\|[^\]]+)?\]\]")   # page links
EXPECTED_DIRS = ("concepts", "entities", "findings", "sources", "decisions")

@dataclass(frozen=True)
class WikiIssue: severity: str; code: str; message: str; page: str | None = None

def lint(pj_path: Path) -> dict[str, Any]: ...       # builds issues, returns _report(issues)
def _report(issues) -> {"ok": errors==0, "summary": {errors,warnings,total}, "issues":[asdict...]}
# bib keys: parse_bib(bib_path.read_text()) -> entries with .citekey
# pages: sorted(docs.rglob("*.md")); page_stems = {p.stem for p in pages}
```

The CLI (`domains/wiki/cli.py::lint_command`) and tests (`tests/unit/wiki/test_lint.py`) already consume that report shape — new issue `code`s flow through automatically.

## Files

- Modify `src/prumo_assist/domains/wiki/lint.py` + `tests/unit/wiki/test_lint.py`.
- Modify `skills/wiki-lint/SKILL.md` (note which checks are now deterministic).
- Modify `CHANGELOG.md`.

---

### Task 1: Broken `_log.md` prefix check (skill §3)

**Files:** Modify `src/prumo_assist/domains/wiki/lint.py`; Test `tests/unit/wiki/test_lint.py`

- [ ] **Step 1: Write the failing test** — add to `tests/unit/wiki/test_lint.py`:

```python
def test_lint_flags_broken_log_prefix(tmp_path: Path) -> None:
    pj = _setup_wiki(tmp_path)
    (pj / "docs" / "_log.md").write_text(
        "# Log\n\n"
        "## [2026-05-30] ingest | added smith2024\n\n"
        "## not a valid header line\n\n"
        "## [2026-05-30] frobnicate | bad verb\n",
        encoding="utf-8",
    )
    report = lint(pj)
    codes = {i["code"] for i in report["issues"]}
    assert "broken_log_prefix" in codes
    msgs = [i["message"] for i in report["issues"] if i["code"] == "broken_log_prefix"]
    assert any("not a valid header" in m for m in msgs)
    assert any("frobnicate" in m for m in msgs)
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/wiki/test_lint.py -k log_prefix -v`
Expected: FAIL — `broken_log_prefix` not in codes.

- [ ] **Step 3: Implement** — in `src/prumo_assist/domains/wiki/lint.py`, add the regex near the other module-level regexes:

```python
LOG_PREFIX_RE = re.compile(
    r"^## \[\d{4}-\d{2}-\d{2}\] (ingest|query|lint|decision|milestone|note) \| .+$"
)
```

Add this helper at module end:

```python
def _check_log_prefixes(docs: Path) -> list[WikiIssue]:
    """Cada ``## `` em ``_log.md`` deve casar ``[YYYY-MM-DD] <verbo> | <texto>``."""
    log = docs / "_log.md"
    if not log.is_file():
        return []
    issues: list[WikiIssue] = []
    for line in log.read_text(encoding="utf-8").splitlines():
        if line.startswith("## ") and not LOG_PREFIX_RE.match(line):
            issues.append(
                WikiIssue("warning", "broken_log_prefix", f"entrada de log fora do padrão: {line!r}")
            )
    return issues
```

Wire it into `lint()` just before `return _report(issues)`:

```python
    issues.extend(_check_log_prefixes(docs))

    return _report(issues)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/wiki/test_lint.py -v`
Expected: PASS (all — `_setup_wiki` writes `_log.md` as `# log\n`, which has no `## ` lines, so existing clean test stays clean).

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/wiki/lint.py tests/unit/wiki/test_lint.py
git commit -m "feat(wiki-lint): deterministic _log.md prefix check"
```

---

### Task 2: Multiple `role: primary` check (skill §4)

**Files:** Modify `src/prumo_assist/domains/wiki/lint.py`; Test `tests/unit/wiki/test_lint.py`

- [ ] **Step 1: Write the failing test** — add to `tests/unit/wiki/test_lint.py`:

```python
def test_lint_flags_multiple_primary_notes(tmp_path: Path) -> None:
    pj = _setup_wiki(tmp_path)
    notes = pj / "references" / "notes"
    for key in ("a", "b"):
        d = notes / key
        d.mkdir(parents=True)
        (d / "_meta.md").write_text(f"---\nid: {key}\nrole: primary\n---\n", encoding="utf-8")
    report = lint(pj)
    codes = {i["code"] for i in report["issues"]}
    assert "multiple_primary" in codes


def test_lint_single_primary_is_clean(tmp_path: Path) -> None:
    pj = _setup_wiki(tmp_path)
    d = pj / "references" / "notes" / "a"
    d.mkdir(parents=True)
    (d / "_meta.md").write_text("---\nid: a\nrole: primary\n---\n", encoding="utf-8")
    report = lint(pj)
    codes = {i["code"] for i in report["issues"]}
    assert "multiple_primary" not in codes
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/wiki/test_lint.py -k primary -v`
Expected: FAIL — `multiple_primary` not in codes.

- [ ] **Step 3: Implement** — add helper at module end of `src/prumo_assist/domains/wiki/lint.py`:

```python
_ROLE_PRIMARY_RE = re.compile(r"^role:\s*primary\s*$", re.MULTILINE)


def _check_single_primary(pj_path: Path) -> list[WikiIssue]:
    """``role: primary`` deve aparecer em no máximo 1 nota de ``references/notes/``."""
    notes_dir = pj_path / "references" / "notes"
    if not notes_dir.is_dir():
        return []
    primaries = [
        meta.parent.name
        for meta in sorted(notes_dir.rglob("_meta.md"))
        if _ROLE_PRIMARY_RE.search(meta.read_text(encoding="utf-8"))
    ]
    if len(primaries) >= 2:
        return [
            WikiIssue(
                "warning",
                "multiple_primary",
                f"{len(primaries)} notas com role: primary ({', '.join(primaries)}); esperado ≤ 1",
            )
        ]
    return []
```

Wire into `lint()` before `return _report(issues)`:

```python
    issues.extend(_check_single_primary(pj_path))

    return _report(issues)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/wiki/test_lint.py -v`
Expected: PASS (all — existing setups create no `references/notes/`, so the helper returns `[]`).

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/wiki/lint.py tests/unit/wiki/test_lint.py
git commit -m "feat(wiki-lint): deterministic multiple role:primary check"
```

---

### Task 3: Dead frontmatter links check (skill §9)

**Files:** Modify `src/prumo_assist/domains/wiki/lint.py`; Test `tests/unit/wiki/test_lint.py`

- [ ] **Step 1: Write the failing test** — add to `tests/unit/wiki/test_lint.py`:

```python
def test_lint_flags_dead_frontmatter_links(tmp_path: Path) -> None:
    pj = _setup_wiki(tmp_path, "@article{real,title={X}}\n")
    (pj / "docs" / "concepts" / "alpha.md").write_text(
        "---\ntype: concept\n---\n\nbody\n", encoding="utf-8"
    )
    (pj / "docs" / "concepts" / "beta.md").write_text(
        "---\ntype: concept\nrelated:\n  - '[[alpha]]'\n  - '[[ghost]]'\n"
        "sources:\n  - '[[@real]]'\n  - '[[@missingkey]]'\n---\n\n"
        "Links to [[alpha]] so beta is not orphan.\n",
        encoding="utf-8",
    )
    report = lint(pj)
    dead = [i["message"] for i in report["issues"] if i["code"] == "dead_link"]
    assert any("ghost" in m for m in dead)
    assert any("missingkey" in m for m in dead)
    assert not any("alpha" in m for m in dead)   # exists
    assert not any("real" in m for m in dead)    # exists in .bib
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/wiki/test_lint.py -k dead_frontmatter -v`
Expected: FAIL — `dead_link` not in codes.

- [ ] **Step 3: Implement** — add to `src/prumo_assist/domains/wiki/lint.py`. Add the import at the top (with the stdlib imports):

```python
import yaml
```

Add the helper at module end (it takes the already-computed `page_stems` and `bib_keys` so it does no extra IO beyond reading each page's frontmatter):

```python
_FM_LINK_FIELDS = ("links_to", "sources", "related")
_WIKILINK_TARGET_RE = re.compile(r"\[\[(@?[^\]|#]+)")


def _check_dead_frontmatter_links(
    pages: list[Path],
    pj_path: Path,
    page_stems: set[str],
    bib_keys: set[str],
) -> list[WikiIssue]:
    """Wikilinks em ``links_to``/``sources``/``related`` cujo alvo não existe."""
    issues: list[WikiIssue] = []
    for page in pages:
        text = page.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            fm = yaml.safe_load(parts[1])
        except yaml.YAMLError:
            continue
        if not isinstance(fm, dict):
            continue
        rel = page.relative_to(pj_path).as_posix()
        for field in _FM_LINK_FIELDS:
            value = fm.get(field)
            if not isinstance(value, list):
                continue
            for raw in value:
                m = _WIKILINK_TARGET_RE.search(str(raw))
                if not m:
                    continue
                target = m.group(1).strip()
                if target.startswith("@"):
                    key = target[1:]
                    if bib_keys and key not in bib_keys:
                        issues.append(
                            WikiIssue("warning", "dead_link", f"{field}: [[@{key}]] ausente do .bib", page=rel)
                        )
                elif target not in page_stems:
                    issues.append(
                        WikiIssue("warning", "dead_link", f"{field}: [[{target}]] não existe no vault", page=rel)
                    )
    return issues
```

Wire into `lint()` before `return _report(issues)` (note: `pages`, `page_stems`, `bib_keys` are already local variables in `lint()`):

```python
    issues.extend(_check_dead_frontmatter_links(pages, pj_path, page_stems, bib_keys))

    return _report(issues)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/wiki/test_lint.py -v`
Expected: PASS (all). Note `_setup_wiki`'s `_index.md` is `---\n---\n` (empty frontmatter → `fm is None`, skipped cleanly).

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/wiki/lint.py tests/unit/wiki/test_lint.py
git commit -m "feat(wiki-lint): deterministic dead frontmatter-link check"
```

---

### Task 4: Concept-candidate check (skill §8, severity `info`)

**Files:** Modify `src/prumo_assist/domains/wiki/lint.py`; Test `tests/unit/wiki/test_lint.py`

- [ ] **Step 1: Write the failing test** — add to `tests/unit/wiki/test_lint.py`:

```python
def test_lint_reports_concept_candidates_as_info(tmp_path: Path) -> None:
    pj = _setup_wiki(tmp_path)
    # "focal loss" wikilinked 3× but has no docs/concepts/focal loss.md page.
    for i, name in enumerate(("p1", "p2", "p3")):
        (pj / "docs" / "concepts" / f"{name}.md").write_text(
            f"---\ntype: concept\n---\n\nSee [[focal loss]] here ({i}). Also [[p1]].\n",
            encoding="utf-8",
        )
    report = lint(pj)
    cand = [i for i in report["issues"] if i["code"] == "concept_candidate"]
    assert any("focal loss" in i["message"] for i in cand)
    assert all(i["severity"] == "info" for i in cand)
    # info must not break ok:
    assert report["ok"] is True


def test_lint_ignores_low_frequency_concepts(tmp_path: Path) -> None:
    pj = _setup_wiki(tmp_path)
    (pj / "docs" / "concepts" / "p1.md").write_text(
        "---\ntype: concept\n---\n\nMentions [[rare term]] once. And [[p1]].\n",
        encoding="utf-8",
    )
    report = lint(pj)
    assert not any(i["code"] == "concept_candidate" for i in report["issues"])
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/unit/wiki/test_lint.py -k concept -v`
Expected: FAIL — `concept_candidate` not in codes.

- [ ] **Step 3: Implement** — add helper at module end of `src/prumo_assist/domains/wiki/lint.py`:

```python
_CONCEPT_CANDIDATE_MIN = 3


def _check_concept_candidates(pages: list[Path], page_stems: set[str]) -> list[WikiIssue]:
    """Wikilink ``[[termo]]`` citado ≥3× sem página correspondente → candidato a concept."""
    counts: dict[str, int] = {}
    for page in pages:
        text = page.read_text(encoding="utf-8")
        for target in PAGE_LINK_RE.findall(text):
            name = (target if isinstance(target, str) else target[0]).strip().split("#")[0]
            if name and name not in page_stems:
                counts[name] = counts.get(name, 0) + 1
    issues: list[WikiIssue] = []
    for name, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if count >= _CONCEPT_CANDIDATE_MIN:
            issues.append(
                WikiIssue("info", "concept_candidate", f"'{name}' citado {count}× sem página (candidato a /wiki-ingest)")
            )
    return issues
```

Wire into `lint()` before `return _report(issues)`:

```python
    issues.extend(_check_concept_candidates(pages, page_stems))

    return _report(issues)
```

Confirm `_report` already counts only `errors`/`warnings` for `ok` (it does: `errors = sum(... severity == "error")`), so `info` items never flip `ok`. The `summary` counts `errors`+`warnings`; that's fine — `info` simply isn't in either bucket but is still in `total` via `len(issues)`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/unit/wiki/test_lint.py -v`
Expected: PASS (all). Existing `test_lint_flags_orphan_pages` is unaffected: `[[alpha]]` there *does* resolve to a page, so it's not a concept candidate.

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/wiki/lint.py tests/unit/wiki/test_lint.py
git commit -m "feat(wiki-lint): deterministic concept-candidate report (info)"
```

---

### Task 5: Update skill + changelog (mark checks as deterministic)

**Files:** Modify `skills/wiki-lint/SKILL.md`, `CHANGELOG.md`

- [ ] **Step 1: Annotate the skill** — in `skills/wiki-lint/SKILL.md`, add this note immediately under the `## Checklist (ordem fixa)` heading (line ~29):

```markdown
> **Determinístico vs. agêntico.** As seções 2, 3, 4, 8 e 9 agora são cobertas
> por `prumo wiki lint` (Python, reprodutível, custo zero de LLM). Rode-o
> primeiro e gaste orçamento de LLM apenas nas seções **6 (contradições)** e
> **7 (stale claims)**, que exigem julgamento semântico. Códigos emitidos:
> `broken_citekey`, `orphan_page`, `broken_log_prefix`, `multiple_primary`,
> `dead_link`, `concept_candidate` (severity `info`).
```

- [ ] **Step 2: Bump skill version** — change `version: 1.0.0` to `version: 1.1.0` in `skills/wiki-lint/SKILL.md` frontmatter.

- [ ] **Step 3: Changelog** — under `## [Não publicado]` → `### Adicionado` add:

```markdown
- **`prumo wiki lint` ganha 4 checks determinísticos** que antes custavam LLM na
  skill `wiki-lint`: prefixo de `_log.md` fora do padrão (`broken_log_prefix`),
  múltiplas notas `role: primary` (`multiple_primary`), links mortos em
  frontmatter `links_to`/`sources`/`related` (`dead_link`) e conceitos citados
  ≥3× sem página (`concept_candidate`, severity `info`). Contradições e stale
  claims permanecem agênticas (Princípio II). Nova severidade `info` não altera
  `ok`.
```

- [ ] **Step 4: Full gate**

Run: `uv run pytest -q && uv run ruff check src tests && uv run mypy --strict src`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add skills/wiki-lint/SKILL.md CHANGELOG.md
git commit -m "docs(wiki-lint): mark deterministic checks + changelog"
```

---

## Self-Review

- **Spec coverage:** item said "contradictions/stale OU alinhar README". Findings: contradictions/stale are *correctly* agentic (lint.py docstring + skill §6-7), and README accurately describes the skill — so neither original option was the real gap. Delivered the higher-value adjacent fix: the deterministic checks the skill specifies (§3/§4/§8/§9) now run cheaply in `lint.py` (Tasks 1-4), with the skill annotated to reserve LLM for §6-7 (Task 5). The README/skill alignment is achieved via the Task-5 note. ✅
- **Placeholders:** none — every helper shown in full, every wire-in point specified. ✅
- **Type consistency:** all helpers return `list[WikiIssue]`; `WikiIssue(severity, code, message, page=None)` matches the frozen dataclass; `info` severity is a plain string the existing `_report` tolerates (counts errors/warnings only). `pages: list[Path]`, `page_stems: set[str]`, `bib_keys: set[str]` are the exact locals `lint()` already computes. ✅
- **Regression safety:** every new check returns `[]` for the minimal `_setup_wiki` fixture (no notes dir, `_log.md` has no `## ` lines, `_index.md` frontmatter empty), so the existing `test_lint_clean_when_minimal_structure` stays green.
