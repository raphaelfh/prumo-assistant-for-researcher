---
status: implemented
verified: 2026-06-11
release: "0.61.0"
---

# `sync-notes` + `sync-all` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar `prumo paper sync-notes` (projeta cada child note do Zotero num arquivo `note__<itemKey>__<slug>.md`) e `prumo paper sync-all` (orquestra `sync` + `sync-annotations` + `sync-notes`), fechando o gap PR-N2/PR-N3 da spec `docs/superpowers/specs/2026-05-03-zotero-notes-integration-design.md` em que a skill `paper-manager` documenta `note__*.md` mas nenhum comando os gera.

**Architecture:**
- `sync-notes` reusa a infraestrutura HTTP que já existe em `zotero.py` (`check_zotero_running`, `resolve_citekey`, `fetch_children`, `split_children`, `html_to_markdown`) e os path helpers que já existem em `core/note_paths.py` (`child_note_path`, `slugify`). Não há HTTP novo — `fetch_children` já traz as child notes; `split_children` já as separa.
- Cada child note vira um arquivo dedicado com YAML estável (`paper`, `zotero_item_key`, `source`, `date_added`, `date_modified`, `tags`, `title`) + bloco delimitado `<!-- BEGIN ZOTERO --> … <!-- END ZOTERO -->`. Só o bloco é regenerado; texto humano fora dele é preservado.
- `sync-all` é um orquestrador fino que chama as três funções de domínio em sequência e agrega os reports.
- `lint` ganha **uma** regra nova: `duplicate_item_key` (mesmo `zotero_item_key` em dois `note__*.md`). A regra "pasta sem `_meta.md`" já existe (`subdir_without_meta`) e cobre o caso de child note sem `_meta.md` irmão; "nota órfã" (itemKey que sumiu do Zotero) é deliberadamente fora de escopo por não ser detectável offline. `lint.py` usa o dataclass `LintIssue` e retorna `{"ok","summary","issues"}` — não há lista `warnings`.

**Tech Stack:** Python 3.11+, Typer, pytest, ruff, mypy strict. `uv` como runner. Mesmo stack do prumo-assist.

---

## File Structure

| Caminho | Ação | Responsabilidade |
|---|---|---|
| `src/prumo_assist/domains/paper/zotero.py` | **Modify** | adicionar `render_child_note`, `compose_child_note_file`, `note_title_from_html`, `sync_notes` |
| `src/prumo_assist/domains/paper/sync_all.py` | **Create** | orquestrador `sync_all` |
| `src/prumo_assist/domains/paper/cli.py` | **Modify** | comandos `sync-notes` e `sync-all` |
| `src/prumo_assist/domains/paper/api.py` | **Modify** | re-export `sync_notes`, `sync_all` |
| `src/prumo_assist/domains/paper/lint.py` | **Modify** | regra nova `duplicate_item_key` (via `LintIssue`) |
| `tests/unit/paper/test_zotero_notes.py` | **Create** | tests de `render_child_note`, `compose_child_note_file`, `note_title_from_html`, `sync_notes` |
| `tests/unit/paper/test_sync_all.py` | **Create** | tests do orquestrador |
| `tests/unit/paper/test_lint.py` | **Modify** | tests das regras novas |
| `tests/unit/paper/test_cli.py` | **Modify** | integration test do `sync-notes` + `sync-all` |
| `skills/paper-manager/SKILL.md` | **Modify** | documentar as duas operações novas |

---

## Task 1: `note_title_from_html` — derivar título e slug da child note

**Files:**
- Modify: `src/prumo_assist/domains/paper/zotero.py` (adicionar função após `html_to_markdown`, ~linha 173)
- Create: `tests/unit/paper/test_zotero_notes.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/paper/test_zotero_notes.py`:

```python
"""Tests para sync-notes: child notes do Zotero → note__<itemKey>__<slug>.md."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from prumo_assist.core.note_paths import child_note_path, meta_path
from prumo_assist.domains.paper.zotero import (
    compose_child_note_file,
    note_title_from_html,
    render_child_note,
    sync_notes,
)


def test_note_title_from_html_uses_first_heading() -> None:
    html = "<h1>Ideias da Introdução</h1><p>corpo</p>"
    assert note_title_from_html(html) == "Ideias da Introdução"


def test_note_title_from_html_uses_first_line_when_no_heading() -> None:
    html = "<p>Crítica metodológica importante</p><p>resto</p>"
    assert note_title_from_html(html) == "Crítica metodológica importante"


def test_note_title_from_html_empty_is_untitled() -> None:
    assert note_title_from_html("") == "(sem título)"
    assert note_title_from_html("<p></p>") == "(sem título)"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/paper/test_zotero_notes.py::test_note_title_from_html_uses_first_heading -v`
Expected: FAIL with `ImportError: cannot import name 'note_title_from_html'`

- [ ] **Step 3: Implement `note_title_from_html`**

