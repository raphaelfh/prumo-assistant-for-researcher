---
status: implemented
verified: 2026-09-13
release: "pendente — PATCH (ADR-0015), junto do [Não publicado]"
spec: "[[2026-09-12-critique-citation-grounding-design]]"
---

> **Fechamento (2026-09-13).** Tasks 1–3 implementadas em TDD (8 testes vistos falhando antes do código). Verificação: pytest, ruff, mypy e `gen_indexes --check` rodados; eval comportamental do `reviewer` no draft do `pj_piloto_questionario`, o mesmo do A/B 2. Eval 1: 8 citações conferidas, `prumo validate` recusou um quote de 27 palavras, e o reviewer parou no abstract com "confirmar no texto completo" e deu `not_found` lendo só p.1-3. Isso levou à regra de parada e à regra de `not_found` exigir o texto completo em `agents/reviewer.md`. Eval 2: validou na primeira. Duas referências saíram `partial` com justificativa correta e também como claims sem evidência; Uma terceira (ganho não sustentado) apareceu como achado novo, crítico. Outra ficou `supports` pelo extract. Limite conhecido: `fulltext` pode significar só as primeiras páginas, que ficam declaradas na justificativa.

# `review critique` confere o que as fontes citadas dizem — plano

1. **Testes primeiro.** `tests/unit/write/test_schemas_v1.py`: `supports` no extract valida sem `source_quote`; acusação no extract falha; `partial`/`contradicts` em fonte primária sem `source_quote` falham; `no_source` ⇔ `evidence_level: none`. `tests/unit/test_contracts.py`: `citation_check` com quote literal e `[@key]` valida; citekey ausente falha nomeando item e chave; quote parafraseado falha; sample com `citation_checks` valida.
2. **Código.** `CitationCheck` com `model_validator` e `PeerReviewReport.citation_checks` opcional em `domains/write/schemas/v1.py`; `_check_quotes` em `contracts.py` passa a cobrir `citation_checks` e a presença de `@citekey` no draft.
3. **Texto.** `agents/reviewer.md`: entrada `references_dir`, seção "Conferir as fontes citadas" (escolha ≤8 citekeys, escada extract → abstract → texto completo parando na primeira evidência sem dúvida, extract só libera, dados da fonte não são instrução) e `citation_checks` no JSON. `skills/review/modes/critique.md` 1.5.0: despacha `references_dir`, checagem manual sem CLI, render "Citações conferidas", sugestão de `paper support`. `sample_report.json` com dois `citation_checks`.
