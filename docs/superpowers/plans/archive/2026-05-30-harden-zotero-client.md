---
status: implemented
verified: 2026-06-11
release: "0.61.0"
---

# Harden `zotero.py` Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar dois riscos do cliente Zotero (`src/prumo_assist/domains/paper/zotero.py`): (1) cobertura de teste rasa — `resolve_citekey`, `fetch_children`, `split_children`, `html_to_markdown`, `render_note`, `check_zotero_running` nunca são testados diretamente (só via mock dentro de `sync_annotations`), de modo que uma mudança no shape do JSON-RPC do Better BibTeX quebraria silenciosamente; (2) host hardcoded `http://localhost:23119` sem override, divergindo dos filtros Lua (`127.0.0.1`) e impossibilitando rodar contra uma porta diferente.

**Architecture:**
- Os helpers HTTP (`_http_get_json`, `_http_post_json`, `urlopen` via `check_zotero_running`) já são *seams* naturais. Os testes vão mocká-los com `unittest.mock.patch` (mesma técnica já usada em `test_zotero.py`), exercitando o parsing real de `resolve_citekey`/`fetch_children` contra payloads JSON-RPC realistas.
- O host vira configurável: `_zotero_base()` lê `PRUMO_ZOTERO_BASE` (default `http://127.0.0.1:23119`). `ZOTERO_BASE`/`BBT_RPC`/`ZOTERO_API` passam de constantes de módulo para funções, e os call-sites passam a chamá-las. Isso unifica o host com os filtros Lua e permite testes/ambientes alternativos sem tocar código.

**Tech Stack:** Python 3.11+ stdlib (`urllib`, `os`), pytest, `unittest.mock`, ruff, mypy strict. `uv` como runner.

---

## File Structure

| Caminho | Ação | Responsabilidade |
|---|---|---|
| `src/prumo_assist/domains/paper/zotero.py` | **Modify** | `_zotero_base()`/`_bbt_rpc()`/`_zotero_api()` lendo env; call-sites atualizados |
| `tests/unit/paper/test_zotero_client.py` | **Create** | tests diretos de `resolve_citekey`, `fetch_children`, `split_children`, `html_to_markdown`, `render_note`, `check_zotero_running` e do override de host |

> Nota: `tests/unit/paper/test_zotero.py` (sync_annotations) permanece intacto. Este plano só **adiciona** um arquivo de teste e refatora o host em `zotero.py` sem mudar a assinatura pública das funções.

---

## Task 1: Tests diretos das funções puras (`html_to_markdown`, `split_children`, `render_note`)

**Files:**
- Create: `tests/unit/paper/test_zotero_client.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/paper/test_zotero_client.py`:

```python
"""Tests diretos das funções de cliente/render do zotero.py (sem rede real)."""

from __future__ import annotations

from prumo_assist.domains.paper.zotero import (
    html_to_markdown,
    render_note,
    split_children,
)


def test_html_to_markdown_basic_formatting() -> None:
    html = "<p>Olá <strong>mundo</strong> e <em>itálico</em></p>"
    out = html_to_markdown(html)
    assert "**mundo**" in out
    assert "*itálico*" in out
    assert "<p>" not in out


def test_html_to_markdown_headings_and_lists() -> None:
    html = "<h2>Título</h2><ul><li>um</li><li>dois</li></ul>"
    out = html_to_markdown(html)
    assert "## Título" in out
    assert "- um" in out
    assert "- dois" in out


def test_html_to_markdown_unescapes_entities() -> None:
    html = "<p>a &amp; b &lt; c</p>"
    out = html_to_markdown(html)
    assert "a & b < c" in out


def test_html_to_markdown_collapses_blank_lines() -> None:
    html = "<p>a</p><p></p><p></p><p>b</p>"
    out = html_to_markdown(html)
    assert "\n\n\n" not in out


def test_split_children_separates_annotations_and_notes() -> None:
    children = [
        {"itemType": "annotation", "annotationText": "x"},
        {"itemType": "note", "note": "<p>y</p>"},
        {"itemType": "attachment", "filename": "z.pdf"},
    ]
    annotations, notes = split_children(children)
    assert len(annotations) == 1
    assert len(notes) == 1
    # attachment descartado
    assert annotations[0]["annotationText"] == "x"
    assert notes[0]["note"] == "<p>y</p>"


def test_split_children_empty() -> None:
    annotations, notes = split_children([])
    assert annotations == []
    assert notes == []


def test_render_note_extracts_title_from_first_line() -> None:
    note = {"note": "<h1>Minha nota</h1><p>corpo da nota</p>"}
    lines = render_note(note)
    joined = "\n".join(lines)
    assert "Minha nota" in joined
    assert "corpo da nota" in joined


def test_render_note_empty_marks_vazia() -> None:
    note = {"note": ""}
    lines = render_note(note)
    joined = "\n".join(lines)
    assert "vazia" in joined.lower()
```

