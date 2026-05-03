# PR-N1 — Migração de Layout (`<key>.md` → `<key>/_meta.md`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrar o layout de notas de paper de **arquivo único** (`references/notes/<key>.md`) pra **pasta-por-paper** (`references/notes/<key>/{_meta,_extract,_annotations}.md`), preservando todo comportamento atual e adicionando um comando `prumo paper migrate-layout` que faz a transição em projetos legados.

**Architecture:**
- Helpers de path centralizados em `core/note_paths.py` — caller único pra qualquer módulo que monta path de nota.
- Cada arquivo do paper é escrito por um caller específico: `_meta.md` por `paper sync`, `_extract.md` pela skill `paper-extract` (via `domains/paper/callout.py`), `_annotations.md` por `paper sync-annotations`.
- Comandos correlatos (`graph`, `find`, `lint`) varrem recursivamente; aceitam ambos layouts durante transição (graceful degradation; warn quando legado).
- `prumo paper migrate-layout` é one-shot: detecta `<key>.md` legado, desmembra em 3 arquivos novos numa pasta `<key>/`, preserva histórico via `git mv` quando possível.

**Tech Stack:** Python 3.11+, Typer, pytest, ruff, mypy strict. Mesmo stack do prumo-assist.

---

## File Structure

| Caminho | Ação | Responsabilidade |
|---|---|---|
| `src/prumo_assist/core/note_paths.py` | **Create** | path helpers (`note_dir`, `meta_path`, `extract_path`, `annotations_path`, `child_note_path`, `slugify`) |
| `src/prumo_assist/domains/paper/sync.py` | **Modify** | escrever em `<key>/_meta.md`; criar pasta se não existe; orphans considera pastas |
| `src/prumo_assist/domains/paper/callout.py` | **Modify** | `apply_extraction` escreve `<key>/_extract.md` (arquivo dedicado, não mais callout em `<key>.md`); atualiza YAML do `_meta.md` |
| `src/prumo_assist/domains/paper/zotero.py` | **Modify** | `sync_annotations` escreve `<key>/_annotations.md` (arquivo dedicado, não mais bloco em `<key>.md`) |
| `src/prumo_assist/domains/paper/migrate.py` | **Create** | função `migrate_pj` que desmembra notas legadas |
| `src/prumo_assist/domains/paper/cli.py` | **Modify** | adicionar `prumo paper migrate-layout` |
| `src/prumo_assist/domains/paper/api.py` | **Modify** | re-export `migrate_pj` como `migrate_layout` |
| `src/prumo_assist/domains/paper/graph.py` | **Modify** | varredura recursiva (legado + α); warn em legado |
| `src/prumo_assist/domains/paper/find.py` | **Modify** | varredura recursiva (legado + α) |
| `src/prumo_assist/domains/paper/lint.py` | **Modify** | varredura recursiva; nova regra "pasta sem `_meta.md`" |
| `tests/unit/core/test_note_paths.py` | **Create** | tests dos helpers |
| `tests/unit/paper/test_sync.py` | **Modify** | tests refletem novo path |
| `tests/unit/paper/test_callout.py` | **Modify** | tests refletem novo arquivo dedicado |
| `tests/unit/paper/test_migrate.py` | **Create** | tests do migrate-layout |
| `tests/unit/paper/test_graph.py` | **Modify** | tests do walking recursivo |
| `tests/unit/paper/test_lint.py` | **Modify** | tests da nova regra |
| `tests/unit/paper/test_cli.py` | **Modify** | integration tests refletem novo layout |
| `templates/pj_base/references/templates/literature_note.md` | **Modify** | template é o body de `_meta.md` (sem callout extract) |
| `skills/paper-manager/SKILL.md` | **Modify** | reflete novo layout |
| `skills/paper-extract/SKILL.md` | **Modify** | escrita em `_extract.md` |

---

## Task 1: Path helpers em `core/note_paths.py`

**Files:**
- Create: `src/prumo_assist/core/note_paths.py`
- Test: `tests/unit/core/test_note_paths.py`

- [ ] **Step 1: Write the failing test for `meta_path`**

Create `tests/unit/core/test_note_paths.py`:

```python
"""Tests para helpers de path do layout α."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.core.note_paths import (
    annotations_path,
    child_note_path,
    extract_path,
    meta_path,
    note_dir,
    slugify,
)


def test_note_dir_returns_subdir(tmp_path: Path) -> None:
    out = note_dir(tmp_path, "smith2024")
    assert out == tmp_path / "references" / "notes" / "smith2024"


def test_meta_path(tmp_path: Path) -> None:
    out = meta_path(tmp_path, "smith2024")
    assert out == tmp_path / "references" / "notes" / "smith2024" / "_meta.md"


def test_extract_path(tmp_path: Path) -> None:
    out = extract_path(tmp_path, "smith2024")
    assert out == tmp_path / "references" / "notes" / "smith2024" / "_extract.md"


def test_annotations_path(tmp_path: Path) -> None:
    out = annotations_path(tmp_path, "smith2024")
    assert out == tmp_path / "references" / "notes" / "smith2024" / "_annotations.md"


def test_child_note_path_with_itemkey_and_slug(tmp_path: Path) -> None:
    out = child_note_path(tmp_path, "smith2024", "ABCD1234", "ideias-da-introducao")
    assert (
        out
        == tmp_path / "references" / "notes" / "smith2024" / "note__ABCD1234__ideias-da-introducao.md"
    )


def test_slugify_converts_to_kebab() -> None:
    assert slugify("Ideias da Introdução") == "ideias-da-introducao"


def test_slugify_strips_punctuation() -> None:
    assert slugify("Crítica Metodológica: parte 2!") == "critica-metodologica-parte-2"


def test_slugify_truncates_to_30_chars() -> None:
    long = "uma frase muito longa que ultrapassa trinta caracteres facilmente"
    out = slugify(long)
    assert len(out) <= 30
    assert not out.endswith("-")  # sem hífen pendurado


def test_slugify_handles_empty() -> None:
    assert slugify("") == "untitled"
    assert slugify("   ") == "untitled"
```

- [ ] **Step 2: Run tests to verify they fail (module missing)**

Run: `uv run pytest tests/unit/core/test_note_paths.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prumo_assist.core.note_paths'`

- [ ] **Step 3: Implement `core/note_paths.py`**

Create `src/prumo_assist/core/note_paths.py`:

