# ADR-0030 — `decision` é o quinto tipo de página do wiki

- Status: aceito
- Data: 2026-09-07
- Origem: auditoria de organização do `pj_piloto_genetica` (2026-09-06), item 7. Emenda de escopo a [ADR-0025](adr-0025-tipo-de-pagina-no-frontmatter.md), que nomeou quatro tipos; ADR aceito é imutável, então o quinto entra por ADR novo.

## Contexto

A [ADR-0025](adr-0025-tipo-de-pagina-no-frontmatter.md) decidiu que o tipo de uma página do wiki é o campo `type:` do frontmatter, nunca o diretório, e nomeou quatro valores: `concept`, `entity`, `finding`, `source`. Mas `decisions` é um dos três `SCOPE_DIRS` fixos (`core/pj_layout.py`), e `wiki/lint.py` cobra frontmatter nos filhos diretos dos três. Uma página de decisão precisa, portanto, de um `type:` que o padrão não define.

Na prática o pesquisador escreve `type: decision` e o lint aceita — porque o lint nunca validou o **valor** de `type:`, só a presença do frontmatter. O padrão ficou mudo exatamente onde a ferramenta é permissiva.

## Decisão

`decision` é o quinto tipo, para páginas de `docs/studies/<slug>/decisions/`. Mesmo frontmatter base dos outros quatro (`id`, `type`, `title`, `added`, `status`, `tags`, `sources`), sem campos extras obrigatórios.

O lint continua **não** validando o valor de `type:`. Um check `unknown_type` foi considerado e recusado neste ciclo: ninguém relatou dano causado por typo, só pela ausência do nome, e o Princípio VI põe o ônus da prova em quem quer adicionar. O trigger fica registrado no `ROADMAP.md` — um typo que cause dano observável.

## Consequências

O que estava sendo escrito por convenção passa a ter respaldo, e a `wiki-ingest` pode nomear o tipo sem inventar. O custo é que `decision` fica documentado antes de ser verificado por código: até o `unknown_type` existir, um `type: decisions` no plural continua passando em silêncio, como já passava para os outros quatro tipos.