- [ ] **Step 2: Run tests to verify the suite is green or red per behavior**

Run: `uv run pytest tests/unit/paper/test_zotero_client.py -v`
Expected: these test **pure functions that already exist** — they should PASS immediately. If any FAIL, it has surfaced a real bug in `html_to_markdown`/`split_children`/`render_note`; fix the function (not the test) before continuing, then re-run.

(If all pass on first run, that is the intended outcome — this task locks in behavior that had zero direct coverage.)

- [ ] **Step 3: Lint + types**

Run: `uv run ruff check tests/unit/paper/test_zotero_client.py`
Run: `uv run --extra dev mypy tests/unit/paper/test_zotero_client.py`
Expected: clean

- [ ] **Step 4: Commit**

```bash
git add tests/unit/paper/test_zotero_client.py
git commit -m "test(paper): direct coverage for html_to_markdown, split_children, render_note"
```

---

## Task 2: Tests de `resolve_citekey` contra payloads JSON-RPC realistas

**Files:**
- Modify: `tests/unit/paper/test_zotero_client.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/paper/test_zotero_client.py`:

```python
from unittest.mock import patch

import urllib.error

from prumo_assist.domains.paper.zotero import resolve_citekey


def test_resolve_citekey_exact_match() -> None:
    rpc_response = {
        "jsonrpc": "2.0",
        "result": [
            {"citationKey": "smith2024", "itemKey": "ABCD1234", "library": {"id": 1}},
        ],
        "id": 1,
    }
    with patch("prumo_assist.domains.paper.zotero._http_post_json", return_value=rpc_response):
        result = resolve_citekey("smith2024")
    assert result == (1, "ABCD1234")


def test_resolve_citekey_falls_back_to_first_result() -> None:
    rpc_response = {
        "jsonrpc": "2.0",
        "result": [
            {"citationKey": "other2023", "itemKey": "ZZZZ9999", "library": {"id": 3}},
        ],
        "id": 1,
    }
    with patch("prumo_assist.domains.paper.zotero._http_post_json", return_value=rpc_response):
        result = resolve_citekey("smith2024")
    assert result == (3, "ZZZZ9999")


def test_resolve_citekey_empty_result_is_none() -> None:
    with patch(
        "prumo_assist.domains.paper.zotero._http_post_json",
        return_value={"jsonrpc": "2.0", "result": [], "id": 1},
    ):
        assert resolve_citekey("missing") is None


def test_resolve_citekey_network_error_is_none() -> None:
    with patch(
        "prumo_assist.domains.paper.zotero._http_post_json",
        side_effect=urllib.error.URLError("connection refused"),
    ):
        assert resolve_citekey("smith2024") is None


def test_resolve_citekey_non_dict_response_is_none() -> None:
    with patch("prumo_assist.domains.paper.zotero._http_post_json", return_value=["unexpected"]):
        assert resolve_citekey("smith2024") is None
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/unit/paper/test_zotero_client.py -k resolve_citekey -v`
Expected: PASS (exercises the real parsing in `resolve_citekey`, lines 78-106). If `test_resolve_citekey_falls_back_to_first_result` FAILS, re-read lines 100-105 — the fallback uses the first item's library/key; align the test's expectation with the actual documented fallback behavior (do not weaken the exact-match test).

