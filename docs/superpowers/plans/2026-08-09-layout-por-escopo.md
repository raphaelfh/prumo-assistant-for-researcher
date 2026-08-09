# Layout por escopo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mover a bibliografia para `docs/references/`, enxugar o `pj_base` a um núcleo universal, e fazer a escrita morar sempre num escopo `docs/studies/<slug>/`.

**Architecture:** Um módulo novo (`core/pj_layout.py`) passa a ser a autoridade única de caminho, com dois resolvedores distintos — `find_pj_root` (sentinela `.claude/pj_config.toml`) e `find_scope_root` (posição: filho direto de `docs/studies/`). Todos os literais de caminho em `domains/` passam a chamar esse módulo. O lint vira por escopo. Nenhuma convivência de layouts: layout legado falha com mensagem que convida à adequação agêntica.

**Tech Stack:** Python 3.13, Typer, Pydantic, pytest, ruff, mypy --strict, uv.

**Spec:** [`docs/superpowers/specs/2026-08-08-layout-por-escopo-design.md`](../specs/2026-08-08-layout-por-escopo-design.md)

## Global Constraints

- `core/` NUNCA importa de `domains/`. Domínios são mutuamente independentes (exceção guardada: `write` → `protocol` em `compose.py`).
- `from __future__ import annotations` em todo módulo novo. `mypy --strict` limpo.
- Docstrings e mensagens de usuário em **pt-BR**, com o comando de correção **embutido na mensagem de erro**. Identificadores em inglês.
- Dataclasses de value object são `frozen=True`. Schemas Pydantic são forward-only: campo nunca é removido nem renomeado; campo novo é opcional com default.
- Nada de `print()` — sempre `core/output.Console`. Todo subcomando Typer envolto em `core/cli_op.cli_run(...)`.
- Testes espelham o layout: `tests/unit/<dominio>/test_<modulo>.py`. Dependências externas (Zotero, qmd, pandoc) mockadas nos seams.
- Verificação a cada task: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy`.
- Índices gerados: após tocar README, `skills/start/SKILL.md`, `docs/_index.md` ou `docs/adr/_index.md`, rodar `uv run python .github/scripts/gen_indexes.py`. CI roda `--check`.
- Branch: `feat/references-sob-docs` (já existe, com a spec commitada).

---

### Task 1: `core/pj_layout.py` — a autoridade de caminho

**Files:**
- Create: `src/prumo_assist/core/pj_layout.py`
- Test: `tests/unit/core/test_pj_layout.py`

**Interfaces:**
- Consumes: nada (é a base).
- Produces: `PJ_CONFIG_RELPATH`, `REFERENCES_RELPATH`, `STUDIES_RELPATH`, `find_pj_root(start: Path) -> Path`, `find_scope_root(start: Path) -> Path`, `iter_scopes(pj_root: Path) -> list[Path]`, `bib_path(pj_root: Path) -> Path`, `papers_dir(pj_root: Path) -> Path`, `paper_dir(pj_root: Path, citekey: str) -> Path`, `pdfs_dir(pj_root: Path) -> Path`, `notes_dir(scope: Path) -> Path`, `writing_dir(scope: Path) -> Path`, `decisions_dir(scope: Path) -> Path`, `is_legacy_layout(pj_root: Path) -> bool`, `PjRootNotFoundError`, `LegacyLayoutError`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/core/test_pj_layout.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist.core import pj_layout as L


def _mk_project(root: Path, *scopes: str) -> Path:
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    (root / "docs" / "references" / "papers").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "references" / "pdfs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "references" / "_references.bib").write_text("", encoding="utf-8")
    for slug in scopes or ("principal",):
        for sub in ("notes", "writing", "decisions"):
            (root / "docs" / "studies" / slug / sub).mkdir(parents=True, exist_ok=True)
    return root


def test_find_pj_root_sobe_ate_o_marcador(tmp_path: Path) -> None:
    root = _mk_project(tmp_path / "pj_x")
    deep = root / "docs" / "studies" / "principal" / "writing"
    assert L.find_pj_root(deep) == root


def test_find_pj_root_levanta_com_mensagem_acionavel(tmp_path: Path) -> None:
    with pytest.raises(L.PjRootNotFoundError) as exc:
        L.find_pj_root(tmp_path)
    assert "prumo init" in str(exc.value)


def test_find_scope_root_devolve_o_filho_de_studies(tmp_path: Path) -> None:
    root = _mk_project(tmp_path / "pj_x", "a", "b")
    page = root / "docs" / "studies" / "b" / "writing" / "paper.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("x", encoding="utf-8")
    assert L.find_scope_root(page) == root / "docs" / "studies" / "b"


def test_find_scope_root_nao_confunde_escopos_irmaos(tmp_path: Path) -> None:
    root = _mk_project(tmp_path / "pj_x", "a", "b")
    assert L.find_scope_root(root / "docs" / "studies" / "a" / "notes") != L.find_scope_root(
        root / "docs" / "studies" / "b" / "notes"
    )


def test_find_scope_root_fora_de_studies_levanta(tmp_path: Path) -> None:
    root = _mk_project(tmp_path / "pj_x")
    with pytest.raises(L.PjRootNotFoundError):
        L.find_scope_root(root / "docs" / "references")


def test_iter_scopes_ordena_e_ignora_arquivo(tmp_path: Path) -> None:
    root = _mk_project(tmp_path / "pj_x", "b", "a")
    (root / "docs" / "studies" / "leia-me.md").write_text("x", encoding="utf-8")
    assert [s.name for s in L.iter_scopes(root)] == ["a", "b"]


def test_caminhos_do_projeto_e_do_escopo(tmp_path: Path) -> None:
    root = _mk_project(tmp_path / "pj_x")
    scope = root / "docs" / "studies" / "principal"
    assert L.bib_path(root) == root / "docs" / "references" / "_references.bib"
    assert L.papers_dir(root) == root / "docs" / "references" / "papers"
    assert L.paper_dir(root, "silva2020") == root / "docs" / "references" / "papers" / "silva2020"
    assert L.pdfs_dir(root) == root / "docs" / "references" / "pdfs"
    assert L.notes_dir(scope) == scope / "notes"
    assert L.writing_dir(scope) == scope / "writing"
    assert L.decisions_dir(scope) == scope / "decisions"


def test_is_legacy_layout_detecta_references_na_raiz(tmp_path: Path) -> None:
    root = tmp_path / "pj_legado"
    (root / "references").mkdir(parents=True)
    (root / "references" / "_references.bib").write_text("", encoding="utf-8")
    (root / "docs").mkdir()
    assert L.is_legacy_layout(root) is True
    assert L.is_legacy_layout(_mk_project(tmp_path / "pj_novo")) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/core/test_pj_layout.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'prumo_assist.core.pj_layout'`

- [ ] **Step 3: Write minimal implementation**

Create `src/prumo_assist/core/pj_layout.py`:

