---
status: accepted
date: 2026-09-12
---

# Safe outputs mínimo no `pj_base`

## Problema

O público-alvo trabalha com dado de paciente e o `pj_*` não tem fronteira de
confidencialidade (ROADMAP, achado "Safe outputs", **atingido**). O `.gitignore` do
`pj_base` já ignora `content/` e `.prumo/`, mas projeto antigo pode não ter essas linhas, e
nada avisa quando dado bruto ou trace de LLM entra no git. O agente também não tem
instrução nenhuma sobre o que pode ir para prosa, notas e contexto.

## Decisão

1. **Rule sempre-on** `templates/pj_base/.claude/rules/safe_outputs.md`, sem `paths:` (a
   0.69.0 mostrou que glob errado deixa a rule muda). Três instruções: não copiar dado
   linha-a-linha ou identificável para prosa, notas, findings ou contexto além do que a
   tarefa exige; agregado respeita célula mínima; dado bruto e `.prumo/` fora do git.
2. **Célula mínima default = 5.** Contagem de 1–4 em tabela cruzada é o caso clássico de
   reidentificação (controle estatístico de divulgação, Five Safes / UK Data Service). Cinco
   é o limiar mais comum em publicação de dado de saúde; o projeto pode subir (ex.: 10)
   declarando no `docs/project_guide.md`. Sem chave de config (Princípio VI). A regra vale
   para contagem de **pacientes**: contagem de clínicos respondentes ("1 de 33") não é dado
   de paciente.
3. **Uma checagem no `doctor`**, `[dado_versionavel]`, em `core/safe_outputs.py`: se o
   `pj_*` está num repositório git, `content/` e `.prumo/` precisam estar ignorados e sem
   arquivo rastreado (exceto `.gitkeep`). Fora de git, ou sem binário `git`, silêncio — não
   dá para afirmar nada. Determinística (Princípio II); o git fica atrás do seam `_git`.
4. **Projetos existentes** recebem a rule pelo `prumo update`, que já copia o que falta do
   `pj_base`. Nenhum mecanismo novo de migração.

## Alternativas rejeitadas

- **Varredura de célula pequena nas tabelas do manuscrito** — falso-positivo é o caso comum
  (contagem de clínicos, n de estudos, número de itens), e distinguir paciente de não-paciente
  exige semântica. YAGNI (Princípio VI); fica na rule, para o agente e o revisor.
- **Chave `min_cell` no `pj_config.toml`** — mais um conceito para aprender (Princípio VIII)
  sem consumidor determinístico.
- **Reescrever o `.gitignore` do projeto no `update`** — o `update` não sobrescreve arquivo
  existente sem confirmação; o `doctor` aponta e a correção é uma linha.

## Aceite

- `prumo init` cria `.claude/rules/safe_outputs.md`.
- `doctor` passa com `content/` e `.prumo/` ignorados e não rastreados; falha quando não
  ignorados ou quando rastreados (git mockado em `_git`); silencia fora de git.
- `prumo update` num projeto sem a rule a copia.
