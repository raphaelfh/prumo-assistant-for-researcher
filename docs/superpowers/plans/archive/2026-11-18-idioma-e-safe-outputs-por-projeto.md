---
status: implemented
verified: 2026-11-18
release: "0.72.1"
spec: "[[2026-11-16-idioma-e-safe-outputs-por-projeto-design]]"
adr: "[[adr/adr-0046-regras-do-projeto-no-agents-md]]"
---

> **Fechamento (2026-11-18).** Tasks 1–5 implementadas em TDD. Verificação: suíte inteira, `ruff`,
> `mypy` e `gen_indexes --check` limpos; teste de ponta a ponta com o CLI num `pj_exemplo`
> (`init` com e sem flags, edição da config, `doctor`, `update`, projeto no formato anterior).
> Três emendas à spec, registradas nela: o bloco atrasado entra em `[fora_do_padrao]` em vez de
> uma issue nova; `core/safe_outputs.py` fica como está; `[writing].language` não é perguntado.
> Não verificado: o wizard interativo num terminal real (só `_project_options` e os caminhos por
> flag têm teste) e se cada host de fato segue o bloco numa sessão real.

# Idioma de interação e saídas seguras por projeto — plano de implementação

**Spec:** [[2026-11-16-idioma-e-safe-outputs-por-projeto-design]] · **ADR:** ADR-0046

- [x] **Task 1 — Config.** `tests/unit/core/test_config.py`: defaults novos, valores inválidos
  com a correção na mensagem, `set_config_values` preservando comentários. Implementar em
  `core/config.py` (`INTERACTION_LANGUAGES`, `[interaction]`, `[safe_outputs]`).
- [x] **Task 2 — Bloco.** `tests/unit/core/test_project_rules.py`: variantes do bloco, template
  igual ao renderizador, `sync_project_rules` (atualiza, troca a linha fixa antiga, insere,
  delimitador sem par), `retire_legacy_rule`, `low_min_cell_warning`. Implementar
  `core/project_rules.py`.
- [x] **Task 3 — Template.** `templates/pj_base/AGENTS.md` com o bloco dos defaults; seções novas
  no `pj_config.toml`; `.claude/rules/safe_outputs.md` removida.
- [x] **Task 4 — CLI.** `init` (`--lang`, `--no-patient-data`, perguntas do wizard), `update`
  (aposenta a rule, regrava o bloco, `--dry-run` só relata), `doctor` (`[fora_do_padrao]`,
  `[config_invalida]`, aviso `[celula_minima_baixa]`). Testes em `test_cli_init.py`,
  `test_cli_update.py`, `test_cli_doctor.py`.
- [x] **Task 5 — Docs.** Skill `start`, onboarding, ARCHITECTURE, CHANGELOG, spec e ADR-0046.
