---
title: Skill `/prumo-assist:formulate-picot` — formulação e propagação de PICOT
date: 2026-05-03
status: approved
tags: [skill, picot, protocol, project, decisions, formulate-picot]
---

# Skill `/prumo-assist:formulate-picot`

## Resumo executivo

Skill que formaliza, propaga e mantém consistente a PICOT do projeto. Canônico em `.claude/picot.toml` (machine-readable + Pydantic-validado). Renderiza blocos delimitados em `docs/protocol.md` (operacional), `docs/project.md` (acadêmico) e gera ADRs em `docs/decisions/` quando a versão do PICOT muda. Auto-detecta o modo (Socrático / Formalize / Propagate / Diff) pelo estado dos arquivos. Suporta variantes clínica e metodológica. **Single PICOT por projeto, hipótese formal única**.

## Contexto e problema

Hoje a formulação de PICOT é totalmente manual:
1. `wiki-query "qual o PICOT atual?"` retorna o que já está escrito em prosa nos arquivos.
2. Usuário edita `docs/protocol.md` (operacional) à mão.
3. Edita `docs/project.md` (formal) à mão — facilmente diverge do operacional.
4. Cria `docs/decisions/adr-NNNN-*.md` à mão, sem snapshot da PICOT vigente.

**Falhas observadas em projetos reais** (`pj_piloto_ml`):
- PICOT existe em 3 formas (operacional, acadêmica, histórica) sem fonte de verdade machine-readable. A consistência depende de disciplina humana.
- Mudanças estruturais (ex.: adicionar coorte, refinar desfecho) deixam pistas em ADRs mas não geram diff explícito entre versões.
- A hipótese formal evolui (`v9-banca` consolidou 3 RQs em 1) sem rastreio campo-a-campo.
- A entrada em busca focada pós-PICOT (cf. canvas `journey.canvas`, Fase 1) depende do PICOT estar fechado — sem skill formal, pesquisador "fecha de ouvido".

**Objetivo da skill**: dar à PICOT um único formato canônico (`PicotSpec/v1`) que serve de fonte pra todos os artefatos derivados, com diff explícito entre versões e ADRs gerados automaticamente.

## Decisões arquiteturais

### D1 — Modo de operação: auto-detect com 4 sub-operações

A skill tem **uma entrada principal** (`/prumo-assist:formulate-picot`) que detecta o estado e despacha:

| Estado detectado | Sub-operação | Comportamento |
|---|---|---|
| `.claude/picot.toml` ausente | `init` | Socrático (pergunta P/I/C/O/T ancorado em wiki-query) |
| `picot.toml` ausente, mas `protocol.md`/`project.md` têm prose | `formalize` | Extrai prose existente, propõe estrutura, confirma com usuário |
| `picot.toml` existe; blocos delimitados nos destinos vazios ou stale (hash mismatch) | `propagate` | Regenera blocos `<!-- picot:begin/end -->` em `protocol.md` + `project.md` |
| `picot.toml` mudou desde último ADR (version bump) | `diff` | Compara, pergunta motivação, gera ADR + propaga |

Sub-operações também podem ser invocadas explicitamente:
```
/prumo-assist:formulate-picot init
/prumo-assist:formulate-picot formalize
/prumo-assist:formulate-picot propagate
/prumo-assist:formulate-picot diff
```

### D2 — Canônico em `.claude/picot.toml` (machine-readable)

Fonte única de verdade pra estrutura PICOT. TOML por:
- Legível por humano
- Schema strict (Pydantic valida no read/write)
- Já é o formato de `pj_config.toml` no `.claude/`
- Não conflita com YAML frontmatter de `protocol.md` (que é prose curada por humano)

Os 3 destinos (`protocol.md`, `project.md`, ADRs) são **renders** (não fontes). Editor humano edita `picot.toml` diretamente OU via skill; nunca direto nos blocos delimitados (mas pode editar prose ao redor dos blocos sem problema).

