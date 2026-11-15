---
status: implemented
verified: 2026-11-12
release: "não publicado (PATCH pela ADR-0015, salvo decisão de marco)"
spec: "[[2026-11-12-pergunta-do-estudo-pesquisa-em-saude-design]]"
---

> **Fechamento (2026-11-12).** Passos 1–10 entregues num só branch: `QuestionSpec/v1` com 13 tipos e 11 frameworks, `question_io` com fallback e migração do `picot.toml`, render/ADR/diff/ops/CLI/status/compose, modo `question` com `picot` como apelido, `cep` (CEUA e dispensa), `sap` por tipo, guidelines de relato, módulo `protocol` com apelido `clinical`, mod lendo `question.toml`, reposicionamento dos textos. `pytest`, `ruff`, `mypy`, `gen_indexes --check`, `validate_manifests` e `claude plugin test .` verdes. ADR-0041 e ADR-0042 seguem "proposto" até o merge. Não medido: roteamento manual das 34 frases no Desktop.


# Plano

1. ADR-0041 e ADR-0042 (propostos); índices regenerados.
2. TDD `QuestionSpec/v1` em `domains/protocol/schemas/v1.py`: tipos, regra hipótese/objetivo, frameworks e `elements`; conversão `from_picot`.
3. TDD `question_io.py`: `read_question` com fallback a `picot.toml`, `write_question` removendo o legado, hash.
4. Render por framework e sem framework; substituição do bloco `picot:begin` antigo.
5. ADR (`question-vN`, snapshot novo e antigo), diff, drift, ops, CLI (`init` aceita QuestionSpec e PicotSpec), `api.py`, `status`, `ComposeInputs.question`.
6. Skill: `modes/question.md` principal, `modes/picot.md` apelido, `cep` (CEUA, dispensa), `sap` (tipos sem SAP), guidelines por tipo.
7. Módulo `protocol` com `aliases = ["clinical"]`; `get_module` resolve apelido.
8. Mod `picot.ts` lê `question.toml` com fallback.
9. Reposicionamento de textos (README, manifestos, pyproject, CITATION, CLI, docs).
10. `gen_indexes`, CHANGELOG (Unreleased), `pytest`, `ruff`, `mypy`, testes dos mods.