- [ ] **Step 3: Lint + types**

Run: `uv run ruff check tests/unit/paper/test_zotero_client.py`
Run: `uv run --extra dev mypy tests/unit/paper/test_zotero_client.py`
Expected: clean

- [ ] **Step 4: Commit**

```bash
git add tests/unit/paper/test_zotero_client.py
git commit -m "test(paper): cover resolve_citekey parsing + fallbacks"
```

---

## Task 3: Tests de `fetch_children` e `check_zotero_running`

**Files:**
- Modify: `tests/unit/paper/test_zotero_client.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/paper/test_zotero_client.py`:

```python
from prumo_assist.domains.paper.zotero import check_zotero_running, fetch_children


def test_fetch_children_extracts_data_field() -> None:
    api_response = [
        {"key": "C1", "data": {"itemType": "annotation", "annotationText": "x"}},
        {"key": "C2", "data": {"itemType": "note", "note": "<p>y</p>"}},
        {"key": "C3", "no_data_here": True},  # ignorado
    ]
    with patch("prumo_assist.domains.paper.zotero._http_get_json", return_value=api_response):
        out = fetch_children(1, "PARENT01")
    assert len(out) == 2
    assert out[0]["itemType"] == "annotation"
    assert out[1]["itemType"] == "note"


def test_fetch_children_non_list_response_is_empty() -> None:
    with patch("prumo_assist.domains.paper.zotero._http_get_json", return_value={"error": "x"}):
        assert fetch_children(1, "PARENT01") == []


def test_fetch_children_network_error_is_empty() -> None:
    with patch(
        "prumo_assist.domains.paper.zotero._http_get_json",
        side_effect=urllib.error.URLError("refused"),
    ):
        assert fetch_children(1, "PARENT01") == []


def test_check_zotero_running_true_when_urlopen_succeeds() -> None:
    with patch("prumo_assist.domains.paper.zotero.urllib.request.urlopen"):
        assert check_zotero_running() is True


def test_check_zotero_running_false_on_urlerror() -> None:
    with patch(
        "prumo_assist.domains.paper.zotero.urllib.request.urlopen",
        side_effect=urllib.error.URLError("refused"),
    ):
        assert check_zotero_running() is False


def test_check_zotero_running_false_on_timeout() -> None:
    with patch(
        "prumo_assist.domains.paper.zotero.urllib.request.urlopen",
        side_effect=TimeoutError(),
    ):
        assert check_zotero_running() is False
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/unit/paper/test_zotero_client.py -k "fetch_children or check_zotero_running" -v`
Expected: PASS (exercises `fetch_children` lines 114-128 and `check_zotero_running` lines 64-70).

- [ ] **Step 3: Lint + types**

Run: `uv run ruff check tests/unit/paper/test_zotero_client.py`
Run: `uv run --extra dev mypy tests/unit/paper/test_zotero_client.py`
Expected: clean

- [ ] **Step 4: Commit**

```bash
git add tests/unit/paper/test_zotero_client.py
git commit -m "test(paper): cover fetch_children + check_zotero_running"
```

---

## Task 4: Host configurável via `PRUMO_ZOTERO_BASE` (default `127.0.0.1`)

**Files:**
- Modify: `src/prumo_assist/domains/paper/zotero.py` (constantes → funções; call-sites)
- Modify: `tests/unit/paper/test_zotero_client.py` (tests do override)

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/paper/test_zotero_client.py`:

```python
import importlib

