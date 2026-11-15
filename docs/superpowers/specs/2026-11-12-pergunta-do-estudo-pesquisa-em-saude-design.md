---
title: Pergunta do estudo — o PAR passa de pesquisa clínica a pesquisa em saúde; PICOT e os demais frameworks viram estrutura opcional da pergunta; módulo `protocol` substitui `clinical`
date: 2026-11-12
status: approved
tags: [protocol, picot, question, schema, modulos, posicionamento, adr-0041, adr-0042]
---

# Pergunta do estudo e pesquisa em saúde

## Resumo executivo

Hoje o PAR se apresenta como assistente de **pesquisa clínica** e a pergunta de pesquisa só
existe como PICOT (`PicotSpec/v1`, três tipos: `clinical`, `prediction`, `methodological`, com
hipótese formal sempre obrigatória). Isso deixa de fora boa parte da pesquisa em saúde: estudos
observacionais, experimentos com animais ou de bancada, revisões, estudos qualitativos,
computacionais, teóricos, relatos de caso.

Três mudanças, decididas com o mantenedor em 2026-11-12:

1. **Posicionamento.** O PAR passa a ser assistente de **pesquisa em saúde**. README,
   manifestos, `pyproject`, `CITATION.cff`, CLI, `positioning` e skills trocam o enquadramento;
   a pesquisa clínica continua como um caso (o tipo `clinical`).
2. **A pergunta do estudo é o artefato principal** (ADR-0041). Novo schema `QuestionSpec/v1` em
   `.claude/question.toml`, com a pergunta em uma frase como único conteúdo sempre obrigatório.
   PICOT, PECO, PCC, PICo, SPIDER e outros viram **framework opcional** que decompõe a
   pergunta. O modo principal passa a ser `protocol question`; `picot` continua como apelido.
3. **Módulo `protocol`** (ADR-0042) substitui `clinical`, com `clinical` como apelido. Ganha
   orientação para CEUA (animais) e para quando o CEP é dispensável.

Sem breaking change: `picot.toml` antigo continua lido, o modo `picot` e `prumo add clinical`
continuam funcionando. Release PATCH pela ADR-0015 (invocável novo), ou MINOR se o mantenedor
tratar o reposicionamento como marco do ROADMAP.

## Decisões do mantenedor (2026-11-12)

| # | Pergunta | Decisão |
|---|---|---|
| D1 | Tipos de estudo | Taxonomia ampla. `clinical` continua como tipo próprio (intervenção em humanos). `experimental` é outro enfoque: animais, bancada, laboratório. |
| D2 | Estudos sem hipótese | Campo `objective`; hipótese obrigatória só onde há teste confirmatório. |
| D3 | Nome | `question` (pergunta do estudo) é o principal; PICOT e os demais frameworks ficam, como opcionais. |
| D4 | Módulo | Novo módulo `protocol`; `clinical` vira apelido. |

## `QuestionSpec/v1`

Arquivo canônico `.claude/question.toml`, tabela `[question]`:

```toml
[question]
type = "observational"
design = "coorte retrospectiva"
question = "Em adultos com DM2 atendidos na APS, o uso de iSGLT2 está associado a menor incidência de DRC em 5 anos, comparado à sulfonilureia?"
objective = "Estimar a associação entre iSGLT2 e DRC incidente."
created_at = "2026-11-12"
last_updated = "2026-11-12"
version = 1
framework = "PECOT"

[question.elements]
population = "Adultos com DM2 na APS de Belo Horizonte, 2015-2020"
exposure = "Início de iSGLT2"
comparison = "Início de sulfonilureia"
outcome = "DRC incidente (TFGe < 60 por 90 dias)"
time = "5 anos"

[question.hypothesis]   # opcional fora dos tipos confirmatórios
statement = "..."
rationale = "..."
metrics = ["HR", "IC 95%"]
```

### Campos

