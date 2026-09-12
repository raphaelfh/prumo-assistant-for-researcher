---
status: implemented
verified: 2026-09-12
release: "pendente — PATCH (ADR-0015), junto do [Não publicado]"
spec: "[[2026-09-12-safe-outputs-design]]"
---

> **Fechamento (2026-09-12).** Tasks 1–4 implementadas em TDD: rule sempre-on `templates/pj_base/.claude/rules/safe_outputs.md`, `core/safe_outputs.py` com a issue `[dado_versionavel]` ligada no `doctor`, e o `update` levando a rule a projeto antigo pelo caminho de arquivo ausente. Verificação: suíte inteira, ruff, mypy e `gen_indexes --check` limpos.

# Safe outputs mínimo — Implementation Plan

**Spec:** [[2026-09-12-safe-outputs-design]]

- [x] Task 1 — Rule: teste em `tests/unit/test_cli_init.py` (init cria a rule) e em
  `tests/unit/test_cli_update.py` (update copia a rule para projeto antigo); criar
  `templates/pj_base/.claude/rules/safe_outputs.md`; atualizar o comentário de
  `COMPARE_PREFIX` em `core/scaffold.py`.
- [x] Task 2 — Check: `tests/unit/core/test_safe_outputs.py` (fora de git silencia; ignorado
  e limpo passa; não ignorado falha; rastreado falha; `.gitkeep` tolerado), com `_git`
  mockado; implementar `core/safe_outputs.py::safe_outputs_issues`.
- [x] Task 3 — Ligar no `doctor` (`cli.py`) e teste de integração em
  `tests/unit/test_cli_doctor.py`.
- [x] Task 4 — Verificação: pytest, ruff, mypy, `gen_indexes` (`--check`); arquivar plano.
