---
status: implemented
verified: 2026-09-12
release: "pendente — PATCH (ADR-0015), junto do [Não publicado]"
spec: "[[2026-09-12-perfis-disclosure-por-periodico-design]]"
---

> **Fechamento (2026-09-12).** Tasks 1–4 implementadas em TDD: `venue_policies.toml` com ICMJE, JAMA e BMJ conferidos na fonte, `load_venue_profiles` com validação, `--venue` no `write disclosure` e modo atualizado. NEJM e The Lancet ficaram de fora (páginas primárias com 403). Verificação: suíte inteira, ruff, mypy e `gen_indexes --check` limpos.

# Perfis de disclosure por periódico — Implementation Plan

**Spec:** [[2026-09-12-perfis-disclosure-por-periodico-design]]

- [x] Task 1 — Testes em `tests/unit/write/test_disclosure_venues.py`: um por perfil, fallback
  desconhecido, saída sem venue inalterada, perfil sem `source_url`/`accessed` falha.
- [x] Task 2 — `VenueProfile` e `AIDisclosure.venue` em `schemas/v1.py`; dados em
  `domains/write/venue_policies.toml`; `load_venue_profiles` e renderização em `disclosure.py`.
- [x] Task 3 — `--venue` em `write disclosure` (`cli.py`) e passo no modo
  `skills/write/modes/disclosure.md`.
- [x] Task 4 — Verificação: pytest, ruff, mypy, `gen_indexes` (`--check`); arquivar plano.
