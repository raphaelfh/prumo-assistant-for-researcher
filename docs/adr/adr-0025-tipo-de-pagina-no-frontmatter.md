# ADR-0025 — Tipo de página é campo do frontmatter, não diretório

- Status: aceito
- Data: 2026-08-19
- Origem: auditoria de prosa pós-0.65.0; generaliza [ADR-0023](adr-0023-finding-como-type.md)

## Contexto
ADR-0023 tirou `findings/` de diretório e o transformou em `type: finding` numa nota de
`docs/studies/<escopo>/notes/`, mas decidiu só sobre finding. Os outros três tipos do wiki
— `concept`, `entity`, `source` — continuaram descritos como diretórios de primeiro nível
(`docs/{concepts,entities,sources}/`) na prosa da `wiki-ingest`, em três seções da `wiki-lint`
e nos templates do `pj_base`. Isso não é só inconsistência de texto: `pj_layout.SCOPE_DIRS` fixa
`notes`/`writing`/`decisions` como a estrutura de todo escopo, e tanto `wiki/lint.py` quanto
`wiki/stats.py` varrem escopos — uma página gravada em `docs/concepts/` seria invisível às duas.
A `wiki-ingest`, seguindo a própria prosa, gravaria exatamente ali.

## Decisão
O tipo de uma página do wiki é o campo `type:` do frontmatter YAML, nunca o diretório. `concept`,
`entity`, `finding` e `source` são todos notas de `docs/studies/<escopo>/notes/`, com o mesmo
frontmatter base (`id`, `type`, `title`, `added`, `status`, `tags`, `sources`) e os campos extras
que cada tipo pedir (`url`/`kind`/`authors` em `source`). `docs/_index.md` continua agrupado por
tipo — é catálogo por `type:`, não espelho de diretório. Um guard test em
`tests/unit/test_guidelines_present.py` rejeita a taxonomia plana em qualquer `SKILL.md` e em
qualquer markdown de `templates/pj_base/`.

## Consequências
`wiki-ingest` deixa de ter caminho próprio de escrita: grava no `notes/` do escopo como as demais
skills, e pergunta qual escopo usar quando houver mais de um. `wiki-lint` audita um escopo por vez
nas seções agênticas, alinhada ao que `prumo wiki lint` já fazia nas determinísticas. O `pj_base`
para de prometer quatro pastas que o núcleo não cria — o que `test_pj_base_integration` já exigia
e a prosa contradizia. A convenção `extended-wiki` deixa de ser pasta por tipo e passa a nomear
subpasta temática dentro do `notes/` do escopo (`docs/studies/<escopo>/notes/<domínio>/`), que
`prumo wiki stats` conta e `prumo wiki lint` audita — a única checagem que não desce é
`no_frontmatter`, que olha só os filhos diretos dos três `SCOPE_DIRS`.
