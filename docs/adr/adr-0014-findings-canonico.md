# ADR-0014 — Caminho canônico de findings: `docs/wiki/findings/` com fallback

- Status: aceito
- Data: 2026-06-11
- Origem: [[2026-06-11-repo-organization-redesign-design]] (D10); `domains/wiki/findings.py:_resolve_findings_dir`

## Contexto
A prosa das skills divergia: `active-learning` dizia `docs/wiki/findings/`; `paper-extract`, `peer-review`, `wiki-query` e `wiki-lint` diziam `docs/findings/`. O resolver real prefere `docs/wiki/findings/` quando `docs/wiki/` existe e cai para `docs/findings/` caso contrário — ou seja, toda prosa estava condicionalmente errada.

## Decisão
O comportamento do resolver é o canônico: `docs/wiki/findings/` (preferido), `docs/findings/` (fallback em projetos sem `docs/wiki/`). A prosa de todas as skills descreve exatamente isso. Nenhuma mudança de código em `src/`.

## Consequências
Skills param de contradizer o runtime. Mudar a preferência do resolver no futuro exige novo ADR + atualização coordenada da prosa de todas as skills que citam findings.
