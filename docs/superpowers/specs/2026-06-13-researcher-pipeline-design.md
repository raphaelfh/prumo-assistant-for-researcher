---
title: Pipeline do pesquisador — espinha de processo estilo superpowers sobre as capacidades do prumo-assist
date: 2026-06-13
status: approved
tags: [pipeline, process, superpowers, cli-bridge, picot, peco, rwe, omop, prisma, equator, ai-reporting, skills, governance]
---

# Pipeline do pesquisador — a fórmula superpowers aplicada ao ciclo de pesquisa clínica

## Resumo executivo

O prumo-assist tem todas as **capacidades** do ciclo de pesquisa (PICOT, Zotero/bibliografia, wiki, escrita, peer-review) mas quase nada da **camada de processo** que faz o [obra/superpowers](https://github.com/obra/superpowers) funcionar: bootstrap ativo por sessão, Iron Laws, gates encadeados, red flags contra racionalizações, e disparo testado como comportamento. Este é o espelho invertido do superpowers, que tem ~14 skills e *nenhuma* é uma capacidade — todas são processo.

Esta spec é um **guarda-chuva** que adiciona a espinha de processo sobre as capacidades existentes e preenche as lacunas do ciclo, em 5 fases sequenciais, cada uma com fronteira de release limpa. Antes de tudo, uma **ponte CLI** torna `prumo` a única superfície determinística (resolvendo a fragilidade de import que motivou o trabalho) e remove a lógica embutida em `skills/*/scripts/` — fazendo a constitution I (lógica em um lugar só) virar literal na árvore de arquivos.

A diretriz transversal, repetida pelo dono ao longo do brainstorming: **a simplicidade e a baixa fricção do superpowers são o objetivo** — um pesquisador que abandona a ferramenta na primeira vez que ela o bloqueia indevidamente não volta. Por isso: Iron Law dura (integridade), gates de etapa suaves (advisory + confirmação).

Decisões travadas com o dono: ponte CLI (não import direto); spec guarda-chuva; escopo retrofit + lacunas, **ambas** as trilhas (primário e síntese); enforcement Iron-Law-dura/gate-suave; teste de prosa via runner local opt-in (não no CI); profundidade da síntese = protocolo + artefatos (sem orquestrar triagem); fenótipo OMOP = spec versionada no prumo com execução externa; pré-registro derivado da spec do prumo (que congela ao registrar); camada `-AI` transversal; ética brasileira = gerar CEP/Plataforma Brasil hoje + INAEP como TODO sinalizado.

## Contexto e problema

### O gatilho imediato (fragilidade de import)
`grep -rn "uv run python -c\|python3 -c\|from prumo_assist" skills/*/SKILL.md` mostra que `paper-extract`, `write-*` e `wiki-query` instruem o agente a `from prumo_assist...` dentro do projeto consumidor `pj_*`. Mas o pacote é distribuído via `uv tool install` (venv isolado) e `templates/pj_base/pyproject.toml` **não** declara prumo-assist como dependência — o import pode falhar no ambiente do consumidor. Além disso, 8 scripts em `skills/{active-learning,formulate-picot}/scripts/*.py` importam o pacote pelo mesmo caminho frágil.

### O problema estrutural (a camada que falta)
A destilação do superpowers (workflow `distill-superpowers`, 2026-06-12) identificou os mecanismos transferíveis, por impacto:
1. **Bootstrap ativo** — hook SessionStart injeta a meta-skill inteira (matcher `startup|clear|compact`); descrição passiva no system prompt é ignorada sob pressão. Crítico: sessões de escrita acadêmica são longas e sofrem compaction.
2. **Iron Law por skill** — uma regra absoluta, em caps, "violar a letra = violar o espírito".
3. **Tabela de racionalizações** — nomear verbatim as desculpas reais; exige **TDD de prosa** (capturar a racionalização *sem* a skill antes de escrevê-la).
4. **Pipeline encadeado com gates** — cada skill nomeia a próxima e proíbe atalhos por nome.
5. **Disparo testado como comportamento** — prompt ingênuo headless que *deve* disparar; erro plantado que o revisor *deve* achar.

O que **não** transferir: infra multi-host, conteúdo de engenharia das skills, granularidade de 2-5 min por passo, agents nomeados (já removidos no prumo via ADR-0012, e o superpowers os removeu em v5.1.0).

### O ciclo real (corrigido por pesquisa)
A pesquisa de taxonomia (workflow `research-clinical-lifecycle`, fontes: Röhrig PMC5037941, FDA RWE framework, Cochrane, OHDSI, EQUATOR) corrigiu uma confusão do design inicial: **revisão da literatura** (narrativa) é um *passo* do tronco comum, presente em todo projeto — distinto de **revisão sistemática**, que é um *desenho de estudo secundário*. Ver a Seção "Pipeline corrigido".

## Decisões travadas

### Distribuição e ponte
- **D1 — Ponte CLI, não import direto.** Toda operação hoje invocada por `uv run python -c "from prumo_assist..."` na prosa vira subcomando `prumo` (CLI já entra no PATH via `uv tool`). Os 8 `skills/*/scripts/*.py` são deletados; sua lógica já vive (ou passa a viver) em `domains/`. Alinha à constitution I. Registrado em ADR.
- **D2 — Distribuição via git+https por ora.** Pré-requisito documentado: `uv tool install git+https://github.com/raphaelfh/prumo-assist`. Sem PyPI agora (trigger de revisão: publicação no PyPI reabre a opção `uv run --with`). README/`prumo doctor` passam a checar o CLI.

### Forma do programa
- **D3 — Spec guarda-chuva, planos por fase.** Uma spec; cada fase (A–E) vira um plano próprio executado e liberado em sequência. A→B→C dependentes; D/E transversais.
- **D4 — Escopo: retrofit + lacunas, ambas as trilhas.** Aplicar a anatomia superpowers aos 14 skills existentes e adicionar skills de lacuna, cobrindo trilha primária e trilha de síntese.

### Enforcement (adoção)
- **D5 — Iron Law dura, gate de etapa suave.** Inviolável (bloqueia sempre): integridade — nenhuma afirmação factual sem citekey resolvível no Zotero; nenhum item EQUATOR marcado sem evidência no texto. Transições de etapa (ex.: ir ao manuscrito sem protocolo) **avisam** com forte recomendação e pedem confirmação, mas não travam.

### Trilhas e artefatos
- **D6 — Síntese = protocolo + artefatos, sem orquestrar triagem.** prumo gera protocolo PRISMA-P, strings de busca por base, scaffold do fluxograma PRISMA e template de extração; delega a dupla-triagem/extração a Covidence/Rayyan. Não reconstrói um Covidence pela metade.
- **D7 — Fenótipo OMOP = spec versionada no prumo, execução externa.** O cohort definition/fenótipo (JSON ATLAS + concept sets + racional) é artefato de 1ª classe versionado no domínio `protocol`, frozen-after-accepted como os ADRs de PICOT. A execução (ATLAS/HADES/Strategus) fica externa, referenciada por ponteiro.
- **D8 — Pré-registro derivado, que congela a spec.** O protocolo no prumo é a fonte; o texto de registro (PROSPERO/OSF/ClinicalTrials/ReBEC) é artefato gerado dela. Ao registrar, o número/timestamp volta e congela o protocolo — mudança vira emenda + changelog (espelha ADR/forward-only).
- **D9 — Camada `-AI` transversal.** Uma capacidade `-AI` que detecta o ramo-base e anexa o checklist `-AI` combinável correto (predição→TRIPOD+AI, LLM→TRIPOD-LLM, diagnóstico→STARD-AI, imagem→CLAIM), com fallback explícito para a lacuna RECORD-AI. `-AI` é sempre combinável, nunca substituta do checklist-base.
- **D10 — PECO de primeira classe.** `formulate-picot` abraça PECO (exposição) além de PICOT (intervenção) e passa a ser também o **gate de desenho** (pergunta → framework → recomendação de desenho → viabilidade). PECO é o framework natural do RWE/OMOP.

### Teste e ética
- **D11 — Teste de prosa via runner local opt-in.** `tests/skills/` com headless `claude -p` + parse de transcript (testes de disparo + erros plantados). Rodado à mão antes de release; **nunca** no CI automático (zero custo de LLM no GitHub Actions). O CI segue determinístico.
- **D12 — Ética brasileira: gerar hoje, INAEP como TODO.** Gerar artefatos CEP/Plataforma Brasil agora (template já existe); tratar a transição CONEP→INAEP (Decreto 12.651/2025) como TODO sinalizado no gate de ética, sem esperar a normatização assentar.

## Seção 0 — Responsabilidades e anatomia (governante)

Toda fase A–E obedece a este mapa. Cada arquivo escrito tem um lar único e óbvio.

### Mapa de responsabilidades (um local = um tipo de conhecimento)

| Local | Responsabilidade ÚNICA | Natureza |
|---|---|---|
| `src/prumo_assist/` (CLI `prumo`) | **toda** lógica determinística — a única ponte | código LLM-free, testado |
| `skills/<n>/SKILL.md` | QUANDO disparar + caminho feliz + Iron Law + gates | prosa agêntica, ≤~250 linhas |
| `skills/<n>/references/*.md` | conhecimento de domínio pesado, on-demand | referência (nome = responsabilidade) |
| `skills/<n>/<papel>-prompt.md` | template de prompt de subagente | template |
| `skills/<n>/template.md`, `examples/` | template de saída / exemplo de referência | conteúdo |
| `skills/using-prumo/` (injetada por hook) | a disciplina: mapa do ciclo, regra 1%, red flags, índice de Iron Laws | meta-skill |
| `hooks/` | mecanismo de bootstrap (injeção) | infra do plugin |
| `docs/constitution.md` | princípios (normas vivas) | governança |
| `docs/adr/` | decisões pontuais (imutáveis após aceitas) | registro |
| `docs/superpowers/specs\|plans/` | design e execução de feature | workflow |
| `docs/` (vault) | knowledge base de uso/orientação | vault Obsidian |
| `templates/` | scaffolding de projetos `pj_*` (PRODUTO) | conteúdo distribuído |
| fenótipo OMOP (em `domains/protocol`) | definição versionada, frozen-after-accepted | artefato |
| `tests/unit/` | verificação determinística (CI) | testes |
| `tests/skills/` (novo) | verificação de comportamento (opt-in, local) | testes de prosa |
| `.github/scripts/` | derivadores/validadores (gen_indexes, sync, audit) | infra |

### Anatomia canônica do SKILL.md (codificada em `.claude/rules/skill-anatomy.md`)

Ordem fixa: frontmatter (`name`/`description` universais + bloco `prumo:`) → H1 → linha de *announce* → Iron Law (quando aplicável) → Pressupostos → Fluxo/Operações numerado (cada passo termina num comando `prumo`) → Gates (suaves, com REQUIRED-NEXT nomeando `/prumo-assist:<skill>`) → Red flags (tabela) → Boundaries → Erros comuns. Material pesado → `references/<topico>.md`.

Convenções: `description` diz **QUANDO** disparar (nunca **O QUE** a skill faz — o resumo do workflow faz o agente pular o corpo); orçamento de tamanho do corpo ≤~250 linhas para skill de capacidade (a meta-skill é exceção); apoio nomeado por responsabilidade (`references/<topico>.md`, `<papel>-prompt.md`, `template.md`, `examples/`). Equivalente enxuto do `writing-skills` do superpowers (a maior skill deles — o controle de qualidade).

Check automatizável: `gen_indexes.py --check` avisa quando um SKILL.md passa do orçamento (extraia para `references/`).

## Pipeline corrigido

### Tronco comum (todo projeto, qualquer desenho)
```
ideia → revisão da literatura (PASSO narrativo) → pergunta estruturada → hipótese/objetivos → [GATE de desenho]
```
- **Revisão da literatura** = passo narrativo de fundamentar a pergunta e achar a lacuna. Já coberto por `wiki-ingest`/`paper-manager`/`paper-extract`/`wiki-query`. **Não é lacuna, não é ramo.**
- **Pergunta estruturada** ramifica o framework: **PICOT** (intervenção) vs **PECO** (exposição — RWE/OMOP).

### Ramificação (decidida pela natureza da pergunta + viabilidade do dado)
```
[GATE]
 ├─ PRIMÁRIO intervencional ── ECR / pragmático
 ├─ PRIMÁRIO observacional ─── coorte / caso-controle / transversal
 │      └─ sub-trilha RWE/OMOP: PECO + gate de viabilidade no CDM
 │         (a coorte existe? exposição e desfecho mensuráveis? poder?)
 │         artefato de 1ª classe: cohort definition / fenótipo (D7)
 └─ SECUNDÁRIO / síntese ───── revisão sistemática / metanálise / escopo
```
- **Estudo primário** = gera dado novo. **RWE/OMOP é observacional primário** (gera dado novo a partir de dados do mundo real) — **não é síntese**.
- A revisão **narrativa** não aparece aqui (é o passo do tronco). Só a **sistemática** (protocolo PROSPERO + busca reprodutível + RoB) é desenho.

### Convergência (pós-ramo)
```
manuscrito → peer-review → submissão
```
com três gates por ramo: (1) protocolo + registro + ética (pré-estudo); (2) condução/diagnostics; (3) manuscrito + checklist de relato + número de registro (submissão). Diretriz anexada por ramo (STROBE/RECORD p/ observacional, PRISMA p/ síntese, CONSORT p/ ECR); camada `-AI` combinável (D9).

### Mapa etapa → diretriz/registro → artefato (resumo)
| Etapa / ramo | Diretriz | Registro | Artefato canônico |
|---|---|---|---|
| Tronco — revisão da literatura | (passo) | — | notas, lacuna, introdução |
| Tronco — pergunta estruturada | — | — | PICOT/PECO; hipótese; objetivos |
| Primário intervencional (ECR) | CONSORT 2025 (+CONSORT-AI) | ClinicalTrials.gov / ReBEC | protocolo SPIRIT 2025; SAP; CONSORT flow |
| Primário observacional | STROBE | OSF | protocolo; SAP |
| Sub-trilha RWE/OMOP | RECORD/RECORD-PE (+STROBE) | OSF | fenótipo (JSON+concept sets); SAP; study diagnostics |
| Secundário — revisão sistemática | PRISMA 2020 | PROSPERO/OSF | protocolo PRISMA-P; strings; fluxograma PRISMA; tabela de extração |
| Modelos de predição (ML/LLM) | TRIPOD+AI / TRIPOD-LLM | OSF | especificação do modelo; validação |
| Acurácia diagnóstica / imagem | STARD 2015 / CLAIM 2024 (+ -AI) | OSF | tabela 2×2; STARD flow |
| Ética (Brasil) | — | Plataforma Brasil/CEP (INAEP = TODO) | projeto CEP, TCLE |

Lacunas embutidas: CONSORT/SPIRIT 2025 saíram sem guidance de IA (camada `-AI` é combinável); **não existe RECORD-AI** (fallback explícito); STROBE ainda 2007.

## Fases (cada uma um plano + release próprio)

### Fase A — Ponte CLI (pré-requisito; release MINOR)
~10 subcomandos `prumo`, fachadas finas via `cli_run`, todos com `--json`, substituindo snippets de prosa e os 8 scripts. Contrato único: corpo markdown via stdin (heredoc, nunca escapado em JSON); payload estruturado via stdin JSON quando já é schema; metadados via flags; relatório via `--json`. Comandos *prep* compõem validação + leitura de contexto num só (paper-extract: 4 passos → 2). `prumo config` standalone morre (YAGNI). Deleta `skills/{active-learning,formulate-picot}/scripts/`. Check `command -v prumo` com erro acionável nas Pressupostos dos 9 skills afetados. ADR + ADR do `--audit` reverso (pega CITATION.cff).

### Fase B — Espinha de processo (release MINOR)
Meta-skill `using-prumo` + hook SessionStart (`startup|clear|compact`, shipped em `hooks/` + wiring no `plugin.json`, convivendo com o hook PreToolUse do graphify). `start` permanece como router conversacional. Retrofit uniforme dos 14 skills à anatomia da Seção 0 (announce, Iron Law, red flags, gate suave com REQUIRED-NEXT, rígido/flexível). Iron Laws duras com backend determinístico de verificação ("citekey resolvível" checado via `prumo` contra `_references.bib`/Zotero). `.claude/rules/skill-anatomy.md`. ADRs (process skills de 1ª classe; bootstrap hook).

### Fase C — Pipeline + lacunas (release MINOR, possivelmente 2)
- `formulate-picot` abraça PECO + vira gate de desenho (D10).
- Skill de síntese: protocolo PRISMA-P, strings, scaffold PRISMA, template de extração (D6).
- Skill de submissão: cover letter + checklist EQUATOR por ramo + resposta a revisor.
- Fenótipo OMOP como artefato versionado em `domains/protocol` (schema v1, frozen-after-accepted) + ponteiro de execução (D7).
- Pré-registro derivado que congela o protocolo (D8).
- Camada `-AI` transversal (D9).
- Gate de ética: CEP/Plataforma Brasil + INAEP TODO (D12).

### Fase D — Runner de teste de skills (não-releasável)
`tests/skills/` opt-in (headless `claude -p` + parse de transcript): testes de disparo (prompt ingênuo deve disparar a skill certa) + erros plantados (draft com citação fantasma, n inconsistente, superlativo → peer-review deve recusar). Disciplina TDD-de-prosa documentada na rule. Não entra no CI (D11).

### Fase E — Governança (infra, não-releasável)
ADRs de cada modo/decisão; `bump --audit`; ROADMAP atualizado; eventual emenda da constitution (disciplina de processo como princípio, ou ADR); CHANGELOG por fase liberável.

## Fora de escopo (YAGNI)
- Orquestração de triagem/extração de revisão sistemática (delega a Covidence/Rayyan — D6).
- Execução de fenótipo OMOP (ATLAS/HADES/Strategus runtime — só a spec versionada é do prumo — D7).
- Publicação no PyPI (deferida com trigger — D2).
- Testes de prosa no CI (deferido; runner local — D11).
- Skills `-AI` separadas por objeto (camada transversal escolhida — D9).
- RECORD-AI (não existe; fallback explícito — D9).
- Infra multi-host (Cursor/Codex/Gemini), agents nomeados (ADR-0012), granularidade de 2-5 min por passo.
- Reescrita de skills existentes além do retrofit de anatomia.
- Análise estatística/execução de código (é Jupyter/código do consumidor, não o prumo).

## Critérios de sucesso
1. Nenhum skill instrui `from prumo_assist` na prosa; `grep -rn "from prumo_assist" skills/` vazio; `skills/*/scripts/` não existe.
2. `prumo --help` expõe os subcomandos novos; cada um com `--json` e erro acionável quando pré-requisito falta.
3. Sessão nova injeta `using-prumo` (mapa do ciclo + Iron Laws + red flags); sobrevive a `/clear` e compaction.
4. Cada um dos 14 skills segue a anatomia da Seção 0; `gen_indexes.py --check` não acusa SKILL.md acima do orçamento.
5. Iron Law de citação bloqueia afirmação factual sem citekey resolvível (verificado por `prumo`, não pelo LLM).
6. `formulate-picot` aceita PECO e emite recomendação de desenho com gate de viabilidade; o pipeline ramifica corretamente primário/observacional/RWE-OMOP/síntese.
7. Skill de síntese gera protocolo PRISMA-P + strings + scaffold PRISMA sem reconstruir triagem; skill de submissão anexa o checklist EQUATOR correto por ramo com camada `-AI` combinável.
8. Fenótipo OMOP versionado e congelável no `protocol`; pré-registro gerado da spec e congelando-a.
9. `tests/skills/` roda localmente: prompt ingênuo dispara a skill certa; draft com erros plantados é recusado pelo peer-review.
10. Cada fase liberável tem release MINOR próprio com tag; fases D/E não bumpam versão.

## Itens abertos / triggers
- Publicar no PyPI → reabre `uv run --with prumo-assist` e simplifica o pré-requisito (revisar a Fase A).
- INAEP normatizado → materializar o gate de ética além do TODO sinalizado.
- RECORD-AI publicado → trocar o fallback da camada `-AI` pelo checklist real.
- `domains/protocol/adr.py` tocado → reavaliar alinhamento `docs/decisions/`→`docs/adr/` no produto (ADR-0001).
