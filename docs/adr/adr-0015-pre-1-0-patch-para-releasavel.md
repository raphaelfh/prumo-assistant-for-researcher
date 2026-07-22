# ADR-0015 — Pré-1.0: PATCH para todo release; MINOR reservado a breaking/marco

- Status: aceito
- Data: 2026-07-22
- Origem: [[2026-07-22-zettlr-front-design]]

## Contexto
Sob o ADR-0011, qualquer skill/subcomando novo bumpa MINOR. Em fase de iteração frequente isso infla o número (0.6 → 0.61 → 0.62…) e treina o consumidor a ignorar releases — o oposto do que a regra-mãe quer.

## Decisão
Enquanto a versão for `0.x`: PATCH cobre tudo que é releasável, inclusive skill/subcomando novo; MINOR fica reservado a breaking ("⚠ Breaking") ou fechamento de fase/marco do ROADMAP. A regra-mãe do ADR-0011 permanece (versão = interface pública; `.github/`, README, CHANGELOG, `.gitignore` e `docs/` não bumpam). Semântica: MINOR = "leia o changelog antes de atualizar"; PATCH = "atualize sem medo".

## Consequências
Supersede o mapeamento pré-1.0 do ADR-0011 (o restante daquele ADR segue válido). RELEASING.md e `.claude/rules/release.md` emendados. Primeiro release sob a política: 0.62.1 (spec Zettlr-front). No 1.0.0, SemVer pleno reassume e este ADR expira.