| Campo | Obrigatório | Nota |
|---|---|---|
| `schema_version` | default `"QuestionSpec/v1"` | |
| `type` | sim | ver tabela de tipos |
| `question` | sim | a pergunta em uma frase; fonte do render |
| `design` | não | subdesenho livre: "coorte prospectiva", "revisão de escopo", "ensaio pré-clínico em camundongos" |
| `objective` | conforme o tipo | objetivo geral |
| `framework` | não | `Literal` dos frameworks abaixo |
| `elements` | se houver `framework` | `dict[str, str]`; chaves do framework |
| `hypothesis` | conforme o tipo | o `Hypothesis` de hoje, reaproveitado |
| `contribution`, `hypothesis_validity_condition` | em `theoretical`/`methodological` | mesmos nomes do `PicotSpec` |
| `created_at`, `last_updated`, `version` | sim | como hoje |

### Tipos

| `type` | Para quê | Exige | Framework típico | Guideline de relato |
|---|---|---|---|---|
| `clinical` | intervenção em humanos (ensaio, quase-experimento) | hipótese | PICOT | CONSORT, SPIRIT |
| `experimental` | animais, bancada, in vitro | hipótese | PICOT | ARRIVE 2.0 |
| `observational` | coorte, caso-controle, transversal, prevalência, ecológico | objetivo ou hipótese | PECO(T), CoCoPop | STROBE (RECORD p/ dado rotineiro) |
| `prediction` | modelo, escore, biomarcador, teste diagnóstico ou prognóstico | hipótese | PICOT, PIRD | TRIPOD+AI, STARD |
| `review` | sistemática, meta-análise, escopo, rápida, umbrella | objetivo ou hipótese | PICOS, PECO, PCC, SPIDER | PRISMA 2020, PRISMA-ScR |
| `qualitative` | entrevistas, grupos focais, etnografia | objetivo | PICo, SPIDER | COREQ, SRQR |
| `mixed_methods` | quanti + quali integrados | objetivo ou hipótese | livre | GRAMMS |
| `economic` | custo-efetividade, custo-utilidade, impacto orçamentário | objetivo ou hipótese | PICO(T) | CHEERS 2022 |
| `computational` | simulação, bioinformática, modelagem, ML metodológico | objetivo ou hipótese | livre | conforme a aplicação |
| `theoretical` | modelo conceitual, ensaio teórico, ética, política | `contribution` + objetivo | nenhum | — |
| `methodological` | método estatístico ou de pesquisa novo | `contribution` + `hypothesis_validity_condition` + hipótese | nenhum | — |
| `case_report` | relato ou série de casos | objetivo | nenhum | CARE |
| `other` | escape para o que não cabe acima | objetivo ou hipótese | livre | — |

`clinical`, `prediction` e `methodological` mantêm as regras de hoje (D1). `prediction` continua
cobrindo acurácia diagnóstica (sem tipo `diagnostic` à parte: Princípio VIII).

### Frameworks

`framework` é opcional em todo tipo. Quando presente, `elements` precisa das chaves obrigatórias
e só aceita as chaves conhecidas do framework (erro com a lista certa e o comando de correção).

| `framework` | Chaves obrigatórias | Opcionais |
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

`comparison` opcional em PICOT preserva o `prediction` de hoje e o caso "sem comparador" do
`clinical` vira erro só se o tipo for `clinical` (regra de hoje, mantida: em `clinical` com
framework PICOT, `comparison` é obrigatório).

### Leitura do legado

- `read_question(pj)` lê `.claude/question.toml`; ausente, lê `.claude/picot.toml` e converte
  `PicotSpec` → `QuestionSpec` sem perda: `framework = "PICOT"` (nada em `methodological`),
  `elements` dos campos P/I/C/O/T não nulos, `question` gerada pela frase que o render acadêmico
  já produz hoje.
- A primeira escrita (`init`, `adr`) grava `question.toml` e remove `picot.toml` (o snapshot no
  ADR e o git guardam o antigo). O CHANGELOG avisa.
- Os blocos Markdown novos usam `<!-- question:begin v= hash= -->`; o substituidor reconhece e troca
  também o `<!-- picot:begin -->` antigo, então não sobram dois blocos.
- ADRs novos: `adr-NNNN-question-vN-<slug>.md`, snapshot em `<!-- question-snapshot -->`;
  `find_last_*` e o `diff` também leem os `picot-vN` e o snapshot antigo.
- `ComposeInputs/v1` ganha `question: QuestionSpec | None`; `picot` fica (forward-only) e só é
  preenchido enquanto o `picot.toml` antigo existir.
- O mod `hooks/mods/picot.ts` passa a injetar "Pergunta do estudo vigente" lendo `question.toml`,
  com `picot.toml` como fallback.
