# ADR-0041 — A pergunta do estudo é o artefato principal; PICOT e os demais frameworks são opcionais

- Status: proposto
- Data: 2026-11-12
- Origem: pedido do mantenedor (o PAR passa a servir à pesquisa em saúde, não só à clínica); spec `docs/superpowers/specs/2026-11-12-pergunta-do-estudo-pesquisa-em-saude-design.md`

## Contexto

A pergunta de pesquisa só existia como PICOT (`PicotSpec/v1`, em `.claude/picot.toml`), com três tipos (`clinical`, `prediction`, `methodological`) e hipótese formal sempre obrigatória. Isso não acomoda estudo observacional, experimento com animais ou de bancada, revisão de escopo, estudo qualitativo, computacional, teórico, relato de caso: cada um tem o seu framework (PECO, PCC, PICo, SPIDER, PIRD, CoCoPop) ou nenhum, e vários não testam hipótese.

## Decisão

1. **Schema novo `QuestionSpec/v1`** em `.claude/question.toml` (tabela `[question]`). Sempre obrigatórios: `type`, `question` (a pergunta em uma frase), `created_at`, `last_updated`, `version`.
2. **Tipos:** `clinical`, `experimental`, `observational`, `prediction`, `review`, `qualitative`, `mixed_methods`, `economic`, `computational`, `theoretical`, `methodological`, `case_report`, `other`. `clinical` (intervenção em humanos) e `experimental` (animais, bancada) são distintos.
3. **Framework opcional:** `framework` (`PICOT`, `PICO`, `PICOS`, `PECO`, `PECOT`, `PEO`, `PCC`, `PICo`, `SPIDER`, `PIRD`, `CoCoPop`) com `elements` (tabela chave → texto); o validador exige as chaves obrigatórias do framework e recusa chave desconhecida.
4. **Hipótese ou objetivo:** hipótese obrigatória em `clinical`, `experimental`, `prediction`, `methodological`; objetivo obrigatório em `qualitative`, `case_report`, `theoretical`; nos demais, um dos dois. `methodological` mantém `contribution` + `hypothesis_validity_condition`; `theoretical` exige `contribution`.
5. **Legado:** `picot.toml` é lido e convertido sem perda quando `question.toml` não existe; a primeira escrita grava `question.toml` e remove `picot.toml` (o snapshot do ADR e o git guardam o antigo). Blocos `<!-- picot:begin -->` e ADRs `picot-vN` continuam reconhecidos. `PicotSpec/v1` fica no código (forward-only, ADR-0006).
6. **Superfície:** o modo principal passa a ser `protocol question`; `protocol picot` continua como apelido. Os subcomandos `prumo protocol *` não mudam de nome.

## Alternativas rejeitadas

Ampliar `PicotSpec/v1` com campos novos (o nome e o arquivo continuariam dizendo PICOT, contra a decisão do mantenedor); um campo tipado por elemento de cada framework (dezenas de campos opcionais, quase todos vazios); um tipo `diagnostic` separado de `prediction` (Princípio VIII: `prediction` já cobre).

## Consequências

Treze tipos e onze frameworks é muita escolha: a skill pergunta em linguagem natural e propõe tipo e framework para a pesquisadora só confirmar. `ComposeInputs/v1` ganha `question`; `picot` fica e deixa de ser preenchido. Sem breaking change.
