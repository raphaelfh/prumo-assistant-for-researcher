---
status: implemented
verified: 2026-09-12
release: "pendente — PATCH (ADR-0015), junto do [Não publicado]"
spec: "[[2026-09-12-proveniencia-ligada-design]]"
---

> **Fechamento (2026-09-12).** Tasks 1–5 implementadas em TDD. `_meta` carimbado em findings, sessão de study, `write draft` (3 modos) e `citemap.json`; disclosure lê o canônico com fallback só para `extracted_model`; `TraceWriter` removido (ADR-0036).

# Proveniência ligada — Implementation Plan

**Goal:** todo produtor de artefato gerado carimba `_meta` via `build_meta`; disclosure lê o canônico.

- [x] **Task 1 — findings.** Teste: frontmatter tem `_meta.skill == generator`, sem `generator` solto. Código: `archive_as_finding` grava `_meta`.
- [x] **Task 2 — study.** Teste: `create_session_log` grava `_meta` com `schema: SessionLog/v1`. Código: `_render_skeleton`.
- [x] **Task 3 — write draft.** Testes: drafts preserva frontmatter e corpo; into preserva texto humano e o bloco `write:begin`. Código: `_stamp_meta` em `compose.write_output`.
- [x] **Task 4 — export.** Teste: `citemap.json` tem `_meta`. Código: campo opcional `meta` (alias `_meta`) em `CiteMapFile/v1` (adição forward-only), preenchido em `_emit_review_sidecars`.
- [x] **Task 5 — disclosure + trace.** Teste de fixture mista (finding e draft canônicos + extract legado). Código: remove leitura de `generator`, OU de `human_reviewed`; remove `TraceWriter` e testes; ADR-0036.