- `prumo status` fala em "pergunta do estudo"; o JSON ganha a chave `question` e mantém `picot`
  com o mesmo valor (consumidores existentes).

## Superfície

- `skills/protocol/modes/question.md` (novo, o principal) com o diálogo: tipo → pergunta em uma
  frase → framework sugerido pelo tipo (pode recusar) → elementos → objetivo/hipótese conforme
  o tipo → confirmação → `prumo protocol init`. `formalize`, `propagate` e `diff` iguais.
- `modes/picot.md` vira apelido: frontmatter próprio com as frases antigas e o corpo manda ler
  `question.md`. Frases novas: "fecha a pergunta do estudo", "qual o desenho do meu estudo",
  "monta a PCC da revisão".
- `prumo protocol *`: mesmos subcomandos; o JSON de entrada passa a ser `QuestionSpec` e aceita
  `PicotSpec` antigo (detectado pela ausência de `question`).
- `cep.md`: CEP para humanos, CEUA para animais (Lei 11.794/2008), e dispensa de CEP para revisão
  de literatura e dado público ou anonimizado de acesso aberto (Res. CNS 510/2016, art. 1º, parágrafo único).
- `sap.md`: não se aplica a `qualitative`, `theoretical`, `case_report`; para eles oferece plano
  de análise qualitativa ou nada.
- `review/references/reporting-guidelines.md`: tabela tipo → guideline acima.

## Módulo `protocol` (ADR-0042)

- `git mv templates/modules/clinical templates/modules/protocol`; `_module.toml` ganha
  `aliases = ["clinical"]`; descrição "Protocolo do estudo: pergunta, plano de análise,
  dicionário de dados, projeto CEP/CEUA".
- `get_module` resolve apelido; `prumo add clinical` aplica `protocol` e avisa do nome novo.
- Projetos com `clinical` aplicado: o `anchor` é o mesmo caminho, então `is_applied(protocol)` já
  é verdadeiro; nada a migrar.

## Posicionamento

Troca de "clinical research"/"pesquisa clínica" por "health research"/"pesquisa em saúde" em:
`README.md`, `.claude-plugin/plugin.json` e `marketplace.json`, `.codex-plugin/`,
`.antigravity-plugin/` (só `description` e `keywords`; versão continua do `sync_manifest_version`),
`pyproject.toml`, `CITATION.cff`, `src/par/__init__.py`, `src/par/cli.py`, `docs/positioning.md`,
`docs/onboarding-pesquisador.md`, `docs/Research Project Structure.md`, `ARCHITECTURE.md`,
`agents/reviewer.md`, e nas skills onde "clínico" é genérico (onde é de fato clínico, fica).
Keyword `health-research` entra; `clinical-research` fica.

Fora: a constitution não cita pesquisa clínica (só "extrair PICOT de PDF livre", que continua
verdadeiro), então não há emenda. Specs, planos arquivados e CHANGELOG antigos não mudam.

## Testes (TDD)

- `test_schemas_v1.py`: cada tipo com mínimo válido e com o campo que falta; cada framework com
  chave faltando e chave desconhecida; `clinical`/`prediction`/`methodological` de hoje
  continuam válidos convertidos.
- `test_question_io.py`: lê `question.toml`; fallback para `picot.toml` com conversão; escrita
  remove `picot.toml`.
- `test_render.py`: render por presença de framework (tabela de elementos) e sem framework
  (pergunta + objetivo); bloco `picot:begin` antigo é substituído.
- `test_adr.py`/`test_diff.py`: `find_last` acha `picot-vN` e `question-vN`; diff entre snapshot
  antigo e spec nova.
- `test_scaffold.py`/`test_cli_add.py`: `prumo add clinical` aplica `protocol`.
- `tests/mods/mods.test.tsx`: fallback para `picot.toml`.
- Índices: `gen_indexes.py --check` com o modo `question`.

## Riscos

- Princípio VIII: 13 tipos e 11 frameworks é muita escolha. Mitigação: a skill pergunta em
  linguagem natural ("o que você vai fazer?") e propõe tipo e framework; a pesquisadora só
  confirma.
- `elements` como `dict` perde tipagem campo a campo; o validador por framework compensa.