```python
"""Autoridade única de caminho do layout de um ``pj_*``.

Dois conceitos que o código antigo fundia num resolvedor só:

- **projeto** (``find_pj_root``) — marcado por ``.claude/pj_config.toml``.
  Guarda a bibliografia, ``build/exports/`` e ``reviews/``.
- **escopo** (``find_scope_root``) — uma unidade de escrita, resolvida por
  POSIÇÃO: todo filho direto de ``docs/studies/`` é um escopo. Não há arquivo
  sentinela: nada a criar, nada a perder num ``git mv``.

Ver ADR-0022 e ADR-0024.
"""

from __future__ import annotations

from pathlib import Path

from prumo_assist import PrumoError

PJ_CONFIG_RELPATH = Path(".claude") / "pj_config.toml"
REFERENCES_RELPATH = Path("docs") / "references"
STUDIES_RELPATH = Path("docs") / "studies"


class PjRootNotFoundError(PrumoError):
    """Nem o projeto nem o escopo foram localizados a partir do caminho dado."""


class LegacyLayoutError(PrumoError):
    """Projeto ainda no layout com ``references/`` na raiz."""


def find_pj_root(start: Path) -> Path:
    """Sobe de ``start`` até o diretório com ``.claude/pj_config.toml``."""
    cur = start.resolve()
    if cur.is_file():
        cur = cur.parent
    for candidate in (cur, *cur.parents):
        if (candidate / PJ_CONFIG_RELPATH).is_file():
            return candidate
    raise PjRootNotFoundError(
        f"Raiz de projeto não encontrada a partir de {start} "
        f"(esperado {PJ_CONFIG_RELPATH}). Rode `prumo init` ou aponte o projeto "
        "com `--path <raiz>`."
    )


def find_scope_root(start: Path) -> Path:
    """Devolve o filho direto de ``docs/studies/`` que contém ``start``."""
    pj_root = find_pj_root(start)
    studies = pj_root / STUDIES_RELPATH
    cur = start.resolve()
    if cur.is_file():
        cur = cur.parent
    for candidate in (cur, *cur.parents):
        if candidate.parent == studies:
            return candidate
    raise PjRootNotFoundError(
        f"{start} não está dentro de um escopo. Todo texto vive em "
        "`docs/studies/<slug>/`. Crie um com `prumo add study <slug>`."
    )


def iter_scopes(pj_root: Path) -> list[Path]:
    """Lista os escopos do projeto, em ordem alfabética."""
    studies = pj_root / STUDIES_RELPATH
    if not studies.is_dir():
        return []
    return sorted(p for p in studies.iterdir() if p.is_dir())


def references_dir(pj_root: Path) -> Path:
    """``<pj>/docs/references/`` — a bibliografia é do PROJETO."""
    return pj_root / REFERENCES_RELPATH


def bib_path(pj_root: Path) -> Path:
    """``<pj>/docs/references/_references.bib``."""
    return references_dir(pj_root) / "_references.bib"


def papers_dir(pj_root: Path) -> Path:
    """``<pj>/docs/references/papers/`` — uma pasta por paper (layout α)."""
    return references_dir(pj_root) / "papers"


def paper_dir(pj_root: Path, citekey: str) -> Path:
    """``<pj>/docs/references/papers/<citekey>/``."""
    return papers_dir(pj_root) / citekey


def pdfs_dir(pj_root: Path) -> Path:
    """``<pj>/docs/references/pdfs/`` — symlinks pro storage do gerenciador."""
    return references_dir(pj_root) / "pdfs"


def notes_dir(scope: Path) -> Path:
    """``<escopo>/notes/`` — prosa humana, inclusive findings (``type:``)."""
    return scope / "notes"


def writing_dir(scope: Path) -> Path:
    """``<escopo>/writing/`` — o produto, com ``figures/`` e ``tables/`` ao lado."""
    return scope / "writing"


def decisions_dir(scope: Path) -> Path:
    """``<escopo>/decisions/`` — append-only."""
    return scope / "decisions"


def is_legacy_layout(pj_root: Path) -> bool:
    """True quando ``references/`` ainda está na raiz e não há ``docs/references/``."""
    return (pj_root / "references").is_dir() and not references_dir(pj_root).is_dir()


def assert_current_layout(pj_root: Path) -> None:
    """Levanta em layout legado, com o convite à adequação embutido."""
    if is_legacy_layout(pj_root):
        raise LegacyLayoutError(
            f"{pj_root} ainda tem `references/` na raiz. A bibliografia agora vive em "
            "`docs/references/`. Peça a adequação ao agente: descreva o projeto e diga "
            "`adeque este projeto ao layout novo do prumo`."
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/core/test_pj_layout.py -v`
Expected: PASS, 8 passed

- [ ] **Step 5: Verify types and lint**

Run: `uv run mypy && uv run ruff check . && uv run ruff format --check .`
Expected: exit 0

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/core/pj_layout.py tests/unit/core/test_pj_layout.py
git commit -m "feat(core): pj_layout como autoridade unica de caminho"
```

---

### Task 2: `core/note_paths.py` sobre `papers_dir` + `core/obsidian.py`

**Files:**
- Modify: `src/prumo_assist/core/note_paths.py:25,57,71`
- Modify: `src/prumo_assist/core/obsidian.py:133-134`
- Test: `tests/unit/core/test_note_paths.py`

**Interfaces:**
- Consumes: `pj_layout.paper_dir`, `pj_layout.papers_dir`, `pj_layout.pdfs_dir`.
- Produces: `note_paths.note_dir(pj_path, citekey)` inalterado na assinatura; `citekey_from_meta_path` passa a reconhecer `papers` como pasta-mãe do layout plano legado.

- [ ] **Step 1: Write the failing test**

Acrescente a `tests/unit/core/test_note_paths.py`:

```python
def test_note_dir_usa_papers_sob_docs(tmp_path: Path) -> None:
    from prumo_assist.core import note_paths

    got = note_paths.note_dir(tmp_path, "silva2020")
    assert got == tmp_path / "docs" / "references" / "papers" / "silva2020"


def test_citekey_from_meta_path_reconhece_papers_plano(tmp_path: Path) -> None:
    from prumo_assist.core import note_paths

    plano = tmp_path / "docs" / "references" / "papers" / "silva2020.md"
    alfa = tmp_path / "docs" / "references" / "papers" / "silva2020" / "_meta.md"
    assert note_paths.citekey_from_meta_path(plano) == "silva2020"
    assert note_paths.citekey_from_meta_path(alfa) == "silva2020"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/core/test_note_paths.py -v`
Expected: FAIL — o caminho devolvido ainda é `references/notes/...`

- [ ] **Step 3: Write minimal implementation**

Em `src/prumo_assist/core/note_paths.py`, troque as três linhas:

```python
# no topo do módulo
from prumo_assist.core import pj_layout

# linha 25 — antes: return pj_path / "references" / "notes" / citekey
    return pj_layout.paper_dir(pj_path, citekey)

# linha 57 — antes: notes_dir = pj_path / "references" / "notes"
    notes_dir = pj_layout.papers_dir(pj_path)

# linha 71 — antes: if meta.parent.name == "notes":
    if meta.parent.name == "papers":
```

Atualize o docstring do módulo: `Layout α: cada paper tem uma pasta ``docs/references/papers/<citekey>/`` contendo:`

Em `src/prumo_assist/core/obsidian.py`, troque as linhas 133-134:

```python
        pj_layout.pdfs_dir(parent) / name,
        pj_layout.pdfs_dir(parent.parent) / name,
```

com `from prumo_assist.core import pj_layout` no topo.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/core/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/core/note_paths.py src/prumo_assist/core/obsidian.py tests/unit/core/test_note_paths.py
git commit -m "refactor(core): note_paths e obsidian sobre pj_layout"
```

---

### Task 3: Domínio `paper` migra para `pj_layout`

**Files:**
- Modify: `src/prumo_assist/domains/paper/connect.py:259,296`
- Modify: `src/prumo_assist/domains/paper/find.py:19`
- Modify: `src/prumo_assist/domains/paper/lint.py:41-43`
- Modify: `src/prumo_assist/domains/paper/migrate.py:82`
- Modify: `src/prumo_assist/domains/paper/pdfs.py:32-33`
- Modify: `src/prumo_assist/domains/paper/prep.py:33-35`
- Modify: `src/prumo_assist/domains/paper/sync.py:188,201,222-223`
- Modify: `src/prumo_assist/domains/paper/verify.py:567`
- Modify: `src/prumo_assist/domains/paper/zotero.py:511-512,607-608`
- Test: `tests/unit/paper/` (todos)

**Interfaces:**
- Consumes: `pj_layout.bib_path`, `papers_dir`, `pdfs_dir`, `references_dir`, `assert_current_layout`.
- Produces: nenhuma assinatura pública muda — só os caminhos internos.

- [ ] **Step 1: Escreva o teste de guarda de layout legado**