### D3 — Schema `PicotSpec/v1`

```toml
[picot]
type = "clinical"            # "clinical" | "methodological"
created_at = "2026-05-03"    # ISO date, primeira escrita
last_updated = "2026-05-03"  # ISO date, última escrita
version = 1                  # incrementa em mudança estrutural

# Campos clínicos (P/I/C/O/T)
# Em type="methodological", I/C/T podem ser null;
# em type="clinical", todos obrigatórios.
population = "..."           # quem (coorte/dataset)
intervention = "..."         # o que (modelo/método sob teste)
comparison = "..."           # contra quê (baseline canônico)
outcome = "..."              # como medir (métrica primária + threshold)
time = "..."                 # janela temporal (retrospectivo/prospectivo)

# Campos metodológicos (opcionais em "clinical", obrigatórios em "methodological")
contribution = "..."         # claim teórico/metodológico (frase única)
hypothesis_validity_condition = "..."  # sob qual condição a contribution vale

[picot.hypothesis]
statement = "..."            # hipótese formal única (frase declarativa)
rationale = "..."            # por que esperamos isso (referência a literatura ok)
metrics = ["AUROC", "ECE"]   # como testar (lista de métricas)
```

**Validação** (Pydantic):
- `type ∈ {clinical, methodological}`
- `version: int >= 1`
- `created_at`, `last_updated`: ISO 8601 date
- Se `type = "clinical"`: P/I/C/O/T não-vazios
- Se `type = "methodological"`: `contribution` + `hypothesis_validity_condition` não-vazios
- `hypothesis.statement`: não-vazio sempre
- `hypothesis.metrics`: lista não-vazia de strings

Schema vive em `src/prumo_assist/domains/protocol/schemas/v1.py` (consistente com o padrão de `domains/paper/schemas/v1.py` que abriga `PaperCallout/v1`). PICOT é responsabilidade do domínio `protocol`, não do core. **Note (TOML)**: TOML não tem `null` nativo. Em `type = "methodological"`, os campos `intervention`/`comparison`/`time` podem ser **omitidos** do arquivo (ausência ≡ null no Python via Pydantic `Optional`); em `type = "clinical"`, qualquer ausência falha na validação.

### D4 — Render mecanismo: blocos delimitados + hash de drift

Cada destino derivado tem um **bloco delimitado** com versão e hash:

```markdown
<!-- picot:begin v=3 hash=a1b2c3d4 -->
... conteúdo regenerável ...
<!-- picot:end -->
```

- `v=N` = `[picot].version` do TOML que gerou esse bloco
- `hash=<sha8>` = `sha256(toml_content)[:8]` — permite detectar drift sem reabrir picot.toml

**Render por destino**:

**`protocol.md` (operacional)**:
```markdown
<!-- picot:begin v=3 hash=a1b2c3d4 -->
**População operacional.** {population}

**Intervenção (sob teste).** {intervention}

**Comparação (baseline).** {comparison}

**Desfecho primário.** {outcome}

**Janela temporal.** {time}

**Hipótese formal.** {hypothesis.statement}

*(Métricas: {hypothesis.metrics | join: ", "}.)*
<!-- picot:end -->
```

**`project.md` (acadêmico)**:
```markdown
<!-- picot:begin v=3 hash=a1b2c3d4 -->
## Pergunta de pesquisa

{rendered_paragraph_with_population_intervention_comparison_outcome}

## Hipótese central

{hypothesis.statement}.
{hypothesis.rationale}

{contribution_paragraph_if_methodological_or_hybrid}
<!-- picot:end -->
```