import prumo_assist.domains.paper.zotero as zot


def test_zotero_base_default_is_loopback_ip(monkeypatch) -> None:
    monkeypatch.delenv("PRUMO_ZOTERO_BASE", raising=False)
    assert zot._zotero_base() == "http://127.0.0.1:23119"


def test_zotero_base_env_override(monkeypatch) -> None:
    monkeypatch.setenv("PRUMO_ZOTERO_BASE", "http://localhost:9999")
    assert zot._zotero_base() == "http://localhost:9999"


def test_bbt_rpc_and_api_follow_base(monkeypatch) -> None:
    monkeypatch.setenv("PRUMO_ZOTERO_BASE", "http://example.test:1234")
    assert zot._bbt_rpc() == "http://example.test:1234/better-bibtex/json-rpc"
    assert zot._zotero_api() == "http://example.test:1234/api"


def test_fetch_children_uses_overridden_base(monkeypatch) -> None:
    monkeypatch.setenv("PRUMO_ZOTERO_BASE", "http://example.test:1234")
    captured: dict[str, str] = {}

    def fake_get(url: str, timeout: float = 10.0) -> object:
        captured["url"] = url
        return []

    monkeypatch.setattr(zot, "_http_get_json", fake_get)
    zot.fetch_children(1, "PARENT01")
    assert captured["url"].startswith("http://example.test:1234/api/")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/paper/test_zotero_client.py -k "zotero_base or bbt_rpc or overridden_base" -v`
Expected: FAIL — `_zotero_base`/`_bbt_rpc`/`_zotero_api` not defined; default is still `localhost`.

- [ ] **Step 3: Refactor the host constants into env-aware functions**

In `src/prumo_assist/domains/paper/zotero.py`, replace the three module constants (lines 23-25):

```python
ZOTERO_BASE = "http://localhost:23119"
BBT_RPC = f"{ZOTERO_BASE}/better-bibtex/json-rpc"
ZOTERO_API = f"{ZOTERO_BASE}/api"
```

with:

```python
import os

_DEFAULT_ZOTERO_BASE = "http://127.0.0.1:23119"


def _zotero_base() -> str:
    """Base URL da API local do Zotero. Override via ``PRUMO_ZOTERO_BASE``.

    Default ``http://127.0.0.1:23119`` — unifica com os filtros Lua e evita
    surpresas de resolução IPv6 (``::1``) que ``localhost`` às vezes traz.
    """
    return os.environ.get("PRUMO_ZOTERO_BASE", _DEFAULT_ZOTERO_BASE)


def _bbt_rpc() -> str:
    """Endpoint JSON-RPC do Better BibTeX."""
    return f"{_zotero_base()}/better-bibtex/json-rpc"


def _zotero_api() -> str:
    """Base da API local do Zotero (``/api``)."""
    return f"{_zotero_base()}/api"
```

Add `import os` at the top with the other stdlib imports (after `import json` on line 12) — the inline `import os` above is shown for locality; place the actual statement in the import block and delete the inline duplicate.

- [ ] **Step 4: Update the call-sites**

In the same file, update every reference to the old constants:

1. `check_zotero_running` (line 67) — `urllib.request.urlopen(ZOTERO_BASE, timeout=2)` becomes:

```python
        urllib.request.urlopen(_zotero_base(), timeout=2)
```

2. `resolve_citekey` (line 87) — `resp = _http_post_json(BBT_RPC, payload)` becomes:

```python
        resp = _http_post_json(_bbt_rpc(), payload)
```

3. `fetch_children` (line 116) — the URL f-string `f"{ZOTERO_API}/users/..."` becomes:

```python
    url = f"{_zotero_api()}/users/{library_id}/items/{item_key}/children?format=json&limit=200"
```

4. `sync_annotations` error message (line 267) — `f"Zotero não está rodando em {ZOTERO_BASE}. ..."` becomes:

```python
            f"Zotero não está rodando em {_zotero_base()}. Abra o Zotero 9 e tente de novo."
