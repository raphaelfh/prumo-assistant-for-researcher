# ADR-0042 — Módulo `protocol` substitui `clinical`, que vira apelido

- Status: proposto
- Data: 2026-11-12
- Origem: pedido do mantenedor; acompanha a ADR-0041

## Contexto

O módulo opcional `clinical` traz o protocolo, o esqueleto do plano de análise, o dicionário de dados e o projeto CEP. Nada disso é exclusivo da pesquisa clínica: um experimento com animais precisa de CEUA, uma coorte com dado secundário precisa de protocolo e dicionário de dados. O nome afasta quem não faz pesquisa clínica.

## Decisão

1. `templates/modules/clinical/` passa a `templates/modules/protocol/`, com `aliases = ["clinical"]` no `_module.toml`.
2. `get_module` resolve apelido: `prumo add clinical` aplica `protocol`. O `anchor` não muda, então projetos que já aplicaram `clinical` aparecem com `protocol` aplicado, sem migração.
3. O modo `protocol cep` passa a cobrir CEUA (Lei 11.794/2008) e a dizer quando o CEP é dispensável (Res. CNS 510/2016, art. 1º, parágrafo único).

## Consequências

Um campo novo e opcional no `_module.toml` (`aliases`). Sem breaking change.
