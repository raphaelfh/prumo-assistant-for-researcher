---
name: picot
description: "Formaliza, propaga e versiona a PICOT do projeto em 3 destinos (.claude/picot.toml canônico, docs/studies/<slug>/writing/protocol.md operacional, docs/project_guide.md acadêmico) + ADR append-only quando muda. Auto-detecta modo (Socrático / Formalize / Propagate / Diff) pelo estado."
argument-hint: "[init | formalize | propagate | diff]"
allowed-tools: Read Write Edit Glob Grep Bash(cat *) Bash(prumo protocol *)
prumo:
  version: 1.0.0
  schema: PicotSpec/v1
  determinism: hybrid
  agent_compat: [claude-code]
  cost_estimate: ~6k tokens (Socrático), ~2k (Formalize/Propagate/Diff)
  inputs:
    pj_path: optional (default cwd)
    mode: optional ('init' | 'formalize' | 'propagate' | 'diff'; default = auto-detect)
  requires: [cli]
  phrases:
    - "fecha a PICOT"
    - "formaliza a pergunta de pesquisa"
    - "a PICOT mudou"
  legacy: [formulate-picot]
---

# Formulate PICOT — formalização canônica + propagação versionada

<!-- prumo:preflight:begin -->
> **Preflight — antes de qualquer operação deste modo:**
>
> 1. **Superfície e CLI:** fora do app Claude na aba Code (Mac) ou do Claude Code no terminal
>    (Mac ou Linux), isto é, numa tarefa do Cowork, num chat, numa sessão SSH, no Windows ou no
>    WSL, diga em uma frase que este modo não roda aqui e pare. Senão, rode `prumo --version`
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

Skill que mantém a PICOT do projeto consistente em **três destinos**:

- `.claude/picot.toml` — canônico (machine-readable, validado por `PicotSpec/v1`)
- `docs/studies/<slug>/writing/protocol.md` — render operacional (concreto, conferível)
- `docs/project_guide.md` — render acadêmico (prosa formal)

Quando a versão muda, grava ainda um ADR append-only em `docs/studies/<slug>/decisions/adr-NNNN-picot-v<N>-<slug>.md`.

## Pressupostos

- cwd é um `pj_*` com `docs/studies/<slug>/writing/protocol.md` e `docs/project_guide.md` (mesmo que vazios) e `docs/studies/<slug>/decisions/`.
- A parte determinística (read/write TOML, render, diff, ADR) é exposta via `prumo protocol *` (detect-mode/init/adr/propagate/diff). A skill **só** cuida do agêntico (Socrático e Formalize).

## Auto-detect

A skill escolhe o modo baseado no estado:

```bash
prumo protocol detect-mode
```

A saída (``init`` / ``formalize`` / ``propagate`` / ``diff``) define qual
operação seguir. Para ``propagate`` e ``diff``, ler primeiro
[`../references/operations-advanced.md`](../references/operations-advanced.md).

## Operação 1: `init` — modo Socrático (greenfield)

Pré-condição: `.claude/picot.toml` ausente, `docs/studies/<slug>/writing/protocol.md` vazio (ou só template).

Passos:

1. **Reunir contexto via `wiki query`**: invocar `/par:wiki query` (ou `Read` em `docs/_index.md`/`_log.md`) pra entender o que já existe de tema. Citações livres ok.

2. **Perguntar `type`** (escolha):
   - "É um estudo **clínico** (PICOT padrão: Population/Intervention/Comparison/Outcome/Time) ou **metodológico** (Contribution + Hypothesis-validity-condition)?"

3. **Para `clinical`**, perguntar uma de cada vez (sugerindo do wiki sempre que possível):
   - **P (Population)**: "Quem é a coorte/dataset principal?" Ex.: "TCGA-BRCA + CPTAC-BRCA, ~1500 pacientes, mama primária."
   - **I (Intervention)**: "Qual o método sob teste?" Ex.: "Fusão multimodal HEALNet com modality dropout."
   - **C (Comparison)**: "Qual o baseline canônico?" Ex.: "Melhor unimodal por modalidade (radiologia-only, clínico-only, omics-only)."
   - **O (Outcome)**: "Métrica primária + threshold?" Ex.: "AUROC ≥ 0.85, IC bootstrap; ECE ≤ 0.05 como secundária."
   - **T (Time)**: "Janela temporal?" Ex.: "Retrospectivo, sem janela prospectiva; cross-cohort split."

