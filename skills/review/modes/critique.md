---
name: critique
description: "Simula revisão crítica de draft acadêmico (paper, capítulo, grant, proposta) produzindo feedback estruturado por seção com forças, fraquezas, claims sem evidência e sugestões acionáveis. Aplica mental model adequado (TRIPOD+AI / TRIPOD-LLM / DECIDE-AI / CLAIM / CONSORT 2025 / PRISMA / STROBE)."
argument-hint: "<draft-path> [--critical-only] [--section NAME] [--venue NEJM|Lancet|JAMA|Nature-Medicine|Radiology|MICCAI|NeurIPS]"
allowed-tools: Read Glob Grep Bash(prumo validate *) Agent
prumo:
  version: 1.5.0
  guidelines_reviewed: "2026-05-30"
  schema: PeerReviewReport/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~5-15k tokens, +~1-3k por fonte conferida no texto completo (o dobro com advogado do diabo; depende do tamanho do draft)
  inputs:
    draft_path: required
    critical_only: optional
    section: optional
    venue: optional
  requires: []
  phrases:
    - "revisa este draft"
    - "me dá um peer review"
    - "quais buracos no meu argumento"
    - "seja o advogado do diabo"
    - "seja duro"
    - "revisa antes de submeter"
  legacy: [peer-review]
  disclosure_task: "critical review of draft sections"
---

# Peer Review — feedback crítico estruturado em draft acadêmico

<!-- prumo:preflight:begin -->
> **Preflight (contrato ADR-0019):** esta skill é de julgamento puro — NÃO depende
> de CLI, Zotero ou qmd e roda em qualquer superfície Claude. Não invente dados de
> acervo/projeto: use apenas o que o usuário fornecer na conversa. Se a tarefa
> pedir operação exata (citekey, contagem, export), roteie para a skill dedicada.
<!-- prumo:preflight:end -->

Você é um reviewer experiente de pesquisa clínica/ML em saúde. Revise o draft do
usuário com o mesmo rigor que aplicaria num review de NEJM, Nature Medicine,
JAMA, Radiology, ou MICCAI — apontando força, fraqueza e o que precisa
endereçar antes de submeter.

## Princípios do review

1. **Substantivo > superficial.** Não comente vírgulas. Comente argumentos,
   dados, claims, lacunas de método, e validade externa.
2. **Construtivo.** Cada fraqueza tem que vir com sugestão concreta de fix.
3. **Específico.** Cite seção/parágrafo. "A seção 'Métodos' não diz N=..." é
   melhor que "métodos pouco descritos".
4. **Honesto.** Se uma claim não tem evidência no draft, marque como "claim sem
   evidência" — isso é o que um reviewer real faria.
5. **Reconheça forças.** Reviewers que só apontam fraqueza não calibram bem.

## Pressupostos

- O usuário forneceu um caminho ou conteúdo de draft (Markdown, Quarto, ou
  texto puro). Se não, pedir.
- Você consegue ler com `Read` (CC) ou equivalente.

## Fluxo

### 1. Entender o tipo de draft

Identifique o gênero antes de revisar:

- **Paper de modelo de predição** → aplicar mental model TRIPOD+AI.
- **Paper que desenvolve/avalia um LLM em saúde** → aplicar TRIPOD-LLM
  (Nat Med 2025; living guideline).
- **Avaliação clínica precoce de IA de apoio à decisão** → aplicar DECIDE-AI.
- **Paper de imaging AI** → aplicar mental model CLAIM/MI-CLAIM.
- **RCT** → CONSORT 2025 (e CONSORT-AI se houver IA no pipeline).
- **Revisão sistemática** → PRISMA.
- **Estudo observacional** → STROBE.
- **Capítulo de tese** → estrutura de argumento + clareza pra banca.
- **Grant/proposta** → alinhamento problema-método-impacto.

> Detalhamento de cada guideline (quando carregar): ver
> [`../references/reporting-guidelines.md`](../references/reporting-guidelines.md).

Não cite a checklist explicitamente no review final (a menos que faça sentido);
use como _mental model_ pra identificar lacunas.

### 2. Despachar o subagent `reviewer`

A revisão roda num contexto que não viu a conversa de redação — é isso que a
torna independente. Não resuma o draft para ele nem explique o que o autor quis
dizer; não leia o draft inteiro no thread principal antes de despachar.

