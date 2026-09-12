---
status: implemented
verified: 2026-09-12
release: "pendente — PATCH (ADR-0015), junto do [Não publicado]"
spec: "[[2026-09-12-figuras-e-tabelas-design]]"
---

> **Fechamento (2026-09-12).** T1–T5 implementadas em TDD. `_filters/crossref.lua` roda antes de `--citeproc`; `export()`/`compose()` passam `[writing].language`. Testes com pandoc 3.11 real verdes (pulados sem pandoc no PATH). Desvio do spec: `@fig:x [@key]` é aceito, porque o Pandoc funde os dois num `Cite` só e o filtro separa a citação real (o citemap segue vendo um grupo). Verificação: suíte inteira, ruff, mypy e `gen_indexes --check` limpos.

# Figuras e tabelas numeradas no export — plano

Spec: [[2026-09-12-figuras-e-tabelas-design]] · ADR-0034.

- [x] T1 (vermelho): testes do builder — `crossref.lua` antes de `--citeproc` em todo formato; `--metadata=prumo_lang:` quando `lang` é dado.
- [x] T2 (vermelho): teste com pandoc real (skip sem pandoc): legenda "Figure 1"/"Table 1" com `SEQ`, `@tbl:x` resolvido, campo `ZOTERO_ITEM` coexistindo, stderr sem citekey ausente; `[@fig:x]` e alvo inexistente falham; rótulo pt-BR.
- [x] T3 (vermelho): fiação — `export()` passa `[writing].language` ao builder.
- [x] T4 (verde): `_filters/crossref.lua`; `_crossref_filter()`; parâmetro `lang` em `_build_pandoc_cmd`; `export()`/`compose()` passam a língua do projeto.
- [x] T5: sintaxe em uma regra do modo `write manuscript`; índices; suíte, ruff, mypy.
