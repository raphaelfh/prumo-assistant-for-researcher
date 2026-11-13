# Reporting guidelines — mental-model reference

Mental model por gênero do draft; não cite a checklist no review final salvo se útil.

| Gênero do draft | Guideline(s) |
|---|---|
| Modelo de predição (regressão ou ML) | **TRIPOD+AI** (2024; 27 itens) |
| Estudo que desenvolve/avalia um **LLM** em saúde | **TRIPOD-LLM** (Nat Med, jan/2025) |
| Avaliação clínica **precoce** de sistema de apoio à decisão por IA | **DECIDE-AI** |
| RCT (geral) | **CONSORT 2025** |
| RCT com IA no pipeline | **CONSORT 2025** + **CONSORT-AI** |
| Protocolo de ensaio com IA | **SPIRIT-AI** |
| Imaging AI | **CLAIM / MI-CLAIM** |
| Revisão sistemática | **PRISMA 2020** |
| Revisão de escopo | **PRISMA-ScR** |
| Estudo observacional | **STROBE** (dado rotineiro: **RECORD**) |
| Acurácia diagnóstica | **STARD 2015** |
| Experimento com animais | **ARRIVE 2.0** |
| Estudo qualitativo | **COREQ** (entrevista/grupo focal) ou **SRQR** |
| Métodos mistos | **GRAMMS** |
| Avaliação econômica em saúde | **CHEERS 2022** |
| Relato de caso | **CARE** |
| Melhoria da qualidade | **SQUIRE 2.0** |

O `type` da pergunta do estudo (`.claude/question.toml`) indica o gênero: `clinical` → CONSORT;
`experimental` → ARRIVE; `observational` → STROBE; `prediction` → TRIPOD+AI ou STARD;
`review` → PRISMA ou PRISMA-ScR; `qualitative` → COREQ/SRQR; `mixed_methods` → GRAMMS;
`economic` → CHEERS; `case_report` → CARE. `computational`, `theoretical` e
`methodological` não têm checklist única: critique pela clareza da contribuição.

## TRIPOD-LLM (Nature Medicine, jan/2025)

Extensão do TRIPOD+AI para estudos que desenvolvem ou avaliam LLMs em saúde.
19 itens principais / 50 subitens; formato modular por tarefa de LLM.
Guideline **viva** (painel revisa a cada ~3 meses). Foco: alucinações,
omissões, confiabilidade, explicabilidade, **reprodutibilidade**, privacy,
viés downstream, e **supervisão humana**. Checklist interativa:
https://tripod-llm.vercel.app/ . Ao revisar um paper que usa LLM, cobrar:
modelo + versão + data de acesso, prompts/temperatura, estratégia de
avaliação task-specific, e a etapa de verificação humana.

## DECIDE-AI

Reporting da avaliação clínica **precoce** (small-scale, live) de sistemas de
apoio à decisão baseados em IA — o estágio entre desenvolvimento do modelo
(TRIPOD+AI) e o RCT completo (CONSORT 2025, + CONSORT-AI se houver IA no
pipeline). 27 itens; ênfase em fatores humanos, segurança, e desempenho em
uso real.

## CONSORT 2025

Atualiza o CONSORT 2010 (não usar mais o 2010). 30 itens + diagrama de fluxo;
adiciona uma seção de **open science** e integra itens de extensões. Para
RCTs com componente de IA, combinar com CONSORT-AI.
