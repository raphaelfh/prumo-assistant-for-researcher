---
status: implemented
verified: 2026-09-12
release: "pendente — PATCH (ADR-0015), junto do [Não publicado]"
spec: "[[2026-09-12-drift-manuscrito-protocolo-design]]"
---

> **Fechamento (2026-09-12).** T1–T6 implementadas em TDD: `domains/protocol/drift.py`, `ops.manuscript_drift`, chave `drift` em `prumo protocol diff`. Smoke read-only no `pj_piloto_questionario` devolve exatamente as três contradições do A/B (janela, testes qui-quadrado/Cochran–Armitage, pré-especificação). Pendente: corte do release.

# Drift manuscrito × protocolo — plano

**Spec:** `docs/superpowers/specs/2026-09-12-drift-manuscrito-protocolo-design.md`

- [x] T1. Fixtures com excertos mínimos (`tests/fixtures/protocol_drift/`).
- [x] T2. `tests/unit/protocol/test_drift.py` (vermelho): três contradições; textos concordantes sem drift; extração bilíngue de janelas, testes e polaridade.
- [x] T3. `domains/protocol/drift.py` (funções puras) + `ops.manuscript_drift(scope, draft=None)` + re-export em `api.py`.
- [x] T4. `protocol diff` emite `drift` (JSON e humano); `path` `.md` restringe o draft. Teste de CLI.
- [x] T5. Skill `protocol` (operations-advanced) cita a chave `drift`.
- [x] T6. pytest, ruff, mypy, gen_indexes `--check`; arquivar plano; commit.
