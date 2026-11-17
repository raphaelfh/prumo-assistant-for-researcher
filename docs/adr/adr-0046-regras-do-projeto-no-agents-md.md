# ADR-0046 — Regras do projeto num bloco gerado do `AGENTS.md`, com valores do `pj_config.toml`

- Status: proposto
- Data: 2026-11-16
- Origem: pedido do mantenedor; spec `docs/superpowers/specs/2026-11-16-idioma-e-safe-outputs-por-projeto-design.md`. Reverte a alternativa rejeitada "chave `min_cell`" da spec `2026-09-12-safe-outputs-design.md`

## Contexto

O `pj_base` tinha duas regras fixas para todo projeto: idioma de interação pt-BR, em texto no `AGENTS.md`, e célula mínima 5 para contagem de pacientes, em `.claude/rules/safe_outputs.md`. Projeto em inglês, ou sem dado de paciente, não tinha como ajustá-las; o limiar só podia subir por prosa no `project_guide.md`, que nenhum código lê. Além disso, `.claude/rules/` só é carregado pelo Claude Code: Codex e Antigravity, que o `pj_base` também atende, leem `AGENTS.md` e nunca viam a regra de célula mínima. Uma rule também é prosa estática e não carrega um valor por projeto.

## Decisão

1. **Valores no `pj_config.toml`**: `[interaction].language` (`pt-BR` | `en-US`), `[safe_outputs].patient_data` (bool) e `[safe_outputs].min_cell` (inteiro `>= 0`; 0 desliga a supressão). Defaults iguais ao comportamento anterior (`pt-BR`, `true`, `5`), validados em `core/config.py`. `INTERACTION_LANGUAGES` é vocabulário próprio, separado dos de escrita e de extração (mesmo motivo do ADR-0021).
2. **Instrução num bloco machine-owned do `AGENTS.md`**, `<!-- prumo:project-rules:begin/end -->` (ADR-0009), renderizado por `core/project_rules.py` a partir da config e escrito pelo `prumo init` e pelo `prumo update`. Todo agente lê o mesmo texto, já com os valores do projeto.
3. **`.claude/rules/safe_outputs.md` sai do `pj_base`.** O `update` remove a cópia não editada e insere o bloco; cópia editada fica, com aviso.
4. **`prumo doctor`** acusa `[regras_desatualizadas]` (bloco ausente ou diferente da config; correção `prumo update`) e avisa `[celula_minima_baixa]` (dado de paciente com `min_cell < 5`). `[dado_versionavel]` continua.
5. **`prumo init`** pergunta idioma de interação e se há dado de paciente; flags `--lang` e `--no-patient-data` no modo não-interativo.

## Consequências

- Regra que precisa valer para todo agente e variar por projeto passa a morar no `AGENTS.md` gerado, não em `.claude/rules/`. Rules de módulo que só orientam o Claude podem continuar onde estão.
- Projeto que não mexe em nada mantém o comportamento anterior.
- Baixar ou desligar a célula mínima vira possível e explícito: aparece no bloco e no `doctor`. A responsabilidade pela escolha é do projeto.
- O texto da regra de saídas seguras muda de lugar (template → `core/project_rules.py`); mudá-lo é mudar Python e teste, e o `doctor` aponta projetos com o bloco velho.
- A regra `.claude/rules/privacy.md` deste repo não muda: protege o repo público, não os projetos.
