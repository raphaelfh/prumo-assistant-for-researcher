# ADR-0024 — Escopo presente desde o `init`; sem máquina de promoção

- Status: aceito
- Data: 2026-08-09
- Origem: [[2026-08-08-layout-por-escopo-design]]

## Contexto
Uma versão anterior deste design adiava o escopo: o projeto nascia "flat" e só ganhava
`docs/studies/<slug>/` quando um segundo estudo aparecesse, via uma máquina de promoção
(manifesto de migração, recusa se o worktree estivesse sujo, reescrita de link pra
profundidade nova). Isso reintroduz o próprio problema que o layout por escopo tenta
eliminar: dois formatos de projeto coexistindo, e um comando de migração a manter e testar
indefinidamente por um evento — o segundo estudo — que a auditoria de estado da arte mostrou
não ter ocorrido em nenhum dos 11 `pj_*` existentes.

## Decisão
`docs/studies/<slug>/` existe desde o `prumo init` — com um escopo default (`principal`) mesmo
em projeto de artigo único. `find_scope_root` resolve por POSIÇÃO (todo filho direto de
`docs/studies/` é um escopo; sem sentinela próprio, ver ADR-0022) e `prumo add study <slug>`
só cria a pasta irmã: nada se move, nenhum link muda de profundidade, nenhum manifesto é
necessário. A profundidade de todo escopo é fixa desde o primeiro dia, o que torna o caminho
relativo à bibliografia (`../../../references/_references.bib`) invariante em qualquer escopo,
presente ou futuro.

## Consequências
A máquina de promoção desenhada numa versão anterior da spec (manifesto, recusa por worktree
sujo, reescrita de links) não é implementada — YAGNI militante (Princípio VI da constitution).
Todo `pj_*` novo nasce com `docs/studies/principal/`; não existe comando `prumo promote` nem
estado intermediário "projeto sem escopo". Segunda escrita é sempre `prumo add study <slug>` —
o mesmo comando, cedo ou tarde, sem migração no meio.