**ADR `decisions/adr-NNNN-picot-v<N>.md`** (gerado só em version bump):
```markdown
---
adr: NNNN
title: PICOT v<N> — <slug-da-mudança>
date: <ISO>
supersedes: adr-(NNNN-1)-picot-v(N-1)
status: accepted
---

# ADR-NNNN: PICOT v<N> — <slug>

## Mudanças (vs v<N-1>)

- **`population`**:
  - antes: "..."
  - agora: "..."
- **`hypothesis.statement`**:
  - antes: "..."
  - agora: "..."

## Motivação

{usuário-respondeu-na-skill}

## Snapshot do PicotSpec/v<N>

<!-- picot-snapshot:begin -->
```toml
[picot]
type = "clinical"
version = 3
...
```
<!-- picot-snapshot:end -->
```

ADRs são **append-only** — nunca regenerados. O snapshot dentro do ADR serve como ground-truth pra `diff` futuro.

### D5 — Detecção de mudança (`diff`)

`formulate-picot diff` faz:

1. Lê `.claude/picot.toml` atual
2. Acha último ADR com `picot-v<N-1>` slug (escaneando `decisions/adr-*-picot-v*.md` por timestamp)
3. Extrai TOML do `<!-- picot-snapshot:begin/end -->` do ADR antigo
4. Compara campo-a-campo (deep diff em nested dicts)
5. Pra cada campo mudado, mostra antes/depois e pergunta motivação
6. Bump de versão automático: se algum campo "estrutural" mudou, `[picot].version += 1`
7. Cria `adr-NNNN-picot-v<N>-<slug>.md`
8. Chama `propagate` pra atualizar blocos delimitados

Campos **estruturais** (mudança = bump de versão + ADR):
- `type`, `population`, `intervention`, `comparison`, `outcome`, `time`
- `contribution`, `hypothesis_validity_condition`
- `hypothesis.statement`, `hypothesis.metrics`

Campos **não-estruturais** (mudança não bump):
- `last_updated` (sempre atualiza)
- `hypothesis.rationale` (refinamento textual; não bump)

## Arquitetura

### Componentes

```
src/prumo_assist/
├── core/
│   └── picot.py                  ← schema PicotSpec/v1 + read/write/diff helpers
├── domains/
│   └── protocol/                 ← novo domínio (ou anexar a paper/?)
│       ├── __init__.py
│       ├── api.py                ← re-export
│       ├── cli.py                ← (sub-comandos prumo protocol *? opcional)
│       ├── render.py             ← render TOML → bloco markdown por destino
│       ├── diff.py               ← compara TOML vs ADR snapshot
│       └── adr.py                ← gera ADR a partir de diff
skills/
└── formulate-picot/
    └── SKILL.md                  ← prompt do agente Socrático/Formalize
```

**Decisão**: criar novo domínio `domains/protocol/`. Justificativa: PICOT é metadata do **estudo** inteiro (escopo cross-cutting); `domains/paper/` é metadata por paper (escopo por-citekey). Conflar os dois nomeia mal as responsabilidades. O custo de criar um domínio novo é trivial (segue padrão existente de `paper`/`wiki`/`write`/`capture`).

### Fluxo de dados

```
                       ┌─────────────────────┐
                       │  .claude/picot.toml │  ← canônico
                       │  (PicotSpec/v1)     │
                       └──┬──────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
   render.protocol  render.project   diff vs último ADR snapshot
        │                 │                 │
        ▼                 ▼                 ▼
  protocol.md         project.md      adr-NNNN-picot-v<N>.md
  bloco delimitado    bloco delimitado    (gerado em bump)
```

### Operações em detalhe

**`init` (Socrático, greenfield)**:
1. Validar precondições: `.claude/picot.toml` ausente.
2. Ler wiki via `wiki-query` ou agente `ml-theory-expert` (contexto: o que o usuário já sabe sobre o tema?).
3. Perguntar (uma por vez):
   - "Qual o tipo de estudo: clínico ou metodológico?"
   - Se clínico: P → I → C → O → T (em sequência, com sugestões do wiki)
   - Se metodológico: contribution + hypothesis_validity_condition
   - Hipótese: statement + rationale + metrics