```python
"""Path helpers para layout α de notas de paper.

Layout α: cada paper tem uma pasta `references/notes/<citekey>/` contendo:

- `_meta.md` — gerado por `prumo paper sync` (YAML CSL-JSON + body humano)
- `_extract.md` — gerado por `/prumo-assist:paper-extract` (callout estruturado)
- `_annotations.md` — gerado por `prumo paper sync-annotations` (highlights+notes)
- `note__<itemKey>__<slug>.md` — gerado por `prumo paper sync-notes` (NOVO em PR-N2)

Centralizar a montagem de path aqui evita drift entre módulos. Spec:
docs/superpowers/specs/2026-05-03-zotero-notes-integration-design.md
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

_SLUG_MAX_LEN = 30


def note_dir(pj_path: Path, citekey: str) -> Path:
    """Retorna `<pj>/references/notes/<citekey>/`."""
    return pj_path / "references" / "notes" / citekey


def meta_path(pj_path: Path, citekey: str) -> Path:
    """Retorna `<pj>/references/notes/<citekey>/_meta.md`."""
    return note_dir(pj_path, citekey) / "_meta.md"


def extract_path(pj_path: Path, citekey: str) -> Path:
    """Retorna `<pj>/references/notes/<citekey>/_extract.md`."""
    return note_dir(pj_path, citekey) / "_extract.md"


def annotations_path(pj_path: Path, citekey: str) -> Path:
    """Retorna `<pj>/references/notes/<citekey>/_annotations.md`."""
    return note_dir(pj_path, citekey) / "_annotations.md"


def child_note_path(pj_path: Path, citekey: str, item_key: str, slug: str) -> Path:
    """Retorna `<pj>/references/notes/<citekey>/note__<itemKey>__<slug>.md`."""
    return note_dir(pj_path, citekey) / f"note__{item_key}__{slug}.md"


def slugify(text: str) -> str:
    """kebab-case ASCII, ≤30 chars, sem hífens pendurados.

    Vazio ou só whitespace vira `"untitled"`.
    """
    text = text.strip()
    if not text:
        return "untitled"
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()
    kebab = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    if not kebab:
        return "untitled"
    if len(kebab) > _SLUG_MAX_LEN:
        kebab = kebab[:_SLUG_MAX_LEN].rstrip("-")
    return kebab or "untitled"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/core/test_note_paths.py -v`
Expected: 8 tests PASS

- [ ] **Step 5: Run linter and type checker**

Run: `uv run ruff check src/prumo_assist/core/note_paths.py tests/unit/core/test_note_paths.py`
Expected: All checks passed!

Run: `uv run --extra dev mypy src/prumo_assist/core/note_paths.py`
Expected: Success: no issues found

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/core/note_paths.py tests/unit/core/test_note_paths.py
git commit -m "feat(core): add note_paths helpers for layout α"
```

---

## Task 2: Refatorar `paper sync` pra escrever em `<key>/_meta.md`

**Files:**
- Modify: `src/prumo_assist/domains/paper/sync.py:214-248` (função `sync`)
- Modify: `tests/unit/paper/test_sync.py:78-106` (3 tests existentes refletem novo path)
- Modify: `tests/unit/paper/test_cli.py:14-32` (integration test reflete novo path)

- [ ] **Step 1: Update tests in `tests/unit/paper/test_sync.py` to expect `<key>/_meta.md`**

Replace lines 78-106 (3 tests) with:

```python
def test_sync_creates_meta_md_for_each_entry(tmp_path: Path) -> None:
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "_references.bib").write_text(
        "@article{smith2024,\n"
        "  title = {Combi-Nado Fusion},\n"
        '  author = "Smith, Jane",\n'
        "  year = 2024\n"
        "}\n"
    )
    report = sync(tmp_path)
    assert report["created"] == 1
    assert report["updated"] == 0
    assert report["orphans"] == []
    meta = refs / "notes" / "smith2024" / "_meta.md"
    assert meta.exists()
    content = meta.read_text()
    assert "Combi-Nado Fusion" in content
    assert "smith2024" in content


def test_sync_re_run_is_idempotent(tmp_path: Path) -> None:
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "_references.bib").write_text(
        "@article{smith2024,\n  title = {X},\n  year = 2024\n}\n"
    )
    sync(tmp_path)
    report = sync(tmp_path)
    assert report["created"] == 0
    # idempotência: nada de novo escrito


def test_sync_detects_orphan_subdirs(tmp_path: Path) -> None:
    refs = tmp_path / "references"
    notes = refs / "notes"
    (notes / "orphan_one").mkdir(parents=True)
    (notes / "orphan_one" / "_meta.md").write_text("---\nid: orphan_one\n---\n\nbody\n")
    (refs / "_references.bib").write_text("@article{a, title={X}}\n")
    report = sync(tmp_path)
    assert "orphan_one" in report["orphans"]


