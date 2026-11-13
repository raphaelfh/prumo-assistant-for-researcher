---
name: question
description: "Fecha, propaga e versiona a pergunta do estudo em qualquer desenho de pesquisa em saúde (clínico, experimental, observacional, predição, revisão, qualitativo, métodos mistos, econômico, computacional, teórico, metodológico, relato de caso). PICOT, PECO, PCC, PICo, SPIDER e outros entram como estrutura opcional. Grava .claude/question.toml (QuestionSpec/v1), blocos em protocol.md e project_guide.md e ADR append-only quando muda."
argument-hint: "[init | formalize | propagate | diff]"
allowed-tools: Read Write Edit Glob Grep Bash(cat *) Bash(prumo protocol *)
prumo:
  version: 2.0.0
  schema: QuestionSpec/v1
  determinism: hybrid
  agent_compat: [claude-code]
  cost_estimate: ~6k tokens (diálogo), ~2k (formalize/propagate/diff)
  inputs:
    pj_path: optional (default cwd)
    mode: optional ('init' | 'formalize' | 'propagate' | 'diff'; default = auto-detect)
  requires: [cli]
  phrases:
    - "fecha a pergunta do estudo"
    - "formaliza a pergunta de pesquisa"
    - "qual o desenho do meu estudo"
    - "a pergunta do estudo mudou"
  legacy: [formulate-picot]
---

# Pergunta do estudo — formalização canônica + propagação versionada

<!-- prumo:preflight:begin -->
> **Preflight — antes de qualquer operação deste modo:**
>
> 1. **Superfície e CLI:** fora de um agente com terminal no seu Mac ou Linux (Claude Code
>    no app ou no terminal, Antigravity, Codex no app ChatGPT ou no terminal), isto é, numa
>    tarefa do Cowork, num chat web, numa sessão SSH, no Windows ou no WSL, diga em uma frase
>    que este modo não roda aqui e pare. Senão, rode `prumo --version`
>    (sem `prumo`, a forma `sh … --version` do bloco PAR; cada comando pedirá permissão). O
>    esperado é `prumo <versão do bloco PAR da porta>`.
>    - Linha `PAR:` do sandbox (saída 77): ofereça repetir o comando fora do sandbox, pedindo
>      permissão.
>    - Qualquer outra saída (outra versão, `PAR: falta o uv`, outra linha `PAR:`, nada): roteie
>      para `/par:start`, que resolve, e pare.
>    Nunca simule a operação.
> 2. **Estrutura:** se o diretório não tiver `docs/references/` de um `pj_*`,
>    oriente `prumo init pj_<nome>`; nunca crie o scaffold à mão.
<!-- prumo:preflight:end -->

A pergunta do estudo é o centro do protocolo (ADR-0041). Ela vale para qualquer pesquisa em
saúde, não só ensaio clínico. PICOT e os demais frameworks são **opcionais**: decompõem a
pergunta quando ajudam, e ficam de fora quando não ajudam (relato de caso, ensaio teórico).

Destinos mantidos consistentes:

- `.claude/question.toml`: canônico, validado por `QuestionSpec/v1`
- `docs/studies/<slug>/writing/protocol.md`: render operacional
- `docs/project_guide.md`: render acadêmico

Quando a versão muda, grava ainda um ADR append-only em
`docs/studies/<slug>/decisions/adr-NNNN-question-v<N>-<slug>.md`.

Projeto antigo com `.claude/picot.toml`: o CLI lê e converte sozinho. A próxima gravação
(`init` ou `adr`) cria `question.toml` e remove o `picot.toml`; o ADR e o git guardam o antigo.
Diga isso à pesquisadora em uma frase quando acontecer.

## Pressupostos

- cwd é um `pj_*` com `docs/studies/<slug>/writing/protocol.md` e `docs/project_guide.md`
  (mesmo que vazios) e `docs/studies/<slug>/decisions/`.
- A parte determinística (TOML, render, diff, ADR) é `prumo protocol *`. Este modo só cuida do
  diálogo e do `formalize`.

## Auto-detect

```bash
prumo protocol detect-mode
```

