---
status: implemented
verified: 2026-09-12
release: "pendente — PATCH (ADR-0015), junto do [Não publicado]"
spec: "[[2026-09-12-recalculo-estatisticas-lint-design]]"
---

> **Nota de arquivamento (2026-09-12).** Implementado. No draft real
> (`paper-piloto-submission.md`) o lint conferiu 13 estatísticas e no
> `material_suplementar_piloto.md` centenas de valores q (por família e globais), zero divergências.

# Recálculo de estatísticas no lint — Implementation Plan

**Goal:** `prumo wiki lint` emite `stat_mismatch` quando %, IC de Wilson ou q de BH relatados
não batem com o recálculo.

1. Fixtures em `tests/fixtures/wiki/`: recorte real (frases do draft + uma família do
   material suplementar) e sintético (IC errado, q errado).
2. Testes vermelhos em `tests/unit/wiki/test_stats_check.py`: `wilson_interval`,
   `benjamini_hochberg`, recorte real sem divergência, sintético com as duas divergências,
   não parseável pulado, agrupamento `global` entre tabelas, integração via `lint()`.
3. `src/par/domains/wiki/stats_check.py`: regex de proporção, parser de tabela,
   BH com limites de arredondamento, `stat_mismatches(text) -> list[str]`.
4. `lint.py`: uma chamada no laço de páginas de `_lint_scope`.
5. `skills/wiki/modes/lint.md`: acrescentar `stat_mismatch` à lista de códigos.
6. Verificar (pytest, ruff, mypy, gen_indexes) e rodar contra o draft real (read-only).