def test_sync_raises_when_bib_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        sync(tmp_path)
```

- [ ] **Step 2: Update integration test in `tests/unit/paper/test_cli.py`**

Replace `test_paper_sync_creates_notes` (lines 23-32) with:

```python
def test_paper_sync_creates_meta_md(tmp_path: Path) -> None:
    pj = _bootstrap_project(
        tmp_path,
        "@article{smith2024,\n  title = {Combinado Fusion},\n  year = 2024\n}\n",
    )
    result = runner.invoke(app, ["paper", "sync", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = _last_json(result.stdout)
    assert payload["created"] == 1
    assert (pj / "references" / "notes" / "smith2024" / "_meta.md").is_file()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/paper/test_sync.py tests/unit/paper/test_cli.py::test_paper_sync_creates_meta_md -v`
Expected: 4 tests FAIL with paths still pointing to old `<key>.md`

- [ ] **Step 4: Refactor `sync.py:sync` to use `note_paths.meta_path`**

Edit `src/prumo_assist/domains/paper/sync.py` — replace the `sync` function (lines 214-248) with:

```python
def sync(pj_path: Path) -> dict[str, Any]:
    """Sync ``.bib`` → ``<key>/_meta.md``. Retorna report com ``created``, ``updated``, ``orphans``."""
    from prumo_assist.core.note_paths import meta_path, note_dir

    bib = pj_path / "references" / "_references.bib"
    notes_dir = pj_path / "references" / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    if not bib.exists():
        raise FileNotFoundError(f"{bib} não encontrado. Rode o auto-export do Better BibTeX.")

    entries = parse_bib(bib.read_text())
    bib_keys = {e.citekey for e in entries}

    created, updated = 0, 0
    template_body = _template_body(pj_path)
    tpl_defaults = _template_yaml_defaults(pj_path)

    for entry in entries:
        meta = bib_entry_to_metadata(entry)
        nota = meta_path(pj_path, entry.citekey)
        nota.parent.mkdir(parents=True, exist_ok=True)
        if nota.exists():
            existing = read_nota_yaml(nota)
            merged = merge_nota_yaml(existing, meta)
            current_text = nota.read_text()
            m = FRONTMATTER_RE.match(current_text)
            body = current_text[m.end() :] if m else current_text
            if merged != existing:
                write_nota(nota, merged, body)
                updated += 1
        else:
            merged = merge_nota_yaml(tpl_defaults, meta)
            write_nota(nota, merged, template_body)
            created += 1

    orphan_keys: list[str] = []
    for child in notes_dir.iterdir():
        # Subdir layout α: pasta com _meta.md
        if child.is_dir() and (child / "_meta.md").is_file():
            if child.name not in bib_keys:
                orphan_keys.append(child.name)
        # Legado: arquivo único <key>.md (suportado em transição)
        elif child.is_file() and child.suffix == ".md":
            if child.stem not in bib_keys:
                orphan_keys.append(child.stem)
    return {"created": created, "updated": updated, "orphans": sorted(orphan_keys)}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/paper/test_sync.py tests/unit/paper/test_cli.py -v`
Expected: All sync tests PASS (other CLI tests may fail temporarily — they get fixed in tasks 6 and 7)

- [ ] **Step 6: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/paper/sync.py tests/unit/paper/test_sync.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/paper/sync.py`
Expected: clean

- [ ] **Step 7: Commit**

```bash
git add src/prumo_assist/domains/paper/sync.py tests/unit/paper/test_sync.py tests/unit/paper/test_cli.py
git commit -m "feat(paper): sync writes to <key>/_meta.md (layout α)"
```

---

## Task 3: Refatorar `paper-extract` callout pra arquivo dedicado `_extract.md`

**Files:**
- Modify: `src/prumo_assist/domains/paper/callout.py:107-138` (função `apply_extraction`)
- Modify: `tests/unit/paper/test_callout.py` (todos os tests refletem novo arquivo)
- Modify: `skills/paper-extract/SKILL.md` (atualizado em Task 7)

- [ ] **Step 1: Write failing tests in `tests/unit/paper/test_callout.py`**

Append after the existing tests (preserve `parse_extraction_template` / `render_callout` tests, they don't change). Replace the file's `test_write_callout_*` and `test_read_callout_roundtrip` tests with these new ones. Final state of the file should look like this:

```python
"""Tests pro render e write do callout estruturado em _extract.md."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.core.note_paths import extract_path, meta_path
from prumo_assist.domains.paper.callout import (
    EXTRACT_BEGIN,
    EXTRACT_END,
    ExtractionSection,
    apply_extraction,
    parse_extraction_template,
    render_callout,
)


def test_parse_template_extracts_section_names_and_instructions() -> None:
    text = "# Header\n\n### TL;DR\n<!-- escreva 2-3 frases -->\n\n### PICOT\n<!-- 5 bullets -->\n"
    sections = parse_extraction_template(text)
    assert [s.name for s in sections] == ["TL;DR", "PICOT"]


def test_render_callout_includes_meta_and_sections() -> None:
    sections = [
        ExtractionSection(name="TL;DR", instruction="x"),
        ExtractionSection(name="PICOT", instruction="y"),
    ]
    out = render_callout(
        sections,
        {"TL;DR": "Two-line summary.", "PICOT": "P: ..."},
        model="claude-test",
        date="2026-04-28",
    )
    assert out.startswith(EXTRACT_BEGIN)
    assert out.endswith(EXTRACT_END)
    assert "claude-test" in out
    assert "Two-line summary." in out


def _bootstrap(tmp_path: Path, citekey: str) -> tuple[Path, Path]:
    """Cria pj_*/references/notes/<key>/_meta.md mínimo + paper_extraction template."""
    meta = meta_path(tmp_path, citekey)
    meta.parent.mkdir(parents=True, exist_ok=True)
    meta.write_text(f"---\nid: {citekey}\nextracted_at: null\n---\n\n## Notas humanas\n")
    template = tmp_path / ".claude" / "paper_extraction.md"
    template.parent.mkdir(parents=True, exist_ok=True)
    template.write_text("### TL;DR\n<!-- 2 linhas -->\n\n### PICOT\n<!-- 5 bullets -->\n")
    return meta, template


def test_apply_extraction_creates_extract_md(tmp_path: Path) -> None:
    citekey = "smith2024"
    meta, template = _bootstrap(tmp_path, citekey)
    changed = apply_extraction(
        pj_path=tmp_path,
        citekey=citekey,
        template_path=template,
        content={"TL;DR": "summary", "PICOT": "p: x"},
        model="claude-test",
        date="2026-05-03",
    )
    assert changed is True
    extract = extract_path(tmp_path, citekey)
    assert extract.exists()
    text = extract.read_text()
    assert "summary" in text
    assert EXTRACT_BEGIN in text
    assert EXTRACT_END in text
    # frontmatter mínimo
    assert text.startswith("---\n")
    assert "paper: smith2024" in text
    assert "source: prumo-paper-extract" in text


def test_apply_extraction_updates_meta_yaml_extracted_fields(tmp_path: Path) -> None:
    citekey = "smith2024"
    meta, template = _bootstrap(tmp_path, citekey)
    apply_extraction(
        pj_path=tmp_path,
        citekey=citekey,
        template_path=template,
        content={"TL;DR": "x"},
        model="claude-test",
        date="2026-05-03",
    )
    meta_text = meta.read_text()
    assert "extracted_at: '2026-05-03'" in meta_text or 'extracted_at: "2026-05-03"' in meta_text
    assert "extracted_model: claude-test" in meta_text or "extracted_model: 'claude-test'" in meta_text


def test_apply_extraction_idempotent_when_content_unchanged(tmp_path: Path) -> None:
    citekey = "smith2024"
    _, template = _bootstrap(tmp_path, citekey)
    apply_extraction(
        pj_path=tmp_path,
        citekey=citekey,
        template_path=template,
        content={"TL;DR": "x"},
        model="m",
        date="2026-05-03",
    )
    changed = apply_extraction(
        pj_path=tmp_path,
        citekey=citekey,
        template_path=template,
        content={"TL;DR": "x"},
        model="m",
        date="2026-05-04",  # data muda mas conteúdo não
    )
    assert changed is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/paper/test_callout.py -v`
Expected: FAIL — `apply_extraction` signature mismatch (expects `pj_path` + `citekey`, current expects `nota_path`).

- [ ] **Step 3: Refactor `callout.py:apply_extraction` to write to `_extract.md`**

Replace the entire `apply_extraction` function and its helpers (lines 107-152) in `src/prumo_assist/domains/paper/callout.py` with:

```python
EXTRACT_FRONTMATTER_KEYS = ("paper", "source", "generated_at")


def apply_extraction(
    pj_path: Path,
    citekey: str,
    template_path: Path,
    content: dict[str, str],
    model: str,
    date: str,
) -> bool:
    """Aplica extração: renderiza callout em ``_extract.md``, atualiza YAML do ``_meta.md``.

    Retorna ``True`` se algum dos dois arquivos mudou; ``False`` se conteúdo idêntico.
    Só atualiza ``extracted_at`` no `_meta.md` quando o callout efetivamente muda.
    """
    from prumo_assist.core.note_paths import extract_path, meta_path

    sections = parse_extraction_template(template_path.read_text())
    new_callout = render_callout(sections, content, model, date)

    extract_file = extract_path(pj_path, citekey)
    extract_file.parent.mkdir(parents=True, exist_ok=True)

    new_extract_text = _compose_extract_file(citekey, new_callout, date)

    if extract_file.exists():
        existing = extract_file.read_text()
        if _extract_body_equal(existing, new_extract_text):
            return False
    extract_file.write_text(new_extract_text)

    # Update extracted_* fields in _meta.md (if it exists)
    meta_file = meta_path(pj_path, citekey)
    if meta_file.exists():
        yaml_dict = read_nota_yaml(meta_file)
        text = meta_file.read_text()
        m = FRONTMATTER_RE.match(text)
        body = text[m.end() :] if m else text
        yaml_dict["extracted_at"] = date
        yaml_dict["extracted_model"] = model
        yaml_dict["extracted_template_hash"] = hash_template(template_path)
        write_nota(meta_file, yaml_dict, body)
    return True


def _compose_extract_file(citekey: str, callout: str, date: str) -> str:
    """Monta o conteúdo de _extract.md: YAML mínimo + callout."""
    fm = (
        f"---\n"
        f"paper: {citekey}\n"
        f"source: prumo-paper-extract\n"
        f"generated_at: '{date}'\n"
        f"---\n\n"
    )
    return fm + callout + "\n"


def _extract_body_equal(a: str, b: str) -> bool:
    """Compara dois _extract.md ignorando linhas voláteis (`generated_at`, `Gerado em`)."""

    def strip_volatile(s: str) -> str:
        s = re.sub(r"^generated_at:.*\n", "", s, flags=re.MULTILINE)
        s = re.sub(r"> \*\*Gerado em:\*\*[^\n]*\n", "", s)
        return s

    return strip_volatile(a) == strip_volatile(b)
```

Then **delete** the old top-level helpers `read_callout`, `write_callout`, `_callout_body_equal`, and the `CALLOUT_RE` constant (now obsolete — they were used to insert callout *inside* `<key>.md`; not needed when `_extract.md` is dedicated). Keep `EXTRACT_BEGIN`, `EXTRACT_END`, `parse_extraction_template`, `render_callout`, `hash_template`, `ExtractionSection`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/paper/test_callout.py -v`
Expected: 5 tests PASS

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/paper/callout.py tests/unit/paper/test_callout.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/paper/callout.py`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/domains/paper/callout.py tests/unit/paper/test_callout.py
git commit -m "feat(paper): paper-extract writes _extract.md (layout α)"
```

---

## Task 4: Refatorar `sync-annotations` pra arquivo dedicado `_annotations.md`

**Files:**
- Modify: `src/prumo_assist/domains/paper/zotero.py` (substituir `upsert_block` + ajustar `sync_annotations`)
- Modify: `tests/unit/paper/test_paper_sync.py` (novo) — não há test atual pro sync_annotations; vamos criar

- [ ] **Step 1: Write failing tests in `tests/unit/paper/test_zotero.py`**

Create `tests/unit/paper/test_zotero.py`:

```python
"""Tests pro sync_annotations escrevendo arquivo dedicado _annotations.md."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from prumo_assist.core.note_paths import annotations_path, meta_path
from prumo_assist.domains.paper.zotero import compose_annotations_file, render_annotation


def test_render_annotation_yellow_highlight() -> None:
    data = {
        "annotationColor": "#ffd400",
        "annotationPageLabel": "5",
        "annotationType": "highlight",
        "annotationText": "Combinado fusion improves...",
        "annotationComment": "verificar",
    }
    lines = render_annotation(data)
    assert any("🟡" in line for line in lines)
    assert any("p. 5" in line for line in lines)
    assert any("> Combinado fusion improves..." in line for line in lines)
    assert any("verificar" in line for line in lines)


def test_compose_annotations_file_has_yaml_and_block() -> None:
    text = compose_annotations_file(
        citekey="smith2024",
        annotations=[{
            "annotationColor": "#ffd400",
            "annotationPageLabel": "1",
            "annotationType": "highlight",
            "annotationText": "Hello",
            "annotationSortIndex": "00001",
        }],
        notes=[],
    )
    assert text.startswith("---\n")
    assert "paper: smith2024" in text
    assert "source: prumo-zotero-annotations" in text
    assert "<!-- BEGIN ZOTERO ANNOTATIONS -->" in text
    assert "<!-- END ZOTERO ANNOTATIONS -->" in text
    assert "Hello" in text


def test_sync_annotations_writes_dedicated_file(tmp_path: Path) -> None:
    from prumo_assist.domains.paper.zotero import sync_annotations

    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "_references.bib").write_text("@article{smith2024, title={X}}\n")
    meta_p = meta_path(tmp_path, "smith2024")
    meta_p.parent.mkdir(parents=True, exist_ok=True)
    meta_p.write_text("---\nid: smith2024\n---\n\nbody\n")

    fake_children = [
        {
            "itemType": "annotation",
            "annotationType": "highlight",
            "annotationColor": "#ffd400",
            "annotationPageLabel": "5",
            "annotationText": "Hello",
            "annotationSortIndex": "001",
        }
    ]

    with (
        patch("prumo_assist.domains.paper.zotero.check_zotero_running", return_value=True),
        patch("prumo_assist.domains.paper.zotero.resolve_citekey", return_value=(1, "ABCD1234")),
        patch("prumo_assist.domains.paper.zotero.fetch_children", return_value=fake_children),
    ):
        report = sync_annotations(tmp_path)

    annot = annotations_path(tmp_path, "smith2024")
    assert annot.exists()
    assert "Hello" in annot.read_text()
    assert report["inserted"] == 1
    # _meta.md NÃO mexido
    assert "Hello" not in meta_p.read_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/paper/test_zotero.py -v`
Expected: FAIL — `compose_annotations_file` not defined; `sync_annotations` still upserts in `<key>.md`.

- [ ] **Step 3: Refactor `zotero.py`: replace `upsert_block` + `sync_annotations`**

In `src/prumo_assist/domains/paper/zotero.py`, **delete** the constant `SECTION_HEADING`, the regex `_BLOCK_RE`, and the function `upsert_block`. Then add `compose_annotations_file` and rewrite `sync_annotations`:

```python
def compose_annotations_file(
    citekey: str,
    annotations: list[dict[str, Any]],
    notes: list[dict[str, Any]],
) -> str:
    """Conteúdo completo de _annotations.md: YAML + bloco delimitado."""
    fm = (
        f"---\n"
        f"paper: {citekey}\n"
        f"source: prumo-zotero-annotations\n"
        f"---\n\n"
    )
    block = render_block(annotations, notes)
    return fm + block


def sync_annotations(pj_path: Path) -> dict[str, Any]:
    """Sincroniza annotations do Zotero pra ``<key>/_annotations.md``.

    Pré-requisitos: Zotero 9 aberto + Better BibTeX instalado. Falha cedo
    com mensagem clara se faltar algum.
    """
    from prumo_assist.core.note_paths import annotations_path, meta_path

    bib = pj_path / "references" / "_references.bib"
    notes_dir = pj_path / "references" / "notes"

    if not bib.exists():
        raise FileNotFoundError(f"{bib} não encontrado.")
    if not notes_dir.exists():
        raise FileNotFoundError(f"{notes_dir} não existe. Rode `prumo paper sync` primeiro.")
    if not check_zotero_running():
        raise ConnectionError(
            f"Zotero não está rodando em {ZOTERO_BASE}. Abra o Zotero 9 e tente de novo."
        )

    citekeys = [e.citekey for e in parse_bib(bib.read_text(encoding="utf-8"))]
    inserted = updated = unchanged = 0
    no_meta: list[str] = []
    no_resolve: list[str] = []
    no_children: list[str] = []
    errors: list[tuple[str, str]] = []

    for citekey in citekeys:
        meta = meta_path(pj_path, citekey)
        if not meta.exists():
            no_meta.append(citekey)
            continue
        resolved = resolve_citekey(citekey)
        if not resolved:
            no_resolve.append(citekey)
            continue
        lib_id, item_key = resolved
        try:
            children = fetch_children(lib_id, item_key)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            errors.append((citekey, str(exc)))
            continue

        annots, notes_lst = split_children(children)
        if not annots and not notes_lst:
            no_children.append(citekey)
            continue

        new_text = compose_annotations_file(citekey, annots, notes_lst)
        annot_file = annotations_path(pj_path, citekey)
        if annot_file.exists():
            old = annot_file.read_text(encoding="utf-8")
            if old == new_text:
                unchanged += 1
                continue
            annot_file.write_text(new_text, encoding="utf-8")
            updated += 1
        else:
            annot_file.write_text(new_text, encoding="utf-8")
            inserted += 1

    return {
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "no_meta": no_meta,
        "no_resolve": no_resolve,
        "no_children": no_children,
        "errors": errors,
    }
```

Note: the old report key `no_note` was renamed to `no_meta` because the prerequisite is now `_meta.md`, not `<key>.md`.

- [ ] **Step 4: Update CLI report message in `cli.py`**

In `src/prumo_assist/domains/paper/cli.py`, the `sync_annotations_command` reads `report['unchanged']`. No change needed — same key still exists. Verify by re-reading the file.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/paper/test_zotero.py -v`
Expected: 3 tests PASS

- [ ] **Step 6: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/paper/zotero.py tests/unit/paper/test_zotero.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/paper/zotero.py`
Expected: clean

- [ ] **Step 7: Commit**

```bash
git add src/prumo_assist/domains/paper/zotero.py tests/unit/paper/test_zotero.py
git commit -m "feat(paper): sync-annotations writes dedicated _annotations.md (layout α)"
```

---

## Task 5: Adicionar `prumo paper migrate-layout`

**Files:**
- Create: `src/prumo_assist/domains/paper/migrate.py`
- Modify: `src/prumo_assist/domains/paper/cli.py` (adicionar comando)
- Modify: `src/prumo_assist/domains/paper/api.py` (re-export)
- Create: `tests/unit/paper/test_migrate.py`

- [ ] **Step 1: Write failing tests in `tests/unit/paper/test_migrate.py`**

Create `tests/unit/paper/test_migrate.py`:

```python
"""Tests para prumo paper migrate-layout."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.core.note_paths import annotations_path, extract_path, meta_path
from prumo_assist.domains.paper.migrate import migrate_pj


def _bootstrap_legacy(tmp_path: Path) -> Path:
    """Cria pj com 1 nota legada incluindo callout extract + bloco zotero annotations."""
    refs = tmp_path / "references"
    notes = refs / "notes"
    notes.mkdir(parents=True)
    (refs / "_references.bib").write_text("@article{smith2024, title={X}}\n")
    legacy = notes / "smith2024.md"
    legacy.write_text(
        "---\n"
        "id: smith2024\n"
        "title: Combi-Nado Fusion\n"
        "tldr: User notes\n"
        "---\n\n"
        "<!-- paper-extract:begin -->\n"
        "> ### TL;DR\n"
        "> auto summary\n"
        "<!-- paper-extract:end -->\n\n"
        "## Problema\n\n"
        "human notes here\n\n"
        "## Anotações do Zotero\n\n"
        "<!-- BEGIN ZOTERO ANNOTATIONS -->\n"
        "### 🟡 p. 5 — highlight\n"
        "> highlighted text\n"
        "<!-- END ZOTERO ANNOTATIONS -->\n"
    )
    return tmp_path


def test_migrate_creates_subdir_with_three_files(tmp_path: Path) -> None:
    pj = _bootstrap_legacy(tmp_path)
    report = migrate_pj(pj)
    assert report["migrated"] == ["smith2024"]
    assert meta_path(pj, "smith2024").is_file()
    assert extract_path(pj, "smith2024").is_file()
    assert annotations_path(pj, "smith2024").is_file()


def test_migrate_meta_keeps_yaml_and_human_body(tmp_path: Path) -> None:
    pj = _bootstrap_legacy(tmp_path)
    migrate_pj(pj)
    meta_text = meta_path(pj, "smith2024").read_text()
    assert "id: smith2024" in meta_text
    assert "tldr: User notes" in meta_text
    assert "## Problema" in meta_text
    assert "human notes here" in meta_text
    # callout e bloco zotero NÃO devem estar em _meta.md
    assert "<!-- paper-extract:begin -->" not in meta_text
    assert "<!-- BEGIN ZOTERO ANNOTATIONS -->" not in meta_text


def test_migrate_extract_md_has_callout(tmp_path: Path) -> None:
    pj = _bootstrap_legacy(tmp_path)
    migrate_pj(pj)
    text = extract_path(pj, "smith2024").read_text()
    assert "<!-- paper-extract:begin -->" in text
    assert "auto summary" in text
    assert text.startswith("---\n")
    assert "paper: smith2024" in text


def test_migrate_annotations_md_has_block(tmp_path: Path) -> None:
    pj = _bootstrap_legacy(tmp_path)
    migrate_pj(pj)
    text = annotations_path(pj, "smith2024").read_text()
    assert "<!-- BEGIN ZOTERO ANNOTATIONS -->" in text
    assert "highlighted text" in text
    assert "paper: smith2024" in text


def test_migrate_idempotent_when_already_migrated(tmp_path: Path) -> None:
    pj = _bootstrap_legacy(tmp_path)
    migrate_pj(pj)
    report = migrate_pj(pj)
    assert report["migrated"] == []
    assert report["already_migrated"] == ["smith2024"]


def test_migrate_legacy_without_callout_or_zotero_block(tmp_path: Path) -> None:
    refs = tmp_path / "references"
    notes = refs / "notes"
    notes.mkdir(parents=True)
    (refs / "_references.bib").write_text("@article{plain2024, title={Y}}\n")
    (notes / "plain2024.md").write_text(
        "---\nid: plain2024\n---\n\n## Notas\n\nNada de zotero aqui.\n"
    )
    report = migrate_pj(tmp_path)
    assert report["migrated"] == ["plain2024"]
    assert meta_path(tmp_path, "plain2024").is_file()
    # _extract.md e _annotations.md NÃO devem ser criados (não havia conteúdo)
    assert not extract_path(tmp_path, "plain2024").exists()
    assert not annotations_path(tmp_path, "plain2024").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/paper/test_migrate.py -v`
Expected: FAIL — `migrate_pj` not defined.

- [ ] **Step 3: Implement `migrate.py`**

Create `src/prumo_assist/domains/paper/migrate.py`:

```python
"""Migração one-shot do layout legado pro layout α.

Layout legado (antes de 0.4.0):
    references/notes/<key>.md  — arquivo único com YAML + body humano +
                                   callout paper-extract + bloco zotero annotations

Layout α (após):
    references/notes/<key>/
    ├── _meta.md         — YAML CSL-JSON + body humano
    ├── _extract.md      — callout paper-extract isolado (se existia)
    └── _annotations.md  — bloco zotero annotations isolado (se existia)

Idempotente: rodar duas vezes não faz mal — pasta já existe e arquivo legado some.
Preserva histórico via `git mv` quando o pj_* é repo git.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from prumo_assist.core.note_paths import annotations_path, extract_path, meta_path
from prumo_assist.domains.paper.sync import FRONTMATTER_RE

CALLOUT_RE = re.compile(
    r"<!--\s*paper-extract:begin\s*-->.*?<!--\s*paper-extract:end\s*-->",
    flags=re.DOTALL,
)
ZOTERO_BLOCK_RE = re.compile(
    r"(?:^##\s+Anotações do Zotero\s*\n+)?<!--\s*BEGIN ZOTERO ANNOTATIONS\s*-->.*?"
    r"<!--\s*END ZOTERO ANNOTATIONS\s*-->",
    flags=re.DOTALL | re.MULTILINE,
)


def _extract_callout_block(body: str) -> tuple[str, str | None]:
    """Remove o callout paper-extract do body. Retorna (body_sem_callout, callout_or_None)."""
    m = CALLOUT_RE.search(body)
    if not m:
        return body, None
    callout = m.group(0)
    cleaned = (body[: m.start()] + body[m.end() :]).strip()
    return cleaned, callout


def _extract_zotero_block(body: str) -> tuple[str, str | None]:
    """Remove o bloco ZOTERO ANNOTATIONS (e o heading ## Anotações do Zotero, se presente)."""
    m = ZOTERO_BLOCK_RE.search(body)
    if not m:
        return body, None
    block = m.group(0)
    # Remove o "## Anotações do Zotero" prefix do block guardado
    inner = re.sub(r"^##\s+Anotações do Zotero\s*\n+", "", block).strip()
    cleaned = (body[: m.start()] + body[m.end() :]).strip()
    return cleaned, inner


def _git_mv(src: Path, dst: Path) -> bool:
    """Tenta git mv. Retorna True se sucedeu (preservou histórico)."""
    try:
        subprocess.run(
            ["git", "mv", str(src), str(dst)],
            check=True,
            capture_output=True,
            cwd=src.parent,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def migrate_pj(pj_path: Path) -> dict[str, Any]:
    """Migra todas as notas legadas em ``pj_path/references/notes/`` pro layout α.

    Retorna report com chaves:
        migrated: list[str]            — citekeys migrados nesta execução
        already_migrated: list[str]    — citekeys já em layout α (puladas)
        warnings: list[str]            — situações inesperadas
    """
    notes_dir = pj_path / "references" / "notes"
    if not notes_dir.exists():
        return {"migrated": [], "already_migrated": [], "warnings": []}

    migrated: list[str] = []
    already_migrated: list[str] = []
    warnings: list[str] = []

    for child in sorted(notes_dir.iterdir()):
        # Layout α — pasta existe e tem _meta.md
        if child.is_dir() and (child / "_meta.md").is_file():
            already_migrated.append(child.name)
            continue
        # Layout legado — arquivo .md
        if not (child.is_file() and child.suffix == ".md"):
            continue

        citekey = child.stem
        text = child.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            warnings.append(f"{child.name}: sem frontmatter; pulado")
            continue

        frontmatter = text[: m.end()]
        body = text[m.end() :]

        body, zotero_block = _extract_zotero_block(body)
        body, callout = _extract_callout_block(body)

        # Cria pasta destino
        target_dir = notes_dir / citekey
        target_dir.mkdir(parents=True, exist_ok=True)

        # Tenta preservar histórico do arquivo principal via git mv pro _meta.md
        target_meta = target_dir / "_meta.md"
        if _git_mv(child, target_meta):
            # Após mv, sobrescreve com conteúdo limpo (sem callout/zotero)
            target_meta.write_text(frontmatter + body.strip() + "\n", encoding="utf-8")
        else:
            # Fallback: write + delete
            target_meta.write_text(frontmatter + body.strip() + "\n", encoding="utf-8")
            child.unlink()

        if callout:
            extract_text = (
                f"---\n"
                f"paper: {citekey}\n"
                f"source: prumo-paper-extract\n"
                f"---\n\n"
                f"{callout}\n"
            )
            extract_path(pj_path, citekey).write_text(extract_text, encoding="utf-8")

        if zotero_block:
            annot_text = (
                f"---\n"
                f"paper: {citekey}\n"
                f"source: prumo-zotero-annotations\n"
                f"---\n\n"
                f"{zotero_block}\n"
            )
            annotations_path(pj_path, citekey).write_text(annot_text, encoding="utf-8")

        migrated.append(citekey)

    return {
        "migrated": sorted(migrated),
        "already_migrated": sorted(already_migrated),
        "warnings": warnings,
    }
```

- [ ] **Step 4: Add CLI command in `cli.py`**

Append this command to `src/prumo_assist/domains/paper/cli.py` (after `sync_annotations_command`):

```python
@paper_app.command("migrate-layout")
def migrate_layout_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """One-shot: migra ``<key>.md`` legado pra ``<key>/_meta.md`` (+ _extract, _annotations).

    Idempotente. Preserva histórico via ``git mv`` quando o pj_* é repo git.
    """
    from prumo_assist.domains.paper import migrate as migrate_mod

    with cli_run(json_mode=json_mode) as console:
        report = migrate_mod.migrate_pj(path.resolve())
        console.success(
            f"{len(report['migrated'])} migradas, "
            f"{len(report['already_migrated'])} já estavam em layout α."
        )
        if report["warnings"]:
            for w in report["warnings"]:
                console.warn(w)
        console.emit(report)
```

- [ ] **Step 5: Re-export in `api.py`**

Edit `src/prumo_assist/domains/paper/api.py` — add to imports and `__all__`:

```python
from prumo_assist.domains.paper.migrate import migrate_pj as migrate_layout

__all__ = [
    "find",
    "lint",
    "migrate_layout",
    "set_primary",
    "sync",
    "sync_annotations",
    "sync_pdfs",
    "update_graph",
]
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/unit/paper/test_migrate.py -v`
Expected: 6 tests PASS

- [ ] **Step 7: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/paper/migrate.py src/prumo_assist/domains/paper/cli.py src/prumo_assist/domains/paper/api.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/paper/migrate.py src/prumo_assist/domains/paper/cli.py`
Expected: clean

- [ ] **Step 8: Commit**

```bash
git add src/prumo_assist/domains/paper/migrate.py src/prumo_assist/domains/paper/cli.py src/prumo_assist/domains/paper/api.py tests/unit/paper/test_migrate.py
git commit -m "feat(paper): add migrate-layout command for legacy notes"
```

---

## Task 6: Adaptar `graph`, `find`, `lint` pra varredura recursiva

**Files:**
- Modify: `src/prumo_assist/domains/paper/graph.py`
- Modify: `src/prumo_assist/domains/paper/find.py`
- Modify: `src/prumo_assist/domains/paper/lint.py`
- Modify: `tests/unit/paper/test_graph.py`
- Modify: `tests/unit/paper/test_lint.py`

- [ ] **Step 1: Read current implementations**

Run: `cat src/prumo_assist/domains/paper/graph.py src/prumo_assist/domains/paper/find.py src/prumo_assist/domains/paper/lint.py`
Note the path patterns being used (they all do `notes_dir.glob("*.md")`).

- [ ] **Step 2: Write helper for "find note metadata file"**

Add to `src/prumo_assist/core/note_paths.py`:

```python
def iter_note_meta_files(pj_path: Path) -> list[Path]:
    """Lista todos os arquivos canônicos de metadata da nota.

    - Layout α: ``<key>/_meta.md``
    - Legado (transição): ``<key>.md`` plano

    Retorna lista ordenada por citekey. Quando ambos existem pra um citekey
    (situação anômala), prefere α e ignora o legado silenciosamente.
    """
    notes_dir = pj_path / "references" / "notes"
    if not notes_dir.exists():
        return []
    found: dict[str, Path] = {}
    for child in sorted(notes_dir.iterdir()):
        if child.is_dir() and (child / "_meta.md").is_file():
            found[child.name] = child / "_meta.md"
        elif child.is_file() and child.suffix == ".md" and child.stem not in found:
            found[child.stem] = child
    return [found[k] for k in sorted(found)]


def citekey_from_meta_path(meta: Path) -> str:
    """Inverte: dado o path de metadata, devolve o citekey."""
    if meta.parent.name == "notes":
        return meta.stem  # legado <key>.md
    return meta.parent.name  # α <key>/_meta.md
```

- [ ] **Step 3: Write tests for the new helper**

Add to `tests/unit/core/test_note_paths.py`:

```python
def test_iter_note_meta_files_includes_alpha(tmp_path: Path) -> None:
    from prumo_assist.core.note_paths import iter_note_meta_files

    notes = tmp_path / "references" / "notes"
    (notes / "smith2024").mkdir(parents=True)
    (notes / "smith2024" / "_meta.md").write_text("---\nid: smith2024\n---\n")
    (notes / "doe2025").mkdir()
    (notes / "doe2025" / "_meta.md").write_text("---\nid: doe2025\n---\n")
    out = iter_note_meta_files(tmp_path)
    assert [p.parent.name for p in out] == ["doe2025", "smith2024"]


def test_iter_note_meta_files_includes_legacy_during_transition(tmp_path: Path) -> None:
    from prumo_assist.core.note_paths import citekey_from_meta_path, iter_note_meta_files

    notes = tmp_path / "references" / "notes"
    notes.mkdir(parents=True)
    (notes / "legacy_one.md").write_text("---\nid: legacy_one\n---\n")
    (notes / "alpha_one").mkdir()
    (notes / "alpha_one" / "_meta.md").write_text("---\nid: alpha_one\n---\n")
    out = iter_note_meta_files(tmp_path)
    assert len(out) == 2
    keys = {citekey_from_meta_path(p) for p in out}
    assert keys == {"alpha_one", "legacy_one"}


def test_iter_note_meta_files_prefers_alpha_when_both_exist(tmp_path: Path) -> None:
    from prumo_assist.core.note_paths import iter_note_meta_files

    notes = tmp_path / "references" / "notes"
    notes.mkdir(parents=True)
    (notes / "smith2024.md").write_text("---\nid: smith2024\n---\n")
    (notes / "smith2024").mkdir()
    (notes / "smith2024" / "_meta.md").write_text("---\nid: smith2024\n---\nALPHA\n")
    out = iter_note_meta_files(tmp_path)
    assert len(out) == 1
    assert "ALPHA" in out[0].read_text()
```

- [ ] **Step 4: Run helper tests**

Run: `uv run pytest tests/unit/core/test_note_paths.py -v`
Expected: 11 tests PASS

- [ ] **Step 5: Refactor `graph.py` to use helper**

Open `src/prumo_assist/domains/paper/graph.py`. Find each occurrence of `notes_dir.glob("*.md")` and replace with a call to `iter_note_meta_files(pj_path)`.

Example transformation in `update_graph`:

```python
# Before:
for nota in notes_dir.glob("*.md"):
    citekey = nota.stem
    # ...

# After:
from prumo_assist.core.note_paths import citekey_from_meta_path, iter_note_meta_files

for nota in iter_note_meta_files(pj_path):
    citekey = citekey_from_meta_path(nota)
    # ...
```

- [ ] **Step 6: Refactor `find.py` similarly**

In `src/prumo_assist/domains/paper/find.py`, replace `(pj_path / "references" / "notes").glob("*.md")` with `iter_note_meta_files(pj_path)`. Use `citekey_from_meta_path` to extract the citekey.

- [ ] **Step 7: Refactor `lint.py` and add new check**

In `src/prumo_assist/domains/paper/lint.py`:
1. Replace path traversals with `iter_note_meta_files`.
2. Add a new lint rule: "subdirectory in `notes/` without `_meta.md`" (sinaliza pasta órfã ou migração incompleta).

Example for the new rule:

```python
# Inside lint(pj_path):
notes_dir = pj_path / "references" / "notes"
if notes_dir.exists():
    for child in notes_dir.iterdir():
        if child.is_dir() and not (child / "_meta.md").is_file():
            warnings.append(
                f"pasta `{child.name}/` sem `_meta.md` — rode "
                f"`prumo paper migrate-layout` ou crie a nota."
            )
```

- [ ] **Step 8: Update existing tests in `test_graph.py` and `test_lint.py` to use layout α**

In `tests/unit/paper/test_graph.py`, change fixture setup from `notes/<key>.md` to `notes/<key>/_meta.md`. Same for `test_lint.py`. Concretely, look for any line that creates `notes_dir / f"{key}.md"` or similar and replace with creating the `<key>` subdirectory and `_meta.md` inside.

Run failing tests to find what needs to change:

Run: `uv run pytest tests/unit/paper/test_graph.py tests/unit/paper/test_lint.py -v`
Iterate until all pass.

- [ ] **Step 9: Add a test for the new "subdir without _meta.md" lint rule**

Append to `tests/unit/paper/test_lint.py`:

```python
def test_lint_warns_subdir_without_meta(tmp_path: Path) -> None:
    refs = tmp_path / "references"
    notes = refs / "notes"
    notes.mkdir(parents=True)
    (refs / "_references.bib").write_text("@article{a, title={X}}\n")
    (notes / "incomplete_dir").mkdir()  # pasta sem _meta.md
    report = lint(tmp_path)
    assert any("incomplete_dir" in w for w in report["warnings"])
```

- [ ] **Step 10: Run full paper test suite**

Run: `uv run pytest tests/unit/paper/ tests/unit/core/test_note_paths.py -v`
Expected: all tests PASS

- [ ] **Step 11: Lint + types**

Run: `uv run ruff check src/ tests/`
Run: `uv run --extra dev mypy src/prumo_assist tests`
Expected: clean

- [ ] **Step 12: Commit**

```bash
git add src/prumo_assist/core/note_paths.py src/prumo_assist/domains/paper/graph.py src/prumo_assist/domains/paper/find.py src/prumo_assist/domains/paper/lint.py tests/unit/core/test_note_paths.py tests/unit/paper/test_graph.py tests/unit/paper/test_lint.py
git commit -m "feat(paper): graph/find/lint walk layout α + legacy fallback"
```

---

## Task 7: Atualizar template + skills + docs

**Files:**
- Modify: `templates/pj_base/references/templates/literature_note.md`
- Modify: `skills/paper-manager/SKILL.md`
- Modify: `skills/paper-extract/SKILL.md`
- Modify: `docs/actions-by-context.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update `literature_note.md` template**

Edit `templates/pj_base/references/templates/literature_note.md` — keep YAML frontmatter and human sections, but **remove** any reference to inline callout (it's now a separate file). Update the comment at the top:

```markdown
---
# CSL-JSON subset (compatível com Pandoc, BibLib, Zotero Integration)
id: <citekey>
type: article-journal
title: ""
author:
  - { family: "", given: "" }
issued: { date-parts: [[YYYY]] }
DOI: ""
container-title: ""
URL: ""

# Curadoria deste projeto
pdf: "../../pdfs/<citekey>.pdf"   # path relativo do _meta.md (sob <key>/)
tags: []
role: supporting
status: unread
rating: null
added: YYYY-MM-DD
tldr: ""
cites: []
extracted_at: null
extracted_model: null
extracted_template_hash: null
---

> [!tldr]
> _(uma frase: o que o paper fez e resultado principal)_

## Problema

_(pergunta clínica/técnica, gap na literatura)_

## Método

_(dataset, n, modalidades, arquitetura, treino, baselines)_

## Resultados

_(métricas principais com IC; referenciar Fig/Tab com página)_

## Limitações

> [!warning]
> _(o que o paper assume, o que não testou)_

## Relevância para este projeto

_(por que entrou no acervo; o que reaproveitar)_

## Referências citadas

- [[@citekey_outro]]

## Notas

_(observações, dúvidas abertas)_
```

Notice the **`pdf:`** path changed from `"../pdfs/<citekey>.pdf"` to `"../../pdfs/<citekey>.pdf"` — `_meta.md` is one level deeper now.

- [ ] **Step 2: Update `skills/paper-manager/SKILL.md`**

Replace the "Layout esperado" section in `skills/paper-manager/SKILL.md`:

```markdown
## Layout esperado

```
pj_*/references/
├── _index.md
├── _references.bib
├── pdfs/<citekey>.pdf           # gitignored
├── templates/literature_note.md # template base (vai virar _meta.md)
├── views/papers.base
└── notes/<citekey>/             # 1 PASTA por paper (layout α)
    ├── _meta.md                 # YAML CSL-JSON + body humano
    ├── _extract.md              # callout estruturado (gerado pela skill paper-extract)
    ├── _annotations.md          # highlights do Zotero (gerado pelo prumo paper sync-annotations)
    └── note__<itemKey>__<slug>.md  # 1 child note Zotero por arquivo (PR-N2)
```

> [!info]
> Layout legado (`notes/<key>.md` plano) ainda é lido por compatibilidade durante transição. Para migrar: `prumo paper migrate-layout`.
```

In the same SKILL.md, find any occurrence of `references/notes/<citekey>.md` and replace with `references/notes/<citekey>/_meta.md`.

- [ ] **Step 3: Update `skills/paper-extract/SKILL.md`**

In `skills/paper-extract/SKILL.md`, the prompt to the subagent currently says "escreve em `references/notes/<citekey>.md`". Replace with "escreve em `references/notes/<citekey>/_extract.md` (arquivo dedicado)". Also update the validation step that checks for `references/notes/<citekey>.md` to check for `references/notes/<citekey>/_meta.md`.

- [ ] **Step 4: Update `docs/actions-by-context.md` reference**

In `docs/actions-by-context.md`, the section "Quero extrair conteúdo estruturado de um PDF" already mentions `_extract.md` (added in earlier session). Verify it still reads correctly. No change needed unless out of date.

- [ ] **Step 5: Update `CHANGELOG.md`**

Add to "Não publicado":

```markdown
### Adicionado

- **Layout α de notas**: cada paper agora vive em `references/notes/<citekey>/` com `_meta.md`, `_extract.md`, `_annotations.md` separados. Permite múltiplas child notes por paper (PR-N2 traz `note__*.md`) e melhora retrieval por chunk pequeno + metadata estável.
- **`prumo paper migrate-layout`**: comando one-shot que desmembra `<key>.md` legado em pasta α, preservando histórico via `git mv`. Idempotente.

### Modificado

- `prumo paper sync` escreve em `<key>/_meta.md` (era `<key>.md`).
- `prumo paper sync-annotations` escreve em `<key>/_annotations.md` dedicado (era bloco delimitado dentro do `<key>.md`).
- `/prumo-assist:paper-extract` escreve em `<key>/_extract.md` dedicado.
- `paper graph`, `paper find`, `paper lint` aceitam ambos layouts durante transição.
```

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest -q`
Expected: all tests PASS

Run: `uv run ruff check .`
Expected: All checks passed!

Run: `uv run --extra dev mypy src/prumo_assist tests`
Expected: clean

- [ ] **Step 7: Commit**

```bash
git add templates/pj_base/references/templates/literature_note.md skills/paper-manager/SKILL.md skills/paper-extract/SKILL.md CHANGELOG.md
git commit -m "docs(paper): update template + skills + CHANGELOG for layout α"
```

---

## Final Verification

- [ ] **All tests pass**

Run: `uv run pytest -q`
Expected: 100% PASS, count > 97 (we added new tests)

- [ ] **Lint clean**

Run: `uv run ruff check . && uv run --extra dev mypy src/prumo_assist tests`
Expected: All checks passed! · Success: no issues

- [ ] **Manifest validation**

Run: `uv run python .github/scripts/validate_manifests.py`
Expected: all valid

- [ ] **Smoke-test `migrate-layout` against `pj_piloto_ml`**

The reference project at `<pasta_do_projeto>/pj_piloto_ml` has many legacy `<key>.md` notes. Test on a copy:

```bash
cp -r <pasta_do_projeto>/pj_piloto_ml /tmp/pj_test_migrate
uv run prumo paper migrate-layout /tmp/pj_test_migrate --json | head -30
```

Inspect 1-2 migrated notes manually:
```bash
ls /tmp/pj_test_migrate/references/notes/ | head
cat /tmp/pj_test_migrate/references/notes/<some_key>/_meta.md | head -30
```

Verify: pastas existem, `_meta.md` tem YAML, `_extract.md` (se havia callout) tem callout intacto, `_annotations.md` (se havia bloco) tem o bloco intacto.

- [ ] **Bump version**

Edit `src/prumo_assist/_version.py`: `0.3.0` → `0.4.0` (MINOR — adições retrocompatíveis com warnings de transição).

Run: `uv run python .github/scripts/sync_manifest_version.py`
Expected: `Sincronizados em v0.4.0`

- [ ] **Update CHANGELOG with version + date**

Move "Não publicado" content under `## [0.4.0] - <today>` and update link footer.

- [ ] **Final commit + tag**

```bash
git add src/prumo_assist/_version.py .claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md
git commit -m "release: 0.4.0 — layout α de notas + migrate-layout"
git tag -a v0.4.0 -m "v0.4.0"
```

---

## Self-review notes

**Spec coverage** — cada item da spec endereçado:
- [x] D1 read-only granular: preservado (escrita Zotero → repo, sem write-back)
- [x] D2 layout α (`_meta`, `_extract`, `_annotations`, `note__*`): tasks 2/3/4/5 (note__*.md fica pra PR-N2)
- [x] D3 qmd único motor: preservado (não tocamos qmd)
- [x] D4 sem banco canônico: preservado (FS continua canônico)
- [x] D5 mgmeyers reposicionado: documentado nas skills (task 7)
- [x] PR-N1 plano de implementação: este documento
- [x] migrate-layout one-shot com `git mv`: task 5
- [x] flag de fallback durante transição: implementado como graceful degradation em graph/find/lint (task 6)

**Type consistency check**:
- `meta_path`, `extract_path`, `annotations_path` recebem `(pj_path, citekey)` — consistente entre tarefas.
- `apply_extraction` muda assinatura de `(nota_path, ...)` pra `(pj_path, citekey, ...)` — testes de Task 3 refletem.
- `compose_annotations_file` é nova; não há sobreposição.
- `iter_note_meta_files` retorna `list[Path]`; usado em graph/find/lint consistentemente.

**Out of scope (explicit, registered as separate work):**
- PR-N2 (`prumo paper sync-notes` para child notes Zotero)
- PR-N3 (`sync-all` orquestrador + ajustes correlatos finos)
- PR-N4 (sync com `mgmeyers Zotero Integration` config — descontinuar como fonte automática)
