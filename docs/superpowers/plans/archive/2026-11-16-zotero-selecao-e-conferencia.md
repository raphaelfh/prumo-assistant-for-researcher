---
status: implemented
verified: 2026-11-16
release: "PATCH (ADR-0015) — pendente do corte"
spec: "[[2026-11-16-vinculo-zotero-design]]"
---

> **Fechamento (2026-11-16).** Tasks 1–6 entregues no branch `feat/painel-cartao-e-grupos`: `domains/paper/selection.py` (conector), `domains/paper/linkcheck.py` (pull export), `connect_resolved`/`record_resolved` em `connect.py`, `--selected` no CLI e `selected` na tool `paper_connect`, aviso no `doctor`, `live=True` no `status` (CLI e tool `project_status`), ADR-0044 emendada (decisões 5–7), skill `paper` (modo library), onboarding e CHANGELOG. Verificação: pytest, ruff, `ruff format --check`, mypy e `gen_indexes --check` limpos. A sonda dos dois endpoints foi feita ao vivo, só lendo, num Zotero com Better BibTeX; o fluxo inteiro (`connect --selected` mutando o Zotero de verdade, aviso no painel do Desktop) não foi exercitado.

# Zotero: connect pela seleção, conferência pelo pull e aviso de seleção divergente

**Goal:** itens 5–7 da emenda de `docs/superpowers/specs/2026-11-16-vinculo-zotero-design.md`.

**Architecture:** `domains/paper/selection.py` lê o servidor do conector (seam `_http_post_json`)
e resolve a seleção contra o `user.groups` do `connect.py`; `domains/paper/linkcheck.py` faz o pull
export (seam `_http_get`). `connect.py` ganha `connect_resolved`/`record_resolved` (Guarda 1 antes
do resolver). O `doctor` (`cli.py`) chama `check_link`; o `status` chama `selection_mismatch` com
`live=True`.

## Tasks

- [x] 1. `selection.py` + testes (TDD): `selected_collection`, `resolve_selected`, `selection_mismatch`.
- [x] 2. `connect.py`: `connect_resolved`, `record_resolved`; CLI `--selected`; tool MCP `selected`.
- [x] 3. `linkcheck.py` + testes; aviso no `doctor`.
- [x] 4. `status.py`: `live`, `LibraryStatus.zotero_elsewhere`, resumo; CLI e tool passam `live=True`.
- [x] 5. ADR-0044 emendada, skill `paper` (modo library), ARCHITECTURE, CHANGELOG, índices.
- [x] 6. pytest, ruff, mypy, `gen_indexes --check`.