Crie `tests/unit/paper/test_legacy_guard.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist.core.pj_layout import LegacyLayoutError
from prumo_assist.domains.paper import sync


def test_sync_recusa_layout_legado_com_convite(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    (tmp_path / "references").mkdir()
    (tmp_path / "references" / "_references.bib").write_text("", encoding="utf-8")
    (tmp_path / "docs").mkdir()

    with pytest.raises(LegacyLayoutError) as exc:
        sync.sync_pj(tmp_path)
    assert "adeque este projeto" in str(exc.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/paper/test_legacy_guard.py -v`
Expected: FAIL — hoje `sync_pj` não levanta

- [ ] **Step 3: Substituir os literais e acrescentar a guarda**

Em cada módulo listado, importe `from prumo_assist.core import pj_layout` e aplique:

| antes | depois |
|---|---|
| `pj_path / "references" / "_references.bib"` | `pj_layout.bib_path(pj_path)` |
| `pj_path / "references" / "notes"` | `pj_layout.papers_dir(pj_path)` |
| `pj_path / "references" / "notes" / citekey / "_meta.md"` | `pj_layout.paper_dir(pj_path, citekey) / "_meta.md"` |
| `pj_path / "references" / "pdfs"` | `pj_layout.pdfs_dir(pj_path)` |
| `pj_path / "references" / "pdfs" / f"{citekey}.pdf"` | `pj_layout.pdfs_dir(pj_path) / f"{citekey}.pdf"` |
| `pj_path / "references" / "templates" / "literature_note.md"` | `pj_layout.references_dir(pj_path) / "_note_template.md"` |

Na primeira linha do corpo de `sync.sync_pj`, `zotero.sync_annotations_pj`, `pdfs.sync_pdfs`, `lint.lint_pj`, `verify.verify_pj`, `find.find_papers` e `connect.connect_collection`, acrescente:

```python
    pj_layout.assert_current_layout(pj_path)
```

- [ ] **Step 4: Atualizar as fixtures dos testes do domínio**

Em cada teste de `tests/unit/paper/` que monta `references/`, troque o prefixo por `docs/references/` e `notes/` por `papers/`. Comando de apoio para localizar:

```bash
grep -rn '"references"\|references/' tests/unit/paper/
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/paper/ -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/domains/paper tests/unit/paper
git commit -m "refactor(paper): caminhos via pj_layout + guarda de layout legado"
```

---

### Task 4: Domínio `protocol` por escopo

**Files:**
- Modify: `src/prumo_assist/domains/protocol/adr.py:30,45`
- Modify: `src/prumo_assist/domains/protocol/ops.py:67,73,108,138,168`
- Test: `tests/unit/protocol/test_adr.py`

**Interfaces:**
- Consumes: `pj_layout.decisions_dir`, `pj_layout.writing_dir`, `pj_layout.find_scope_root`.
- Produces: `adr.next_number(scope: Path) -> int` e `adr.write_adr(scope: Path, ...)` — **assinatura muda de `pj_path` para `scope`**. `ops.propagate(scope: Path, ...)`.

- [ ] **Step 1: Write the failing test**

Acrescente a `tests/unit/protocol/test_adr.py`:

```python
def test_numeracao_de_adr_e_por_escopo(tmp_path: Path) -> None:
    from prumo_assist.domains.protocol import adr

    a = tmp_path / "docs" / "studies" / "a" / "decisions"
    b = tmp_path / "docs" / "studies" / "b" / "decisions"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    (a / "adr-0001-x.md").write_text("x", encoding="utf-8")
    (a / "adr-0002-y.md").write_text("y", encoding="utf-8")

    assert adr.next_number(a.parent) == 3
    assert adr.next_number(b.parent) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/protocol/test_adr.py::test_numeracao_de_adr_e_por_escopo -v`
Expected: FAIL — `next_number` recebe `pj_path` e monta `pj_path/"docs"/"decisions"`

- [ ] **Step 3: Write minimal implementation**

Em `adr.py`, as duas ocorrências de `decisions = pj_path / "docs" / "decisions"` viram:

```python
    decisions = pj_layout.decisions_dir(scope)
```

com o parâmetro renomeado de `pj_path` para `scope` nas duas funções.

Em `ops.py`:

```python
# :67  — antes: target=pj_path / "docs" / "protocol.md"
        target=pj_layout.writing_dir(scope) / "protocol.md",
# :73  — antes: target=pj_path / "docs" / "project_guide.md"
        target=find_pj_root(scope) / "docs" / "project_guide.md",
# :108 — antes: protocol_md = pj_path / "docs" / "protocol.md"
    protocol_md = pj_layout.writing_dir(scope) / "protocol.md"
# :138 e :168 — antes: pj_path / "docs" / "decisions" / f"adr-..."
    adr_path = pj_layout.decisions_dir(scope) / f"adr-{n:04d}-picot-v1-versao-inicial.md"
    adr_path = pj_layout.decisions_dir(scope) / f"adr-{n:04d}-picot-v{spec.version}-{slug}.md"
```

`project_guide.md` é do PROJETO, não do escopo — por isso resolve por `find_pj_root`.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/protocol/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/protocol tests/unit/protocol
git commit -m "refactor(protocol): ADR e protocolo por escopo"
```

---

### Task 5: `wiki/lint.py` por escopo

Esta é a mudança de comportamento mais visível. Cinco defeitos, todos silenciosos hoje.

**Files:**
- Modify: `src/prumo_assist/domains/wiki/lint.py:32,53,64,69-70,80-82,87,175-193`
- Test: `tests/unit/wiki/test_lint.py`

**Interfaces:**
- Consumes: `pj_layout.iter_scopes`, `bib_path`, `papers_dir`, `references_dir`.
- Produces: `lint(pj_path: Path) -> dict[str, Any]` (assinatura preservada, agora itera escopos); `WikiIssue` ganha campo `scope: str | None = None`.

- [ ] **Step 1: Write the failing tests**

Acrescente a `tests/unit/wiki/test_lint.py`:

```python
def _scope(root: Path, slug: str) -> Path:
    s = root / "docs" / "studies" / slug
    for sub in ("notes", "writing", "decisions"):
        (s / sub).mkdir(parents=True, exist_ok=True)
    return s


def _project(root: Path) -> Path:
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    (root / "docs" / "references" / "papers").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "references" / "_references.bib").write_text("", encoding="utf-8")
    (root / "docs" / "_index.md").write_text("# i", encoding="utf-8")
    (root / "docs" / "_log.md").write_text("# l", encoding="utf-8")
    return root


def test_lint_nao_conta_a_bibliografia_como_pagina(tmp_path: Path) -> None:
    from prumo_assist.domains.wiki.lint import lint

    root = _project(tmp_path)
    _scope(root, "a")
    papers = root / "docs" / "references" / "papers" / "silva2020"
    papers.mkdir(parents=True)
    (papers / "_meta.md").write_text("---\ntype: paper\n---\n", encoding="utf-8")

    codes = [i["code"] for i in lint(root)["issues"]]
    assert "orphan_page" not in codes


def test_bib_ausente_sem_citacao_nao_emite_nada(tmp_path: Path) -> None:
    from prumo_assist.domains.wiki.lint import lint

    root = _project(tmp_path)
    (root / "docs" / "references" / "_references.bib").unlink()
    s = _scope(root, "a")
    (s / "notes" / "n.md").write_text("---\ntype: note\n---\nsem citacao", encoding="utf-8")

    codes = [i["code"] for i in lint(root)["issues"]]
    assert "bib_missing" not in codes


def test_bib_ausente_com_citacao_emite_warning(tmp_path: Path) -> None:
    from prumo_assist.domains.wiki.lint import lint

    root = _project(tmp_path)
    (root / "docs" / "references" / "_references.bib").unlink()
    s = _scope(root, "a")
    (s / "notes" / "n.md").write_text("---\ntype: note\n---\ntexto [@silva2020]", encoding="utf-8")

    issues = [i for i in lint(root)["issues"] if i["code"] == "bib_missing"]
    assert len(issues) == 1
    assert issues[0]["severity"] == "warning"


