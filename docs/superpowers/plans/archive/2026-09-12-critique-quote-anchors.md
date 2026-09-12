---
status: implemented
verified: 2026-09-12
release: "pendente — PATCH (ADR-0015), junto do [Não publicado]"
spec: "[[2026-09-12-critique-quote-anchors-design]]"
---

> **Fechamento (2026-09-12).** Tasks 1–3 implementadas em TDD. Verificação: pytest, ruff, mypy e `gen_indexes --check` rodados antes do commit.

# Achados ancorados em trecho literal — plano

1. **Testes primeiro** (`tests/unit/test_contracts.py`): quote válido, parafraseado, acima de 25 palavras, campos ausentes, draft ilegível, sample do plugin validando com o draft presente.
2. **Código:** campos opcionais em `domains/write/schemas/v1.py`; `_check_quotes` em `contracts.py`, chamado após `model_validate` quando o modelo é `PeerReviewReport`.
3. **Texto:** `agents/reviewer.md` (quote + sources_read no JSON e uma linha no procedimento), `skills/review/modes/critique.md` (render do trecho e das fontes; checagem manual sem CLI), `sample_report.json` com `quote` e `sources_read`.
