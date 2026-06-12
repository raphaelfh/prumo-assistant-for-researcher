# ADR-0011 — SemVer por visibilidade ao consumidor; deferrals com trigger

- Status: aceito
- Data: 2026-06-11
- Origem: RELEASING.md + ROADMAP.md "Decisões deliberadas postergadas" (pré-existente; formalizado nesta data)

## Contexto
Num plugin, "breaking" é o que muda o que o usuário invoca — não o tamanho do diff. Releases ruidosos treinam o consumidor a ignorá-los.

## Decisão
Bump guiado pela interface pública do plugin (regra-mãe do RELEASING.md). Mudanças em `.github/`, README, CHANGELOG, `.gitignore` e `docs/` são não-releasáveis. Pré-1.0, breaking vai em MINOR com "⚠ Breaking". Cada adição postergada (hooks, cache LLM, lockfile, multi-host, packs, MkDocs) tem trigger concreto registrado no ROADMAP — sem trigger, não entra (Princípio VI).

## Consequências
Reorganizações de repo (como a de 2026-06-11) não geram release. A lista de deferrals do ROADMAP funciona como mini-ADRs de adiamento; promover um deferral a feature exige citar o trigger atingido.