In `src/prumo_assist/domains/paper/zotero.py`, add after `html_to_markdown` (after line 173):

```python
def note_title_from_html(html: str) -> str:
    """Deriva um título legível da child note: primeiro heading ou primeira linha.

    Retorna ``"(sem título)"`` se vazia. Usado pro YAML ``title`` e pro slug.
    """
    md = html_to_markdown(html)
    for line in md.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped
    return "(sem título)"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/paper/test_zotero_notes.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/paper/zotero.py tests/unit/paper/test_zotero_notes.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/paper/zotero.py`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/domains/paper/zotero.py tests/unit/paper/test_zotero_notes.py
git commit -m "feat(paper): note_title_from_html helper for sync-notes"
```

---

## Task 2: `render_child_note` + `compose_child_note_file`

**Files:**
- Modify: `src/prumo_assist/domains/paper/zotero.py` (adicionar após `note_title_from_html`)
- Modify: `tests/unit/paper/test_zotero_notes.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/paper/test_zotero_notes.py`:

```python
def _sample_note() -> dict[str, object]:
    return {
        "itemType": "note",
        "key": "ABCD1234",
        "note": "<h1>Ideias da Introdução</h1><p>risk prediction ajuda</p>",
        "dateAdded": "2026-04-30T14:23:00Z",
        "dateModified": "2026-05-02T09:11:00Z",
        "tags": [{"tag": "hipoteses"}, {"tag": "datasets"}],
    }


def test_render_child_note_has_begin_end_block() -> None:
    out = render_child_note(_sample_note())
    assert out.startswith("<!-- BEGIN ZOTERO -->")
    assert out.endswith("<!-- END ZOTERO -->")
    assert "risk prediction ajuda" in out


def test_compose_child_note_file_has_stable_yaml() -> None:
    text = compose_child_note_file("smith2024", _sample_note())
    assert text.startswith("---\n")
    assert "paper: smith2024" in text
    assert "zotero_item_key: ABCD1234" in text
    assert "source: zotero-child-note" in text
    assert "date_added: '2026-04-30T14:23:00Z'" in text
    assert "date_modified: '2026-05-02T09:11:00Z'" in text
    assert "title: Ideias da Introdução" in text
    assert "hipoteses" in text and "datasets" in text
    assert "<!-- BEGIN ZOTERO -->" in text
    assert "<!-- END ZOTERO -->" in text


def test_compose_child_note_file_handles_missing_optional_fields() -> None:
    note = {"itemType": "note", "key": "EFGH5678", "note": "<p>corpo</p>"}
    text = compose_child_note_file("doe2025", note)
    assert "zotero_item_key: EFGH5678" in text
    assert "date_added: ''" in text
    assert "tags: []" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/paper/test_zotero_notes.py -v`
Expected: FAIL — `render_child_note` / `compose_child_note_file` not defined.

- [ ] **Step 3: Implement both functions**

In `src/prumo_assist/domains/paper/zotero.py`, add a constant near the other markers (after `END` on line 28):

```python
NOTE_BEGIN = "<!-- BEGIN ZOTERO -->"
NOTE_END = "<!-- END ZOTERO -->"
```

Then add after `note_title_from_html`:

```python
def render_child_note(note: dict[str, Any]) -> str:
    """Conteúdo delimitado de uma child note: ``BEGIN ZOTERO`` … ``END ZOTERO``."""
    body = html_to_markdown(note.get("note") or "")
    return f"{NOTE_BEGIN}\n\n{body or '_(vazia)_'}\n\n{NOTE_END}"


def _note_tags(note: dict[str, Any]) -> list[str]:
    """Extrai tags do formato Zotero ``[{'tag': 'x'}, ...]`` → ``['x', ...]``."""
    raw = note.get("tags") or []
    out: list[str] = []
    for t in raw:
        if isinstance(t, dict) and t.get("tag"):
            out.append(str(t["tag"]))
    return out


