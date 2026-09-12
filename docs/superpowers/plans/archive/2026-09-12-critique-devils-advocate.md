---
status: implemented
verified: 2026-09-12
release: "pendente — PATCH (ADR-0015), junto do [Não publicado]"
spec: "[[2026-09-12-critique-devils-advocate-design]]"
---

> **Fechamento (2026-09-12).** Tasks 1–3 implementadas. Não houve Python (sem TDD aplicável). Verificação: pytest, ruff, mypy e `gen_indexes --check` rodados antes do commit, mais uma medição no draft piloto. Passe base com cerca de 1,7 mil palavras, passe adversarial com cerca de 0,7 mil (≈84k tokens de subagent). Os dois apontaram a conclusão central contra o item que a contradiz: o quote anchoring já afiou o passe base. O único achado novo do adversarial foi evidência seletiva entre dois itens do questionário. O relatório juntado foi aceito por `prumo validate PeerReviewReport/v1`.

# Passe advogado do diabo — plano

1. **Agent:** `agents/reviewer.md` recebe a entrada `pass` e a seção "Passe `adversarial`", com foco no argumento, até 5 achados e JSON parcial.
2. **Modo:** `skills/review/modes/critique.md` despacha o passe em paralelo (pulado com `--section`), junta sem duplicar, reavalia a recomendação e valida o relatório juntado. Versão 1.4.0, custo estimado atualizado.
3. **Medição:** os dois passes no draft piloto, via `general-purpose` com o prompt canônico. Conferir se a conclusão central sem sustento foi apontada, contar palavras e validar o relatório juntado com `uv run prumo validate PeerReviewReport/v1`.