4. Mostrar TOML proposto, confirmar.
5. Gravar `.claude/picot.toml` (v=1, created_at=hoje).
6. Chamar `propagate` (gera blocos em protocol.md/project.md).
7. Criar `adr-0001-picot-v1-initial.md` (ou próximo número livre).

**`formalize` (de prosa existente)**:
1. Validar: `picot.toml` ausente; `protocol.md` ou `project.md` tem conteúdo.
2. Ler ambos arquivos, extrair candidatos pra cada campo PICOT (regex/heurística — ex.: parágrafo após "## População" → candidate de `population`).
3. Mostrar candidatos ao usuário (table: campo / proposta extraída / fonte).
4. Confirmar/editar campo a campo.
5. Mesma cauda de `init` (gravar TOML, propagate, adr-0001).

**`propagate` (regenerar destinos)**:
1. Ler `picot.toml` atual.
2. Calcular hash sha8.
3. Pra cada destino:
   - Achar bloco `<!-- picot:begin -->` ... `<!-- picot:end -->`
   - Se ausente: inserir após section apropriada (heurística: primeira section em `protocol.md` ou após frontmatter em `project.md`)
   - Se presente: substituir conteúdo, atualizar `v=` e `hash=`
4. Reportar quais destinos atualizados / inalterados (hash match = inalterado).

**`diff` (comparar e gerar ADR)**:
1. Ler `picot.toml` atual.
2. Achar último ADR `adr-*-picot-v<N>.md` (sort por número descendente; pegar o primeiro que tem snapshot).
3. Extrair TOML do snapshot do ADR.
4. Deep-diff os 2 TOMLs.
5. Se nada mudou: reportar "no changes" e sair.
6. Se mudaram só campos não-estruturais: re-gravar `picot.toml` com `last_updated = hoje` (sem bump) e chamar `propagate`. Sem ADR.
7. Se mudaram campos estruturais:
   - Mostrar diff campo-a-campo
   - Perguntar motivação (livre ou multipla escolha "novo dataset / refinamento conceitual / feedback de orientador / ...")
   - Bumpar `version` em `picot.toml`
   - Gerar `adr-NNNN-picot-v<N>-<slug>.md` com diff + motivação + snapshot
   - Chamar `propagate`

### SKILL.md (prompt do agente)

A parte **agêntica** vive na skill:
- Modo Socrático: perguntas adaptativas baseadas em wiki-query
- Modo Formalize: extração heurística + confirmação
- Modo Diff: pergunta motivação em prosa natural

A parte **determinística** (validation, render, diff, ADR generation) vive em `domains/protocol/` em Python puro.

## Casos de borda

| Caso | Comportamento |
|---|---|
| Bloco `<!-- picot:begin -->` não existe em `protocol.md` | Skill insere após primeiro `##` heading; warn no relatório |
| Usuário editou dentro do bloco delimitado manualmente | Skill detecta hash mismatch; oferece overwrite (default Y) ou cancela |
| `picot.toml` corrompido (não-parseable) | Skill aborta com erro claro; sugere `git diff .claude/picot.toml` |
| `type` mudou de "clinical" pra "methodological" mid-projeto | Bump estrutural; ADR especial com warning "type change drops P/I/C/O/T fields" |
| ADR antigo sem snapshot (legado, antes da skill) | `diff` reporta "sem baseline" e oferece criar `adr-0001-picot-v1-baseline.md` capturando TOML atual como v1 |
| Múltiplos ADRs criados no mesmo dia | Numeração `adr-NNNN-` é sequencial; skill busca próximo livre |
| Projeto sem `docs/protocol.md` ou `docs/project.md` | Skill avisa, sugere rodar `prumo init` ou criar arquivos manualmente; segue criando picot.toml mesmo assim |

## Fora do escopo (deliberado)