A saída (`init` / `formalize` / `propagate` / `diff`) define a operação. Para `propagate` e
`diff`, leia antes [`../references/operations-advanced.md`](../references/operations-advanced.md).

## Tipos de estudo

| `type` | Quando | Exige | Framework sugerido | Guideline de relato |
|---|---|---|---|---|
| `clinical` | intervenção em humanos: ensaio clínico, quase-experimento | hipótese | PICOT | CONSORT 2025, SPIRIT 2025 |
| `experimental` | animais, bancada, in vitro | hipótese | PICOT | ARRIVE 2.0 |
| `observational` | coorte, caso-controle, transversal, prevalência, ecológico | objetivo ou hipótese | PECO, PECOT, CoCoPop | STROBE (RECORD para dado rotineiro) |
| `prediction` | modelo, escore, biomarcador, teste diagnóstico ou prognóstico | hipótese | PICOT, PIRD | TRIPOD+AI, STARD 2015 |
| `review` | sistemática, meta-análise, escopo, rápida, umbrella | objetivo ou hipótese | PICOS, PECO, PCC, SPIDER | PRISMA 2020, PRISMA-ScR |
| `qualitative` | entrevistas, grupos focais, etnografia | objetivo | PICo, SPIDER | COREQ, SRQR |
| `mixed_methods` | quanti e quali integrados | objetivo ou hipótese | livre | GRAMMS |
| `economic` | custo-efetividade, custo-utilidade, impacto orçamentário | objetivo ou hipótese | PICO, PICOT | CHEERS 2022 |
| `computational` | simulação, bioinformática, modelagem, ML metodológico | objetivo ou hipótese | livre | conforme a aplicação |
| `theoretical` | modelo conceitual, ensaio teórico, ética, política de saúde | `contribution` + objetivo | nenhum | — |
| `methodological` | método estatístico ou de pesquisa novo | `contribution` + `hypothesis_validity_condition` + hipótese | nenhum | — |
| `case_report` | relato ou série de casos | objetivo | nenhum | CARE |
| `other` | o que não couber acima | objetivo ou hipótese | livre | — |

"Objetivo ou hipótese" quer dizer ao menos um dos dois; estudo descritivo usa objetivo.

## Frameworks (opcionais)

| `framework` | Elementos obrigatórios | Opcional |
|---|---|---|
| `PICOT` | population, intervention, outcome, time | comparison |
| `PICO` | population, intervention, outcome | comparison |
| `PICOS` | population, intervention, outcome, study_design | comparison |
| `PECO` | population, exposure, outcome | comparison |
| `PECOT` | population, exposure, outcome, time | comparison |
| `PEO` | population, exposure, outcome | — |
| `PCC` | population, concept, context | — |
| `PICo` | population, phenomenon, context | — |
| `SPIDER` | sample, phenomenon, design, evaluation, research_type | — |
| `PIRD` | population, index_test, reference_standard, diagnosis | — |
| `CoCoPop` | condition, context, population | — |

Em `clinical` com PICOT, PICO ou PICOS, `comparison` é obrigatório. Em `prediction`,
`intervention` guarda o index (preditor, teste, escore) e `time` o horizonte de predição.

## Operação 1: `init` — diálogo (greenfield)

Pré-condição: nenhum `question.toml` nem `picot.toml`, `protocol.md` vazio ou só template.

1. **Contexto.** Invoque `/par:wiki query` (ou leia `docs/_index.md` e `_log.md`) para saber
   o tema. Sugira a partir do wiki sempre que puder.
2. **Tipo, em linguagem natural.** Pergunte "o que você vai fazer?" e proponha o `type` (e o
   `design`, como "coorte retrospectiva" ou "revisão de escopo") pela resposta, usando a tabela
   de tipos. A pesquisadora confirma; não despeje a lista de 13 tipos.
3. **A pergunta em uma frase.** É o único conteúdo sempre obrigatório. Ajude a deixá-la
   respondível: quem, o quê, comparado a quê (se houver), medido como, em que prazo.
   Ex.: "Em adultos com DM2 na APS, o início de iSGLT2 está associado a menor incidência de
   DRC em 5 anos, comparado à sulfonilureia?"
