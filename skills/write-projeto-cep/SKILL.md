---
name: write-projeto-cep
description: "Gera projeto pra CEP/CONEP via Plataforma Brasil a partir do PICOT, protocol.md e acervo — estrutura formal (Resumo, Pergunta, Justificativa, Hipótese, Coorte, Métodos, Riscos, TCLE, Cronograma, Orçamento, Conformidade). Citação strict. Linguagem acessível pra revisor não-técnico no Resumo."
when_to_use: |
  Quando o usuário pedir "gera o projeto CEP", "preciso submeter pra CEP",
  "projeto pra Plataforma Brasil", "documento de submissão ética".
argument-hint: "[--section NAME] [--into PATH | --out PATH] [--template PATH]"
allowed-tools: Read Write Edit Glob Grep Bash(uv run python *) Bash(python3 *)
prumo:
  version: 1.0.0
  schema: WriteOutput/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~10-25k tokens
  inputs:
    section: optional
    template: optional
    into: optional
    out: optional
    slug: optional
---

# Write Projeto CEP — submissão ética brasileira

Você é um pesquisador clínico escrevendo projeto pra CEP/CONEP via Plataforma
Brasil. Documento brasileiro com estrutura específica (TCLE quando aplicável,
Resolução CNS 466/2012 + 510/2016, LGPD). Template default co-localizado:
[`./template.md`](template.md). Override por projeto:
`<pj>/.claude/writing_templates/projeto-cep.md`.

## Regras invioláveis

1. **Linguagem acessível** no Resumo (revisor de CEP é multidisciplinar; minimize jargão de ML).
2. **Citação strict**, mesma regra do `write-paper`. `[REF FALTANTE]` quando faltar.
3. **PicotSpec obrigatório** + `protocol.md` populado (coorte, critérios, governança). Aborta se faltarem.
4. **TCLE**: aplicável só se há contato com participantes. Para estudo retrospectivo de dados públicos anonimizados, marcar N/A com justificativa via Resolução CNS 510/2016 Art 1.
5. **Conformidade ética** explícita: CNS 466/2012, 510/2016, LGPD, HIPAA/GDPR se aplicável, DUAs das coortes.

## Fluxo

(idêntico ao write-paper: 1. carregar inputs → 2. resolver template `projeto-cep.md` → 3. gerar por section → 4. validar citação → 5. escrever output → 6. reportar)

## Boundaries

- **Não invente** dados de orçamento ou cronograma — use placeholders `[ORÇAMENTO: ...]` se não souber.
- **Não infira** CAAE / Plataforma Brasil ID — deixar vazio.
- **Não preencha** TCLE com texto inventado — use placeholder + nota dizendo qual cenário motiva (com participante / sem participante).