def compose_child_note_file(citekey: str, note: dict[str, Any]) -> str:
    """Conteúdo completo de ``note__<itemKey>__<slug>.md``: YAML estável + bloco.

    O contrato de YAML (``paper``, ``zotero_item_key``, ``source``,
    ``date_added``, ``date_modified``, ``tags``, ``title``) é consumido pelas
    skills ``write-*`` — não remover nem renomear campos sem coordenar.
    """
    item_key = str(note.get("key") or "")
    title = note_title_from_html(note.get("note") or "")
    date_added = str(note.get("dateAdded") or "")
    date_modified = str(note.get("dateModified") or "")
    tags = _note_tags(note)
    tags_yaml = "[]" if not tags else "[" + ", ".join(tags) + "]"
    fm = (
        f"---\n"
        f"paper: {citekey}\n"
        f"zotero_item_key: {item_key}\n"
        f"source: zotero-child-note\n"
        f"date_added: '{date_added}'\n"
        f"date_modified: '{date_modified}'\n"
        f"tags: {tags_yaml}\n"
        f"title: {title}\n"
        f"---\n\n"
    )
    return fm + render_child_note(note) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/paper/test_zotero_notes.py -v`
Expected: 6 tests PASS

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/paper/zotero.py tests/unit/paper/test_zotero_notes.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/paper/zotero.py`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/domains/paper/zotero.py tests/unit/paper/test_zotero_notes.py
git commit -m "feat(paper): render_child_note + compose_child_note_file"
```

---

## Task 3: `sync_notes` — orquestra fetch → render → write por citekey

**Files:**
- Modify: `src/prumo_assist/domains/paper/zotero.py` (adicionar `sync_notes` após `sync_annotations`)
- Modify: `tests/unit/paper/test_zotero_notes.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/paper/test_zotero_notes.py`:

```python
def _bootstrap_pj(tmp_path: Path, citekey: str = "smith2024") -> Path:
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "_references.bib").write_text(f"@article{{{citekey}, title={{X}}}}\n")
    meta_p = meta_path(tmp_path, citekey)
    meta_p.parent.mkdir(parents=True, exist_ok=True)
    meta_p.write_text(f"---\nid: {citekey}\n---\n\nbody\n")
    return tmp_path


def test_sync_notes_writes_one_file_per_child_note(tmp_path: Path) -> None:
    pj = _bootstrap_pj(tmp_path)
    children = [_sample_note()]
    with (
        patch("prumo_assist.domains.paper.zotero.check_zotero_running", return_value=True),
        patch("prumo_assist.domains.paper.zotero.resolve_citekey", return_value=(1, "PARENT01")),
        patch("prumo_assist.domains.paper.zotero.fetch_children", return_value=children),
    ):
        report = sync_notes(pj)
    out = child_note_path(pj, "smith2024", "ABCD1234", "ideias-da-introducao")
    assert out.exists()
    assert "risk prediction ajuda" in out.read_text()
    assert report["inserted"] == 1


def test_sync_notes_idempotent_second_run(tmp_path: Path) -> None:
    pj = _bootstrap_pj(tmp_path)
    children = [_sample_note()]
    with (
        patch("prumo_assist.domains.paper.zotero.check_zotero_running", return_value=True),
        patch("prumo_assist.domains.paper.zotero.resolve_citekey", return_value=(1, "PARENT01")),
        patch("prumo_assist.domains.paper.zotero.fetch_children", return_value=children),
    ):
        sync_notes(pj)
        report = sync_notes(pj)
    assert report["inserted"] == 0
    assert report["unchanged"] == 1


def test_sync_notes_preserves_human_text_outside_block(tmp_path: Path) -> None:
    pj = _bootstrap_pj(tmp_path)
    children = [_sample_note()]
    with (
        patch("prumo_assist.domains.paper.zotero.check_zotero_running", return_value=True),
        patch("prumo_assist.domains.paper.zotero.resolve_citekey", return_value=(1, "PARENT01")),
        patch("prumo_assist.domains.paper.zotero.fetch_children", return_value=children),
    ):
        sync_notes(pj)
        out = child_note_path(pj, "smith2024", "ABCD1234", "ideias-da-introducao")
        original = out.read_text()
        out.write_text(original + "\n## Minha anotação humana\n\ntexto meu\n")
        updated = [dict(_sample_note(), note="<h1>Ideias da Introdução</h1><p>NOVO corpo</p>")]
        with patch("prumo_assist.domains.paper.zotero.fetch_children", return_value=updated):
            sync_notes(pj)
    final = out.read_text()
    assert "NOVO corpo" in final
    assert "Minha anotação humana" in final  # texto humano preservado


def test_sync_notes_raises_when_zotero_offline(tmp_path: Path) -> None:
    import pytest

    pj = _bootstrap_pj(tmp_path)
    with patch("prumo_assist.domains.paper.zotero.check_zotero_running", return_value=False):
        with pytest.raises(ConnectionError):
            sync_notes(pj)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/paper/test_zotero_notes.py -v`
Expected: FAIL — `sync_notes` not defined.

- [ ] **Step 3: Implement `sync_notes`**

In `src/prumo_assist/domains/paper/zotero.py`, add after `sync_annotations` (after line 319). It mirrors `sync_annotations`'s prerequisite checks and per-citekey loop, but writes one file per note and replaces only the delimited block:

```python
def _replace_note_block(existing: str, new_file_text: str) -> str:
    """Regenera YAML + bloco ``BEGIN/END ZOTERO``, preservando texto humano após o END.

    ``new_file_text`` é o output de ``compose_child_note_file`` (YAML + bloco).
    Qualquer conteúdo no arquivo existente após ``NOTE_END`` é mantido.
    """
    idx = existing.find(NOTE_END)
    if idx == -1:
        return new_file_text
    human_tail = existing[idx + len(NOTE_END) :]
    return new_file_text.rstrip("\n") + human_tail