4. **Framework (opcional).** Sugira o da coluna "Framework sugerido" e pergunte se quer
   decompor a pergunta nele. Se sim, pergunte um elemento por vez. Se não, siga sem
   `framework` e sem `elements`.
5. **Objetivo e/ou hipótese**, conforme a coluna "Exige":
   - **Objetivo**: uma frase com o verbo do que o estudo faz (estimar, descrever,
     compreender, mapear, comparar).
   - **Hipótese formal**: `statement` (frase declarativa testável), `rationale` (por que
     esperar isso) e `metrics` (lista de métricas ou estimadores, ex.: `["HR", "IC 95%"]`).
   - `theoretical` e `methodological`: também `contribution`; `methodological` pede ainda
     `hypothesis_validity_condition` (sob qual condição a contribuição vale).
6. **Mostrar o JSON proposto e pedir confirmação.** Campos `None` ficam de fora.

   ```json
   {
     "type": "observational",
     "design": "coorte retrospectiva",
     "question": "Em adultos com DM2 na APS, o início de iSGLT2 ...?",
     "objective": "Estimar a associação entre iSGLT2 e DRC incidente.",
     "created_at": "<hoje ISO>",
     "last_updated": "<hoje ISO>",
     "version": 1,
     "framework": "PECOT",
     "elements": {
       "population": "Adultos com DM2 na APS de BH, 2015-2020",
       "exposure": "Início de iSGLT2",
       "comparison": "Início de sulfonilureia",
       "outcome": "DRC incidente (TFGe < 60 por 90 dias)",
       "time": "5 anos"
     }
   }
   ```

   Hipótese, quando houver: `"hypothesis": {"statement": "...", "rationale": "...", "metrics": ["..."]}`.
   Pergunte "OK assim?".
7. **Após confirmação, gravar:**

   ```bash
   cat <<'JSON' | prumo protocol init --date "<hoje ISO>" --json
   <QuestionSpec JSON aprovado>
   JSON
   ```

   Grava `.claude/question.toml`, propaga os blocos em `protocol.md` e `project_guide.md` e
   cria `adr-NNNN-question-v1-versao-inicial.md`. A última linha de stdout é JSON
   `{"propagate": ..., "adr_path": ...}`. Erro de validação traz o campo que falta: corrija
   com a pesquisadora e rode de novo.
8. **Reportar**: arquivos criados e blocos atualizados. Se o tipo tem guideline de relato,
   diga qual vale para o manuscrito (coluna da tabela de tipos).

## Operação 2: `formalize` — extrair de prosa existente

Pré-condição: sem pergunta canônica, mas `protocol.md` ou `project_guide.md` têm prosa.

1. Leia `protocol.md` e `project_guide.md` e identifique tipo, pergunta, objetivo, hipótese e,
   se a prosa já usa um framework, os elementos.
2. Apresente a tabela:

   | Campo | Candidato extraído | Fonte |
   |---|---|---|
   | `type` | "observational" | `protocol.md § Desenho` |
   | `question` | "..." | `project_guide.md § Pergunta` |
   | ... | ... | ... |

3. Confirme ou edite campo a campo com a pesquisadora.
4. Siga os passos 6 a 8 do `init`.

## Operações 3 e 4: `propagate` e `diff`

Ver [`../references/operations-advanced.md`](../references/operations-advanced.md).

## Boundaries

- Nunca edite `.claude/question.toml` sem confirmação da pesquisadora.
- Nunca edite ADR existente (append-only).
- Nunca edite prosa fora dos blocos `<!-- question:begin/end -->` (o bloco antigo
  `<!-- picot:begin/end -->` é trocado pelo CLI, não à mão).
- Não valide a pergunta semanticamente com o LLM além do diálogo: a validação é do schema.
- Prosa do `project_guide.md` fora do bloco: delegue a `/par:write section`.

## Erros comuns

- `question.toml` não parseável: reporte o erro do `tomllib` e sugira
  `git diff .claude/question.toml`.
- `protocol.md` ou `project_guide.md` ausentes: o CLI reporta `missing`; siga, a pesquisadora
  cria depois.
- Pergunta canônica existe mas não há ADR baseline: `detect-mode` devolve `propagate`; rode-o
  e trate o próximo `adr` como a versão inicial.