def test_paginas_homonimas_em_escopos_distintos_nao_se_anulam(tmp_path: Path) -> None:
    from prumo_assist.domains.wiki.lint import lint

    root = _project(tmp_path)
    a = _scope(root, "a")
    b = _scope(root, "b")
    (a / "notes" / "metodo.md").write_text("---\ntype: note\n---\nx", encoding="utf-8")
    (a / "writing" / "paper.md").write_text("---\ntype: draft\n---\n[[metodo]]", encoding="utf-8")
    (b / "notes" / "metodo.md").write_text("---\ntype: note\n---\ny", encoding="utf-8")

    orfas = [i for i in lint(root)["issues"] if i["code"] == "orphan_page"]
    paginas = {i["page"] for i in orfas}
    assert any("studies/b/notes/metodo.md" in p for p in paginas)
    assert not any("studies/a/notes/metodo.md" in p for p in paginas)


def test_multiple_primary_desligado_por_default(tmp_path: Path) -> None:
    from prumo_assist.domains.wiki.lint import lint

    root = _project(tmp_path)
    _scope(root, "a")
    for key in ("um", "dois"):
        d = root / "docs" / "references" / "papers" / key
        d.mkdir(parents=True)
        (d / "_meta.md").write_text("---\nrole: primary\n---\n", encoding="utf-8")

    codes = [i["code"] for i in lint(root)["issues"]]
    assert "multiple_primary" not in codes
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/wiki/test_lint.py -v -k "bibliografia or bib_ausente or homonimas or multiple_primary"`
Expected: FAIL nos cinco

- [ ] **Step 3: Write minimal implementation**

Em `src/prumo_assist/domains/wiki/lint.py`:

```python
# topo
from prumo_assist.core import pj_layout

# :32 — EXPECTED_DIRS deixa de ser taxonomia e vira os subdiretórios do escopo
EXPECTED_DIRS = ("notes", "writing", "decisions")


# WikiIssue ganha o escopo
@dataclass(frozen=True)
class WikiIssue:
    severity: str
    code: str
    message: str
    page: str | None = None
    scope: str | None = None


def lint(pj_path: Path) -> dict[str, Any]:
    """Roda os checks do wiki, um escopo por vez."""
    pj_layout.assert_current_layout(pj_path)
    issues: list[WikiIssue] = []
    docs = pj_path / "docs"

    if not docs.is_dir():
        issues.append(WikiIssue("error", "docs_missing", f"{docs} não existe"))
        return _report(issues)

    if not (docs / "_index.md").is_file():
        issues.append(WikiIssue("warning", "no_index", "docs/_index.md ausente"))
    if not (docs / "_log.md").is_file():
        issues.append(WikiIssue("warning", "no_log", "docs/_log.md ausente"))

    bib = pj_layout.bib_path(pj_path)
    bib_keys: set[str] = set()
    if bib.is_file():
        bib_keys = {e.citekey for e in parse_bib(bib.read_text())}

    scopes = pj_layout.iter_scopes(pj_path)
    if not scopes:
        issues.append(
            WikiIssue(
                "warning",
                "no_scope",
                "nenhum escopo em docs/studies/. Crie um com `prumo add study <slug>`.",
            )
        )
    for scope in scopes:
        issues.extend(_lint_scope(pj_path, scope, bib_keys, bib.is_file()))

    issues.extend(_check_log_prefixes(docs))
    return _report(issues)


def _lint_scope(
    pj_path: Path, scope: Path, bib_keys: set[str], bib_exists: bool
) -> list[WikiIssue]:
    """Checks de um escopo. Identidade de página é o caminho relativo ao escopo."""
    issues: list[WikiIssue] = []
    slug = scope.name
    pages = sorted(scope.rglob("*.md"))
    texts = {p: p.read_text(encoding="utf-8") for p in pages}
    # Identidade por CAMINHO — `stem` funde homônimas de escopos diferentes.
    keys = {p: p.relative_to(scope).as_posix() for p in pages}
    incoming: dict[str, int] = dict.fromkeys(keys.values(), 0)
    # Índice stem -> caminhos, para resolver wikilink dentro do escopo.
    by_stem: dict[str, list[str]] = {}
    for p in pages:
        by_stem.setdefault(p.stem, []).append(keys[p])

    cited = False
    for page in pages:
        text = texts[page]
        rel = page.relative_to(pj_path).as_posix()

        parent = page.parent.name
        if parent in EXPECTED_DIRS and not text.startswith("---"):
            issues.append(
                WikiIssue("warning", "no_frontmatter", "sem frontmatter", page=rel, scope=slug)
            )

        for ck in scan_marked_citekeys(text):
            cited = True
            if bib_exists and ck not in bib_keys:
                issues.append(
                    WikiIssue(
                        "warning", "broken_citekey", f"@{ck} não existe no .bib", page=rel, scope=slug
                    )
                )

        for stem in _page_link_targets(text):
            targets = by_stem.get(stem, [])
            if len(targets) > 1:
                issues.append(
                    WikiIssue(
                        "warning",
                        "ambiguous_link",
                        f"[[{stem}]] casa {len(targets)} páginas neste escopo",
                        page=rel,
                        scope=slug,
                    )
                )
            for t in targets:
                incoming[t] += 1

    if cited and not bib_exists:
        issues.append(
            WikiIssue(
                "warning",
                "bib_missing",
                "há citação `[@key]` e nenhuma bibliografia em docs/references/_references.bib. "
                "Aponte o .bib do seu gerenciador ou rode `prumo paper connect <coleção>`.",
                scope=slug,
            )
        )

    for key, count in sorted(incoming.items()):
        stem = Path(key).stem
        if count == 0 and not stem.startswith("_") and stem not in {"README", "protocol"}:
            issues.append(
                WikiIssue(
                    "warning",
                    "orphan_page",
                    "página sem links de entrada",
                    page=(scope / key).relative_to(pj_path).as_posix(),
                    scope=slug,
                )
            )

    return issues