def sync_notes(pj_path: Path) -> dict[str, Any]:
    """Sincroniza child notes do Zotero pra ``<key>/note__<itemKey>__<slug>.md``.

    Read-only Zotero → repo. Um arquivo por child note. Só o bloco
    ``BEGIN/END ZOTERO`` é regenerado; texto humano após o END é preservado.
    Pré-requisitos: Zotero 9 aberto + Better BibTeX. Falha cedo se faltar.
    """
    from prumo_assist.core.note_paths import child_note_path, meta_path, slugify

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
    errors: list[tuple[str, str]] = []

    for citekey in citekeys:
        if not meta_path(pj_path, citekey).exists():
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

        _annots, notes_lst = split_children(children)
        for note in notes_lst:
            note_key = str(note.get("key") or "")
            if not note_key:
                continue
            slug = slugify(note_title_from_html(note.get("note") or ""))
            target = child_note_path(pj_path, citekey, note_key, slug)
            new_text = compose_child_note_file(citekey, note)
            if target.exists():
                old = target.read_text(encoding="utf-8")
                merged = _replace_note_block(old, new_text)
                if old == merged:
                    unchanged += 1
                    continue
                target.write_text(merged, encoding="utf-8")
                updated += 1
            else:
                target.write_text(new_text, encoding="utf-8")
                inserted += 1

    return {
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "no_meta": no_meta,
        "no_resolve": no_resolve,
        "errors": errors,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/paper/test_zotero_notes.py -v`
Expected: 10 tests PASS

- [ ] **Step 5: Run the whole zotero + paper suite (no regressions)**

Run: `uv run pytest tests/unit/paper/ -v`
Expected: all PASS (existing `test_zotero.py` untouched)

- [ ] **Step 6: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/paper/zotero.py tests/unit/paper/test_zotero_notes.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/paper/zotero.py`
Expected: clean

- [ ] **Step 7: Commit**

```bash
git add src/prumo_assist/domains/paper/zotero.py tests/unit/paper/test_zotero_notes.py
git commit -m "feat(paper): sync_notes writes one file per Zotero child note"
```

---

## Task 4: `sync_all` orquestrador

**Files:**
- Create: `src/prumo_assist/domains/paper/sync_all.py`
- Create: `tests/unit/paper/test_sync_all.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/paper/test_sync_all.py`:

```python
"""Tests do orquestrador prumo paper sync-all."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from prumo_assist.domains.paper.sync_all import sync_all


def _bootstrap(tmp_path: Path) -> Path:
    refs = tmp_path / "references"
    (refs / "notes").mkdir(parents=True)
    (refs / "_references.bib").write_text("@article{smith2024, title={X}}\n")
    return tmp_path


def test_sync_all_runs_three_phases(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    with (
        patch(
            "prumo_assist.domains.paper.sync_all.sync",
            return_value={"created": 1, "updated": 0, "orphans": []},
        ) as m_sync,
        patch(
            "prumo_assist.domains.paper.sync_all.sync_annotations",
            return_value={"inserted": 2, "updated": 0, "unchanged": 0,
                          "no_meta": [], "no_resolve": [], "no_children": [], "errors": []},
        ) as m_annot,
        patch(
            "prumo_assist.domains.paper.sync_all.sync_notes",
            return_value={"inserted": 3, "updated": 0, "unchanged": 0,
                          "no_meta": [], "no_resolve": [], "errors": []},
        ) as m_notes,
    ):
        report = sync_all(pj)
    m_sync.assert_called_once_with(pj)
    m_annot.assert_called_once_with(pj)
    m_notes.assert_called_once_with(pj)
    assert report["sync"]["created"] == 1
    assert report["annotations"]["inserted"] == 2
    assert report["notes"]["inserted"] == 3


def test_sync_all_reports_zotero_offline_without_crashing(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    with (
        patch(
            "prumo_assist.domains.paper.sync_all.sync",
            return_value={"created": 1, "updated": 0, "orphans": []},
        ),
        patch(
            "prumo_assist.domains.paper.sync_all.sync_annotations",
            side_effect=ConnectionError("Zotero offline"),
        ),
        patch(
            "prumo_assist.domains.paper.sync_all.sync_notes",
            side_effect=ConnectionError("Zotero offline"),
        ),
    ):
        report = sync_all(pj)
    assert report["sync"]["created"] == 1
    assert report["annotations"] is None
    assert report["notes"] is None
    assert any("Zotero offline" in w for w in report["warnings"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/paper/test_sync_all.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prumo_assist.domains.paper.sync_all'`

- [ ] **Step 3: Implement `sync_all.py`**

Create `src/prumo_assist/domains/paper/sync_all.py`:

```python
"""Orquestrador ``prumo paper sync-all``: sync + sync-annotations + sync-notes.

``sync`` é offline (lê o ``.bib``). ``sync-annotations`` e ``sync-notes`` exigem
Zotero rodando — se ele estiver offline, capturamos a ``ConnectionError`` e
seguimos, reportando como warning. Assim ``sync-all`` sempre atualiza o ``_meta.md``
mesmo sem o Zotero aberto.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from prumo_assist.domains.paper.sync import sync
from prumo_assist.domains.paper.zotero import sync_annotations, sync_notes


def sync_all(pj_path: Path) -> dict[str, Any]:
    """Roda as três fases em sequência. Retorna report agregado.

    Chaves: ``sync`` (sempre dict), ``annotations`` (dict ou ``None`` se Zotero
    offline), ``notes`` (idem), ``warnings`` (lista de strings).
    """
    warnings: list[str] = []

    sync_report = sync(pj_path)

    annotations_report: dict[str, Any] | None
    try:
        annotations_report = sync_annotations(pj_path)
    except (ConnectionError, FileNotFoundError) as exc:
        annotations_report = None
        warnings.append(f"sync-annotations pulado: {exc}")

    notes_report: dict[str, Any] | None
    try:
        notes_report = sync_notes(pj_path)
    except (ConnectionError, FileNotFoundError) as exc:
        notes_report = None
        warnings.append(f"sync-notes pulado: {exc}")

    return {
        "sync": sync_report,
        "annotations": annotations_report,
        "notes": notes_report,
        "warnings": warnings,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/paper/test_sync_all.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/paper/sync_all.py tests/unit/paper/test_sync_all.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/paper/sync_all.py`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/domains/paper/sync_all.py tests/unit/paper/test_sync_all.py
git commit -m "feat(paper): sync_all orchestrator (sync + annotations + notes)"
```

---

## Task 5: CLI commands `sync-notes` e `sync-all`

**Files:**
- Modify: `src/prumo_assist/domains/paper/cli.py` (importar `sync_all`; adicionar 2 comandos após `sync_annotations_command`, antes de `migrate_layout_command`)
- Modify: `tests/unit/paper/test_cli.py` (integration tests)

- [ ] **Step 1: Write the failing integration tests**

First inspect the existing helpers in the test file so the new tests match its conventions:

Run: `sed -n '1,40p' tests/unit/paper/test_cli.py`

Then append two tests to `tests/unit/paper/test_cli.py` (use the same `runner`/`app` imports already at the top of that file; if a `_bootstrap_project` helper exists, reuse it — otherwise inline the minimal project as below):

```python
def test_paper_sync_notes_cli_writes_files(tmp_path: Path) -> None:
    from unittest.mock import patch

    pj = tmp_path / "pj_x"
    refs = pj / "references"
    (refs / "notes" / "smith2024").mkdir(parents=True)
    (refs / "_references.bib").write_text("@article{smith2024, title={X}}\n")
    (refs / "notes" / "smith2024" / "_meta.md").write_text("---\nid: smith2024\n---\n\nbody\n")

    note = {
        "itemType": "note",
        "key": "ABCD1234",
        "note": "<h1>Ideia</h1><p>corpo</p>",
        "dateAdded": "2026-04-30T14:23:00Z",
        "dateModified": "2026-05-02T09:11:00Z",
        "tags": [],
    }
    with (
        patch("prumo_assist.domains.paper.zotero.check_zotero_running", return_value=True),
        patch("prumo_assist.domains.paper.zotero.resolve_citekey", return_value=(1, "P1")),
        patch("prumo_assist.domains.paper.zotero.fetch_children", return_value=[note]),
    ):
        result = runner.invoke(app, ["paper", "sync-notes", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    assert (refs / "notes" / "smith2024" / "note__ABCD1234__ideia.md").is_file()


def test_paper_sync_all_cli_runs_offline_sync(tmp_path: Path) -> None:
    from unittest.mock import patch

    pj = tmp_path / "pj_y"
    refs = pj / "references"
    (refs / "notes").mkdir(parents=True)
    (refs / "_references.bib").write_text("@article{smith2024, title={X}}\n")

    with (
        patch("prumo_assist.domains.paper.zotero.check_zotero_running", return_value=False),
    ):
        result = runner.invoke(app, ["paper", "sync-all", str(pj), "--json"])
    # sync (offline) succeeds; annotations/notes skipped with warnings → exit 0
    assert result.exit_code == 0, result.output
    assert (refs / "notes" / "smith2024" / "_meta.md").is_file()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/paper/test_cli.py::test_paper_sync_notes_cli_writes_files tests/unit/paper/test_cli.py::test_paper_sync_all_cli_runs_offline_sync -v`
Expected: FAIL — `No such command 'sync-notes'` / `'sync-all'`.

- [ ] **Step 3: Add the import**

In `src/prumo_assist/domains/paper/cli.py`, line 15, extend the domain import to include `sync_all`:

```python
from prumo_assist.domains.paper import find, graph, lint, migrate, pdfs, sync, zotero
from prumo_assist.domains.paper.sync_all import sync_all as _sync_all
```

- [ ] **Step 4: Add the two commands**

In `src/prumo_assist/domains/paper/cli.py`, insert after `sync_annotations_command` (after line 134) and before `migrate_layout_command`:

```python
@paper_app.command("sync-notes")
def sync_notes_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Projeta cada child note do Zotero em ``<key>/note__<itemKey>__<slug>.md``.

    Read-only Zotero → repo. Requer Zotero 9 aberto + Better BibTeX
    (API local em ``http://localhost:23119``)."""
    with cli_run(
        json_mode=json_mode,
        catches=(FileNotFoundError, ConnectionError),
        exit_code=2,
    ) as console:
        report = zotero.sync_notes(path.resolve())
        console.success(
            f"{report['inserted']} inseridas, {report['updated']} atualizadas, "
            f"{report['unchanged']} já em dia."
        )
        console.emit(report)


@paper_app.command("sync-all")
def sync_all_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Orquestra ``sync`` + ``sync-annotations`` + ``sync-notes`` numa tacada.

    ``sync`` roda offline (lê o ``.bib``). As fases que precisam do Zotero são
    puladas com aviso se ele estiver fechado — o comando não falha por isso."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError,)) as console:
        report = _sync_all(path.resolve())
        s = report["sync"]
        console.success(
            f"meta: {s['created']} novas / {s['updated']} atualizadas."
        )
        if report["annotations"] is not None:
            a = report["annotations"]
            console.info(f"  annotations: {a['inserted']} novas / {a['updated']} atualizadas.")
        if report["notes"] is not None:
            n = report["notes"]
            console.info(f"  notes: {n['inserted']} novas / {n['updated']} atualizadas.")
        for w in report["warnings"]:
            console.warn(w)
        console.emit(report)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/paper/test_cli.py -v`
Expected: the two new tests PASS (and existing CLI tests still PASS)

- [ ] **Step 6: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/paper/cli.py tests/unit/paper/test_cli.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/paper/cli.py`
Expected: clean

- [ ] **Step 7: Commit**

```bash
git add src/prumo_assist/domains/paper/cli.py tests/unit/paper/test_cli.py
git commit -m "feat(paper): add sync-notes and sync-all CLI commands"
```

---

## Task 6: Re-export `sync_notes` + `sync_all` na API pública

**Files:**
- Modify: `src/prumo_assist/domains/paper/api.py`
- Modify: `tests/unit/paper/test_zotero_notes.py` (smoke test do re-export)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/paper/test_zotero_notes.py`:

```python
def test_api_reexports_sync_notes_and_sync_all() -> None:
    from prumo_assist.domains.paper import api

    assert hasattr(api, "sync_notes")
    assert hasattr(api, "sync_all")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/paper/test_zotero_notes.py::test_api_reexports_sync_notes_and_sync_all -v`
Expected: FAIL with `AssertionError`

- [ ] **Step 3: Update `api.py`**

Edit `src/prumo_assist/domains/paper/api.py` — add the two imports and extend `__all__`. The full file becomes:

```python
"""Python API pra ``paper`` — gateway pra notebooks.

Re-exports puros dos módulos de domínio. Mantém superfície estável (SemVer)
sem boilerplate de wrappers passthrough::

    from prumo_assist import api
    api.paper.sync(pj_path)
    api.paper.find(pj_path, "risk prediction")
"""

from __future__ import annotations

from prumo_assist.domains.paper.find import fuzzy_search as find
from prumo_assist.domains.paper.graph import update_graph
from prumo_assist.domains.paper.lint import lint, set_primary
from prumo_assist.domains.paper.migrate import migrate_pj as migrate_layout
from prumo_assist.domains.paper.pdfs import sync_pdfs
from prumo_assist.domains.paper.sync import sync
from prumo_assist.domains.paper.sync_all import sync_all
from prumo_assist.domains.paper.zotero import sync_annotations, sync_notes

__all__ = [
    "find",
    "lint",
    "migrate_layout",
    "set_primary",
    "sync",
    "sync_all",
    "sync_annotations",
    "sync_notes",
    "sync_pdfs",
    "update_graph",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/paper/test_zotero_notes.py::test_api_reexports_sync_notes_and_sync_all -v`
Expected: PASS

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/paper/api.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/paper/api.py`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/domains/paper/api.py tests/unit/paper/test_zotero_notes.py
git commit -m "feat(paper): re-export sync_notes and sync_all in api"
```

---

## Task 7: Regra de lint para itemKey duplicado em child notes

> **Important — read first.** `lint.py` already returns a `LintIssue`-based report
> with shape `{"ok": bool, "summary": {...}, "issues": [list of dicts]}` — each
> issue dict has keys `severity` / `code` / `message` / `citekey`. There is **no**
> `report["warnings"]` list and **no** `_read_yaml_block` helper — YAML is read via
> `read_nota_yaml(path)` (imported from `prumo_assist.domains.paper.sync`). The
> "child note without `_meta.md` sibling" case is **already covered** by the
> existing rule #6 `subdir_without_meta` (a folder with a `note__*.md` but no
> `_meta.md` is a subdir without `_meta.md`), so the only genuinely new rule here
> is **duplicate `itemKey`** across `note__*.md` files. "Orphan child note" (note
> whose `itemKey` vanished from Zotero) is deliberately out of scope — it can't be
> checked offline.

**Files:**
- Modify: `src/prumo_assist/domains/paper/lint.py` (add rule #7: duplicate itemKey)
- Modify: `tests/unit/paper/test_lint.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/paper/test_lint.py` (the file already imports `lint`; confirm with `head -20 tests/unit/paper/test_lint.py`). The assertion reads `report["issues"]` (a list of dicts), matching the real report shape:

```python
def test_lint_flags_duplicate_item_key(tmp_path: Path) -> None:
    refs = tmp_path / "references"
    notes = refs / "notes" / "smith2024"
    notes.mkdir(parents=True)
    (refs / "_references.bib").write_text("@article{smith2024, title={X}}\n")
    (notes / "_meta.md").write_text("---\nid: smith2024\n---\n\nbody\n")
    (notes / "note__ABCD1234__um.md").write_text(
        "---\npaper: smith2024\nzotero_item_key: ABCD1234\n---\n\nA\n"
    )
    (notes / "note__ABCD1234__dois.md").write_text(
        "---\npaper: smith2024\nzotero_item_key: ABCD1234\n---\n\nB\n"
    )
    report = lint(tmp_path)
    dup = [i for i in report["issues"] if i["code"] == "duplicate_item_key"]
    assert len(dup) >= 1
    assert "ABCD1234" in dup[0]["message"]


def test_lint_no_duplicate_when_item_keys_distinct(tmp_path: Path) -> None:
    refs = tmp_path / "references"
    notes = refs / "notes" / "smith2024"
    notes.mkdir(parents=True)
    (refs / "_references.bib").write_text("@article{smith2024, title={X}}\n")
    (notes / "_meta.md").write_text("---\nid: smith2024\n---\n\nbody\n")
    (notes / "note__ABCD1234__um.md").write_text(
        "---\npaper: smith2024\nzotero_item_key: ABCD1234\n---\n\nA\n"
    )
    (notes / "note__EFGH5678__dois.md").write_text(
        "---\npaper: smith2024\nzotero_item_key: EFGH5678\n---\n\nB\n"
    )
    report = lint(tmp_path)
    assert not [i for i in report["issues"] if i["code"] == "duplicate_item_key"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/paper/test_lint.py::test_lint_flags_duplicate_item_key tests/unit/paper/test_lint.py::test_lint_no_duplicate_when_item_keys_distinct -v`
Expected: FAIL — `test_lint_flags_duplicate_item_key` finds no issue with code `duplicate_item_key`.

- [ ] **Step 3: Add rule #7 to `lint()`**

In `src/prumo_assist/domains/paper/lint.py`, inside `lint()`, after the existing rule #6 block (`subdir_without_meta`, ends at line 134) and before `return _report(issues)` (line 136), insert. This uses the real `LintIssue` dataclass and `read_nota_yaml` (both already in scope in this module):

```python
    # 7. itemKey duplicado entre child notes (mesmo note importada duas vezes)
    if notes_dir.exists():
        seen_item_keys: dict[str, str] = {}
        for note_file in sorted(notes_dir.glob("*/note__*.md")):
            data = read_nota_yaml(note_file)
            item_key = str(data.get("zotero_item_key") or "")
            if not item_key:
                continue
            if item_key in seen_item_keys:
                issues.append(
                    LintIssue(
                        "warning",
                        "duplicate_item_key",
                        f"itemKey {item_key} duplicado: {seen_item_keys[item_key]} "
                        f"e {note_file.name}",
                        citekey=note_file.parent.name,
                    )
                )
            else:
                seen_item_keys[item_key] = note_file.name
```

Note: `read_nota_yaml` is already imported at the top of `lint.py` (`from prumo_assist.domains.paper.sync import read_nota_yaml`). No new import needed. Add a one-line mention of the new rule to the module docstring's bullet list (after the `subdir_without_meta` line, ~line 10):

```python
- duplicate_item_key — duas child notes (`note__*.md`) com o mesmo `zotero_item_key`.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/paper/test_lint.py -v`
Expected: all lint tests PASS (existing + 2 new)

- [ ] **Step 5: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/paper/lint.py tests/unit/paper/test_lint.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/paper/lint.py`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/domains/paper/lint.py tests/unit/paper/test_lint.py
git commit -m "feat(paper): lint flags duplicate itemKey across child notes"
```

---

## Task 8: Documentar `sync-notes` e `sync-all` na skill `paper-manager`

**Files:**
- Modify: `skills/paper-manager/SKILL.md`

- [ ] **Step 1: Update the `argument-hint` and `when_to_use`**

In `skills/paper-manager/SKILL.md`, replace line 9 (`argument-hint:`) with:

```
argument-hint: "[sync | sync-annotations | sync-notes | sync-all | update-cites | set-primary <citekey> | list | graph <citekey> | sync-bib | find <query>]"
```

And extend `when_to_use` (lines 4-8) to include the new triggers — replace the block with:

```yaml
when_to_use: |
  Quando o usuário pedir para sincronizar bibliografia, importar anotações
  ou child notes do Zotero, atualizar grafo, marcar paper principal, listar
  papers, "encontrar paper sobre Y", "quem cita Z", auditar consistência, ou
  mencionar "bibliografia", "paper principal", "referências do projeto",
  "minhas notas do Zotero".
```

- [ ] **Step 2: Add the two operations after the `sync` section**

In `skills/paper-manager/SKILL.md`, after the `### 1. sync` section (after line 86) and before `### 2. update-cites`, insert:

````markdown
### 1b. `sync-annotations`

Importa highlights + comentários do PDF do Zotero pra `references/notes/<key>/_annotations.md` (arquivo dedicado). Read-only Zotero → repo.

```bash
prumo paper sync-annotations <pj_path_absoluto>
```

Requer **Zotero 9 aberto** + Better BibTeX instalado (API local em `http://localhost:23119`). Se o Zotero estiver fechado, o comando falha com mensagem clara (exit code 2).

### 1c. `sync-notes`

Projeta cada **child note** do Zotero (rascunhos de leitura: "ideias da intro", "crítica metodológica") num arquivo próprio `references/notes/<key>/note__<itemKey>__<slug>.md`. Um arquivo por nota; identificador estável é o `itemKey` do Zotero.

```bash
prumo paper sync-notes <pj_path_absoluto>
```

Read-only Zotero → repo. Edição da nota acontece **no Zotero**; o repo é espelho navegável. Texto humano escrito **após** o bloco `<!-- END ZOTERO -->` é preservado entre syncs. Requer Zotero aberto (mesmo pré-requisito do `sync-annotations`).

### 1d. `sync-all`

Atalho ergonômico: roda `sync` + `sync-annotations` + `sync-notes` em sequência.

```bash
prumo paper sync-all <pj_path_absoluto>
```

`sync` roda offline (lê o `.bib`). As fases que precisam do Zotero são **puladas com aviso** se ele estiver fechado — o comando não falha por isso. Use este como o comando padrão pós-leitura.
````

- [ ] **Step 2b: Fix the stale layout comment**

In `skills/paper-manager/SKILL.md` line 40, the layout block already mentions `note__<itemKey>__<slug>.md` with a "(PR-N2)" marker. Replace `(PR-N2)` with `(gerado pelo prumo paper sync-notes)`:

```
    └── note__<itemKey>__<slug>.md  # 1 child note Zotero por arquivo (gerado pelo prumo paper sync-notes)
```

- [ ] **Step 3: Verify the skill still parses**

Run: `uv run prumo skills --json`
Expected: JSON output lists `paper-manager` without errors (the SKILL.md frontmatter is valid YAML).

- [ ] **Step 4: Commit**

```bash
git add skills/paper-manager/SKILL.md
git commit -m "docs(skill): document sync-annotations, sync-notes, sync-all in paper-manager"
```

---

## Task 9: Suíte completa + sanity manual

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite**

Run: `uv run pytest -q`
Expected: all tests PASS (no regressions across `tests/unit/`)

- [ ] **Step 2: Lint + type-check the whole tree**

Run: `uv run ruff check src tests`
Run: `uv run --extra dev mypy src tests`
Expected: both clean

- [ ] **Step 3: Smoke-test the CLI help surfaces the new commands**

Run: `uv run prumo paper --help`
Expected: `sync-notes` and `sync-all` appear in the command list.

- [ ] **Step 4: Final commit (if any doc/changelog tweak)**

Add a CHANGELOG entry under the unreleased section noting `sync-notes` + `sync-all`, then:

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): sync-notes + sync-all"
```

---

## Self-Review notes (for the implementer)

- **Spec coverage:** This plan implements PR-N2 (`sync-notes`) and PR-N3 (`sync-all` + lint awareness of child notes) from `2026-05-03-zotero-notes-integration-design.md §"Plano de implementação"`. The YAML contract (`paper`, `zotero_item_key`, `source`, `date_added`, `date_modified`, `tags`, `title`) matches §"Anatomia de `<citekey>/`" exactly — do not rename fields (the `write-*` skills read them).
- **Out of scope (deliberate, per spec §"Fora do escopo"):** standalone notes (`itemType: note` without parent), write-back to Zotero, orphan *deletion* (we only warn). `graph`/`find` recursive scanning already landed in PR-N1 (`iter_note_meta_files` exists) — not re-touched here.
- **Type consistency:** `sync_notes` returns the same report shape as `sync_annotations` minus `no_children` (notes don't have that failure mode). `sync_all` wraps reports under keys `sync`/`annotations`/`notes`/`warnings`.