- **Multi-PICOT / múltiplas hipóteses por projeto** — cardinalidade single confirmada (decisão de brainstorm). Projetos com múltiplas hipóteses operacionais (como `pj_piloto_ml` 3 RQs) usam single PICOT + hipótese formal única; objetivos específicos secundários ficam em prose livre fora dos blocos delimitados.
- **Validação semântica** (ex.: "essa população permite testar essa hipótese?") — escopo de revisão humana, não de skill determinística.
- **Render por venue específico** (NEJM/Lancet/Nature Med/CEP) — escopo da família `write-*` (spec separada).
- **Tracking de status de hipótese ao longo do tempo** (`a-priori → testando → confirmada → refutada`) — não cabe em "single PICOT, hipótese única". Avaliar em iteração futura se virar dor real.
- **Geração de query de busca focada pós-PICOT** — escopo de `wiki-ingest --batch` (já existe) ou skill futura `literature-survey`.
- **Comparação entre PICOTs de projetos diferentes** — fora do escopo do plugin (cada `pj_*` é isolado).

## Quando re-avaliar

Triggers concretos pra mudar arquitetura:

| Trigger | Resposta |
|---|---|
| Usuário acaba criando 2+ PICOTs em projetos por necessidade real | Reabrir cardinalidade; considerar `[picot.rq.<id>]` arrays |
| Hipóteses precisam de tracking de status (a-priori → confirmada) | Adicionar campo `hypothesis.status` + transições documentadas |
| Render pra venue (NEJM/CEP/etc.) puxa pra dentro | Skill `write-projeto-cep` etc. consome `picot.toml` — fica fora desta skill |
| Volume de ADRs picot-* > 20/projeto | Adicionar `formulate-picot history` que sumariza linha do tempo |

## Plano de implementação (alto nível)

Cinco PRs sequenciais:

1. **PR-P1** — `core/picot.py` (PicotSpec/v1 schema + read/write/validate). Tests de schema + round-trip.
2. **PR-P2** — `domains/protocol/render.py` (TOML → blocos markdown pros 3 destinos) + integration tests.
3. **PR-P3** — `domains/protocol/diff.py` + `adr.py` (deep diff + ADR generation). Tests com fixtures de ADRs antigos.
4. **PR-P4** — `skills/formulate-picot/SKILL.md` (prompt do agente Socrático/Formalize). Manual smoke-test em `pj_piloto_ml`.
5. **PR-P5** — Wiring no CLI (opcional `prumo protocol *`?), docs (paper-manager skill mention, actions-by-context, README do plugin).

Cada PR independente; PR-P1 e PR-P2 podem rodar em paralelo (PR-P2 mocka PicotSpec se PR-P1 ainda não mergeou).

## Referências

- `docs/canvas/journey.canvas` (removido do repo; conteúdo na tag `v0.65.0`) — Fase 1 (Discover+Define) p1-precisa "Formular pergunta em PICOT" + p1-prumo-picot "candidata futura: `/prumo-assist:formulate-picot`"
- [`docs/actions-by-context.md`](../../actions-by-context.md) — gatilhos "Preciso fechar um PICOT antes de prosseguir" e "PICOT fechado — busca focada"
- [`templates/pj_base/docs/protocol.md`](../../../templates/pj_base/docs/protocol.md) — template atual da seção operacional
- `monorepo-anterior/pj_piloto_ml/docs/protocol.md` + `qualification/projeto.md` + `decisions/adr-*.md` — projeto-referência com PICOT evoluindo (várias RQs → 1 hipótese formal)
- [`docs/constitution.md`](../../constitution.md) — princípios I (Lógica em um lugar só), III (Forward-only schemas) e VI (YAGNI militante)
- [`docs/superpowers/specs/2026-05-03-zotero-notes-integration-design.md`](2026-05-03-zotero-notes-integration-design.md) — padrão arquitetural de blocos delimitados (`<!-- picot:begin/end -->` espelha `<!-- paper-extract:begin/end -->`)