```

Em `_check_single_primary`, troque a chamada incondicional por um gate. A função continua existindo; deixa de ser chamada por `lint()` e passa a ser exposta como `check_single_primary(pj_path)` para quem quiser. Substitua o corpo do caminho de notas:

```python
def check_single_primary(pj_path: Path) -> list[WikiIssue]:
    """Opt-in: só faz sentido quando o projeto declara ter paper principal."""
    notes_dir = pj_layout.papers_dir(pj_path)
    ...
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/wiki/test_lint.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/wiki/lint.py tests/unit/wiki/test_lint.py
git commit -m "feat(wiki): lint por escopo, bib_missing como warning, multiple_primary opt-in"
```

---

### Task 6: `wiki/stats.py` com `by_scope`

**Files:**
- Modify: `src/prumo_assist/domains/wiki/stats.py:8,13-14,23-44`
- Test: `tests/unit/wiki/test_stats.py`

**Interfaces:**
- Consumes: `pj_layout.iter_scopes`, `papers_dir`.
- Produces: `stats(pj_path)` devolve `{"by_type": {...}, "by_scope": {...}, "totals": {...}}`. **`by_type["references"]` continua existindo** — remover violaria forward-only (`constitution.md:62`).

- [ ] **Step 1: Write the failing test**

```python
def test_stats_mantem_by_type_e_ganha_by_scope(tmp_path: Path) -> None:
    from prumo_assist.domains.wiki.stats import stats

    root = _project(tmp_path)   # mesmo helper do test_lint
    a = _scope(root, "a")
    (a / "notes" / "n.md").write_text("x" * 10, encoding="utf-8")
    d = root / "docs" / "references" / "papers" / "silva2020"
    d.mkdir(parents=True)
    (d / "_meta.md").write_text("y" * 20, encoding="utf-8")

    out = stats(root)
    assert out["by_type"]["references"]["pages"] == 1
    assert out["by_scope"]["a"]["notes"]["pages"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/wiki/test_stats.py -v`
Expected: FAIL — `KeyError: 'by_scope'`

- [ ] **Step 3: Write minimal implementation**

```python
from prumo_assist.core import pj_layout

EXPECTED_DIRS = ("notes", "writing", "decisions")


def stats(pj_path: Path) -> dict[str, Any]:
    """Contagem por escopo e por tipo, mais o total do projeto."""
    docs = pj_path / "docs"
    out: dict[str, Any] = {"by_type": {}, "by_scope": {}, "totals": {}}

    if not docs.is_dir():
        out["docs_missing"] = True
        return out

    grand_total = 0
    grand_bytes = 0
    for scope in pj_layout.iter_scopes(pj_path):
        per_scope: dict[str, Any] = {}
        for d in EXPECTED_DIRS:
            target = scope / d
            pages = list(target.rglob("*.md")) if target.is_dir() else []
            size = sum(p.stat().st_size for p in pages)
            per_scope[d] = {"pages": len(pages), "bytes": size}
            grand_total += len(pages)
            grand_bytes += size
        out["by_scope"][scope.name] = per_scope

    papers = pj_layout.papers_dir(pj_path)
    if papers.is_dir():
        rn = list(papers.rglob("*.md"))
        size = sum(p.stat().st_size for p in rn)
        out["by_type"]["references"] = {"pages": len(rn), "bytes": size}
        grand_total += len(rn)
        grand_bytes += size
    else:
        out["by_type"]["references"] = {"pages": 0, "bytes": 0}

    out["totals"] = {"pages": grand_total, "bytes": grand_bytes}
    return out
```

`rglob` no lugar de `glob` conserta de passagem os 85 papers em layout α que o `glob` raso não via.

- [ ] **Step 4: Run tests and commit**

```bash
uv run pytest tests/unit/wiki/ -v
git add src/prumo_assist/domains/wiki/stats.py tests/unit/wiki/test_stats.py
git commit -m "feat(wiki): stats por escopo, references por rglob"
```

---

### Task 7: Findings viram `type:` em `notes/`

**Files:**
- Modify: `src/prumo_assist/domains/wiki/findings.py:16-24,45,50-51,75,91`
- Modify: `src/prumo_assist/domains/write/compose.py:178-193`
- Modify: `src/prumo_assist/domains/wiki/study.py:29,33`
- Test: `tests/unit/wiki/test_findings.py`, `tests/unit/write/test_compose_inputs.py`

**Interfaces:**
- Consumes: `pj_layout.notes_dir`, `find_scope_root`.
- Produces: `archive_as_finding(*, scope: Path, slug, title, body, sources, date, tags, generator) -> Path` — **`pj_path` vira `scope`**. `compose._read_findings(scope: Path) -> list[...]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_finding_nasce_em_notes_com_type(tmp_path: Path) -> None:
    from prumo_assist.domains.wiki.findings import archive_as_finding

    root = _project(tmp_path)
    scope = _scope(root, "a")
    out = archive_as_finding(
        scope=scope, slug="auc-subgrupo", title="AUC", body="corpo",
        sources=["[@silva2020]"], date="2026-08-09",
    )
    assert out == scope / "notes" / "auc-subgrupo.md"
    assert "type: finding" in out.read_text(encoding="utf-8")
    assert not (root / "docs" / "findings").exists()
    assert not (root / "docs" / "wiki").exists()


def test_compose_acha_finding_por_type(tmp_path: Path) -> None:
    from prumo_assist.domains.write import compose

    root = _project(tmp_path)
    scope = _scope(root, "a")
    (scope / "notes" / "f.md").write_text(
        "---\ntype: finding\ntitle: F\n---\ncorpo", encoding="utf-8"
    )
    (scope / "notes" / "n.md").write_text("---\ntype: note\n---\noutro", encoding="utf-8")

    achados = compose._read_findings(scope)
    assert len(achados) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/wiki/test_findings.py tests/unit/write/test_compose_inputs.py -v`
Expected: FAIL — `archive_as_finding` ainda recebe `pj_path` e cria diretório

- [ ] **Step 3: Write minimal implementation**

Em `findings.py`, apague `_resolve_findings_dir` inteiro e troque a assinatura:

```python
def archive_as_finding(
    *,
    scope: Path,
    slug: str,
    title: str,
    body: str,
    sources: list[str],
    date: str,
    tags: list[str] | None = None,
    generator: str = "wiki-query",
) -> Path:
    """Cria ``<escopo>/notes/<slug>.md`` com ``type: finding``.

    Não existe diretório ``findings/``: o finding é uma nota com procedência,
    distinguida pelo ``type:`` do frontmatter (ADR-0023).
    """
    notes = pj_layout.notes_dir(scope)
    notes.mkdir(parents=True, exist_ok=True)
    finding_path = notes / f"{slug}.md"
    ...
```

`_append_to_index` e `_append_to_log` passam a receber `pj_root` explícito (o `_index.md` e o `_log.md` são do PROJETO):

```python
    pj_root = pj_layout.find_pj_root(scope)
    index = pj_root / "docs" / "_index.md"
    log = pj_root / "docs" / "_log.md"
```

Em `compose.py`, substitua `_read_findings`:

```python
def _read_findings(scope: Path) -> list[dict[str, str]]:
    """Varre ``<escopo>/notes/`` e devolve as notas com ``type: finding``."""
    notes = pj_layout.notes_dir(scope)
    if not notes.is_dir():
        return []
    out: list[dict[str, str]] = []
    for page in sorted(notes.rglob("*.md")):
        text = page.read_text(encoding="utf-8")
        if _extract_yaml_field(text, "type") != "finding":
            continue
        out.append({"slug": page.stem, "title": _extract_yaml_field(text, "title") or page.stem, "body": text})
    return out
```

Em `study.py:29,33`, a sessão de estudo passa a gravar em `<escopo>/notes/`:

```python
    out = pj_layout.notes_dir(scope) / f"session-{topic}-{date}.md"
```

- [ ] **Step 4: Run tests and commit**

```bash
uv run pytest tests/unit/wiki/ tests/unit/write/ -v
git add src/prumo_assist/domains/wiki/findings.py src/prumo_assist/domains/wiki/study.py src/prumo_assist/domains/write/compose.py tests/unit
git commit -m "feat(wiki): finding vira type: em notes/, sem diretorio proprio"
```

---

### Task 8: `write/export.py` — raiz, figuras e guarda de sobrescrita

**Files:**
- Modify: `src/prumo_assist/domains/write/export.py:676-682,738-749,785,902,685-735,793-797`
- Test: `tests/unit/write/test_export_docx_validation.py`

**Interfaces:**
- Consumes: `pj_layout.find_pj_root`, `find_scope_root`, `bib_path`.
- Produces: `export(page, *, force: bool = False, ...)` — parâmetro novo `force`; `detect_project_root` é substituída por `pj_layout.find_pj_root`.

- [ ] **Step 1: Write the failing tests**

```python
def test_export_recusa_sobrescrever_sem_force(tmp_path: Path, init_project) -> None:
    from prumo_assist.domains.write import export

    root, page = init_project()
    out = root / "build" / "exports" / "pagina.docx"
    out.parent.mkdir(parents=True)
    out.write_bytes(b"conteudo do coautor")

    with pytest.raises(FileExistsError) as exc:
        export.export(page, to="docx", out=out)
    assert "--force" in str(exc.value)


def test_export_falha_alto_quando_figura_falta(tmp_path: Path, init_project) -> None:
    from prumo_assist.domains.write import export

    root, page = init_project(body="Texto\n\n![Fig](figures/ausente.png)\n")
    with pytest.raises(export.MissingResourceError) as exc:
        export.export(page, to="docx")
    assert "figures/ausente.png" in str(exc.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/write/test_export_docx_validation.py -v -k "sobrescrever or figura"`
Expected: FAIL — hoje sobrescreve em silêncio e o pandoc sai 0 sem imagem

- [ ] **Step 3: Write minimal implementation**

Substitua `detect_project_root` por delegação (mantendo o nome para não quebrar callers internos):

```python
def detect_project_root(page: Path) -> Path:
    """Delegação para ``pj_layout.find_pj_root`` — sentinela é ``.claude/pj_config.toml``."""
    return pj_layout.find_pj_root(page)
```

`bib` nas linhas 785 e 902:

```python
    bib = bib or pj_layout.bib_path(project_root)
```

Em `_build_pandoc_cmd`, acrescente o resource-path apontando para o diretório da página:

```python
    cmd += ["--resource-path", str(page.parent)]
```

Nova exceção e checagem sobre o stderr, no mesmo padrão de `_assert_no_citeproc_missing`:

```python
class MissingResourceError(PrumoError):
    """Pandoc não encontrou um recurso referenciado (imagem, tabela incluída)."""


_MISSING_RESOURCE_RE = re.compile(r"Could not fetch resource ([^\s:]+)")


def _assert_no_missing_resource(stderr: str) -> None:
    faltando = _MISSING_RESOURCE_RE.findall(stderr)
    if faltando:
        alvos = ", ".join(sorted(set(faltando)))
        raise MissingResourceError(
            f"Recurso não encontrado no export: {alvos}. "
            "Confira o caminho relativo à página (ex.: `figures/x.png` ao lado do .md)."
        )
```

Chame `_assert_no_missing_resource(proc.stderr)` dentro de `_run_pandoc_checked`, logo após a checagem de `returncode`.

Guarda de sobrescrita em `export()`, antes de invocar o pandoc:

```python
    if out.exists() and not force:
        raise FileExistsError(
            f"{out} já existe. Use `--force` para sobrescrever — atenção: se este for o "
            "docx que voltou do coautor, sobrescrever perde a revisão."
        )
```

- [ ] **Step 4: Run tests and commit**

```bash
uv run pytest tests/unit/write/ -v
git add src/prumo_assist/domains/write/export.py tests/unit/write
git commit -m "feat(write): resource-path para figuras, guarda de sobrescrita, raiz via pj_layout"
```

---

### Task 9: `write/compose.py` e `write/zettlr.py` por escopo

**Files:**
- Modify: `src/prumo_assist/domains/write/compose.py:46,47,150,158,271`
- Modify: `src/prumo_assist/domains/write/zettlr.py:56`
- Test: `tests/unit/write/test_compose_inputs.py`, `tests/unit/write/test_zettlr_profile.py`

**Interfaces:**
- Consumes: `pj_layout.bib_path`, `writing_dir`, `find_pj_root`, `find_scope_root`.
- Produces: `compose.read_inputs(scope: Path)` — **`pj_path` vira `scope`**.

- [ ] **Step 1: Write the failing test**

```python
def test_compose_le_protocolo_do_escopo(tmp_path: Path) -> None:
    from prumo_assist.domains.write import compose

    root = _project(tmp_path)
    scope = _scope(root, "a")
    (scope / "writing" / "protocol.md").write_text("PROTOCOLO", encoding="utf-8")
    (root / "docs" / "project_guide.md").write_text("GUIA", encoding="utf-8")

    got = compose.read_inputs(scope)
    assert got.protocol == "PROTOCOLO"
    assert got.project == "GUIA"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/write/test_compose_inputs.py -v -k protocolo`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# compose.py:46-47
        protocol=_read_text(pj_layout.writing_dir(scope) / "protocol.md"),
        project=_read_text(pj_layout.find_pj_root(scope) / "docs" / "project_guide.md"),
# :150 e :158
    bib = pj_layout.bib_path(pj_layout.find_pj_root(scope))
# :271 — drafts deixa de existir; o índice mora em writing/
    drafts = pj_layout.writing_dir(scope)
# zettlr.py:56
    bib = pj_layout.bib_path(pj_path)
```

- [ ] **Step 4: Run tests and commit**

```bash
uv run pytest tests/unit/write/ -v
git add src/prumo_assist/domains/write tests/unit/write
git commit -m "refactor(write): compose e zettlr por escopo"
```

---

### Task 10: CLI — `doctor`, `init` com escopo, `add study`

**Files:**
- Modify: `src/prumo_assist/cli.py:572` (`doctor`), `:331` (`init`), `:224` (`_wizard`)
- Create: comando `add study` em `src/prumo_assist/cli.py`
- Test: `tests/unit/test_cli_doctor.py`, `tests/unit/test_cli_init.py`

**Interfaces:**
- Consumes: `pj_layout.*`.
- Produces: `prumo add study <slug>`; `doctor` com códigos `legacy_layout` e `references_ressuscitado`.

- [ ] **Step 1: Write the failing tests**

```python
def test_doctor_acusa_layout_legado(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    (tmp_path / "references").mkdir()
    (tmp_path / "docs").mkdir()
    result = runner.invoke(app, ["doctor", "--path", str(tmp_path), "--json"])
    assert "legacy_layout" in result.stdout


def test_doctor_acusa_references_ressuscitado_pelo_zotero(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "references").mkdir()
    result = runner.invoke(app, ["doctor", "--path", str(root), "--json"])
    assert "references_ressuscitado" in result.stdout


def test_add_study_cria_pasta_irma_sem_tocar_no_resto(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _scope(root, "principal")
    antes = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
    result = runner.invoke(app, ["add", "study", "sepse", "--target", str(root)])
    assert result.exit_code == 0
    for sub in ("notes", "writing", "decisions"):
        assert (root / "docs" / "studies" / "sepse" / sub).is_dir()
    depois = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
    assert set(antes).issubset(set(depois))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_cli_doctor.py tests/unit/test_cli_init.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

`doctor`, linha 572:

```python
    expected = [".claude", "docs"]
    ...
    if pj_layout.is_legacy_layout(target):
        problems.append(
            {
                "code": "legacy_layout",
                "message": "`references/` na raiz. A bibliografia agora vive em "
                "`docs/references/`. Peça ao agente: `adeque este projeto ao layout novo`.",
            }
        )
    elif (target / "references").is_dir():
        problems.append(
            {
                "code": "references_ressuscitado",
                "message": "`docs/references/` existe E `references/` reapareceu na raiz — "
                "assinatura do autoexport do Better BibTeX apontando para o caminho antigo. "
                "Corrija em Zotero → Preferences → Better BibTeX → Automatic export.",
            }
        )
```

`add study` como subcomando do `add_app` existente:

```python
@add_app.command("study")
def add_study_command(
    slug: Annotated[str, typer.Argument(help="Slug do escopo, ex.: mortalidade-uti.")],
    target: Annotated[Path, typer.Option("--target", "-t")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Cria um escopo de escrita novo em ``docs/studies/<slug>/``.

    Não move nem reescreve nada: o escopo novo é uma pasta irmã.
    """
    with cli_run(json_mode=json_mode) as console:
        pj_root = pj_layout.find_pj_root(target.resolve())
        pj_layout.assert_current_layout(pj_root)
        scope = pj_root / pj_layout.STUDIES_RELPATH / slug
        if scope.exists():
            raise PrumoError(f"{scope} já existe. Escolha outro slug.")
        for sub in ("notes", "writing", "decisions"):
            (scope / sub).mkdir(parents=True)
            (scope / sub / ".gitkeep").touch()
        console.success(f"Escopo `{slug}` criado em {scope}.")
        console.emit({"scope": str(scope), "slug": slug})
```

No `_wizard`, acrescente a pergunta do slug do primeiro escopo, com default derivado do nome do projeto (sem o prefixo `pj_`):

```python
    slug_default = name.removeprefix("pj_") or "principal"
    scope_slug = console.ask("Slug do primeiro escopo de escrita", default=slug_default)
```

- [ ] **Step 4: Run tests and commit**

```bash
uv run pytest tests/unit/ -v
git add src/prumo_assist/cli.py tests/unit
git commit -m "feat(cli): doctor de layout, add study, wizard com escopo"
```

---

### Task 11: `templates/pj_base/` — o núcleo universal

**Files:**
- Delete: `templates/pj_base/references/` (a árvore inteira), `templates/pj_base/pyproject.toml`
- Create: `templates/pj_base/docs/references/{_references.bib,_index.md,.gitignore}`, `templates/pj_base/docs/references/papers/.gitkeep`, `templates/pj_base/docs/references/pdfs/.gitkeep`, `templates/pj_base/docs/references/_note_template.md`, `templates/pj_base/docs/studies/principal/{notes,writing,decisions}/.gitkeep`
- Modify: `templates/pj_base/.gitignore`, `templates/pj_base/docs/_index.md`, `templates/pj_base/.claude/rules/documentation.md`, `templates/pj_base/CLAUDE.md`, `templates/pj_base/Makefile`
- Delete: `templates/pj_base/docs/decisions/` (vai para o escopo)
- Test: `tests/unit/test_pj_base_integration.py`

**Interfaces:**
- Consumes: nada.
- Produces: a árvore que `prumo init` copia.

- [ ] **Step 1: Write the failing test**

```python
def test_pj_base_e_o_nucleo_universal() -> None:
    base = resolve_resource("templates") / "pj_base"
    assert (base / "docs" / "references" / "papers").is_dir()
    assert (base / "docs" / "studies" / "principal" / "writing").is_dir()
    # nada de codigo no nucleo
    for proibido in ("src", "tests", "notebooks", "content", "pyproject.toml"):
        assert not (base / proibido).exists(), f"{proibido} nao pertence ao nucleo"
    # a bibliografia nao mora mais na raiz
    assert not (base / "references").exists()


def test_gitignore_do_pj_base_protege_o_essencial() -> None:
    base = resolve_resource("templates") / "pj_base"
    texto = (base / ".gitignore").read_text(encoding="utf-8")
    assert ".prumo/" in texto
    assert "~$*" in texto
    assert "uv.lock" not in texto  # lockfile passa a ser versionado


def test_gitignore_da_bibliografia_e_local_e_nao_ancorado() -> None:
    base = resolve_resource("templates") / "pj_base"
    texto = (base / "docs" / "references" / ".gitignore").read_text(encoding="utf-8")
    assert texto.splitlines()[:2] == ["pdfs/*.pdf", "!pdfs/.gitkeep"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_pj_base_integration.py -v`
Expected: FAIL

- [ ] **Step 3: Reestruturar o template**

```bash
cd templates/pj_base
git mv references docs/references
git mv docs/references/notes docs/references/papers
git mv docs/references/templates/literature_note.md docs/references/_note_template.md
rmdir docs/references/templates
mkdir -p docs/studies/principal/{notes,writing,decisions}
touch docs/studies/principal/{notes,writing,decisions}/.gitkeep
git mv docs/decisions/.gitkeep docs/studies/principal/decisions/.gitkeep
rmdir docs/decisions
git rm pyproject.toml
```

`templates/pj_base/docs/references/.gitignore` (novo):

```gitignore
# Padrões NÃO ancorados: viajam com a pasta em qualquer profundidade.
pdfs/*.pdf
!pdfs/.gitkeep
```

Em `templates/pj_base/.gitignore`: remova as linhas `references/pdfs/*.pdf` e `!references/pdfs/.gitkeep`; remova `uv.lock`; acrescente:

```gitignore
# Trace local de execução (saída de LLM — nunca no histórico)
.prumo/

# Lixo de editor de texto (lock do Word)
~$*
```

Em `docs/_index.md`, o link `[`../references/_index.md`](../references/_index.md)` vira `[`references/_index.md`](references/_index.md)`.

Em `.claude/rules/documentation.md`, `CLAUDE.md` e `Makefile`: substitua `references/notes/` por `docs/references/papers/`, `references/pdfs/` por `docs/references/pdfs/`, `references/_references.bib` por `docs/references/_references.bib`.

- [ ] **Step 4: Run tests and commit**

```bash
uv run pytest tests/unit/test_pj_base_integration.py -v
git add templates/pj_base tests/unit/test_pj_base_integration.py
git commit -m "feat(template): pj_base vira o nucleo universal"
```

---

### Task 12: Camadas `code`, `data`, `notebooks` + anchor do `clinical`

**Files:**
- Create: `templates/modules/code/{_module.toml,src/.gitkeep,tests/.gitkeep,pyproject.toml}`
- Create: `templates/modules/data/{_module.toml,content/01_raw/.gitkeep,content/02_processed/.gitkeep}`
- Create: `templates/modules/notebooks/{_module.toml,notebooks/.gitkeep}`
- Modify: `templates/modules/clinical/_module.toml:3`
- Modify: `templates/modules/clinical/docs/` → `templates/modules/clinical/docs/studies/principal/writing/`
- Test: `tests/unit/test_modules.py`

**Interfaces:**
- Consumes: `core/scaffold.overlay`, `discover_modules`.
- Produces: três módulos novos descobertos por `prumo add --list`.

- [ ] **Step 1: Write the failing test**

```python
def test_modulos_do_nucleo_existem_e_sao_descobriveis() -> None:
    from prumo_assist.core.scaffold import discover_modules

    nomes = {m.name for m in discover_modules()}
    assert {"code", "data", "notebooks", "clinical", "ml"} <= nomes


def test_add_clinical_nao_cria_protocolo_fora_do_escopo(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _scope(root, "principal")
    runner.invoke(app, ["add", "clinical", "--target", str(root)])
    assert (root / "docs" / "studies" / "principal" / "writing" / "protocol.md").is_file()
    assert not (root / "docs" / "protocol.md").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_modules.py -v`
Expected: FAIL — só `clinical` e `ml` existem

- [ ] **Step 3: Criar os módulos**

`templates/modules/code/_module.toml`:

```toml
description = "Código de análise: src/ importável, tests/ espelhado, pyproject.toml."
when_to_use = "O projeto vai ter script ou pacote Python próprio."
anchor = "src/__init__.py"
```

`templates/modules/data/_module.toml`:

```toml
description = "Dado do projeto: content/01_raw (somente leitura) e content/02_processed."
when_to_use = "Entra o primeiro dataset no projeto."
anchor = "content/01_raw/.gitkeep"
```

`templates/modules/notebooks/_module.toml`:

```toml
description = "Exploração interativa: notebooks/ fora do workspace de leitura."
when_to_use = "Primeira análise exploratória em notebook."
anchor = "notebooks/.gitkeep"
```

Mova o `pyproject.toml` que saiu do `pj_base` (Task 11) para `templates/modules/code/pyproject.toml`.

Em `templates/modules/clinical/_module.toml`, troque a linha 3:

```toml
anchor = "docs/studies/principal/writing/protocol.md"
```

E mova o payload: `templates/modules/clinical/docs/protocol.md` → `templates/modules/clinical/docs/studies/principal/writing/protocol.md`; idem para `statistical_analysis_plan_skeleton.md` e `projeto-cep.md`, que saem de `docs/templates/` para `docs/studies/principal/writing/`.

- [ ] **Step 4: Run tests and commit**

```bash
uv run pytest tests/unit/test_modules.py -v
git add templates/modules tests/unit/test_modules.py
git commit -m "feat(modules): camadas code/data/notebooks e anchor do clinical no escopo"
```

---

### Task 13: Prosa — templates de escrita, skills e docs do repo

**Files:**
- Modify: `skills/write-paper/template.md:5`, `skills/write-scientific/template.md:4`, `skills/write-statistics/template.md:4`, `skills/write-projeto-cep/template.md:6`
- Modify: os 15 `skills/*/SKILL.md` que citam `references/`
- Modify: `ARCHITECTURE.md`, `README.md`, `docs/Research Project Structure.md`, `docs/actions-by-context.md`, `docs/onboarding-pesquisador.md`, `docs/canvas/*.canvas`
- Test: `tests/unit/test_guidelines_present.py`

**Interfaces:**
- Consumes: nada.
- Produces: prosa coerente com o layout.

- [ ] **Step 1: Write the failing test**

```python
def test_templates_de_escrita_apontam_a_bibliografia_do_escopo() -> None:
    from prumo_assist.core.paths import resolve_resource

    esperado = "bibliography: ../../../references/_references.bib"
    for nome in ("write-paper", "write-scientific", "write-statistics", "write-projeto-cep"):
        texto = (resolve_resource("skills") / nome / "template.md").read_text(encoding="utf-8")
        assert esperado in texto, nome


def test_nenhuma_skill_cita_o_caminho_antigo() -> None:
    from prumo_assist.core.paths import resolve_resource

    for skill in (resolve_resource("skills")).glob("*/SKILL.md"):
        texto = skill.read_text(encoding="utf-8")
        assert "references/notes/" not in texto, skill.name
        assert "docs/wiki/findings" not in texto, skill.name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_guidelines_present.py -v`
Expected: FAIL

- [ ] **Step 3: Substituições**

Nos quatro `template.md`, o campo `bibliography` passa a `../../../references/_references.bib` — três níveis, invariante porque todo draft mora em `docs/studies/<slug>/writing/`.

Nos `SKILL.md` e docs do repo:

| antes | depois |
|---|---|
| `references/notes/<citekey>/` | `docs/references/papers/<citekey>/` |
| `references/pdfs/` | `docs/references/pdfs/` |
| `references/_references.bib` | `docs/references/_references.bib` |
| `docs/wiki/findings/` e `docs/findings/` | `docs/studies/<slug>/notes/` com `type: finding` |
| `docs/protocol.md` | `docs/studies/<slug>/writing/protocol.md` |
| `docs/decisions/` | `docs/studies/<slug>/decisions/` |

Em `docs/Research Project Structure.md`, atualize a tabela de módulos para os fatos do repo: `code`, `data`, `notebooks`, `ml`, `clinical` existem; `extended-wiki`, `brainstorm-pipeline`, `peer-review-loop`, `versioned-milestones`, `specify-workflow` são convenção documentada sem `_module.toml`. Remova a promessa de `findings/` como diretório.

- [ ] **Step 4: Regenerar índices, rodar e commitar**

```bash
uv run python .github/scripts/gen_indexes.py
uv run pytest -v
git add skills docs ARCHITECTURE.md README.md tests/unit/test_guidelines_present.py
git commit -m "docs: prosa das skills e do repo alinhada ao layout por escopo"
```

---

### Task 14: ADRs, constitution e ROADMAP

**Files:**
- Create: `docs/adr/adr-0022-layout-por-escopo.md`, `docs/adr/adr-0023-finding-como-type.md`, `docs/adr/adr-0024-escopo-desde-o-init.md`
- Modify: `docs/constitution.md:65`
- Modify: `docs/adr/adr-0014-findings-canonico.md` (marcar substituído)
- Modify: `ROADMAP.md`

**Interfaces:** documentação de governança.

- [ ] **Step 1: Escrever ADR-0022**

```markdown
# ADR-0022 — Layout por escopo: `docs/` como raiz única de leitura

- Status: aceito
- Data: 2026-08-09
- Origem: [[2026-08-08-layout-por-escopo-design]]

## Contexto
O `pj_*` tinha dois topos de leitura (`docs/` e `references/`), o manuscrito não tinha casa,
e o `pj_base` embutia estrutura de código que 4 de 5 arquétipos de pesquisador nunca abrem.

## Decisão
`docs/` é a raiz única de leitura. A bibliografia é do PROJETO e vive em `docs/references/`,
com `papers/<citekey>/` no lugar de `notes/<citekey>/`. `core/pj_layout.py` é a autoridade
única de caminho, com `find_pj_root` (sentinela `.claude/pj_config.toml`) separado de
`find_scope_root` (posição). Tudo que serve só a alguns arquétipos vira camada com gatilho
observável. Corte limpo: layout legado falha com convite à adequação agêntica.

## Consequências
O literal `"references"` não desaparece do código — reaparece como exclusão de varredura no
lint. `paper connect` segue exclusivo do Better BibTeX; o contrato do núcleo é BibTeX.
Projeto legado exige reconfigurar o autoexport do BBT, que guarda caminho absoluto.
```

- [ ] **Step 2: Escrever ADR-0023 e ADR-0024**

ADR-0023 registra finding como `type:` em `notes/` e marca **ADR-0014 como substituído**.
ADR-0024 registra o escopo presente desde o `init` e a promoção que deixou de existir.

- [ ] **Step 3: Emendar a constitution**

`docs/constitution.md:65`: `references/notes/` → `docs/references/papers/`. Acrescente ao PR
um **Sync impact report** registrando que o conserto de `stats.py` é o que impede a remoção
da chave `references` do payload, proibida por `constitution.md:62`.

Em `docs/adr/adr-0014-findings-canonico.md`, acrescente ao topo:
`- Status: substituído por [ADR-0023](adr-0023-finding-como-type.md)`

- [ ] **Step 4: Regenerar índices e commitar**

```bash
uv run python .github/scripts/gen_indexes.py
git add docs/adr docs/constitution.md docs/_index.md ROADMAP.md
git commit -m "docs: ADR-0022/0023/0024 + emenda da constitution"
```

---

### Task 15: Release 0.65.0

**Files:**
- Modify: `src/prumo_assist/_version.py`
- Modify: `CHANGELOG.md`, `CITATION.cff`
- Modify: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (via script, nunca à mão)

- [ ] **Step 1: Bump e propagação**

```bash
sed -i '' 's/__version__ = "0.64.1"/__version__ = "0.65.0"/' src/prumo_assist/_version.py
uv run python .github/scripts/sync_manifest_version.py
uv run python .github/scripts/validate_manifests.py
uv run python .github/scripts/sync_manifest_version.py --check
```

- [ ] **Step 2: CHANGELOG**

Entrada `## [0.65.0] - 2026-08-09` com seção `⚠ Breaking` citando: a bibliografia sob
`docs/references/`, `papers/` no lugar de `notes/`, o escopo `docs/studies/<slug>/`, o
`pj_base` sem estrutura de código, e o **passo manual no Zotero** (Preferences → Better
BibTeX → Automatic export) sem o qual o BBT recria `references/` na raiz. Referencie
ADR-0022, ADR-0023, ADR-0024 e o Princípio VI da constitution.

- [ ] **Step 3: `CITATION.cff`**

Campo `version: 0.65.0`.

- [ ] **Step 4: Verificação final**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run python .github/scripts/gen_indexes.py --check
```
Expected: tudo verde.

- [ ] **Step 5: Commit e PR**

```bash
git add -A
git commit -m "release: 0.65.0 - layout por escopo"
gh pr create --title "release: 0.65.0 - layout por escopo" --body "..."
```

---

## Self-Review

**Cobertura da spec:**

| seção da spec | task |
|---|---|
| núcleo universal (7 entradas) | 11 |
| escopo por posição, `find_pj_root`/`find_scope_root` | 1 |
| bibliografia do projeto, `papers/` | 1, 2, 3 |
| lint por escopo, `bib_missing` warning, `multiple_primary` opt-in | 5 |
| `stats` com `by_scope` | 6 |
| findings como `type:` nos dois lados | 7 |
| figuras no export + guarda de sobrescrita | 8 |
| `bibliography` literal invariante | 13 |
| `references/.gitignore` próprio | 11 |
| `pdfs/` flat, inalterado | — (nenhuma mudança necessária) |
| camadas com gatilho | 12 |
| anchor do `clinical` | 12 |
| adequação agêntica (mensagem de erro) | 1 (`assert_current_layout`), 10 (`doctor`) |
| ADRs, constitution, RPS | 13, 14 |
| release | 15 |

**Consistência de tipos:** `find_pj_root`/`find_scope_root` devolvem `Path` e levantam
`PjRootNotFoundError` (Task 1) — usados com esse contrato nas Tasks 3, 4, 7, 8, 9, 10.
`archive_as_finding` recebe `scope` (Task 7), consumido por `compose._read_findings(scope)`
na mesma task. `WikiIssue.scope` é `str | None = None` (Task 5), lido em `test_lint`.

**Ordem:** Tasks 1-2 são pré-requisito de tudo. 3-9 são independentes entre si e podem
paralelizar. 10 depende de 1. 11-12 dependem de 10 (o `init` precisa da árvore).
13-15 fecham.