4. **Para `methodological`**, perguntar:
   - **Contribution**: "Qual a contribuição teórica/metodológica?" Ex.: "Predição conformal sensível à modalidade com IPW."
   - **Hypothesis-validity-condition**: "Sob qual condição a contribuição vale?" Ex.: "Quando exchangeability quebra sob MNAR."

5. **Hipótese formal única** (sempre):
   - **Statement**: frase declarativa testável. Ex.: "Modelos multimodais superam unimodais em ≥5 pts AUROC quando ≥60% modalidades disponíveis."
   - **Rationale**: por que esperar isso. Ex.: "Decomposição PID indica sinergia substancial em cobertura ≥60%."
   - **Metrics**: lista de métricas pra testar. Ex.: `["AUROC", "ECE", "coverage"]`.

6. **Mostrar PicotSpec proposto pro usuário e pedir confirmação**.
   Renderizar como JSON (mais legível em chat) com os campos coletados nos
   passos 3-5. Estrutura mínima para ``clinical``:

   ```json
   {
     "type": "clinical",
     "created_at": "<hoje ISO>",
     "last_updated": "<hoje ISO>",
     "version": 1,
     "population": "...",
     "intervention": "...",
     "comparison": "...",
     "outcome": "...",
     "time": "...",
     "hypothesis": {
       "statement": "...",
       "rationale": "...",
       "metrics": ["AUROC", "ECE"]
     }
   }
   ```

   Para ``methodological``: substituir P/I/C/O/T por ``contribution`` +
   ``hypothesis_validity_condition``. Pedir "OK assim?".

7. **Após confirmação, escrever**:

   ```bash
   cat <<'JSON' | prumo protocol init --date "<hoje ISO>" --json
   <PicotSpec JSON aprovado>
   JSON
   ```

   O script grava ``.claude/picot.toml``, propaga blocos em
   ``docs/studies/<slug>/writing/protocol.md`` + ``docs/project_guide.md`` e cria
   ``adr-0001-picot-v1-versao-inicial.md``.
   Saída em stdout é JSON ``{"propagate": ..., "adr_path": ...}``.

8. **Reportar ao usuário**: arquivos criados (``.claude/picot.toml``,
   ``docs/studies/<slug>/decisions/adr-NNNN-picot-v1-*.md``) e blocos atualizados em
   ``protocol.md`` / ``project_guide.md``.

## Operação 2: `formalize` — extrair de prosa existente

Pré-condição: `.claude/picot.toml` ausente, mas `docs/studies/<slug>/writing/protocol.md` ou `docs/project_guide.md` têm prose com sinais de PICOT.

Passos:

1. **Ler `protocol.md` e `project_guide.md`**, identificar candidatos pra cada campo (heurística: parágrafo após heading "## Contexto" / "## Coorte" / "## Desfecho").

2. **Apresentar tabela**:

| Campo | Candidato extraído | Fonte |
|---|---|---|
| `population` | "..." | `protocol.md § Coorte` |
| `intervention` | "..." | `project_guide.md § Hipótese` |
| ... | ... | ... |

3. **Confirmar/editar campo a campo** com o usuário.

4. **Resto idêntico ao `init` passos 5–8** (hipótese, write, propagate, ADR-0001).

## Operações 3 e 4 — ``propagate`` e ``diff``

Ver [`../references/operations-advanced.md`](../references/operations-advanced.md).

## Boundaries

- Skill **nunca** edita `.claude/picot.toml` sem confirmação do usuário.
- Skill **nunca** edita ADR existente (append-only).
- Skill **nunca** edita prose fora dos blocos `<!-- picot:begin/end -->` em protocol.md/project_guide.md.
- Skill **não** invoca LLM para validar PICOT semanticamente — só estrutura.
- Para escrita acadêmica do `project_guide.md` § não delimitado, delegar a `/par:write section`.

## Erros comuns

- `picot.toml` corrompido (não-parseable) → reportar erro do `tomllib`, sugerir `git diff .claude/picot.toml`.
- `docs/studies/<slug>/writing/protocol.md` ou `docs/project_guide.md` ausentes → reportar `missing` e seguir; humano cria depois.
- Nenhum ADR baseline mas `picot.toml` existe → tratar como ADR-0001 inicial; criar.