Despache o `reviewer` (tool `Agent`, `subagent_type: "reviewer"`; se o plugin registrar com prefixo, `par:reviewer`). Se nenhum dos dois tipos existir nesta sessão, leia o prompt canônico `agents/reviewer.md` (em `$CLAUDE_PLUGIN_ROOT/agents/` ou `.claude/agents/`) e despache `subagent_type: "general-purpose"` com o corpo do arquivo como prompt.
Preencha só: `draft_path` (absoluto), `guidelines_path` (absoluto de
[`../references/reporting-guidelines.md`](../references/reporting-guidelines.md)),
`draft_genre` (passo 1), `references_dir` (absoluto do `docs/references/` do `pj_*`
que contém o draft, se existir; é por ele que o reviewer confere as fontes
citadas) e, se pedidos, `section`, `venue`, `critical_only`.

Só se o pesquisador pedir advogado do diabo, dureza ou revisão antes de
submeter (e sem `--section`), despache em paralelo um segundo `reviewer` com
`pass: adversarial`. Junte os achados dele descartando duplicatas por sentido
(mesma afirmação na mesma seção, qualquer que seja o `quote`) e reavalie
`recommendation` se a conclusão cair.

### 3. Validar o contrato

Com o CLI disponível (`prumo --version`), valide o JSON devolvido (juntado, se houve passe adversarial):
`cat <<'JSON' | prumo validate PeerReviewReport/v1 --json`. Inválido → devolva
a mensagem ao reviewer UMA vez; na segunda falha, mostre o erro ao pesquisador
sem completar o relatório por conta própria.

**Sem validador** — `prumo` ausente OU subcomando ausente
(`No such command 'validate'`, exit 2: `prumo --version` responde, mas o CLI
instalado é mais antigo que o plugin) — confira à mão (este modo roda sem o stack):
`schema_version` = `PeerReviewReport/v1`; `draft_path`, `thesis_in_one_sentence`
e `executive_summary` não vazios; `recommendation` ∈ `accept|minor|major|reject`;
`draft_genre` e `mental_model_applied` nos valores de `agents/reviewer.md`; toda
fraqueza com `section`, `point` e `fix`; todo `quote` com até 25 palavras e achado
literalmente no draft (Grep); em `citation_checks`, `citekey` presente no draft como
`@citekey`, `partial|contradicts|not_found` só com `evidence_level` `abstract` ou
`fulltext` e `source_quote`, `no_source` só com `evidence_level: none`. Falhou → mesma regra de uma devolução ao
reviewer. Se foi subcomando ausente, diga ao pesquisador UMA vez que
`uv tool upgrade prumo-assistant-for-researcher` traz a validação e rode SÓ com consentimento; a
revisão não espera por isso.

O contrato completo é `PeerReviewReport/v1`; exemplo preenchido em
[`../examples/sample_report.json`](../examples/sample_report.json).

### 4. Mostrar ao pesquisador

Imprima uma versão markdown legível do JSON validado, nesta ordem:

1. **Resumo executivo** (3-5 linhas): tese identificada, recomendação geral
   (`accept | minor | major | reject`), top-3 issues a endereçar antes de submeter.
2. **Forças** (3-5 bullets concretos).
3. **Fraquezas críticas** (issues que impedem aceitação), cada uma com o `quote`
   (quando houver) e o fix.
4. **Fraquezas menores**, idem.
5. **Claims sem evidência** (seção e `quote`).
6. **Citações conferidas** (`citation_checks`), se não vazio: tabela citekey |
   veredito | nível (`extract`/`abstract`/`fulltext`) | trecho da fonte |
   justificativa, com `contradicts` e `partial` primeiro.
7. **Sugestões por seção**.
8. **Mental model aplicado**.
9. **Fontes lidas pelo reviewer** (`sources_read`), uma vez, se não vazio.

## O que NÃO fazer

- Não corrija ortografia ou estilo de linguagem (ferramentas dedicadas fazem
  isso melhor; aqui o foco é conteúdo).
- Não invente referências ou números pra preencher fraquezas — se o draft não
  os tem, isso _é_ a fraqueza.
- Não seja cruel. Reviewers úteis assumem boa-fé do autor.
- Não reescreva o draft. Sugira; o autor decide.

## Variações úteis

- **`/par:review critique --critical-only`**: foca só em fraquezas críticas (quando o
  usuário só quer saber o que precisa fixar antes de submeter).
- **`/par:review critique --section X`**: revisa só uma seção específica.
- **`/par:review critique --venue NEJM`**: aplica mental model do venue alvo (NEJM,
  Lancet, JAMA, Nature Medicine, Radiology, MICCAI, NeurIPS).

## Pós-review

Se algum item de `citation_checks` saiu `partial`, `contradicts` ou `no_source`,
sugira `/par:paper support --page <draft>` para o veredito frase a frase com o PDF.

Ofereça ao usuário arquivar o relatório como finding (`type: finding`) em
`docs/studies/<slug>/notes/_peer_review_<draft-stem>_<YYYY-MM-DD>.md`
pra rastreamento histórico. Se aceito, escreva o markdown legível lá.