```

5. If Plan A (`sync_notes`) has already landed, update its identical error message the same way (search the file for `ZOTERO_BASE`). After this task, `grep -n "ZOTERO_BASE" src/prumo_assist/domains/paper/zotero.py` must return **only** `_DEFAULT_ZOTERO_BASE` and `_zotero_base`.

- [ ] **Step 5: Run the full zotero test set**

Run: `uv run pytest tests/unit/paper/test_zotero_client.py tests/unit/paper/test_zotero.py -v`
Expected: all PASS (existing `test_zotero.py` still green — it patches `check_zotero_running`/`resolve_citekey`/`fetch_children`, which are unaffected by the host refactor).

- [ ] **Step 6: Verify no dangling constant references**

Run: `grep -n "ZOTERO_BASE\|BBT_RPC\|ZOTERO_API" src/prumo_assist/domains/paper/zotero.py`
Expected: only `_DEFAULT_ZOTERO_BASE`, `_zotero_base`, `_bbt_rpc`, `_zotero_api` appear — no bare `ZOTERO_BASE`/`BBT_RPC`/`ZOTERO_API`.

- [ ] **Step 7: Lint + types**

Run: `uv run ruff check src/prumo_assist/domains/paper/zotero.py tests/unit/paper/test_zotero_client.py`
Run: `uv run --extra dev mypy src/prumo_assist/domains/paper/zotero.py`
Expected: clean

- [ ] **Step 8: Commit**

```bash
git add src/prumo_assist/domains/paper/zotero.py tests/unit/paper/test_zotero_client.py
git commit -m "feat(paper): configurable Zotero host via PRUMO_ZOTERO_BASE (default 127.0.0.1)"
```

---

## Task 5: Alinhar `core/deps.py` (se Plano B já tiver landado) e documentar a env var

**Files:**
- Modify: `src/prumo_assist/core/deps.py` (somente se existir — Plano B)
- Modify: `README.md` (nota sobre `PRUMO_ZOTERO_BASE`)

- [ ] **Step 1: Conditionally align the deps port with the env var**

Check whether Plan B landed:

Run: `test -f src/prumo_assist/core/deps.py && echo EXISTS || echo ABSENT`

If `ABSENT`, skip to Step 3 (nothing to align). If `EXISTS`, make the Zotero check honor the same override so `doctor` and the client agree. In `src/prumo_assist/core/deps.py`, replace the hardcoded `ZOTERO_HOST`/`ZOTERO_PORT` usage inside `check_external_deps` with a parse of the env var:

```python
import os
from urllib.parse import urlparse

_DEFAULT_ZOTERO_BASE = "http://127.0.0.1:23119"


def _zotero_host_port() -> tuple[str, int]:
    """Host/porta da API local do Zotero, honrando ``PRUMO_ZOTERO_BASE``."""
    base = os.environ.get("PRUMO_ZOTERO_BASE", _DEFAULT_ZOTERO_BASE)
    parsed = urlparse(base)
    return parsed.hostname or "127.0.0.1", parsed.port or 23119
```

Then inside `check_external_deps`, replace `zotero_up = _port_open(ZOTERO_HOST, ZOTERO_PORT)` with:

```python
    host, port = _zotero_host_port()
    zotero_up = _port_open(host, port)
```

and use `host`/`port` in the `detail`/`hint` f-strings. Keep the module-level `ZOTERO_HOST`/`ZOTERO_PORT` constants for backward reference or delete them if unused (run `grep -n "ZOTERO_HOST\|ZOTERO_PORT" src/prumo_assist/core/deps.py` to confirm before deleting).

- [ ] **Step 2: Run deps tests (only if Plan B landed)**

Run: `uv run pytest tests/unit/core/test_deps.py -v`
Expected: still PASS (the existing tests patch `_port_open`, so the parse change is transparent). If you want explicit coverage, add:

```python
def test_zotero_check_honors_env_override(monkeypatch) -> None:
    monkeypatch.setenv("PRUMO_ZOTERO_BASE", "http://example.test:1234")
    captured: dict[str, object] = {}

    def fake_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
        captured["host"] = host
        captured["port"] = port
        return False

    monkeypatch.setattr("prumo_assist.core.deps._port_open", fake_port_open)
    monkeypatch.setattr("prumo_assist.core.deps._binary_on_path", lambda name: None)
    check_external_deps()
    assert captured == {"host": "example.test", "port": 1234}
```

- [ ] **Step 3: Document the env var in README**

In `README.md`, in the Zotero row of the "Pré-requisitos externos" table (added by Plan B) — or, if Plan B has not landed, in the "Stack implícita" bullet about Zotero — append:

```markdown
> [!note]
> Por padrão o prumo fala com o Zotero em `http://127.0.0.1:23119`. Para usar
> outra porta/host, exporte `PRUMO_ZOTERO_BASE` (ex.:
> `export PRUMO_ZOTERO_BASE=http://localhost:23200`).
```

- [ ] **Step 4: Commit**

```bash
git add src/prumo_assist/core/deps.py README.md
git commit -m "feat: align doctor's zotero check with PRUMO_ZOTERO_BASE + document env var"
```

(If `core/deps.py` did not exist, `git add` only `README.md`.)

---

## Task 6: Suíte completa + verificação final

**Files:** none (verification only)

- [ ] **Step 1: Full test suite**

Run: `uv run pytest -q`
Expected: all PASS

- [ ] **Step 2: Coverage check on zotero.py (optional but recommended)**

Run: `uv run pytest tests/unit/paper/test_zotero_client.py tests/unit/paper/test_zotero.py --cov=prumo_assist.domains.paper.zotero --cov-report=term-missing`
Expected: every public function in `zotero.py` now has at least one direct test; note any remaining `Missing` lines (acceptable: the inner bodies of `_http_get_json`/`_http_post_json`, which wrap stdlib `urlopen` and are exercised only by integration with a live Zotero).

- [ ] **Step 3: Lint + types whole tree**

Run: `uv run ruff check src tests`
Run: `uv run --extra dev mypy src tests`
Expected: clean

- [ ] **Step 4: Confirm default host changed end-to-end**

Run: `uv run python -c "import prumo_assist.domains.paper.zotero as z; print(z._zotero_base()); print(z._bbt_rpc()); print(z._zotero_api())"`
Expected:
```
http://127.0.0.1:23119
http://127.0.0.1:23119/better-bibtex/json-rpc
http://127.0.0.1:23119/api
```

---

## Self-Review notes (for the implementer)

- **Scope:** Covers gaps #4 (shallow network-helper coverage) and #5 (host hardcoded / `localhost` vs `127.0.0.1`) from the audit.
- **Behavior-preserving:** No public function signature changes. `sync_annotations`/`sync_notes` keep working; existing `test_zotero.py` is untouched and must stay green (it patches the high-level functions, not the host helpers).
- **Ordering with other plans:** Independent of Plan A and Plan B. If run after Plan A, Step 4.5 also fixes `sync_notes`'s error string. Task 5 is conditional on Plan B's `core/deps.py` — explicitly guarded with a `test -f` check so it never references a file that doesn't exist.
- **Why default flips to `127.0.0.1`:** matches the vendored Lua filters and CHANGELOG wording (`127.0.0.1:23119`) and avoids `localhost`→`::1` IPv6 resolution stalls on some macOS setups. Anyone depending on the old literal can set `PRUMO_ZOTERO_BASE=http://localhost:23119`.
- **Type consistency:** host helpers are `_zotero_base()`/`_bbt_rpc()`/`_zotero_api()` everywhere (no bare constants remain — verified by the grep in Task 4 Step 6).
```
