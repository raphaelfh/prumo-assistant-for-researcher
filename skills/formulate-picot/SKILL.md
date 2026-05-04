---
name: formulate-picot
description: Formaliza, propaga e versiona a PICOT do projeto (Population, Intervention, Comparison, Outcome, Time + Hipótese formal única). Invocar quando o usuário pedir "fechar PICOT", "formalizar pergunta de pesquisa", "propagar PICOT pra protocol/project/ADR", "PICOT mudou — gera novo ADR", "/formulate-picot", ou quando estiver na transição de busca ampla pra busca focada (Fase 1 da journey). Auto-detecta modo (Socrático / Formalize / Propagate / Diff) pelo estado do `.claude/picot.toml` e dos 3 destinos (`docs/protocol.md`, `docs/project.md`, `docs/decisions/adr-*-picot-*.md`).
prumo:
  version: 1.0.0
  schema: PicotSpec/v1
  determinism: hybrid
  agent_compat: [claude-code]
  cost_estimate: ~6k tokens (Socrático), ~2k (Formalize/Propagate/Diff)
  inputs:
    pj_path: optional (default cwd)
    mode: optional ('init' | 'formalize' | 'propagate' | 'diff'; default = auto-detect)
---

# Formulate PICOT — formalização canônica + propagação versionada

Skill que mantém a PICOT do projeto consistente em **três destinos**:

- `.claude/picot.toml` — canônico (machine-readable, validado por `PicotSpec/v1`)
- `docs/protocol.md` — render operacional (concreto, conferível)
- `docs/project.md` — render acadêmico (prosa formal)
- `docs/decisions/adr-NNNN-picot-v<N>-<slug>.md` — ADR append-only quando versão muda

## Pressupostos

- cwd é um `pj_*` com `docs/protocol.md` e `docs/project.md` (mesmo que vazios) e `docs/decisions/`.
- A parte determinística (read/write TOML, render, diff, ADR) vive em `prumo_assist.domains.protocol`. A skill **só** cuida do agêntico (Socrático e Formalize).

## Auto-detect

A skill escolhe o modo baseado no estado, executando este check em `Bash`:

```bash
python3 -c '
from pathlib import Path
from prumo_assist.domains.protocol.picot_io import picot_path
from prumo_assist.domains.protocol.adr import find_last_picot_adr

pj = Path(".")
toml = picot_path(pj)
last_adr = find_last_picot_adr(pj)
protocol_md = pj / "docs" / "protocol.md"
project_md = pj / "docs" / "project.md"

if not toml.exists():
    print("init" if not protocol_md.read_text(errors="ignore").strip() else "formalize")
elif last_adr is None:
    print("propagate")
else:
    # delegar diff: pode retornar zero changes (= já em dia) ou detectar mudança
    print("diff")
'
```

A saída (`init` / `formalize` / `propagate` / `diff`) define qual operação seguir.

## Operação 1: `init` — modo Socrático (greenfield)

Pré-condição: `.claude/picot.toml` ausente, `docs/protocol.md` vazio (ou só template).

Passos:

1. **Reunir contexto via wiki-query**: invocar `wiki-query` (ou `Read` em `docs/_index.md`/`_log.md`) pra entender o que já existe de tema. Citações livres ok.

2. **Perguntar `type`** (escolha):
   - "É um estudo **clínico** (PICOT padrão: Population/Intervention/Comparison/Outcome/Time) ou **metodológico** (Contribution + Hypothesis-validity-condition)?"

3. **Para `clinical`**, perguntar uma de cada vez (sugerindo do wiki sempre que possível):
   - **P (Population)**: "Quem é a coorte/dataset principal?" Ex.: "Coorte A + Coorte B, ~1500 participantes."
   - **I (Intervention)**: "Qual o método sob teste?" Ex.: "Intervenção X em dose padrão."
   - **C (Comparison)**: "Qual o baseline canônico?" Ex.: "Cuidado usual."
   - **O (Outcome)**: "Métrica primária + threshold?" Ex.: "AUROC ≥ 0.85, IC bootstrap; ECE ≤ 0.05 como secundária."
   - **T (Time)**: "Janela temporal?" Ex.: "Retrospectivo, sem janela prospectiva; cross-cohort split."

4. **Para `methodological`**, perguntar:
   - **Contribution**: "Qual a contribuição teórica/metodológica?" Ex.: "Método estatístico M."
   - **Hypothesis-validity-condition**: "Sob qual condição a contribuição vale?" Ex.: "Quando a suposição S falha."

5. **Hipótese formal única** (sempre):
   - **Statement**: frase declarativa testável. Ex.: "A intervenção X supera o comparador em ≥5 pts no desfecho primário."
   - **Rationale**: por que esperar isso. Ex.: "Estudos-piloto sugerem efeito clinicamente relevante."
   - **Metrics**: lista de métricas pra testar. Ex.: `["AUROC", "ECE", "coverage"]`.

6. **Mostrar TOML proposto pro usuário e pedir confirmação**:

```python
from prumo_assist.domains.protocol.schemas.v1 import PicotSpec, Hypothesis
spec = PicotSpec(
    type="clinical",
    created_at="<hoje ISO>",
    last_updated="<hoje ISO>",
    version=1,
    population="...",
    intervention="...",
    comparison="...",
    outcome="...",
    time="...",
    hypothesis=Hypothesis(statement="...", rationale="...", metrics=["..."]),
)
```

Mostrar o output de `tomli_w.dumps(spec.model_dump(...))` e perguntar "OK assim?".

7. **Após confirmação, escrever** via `Bash`:

```bash
python3 -c '
import sys
sys.path.insert(0, ".")
from pathlib import Path
from prumo_assist.domains.protocol.api import (
    PicotSpec, Hypothesis, write_picot, propagate
)
from prumo_assist.domains.protocol.adr import compose_adr, next_adr_number
from prumo_assist.domains.protocol.diff import PicotDiff

pj = Path(".")
spec = PicotSpec(...)  # campos preenchidos pela conversa
write_picot(pj, spec)
report = propagate(pj)

# ADR-0001 inicial
n = next_adr_number(pj)
body = compose_adr(
    adr_number=n,
    spec=spec,
    diff=PicotDiff(changes=[]),
    motivation="versão inicial — primeira formalização",
    supersedes_path=None,
    date="<hoje ISO>",
)
adr_path = pj / "docs" / "decisions" / f"adr-{n:04d}-picot-v1-versao-inicial.md"
adr_path.write_text(body, encoding="utf-8")
print(f"ok: {report}, adr={adr_path}")
'
```

8. **Reportar ao usuário**: arquivos criados (`.claude/picot.toml`, `docs/decisions/adr-NNNN-picot-v1-*.md`) e blocos atualizados em `protocol.md`/`project.md`.

## Operação 2: `formalize` — extrair de prosa existente

Pré-condição: `.claude/picot.toml` ausente, mas `docs/protocol.md` ou `docs/project.md` têm prose com sinais de PICOT.

Passos:

1. **Ler `protocol.md` e `project.md`**, identificar candidatos pra cada campo (heurística: parágrafo após heading "## Contexto" / "## Coorte" / "## Desfecho").

2. **Apresentar tabela**:

| Campo | Candidato extraído | Fonte |
|---|---|---|
| `population` | "..." | `protocol.md § Coorte` |
| `intervention` | "..." | `project.md § Hipótese` |
| ... | ... | ... |

3. **Confirmar/editar campo a campo** com o usuário.

4. **Resto idêntico ao `init` passos 5–8** (hipótese, write, propagate, ADR-0001).

## Operação 3: `propagate` — apenas regenerar destinos

Quando: `.claude/picot.toml` existe e os blocos delimitados em `protocol.md`/`project.md` estão stale (hash mismatch). Sem mudança estrutural.

Executar via `Bash`:

```bash
prumo protocol propagate --json
```

Reportar status por destino (`inserted`/`updated`/`unchanged`/`missing`).

## Operação 4: `diff` — detectar mudança e gerar ADR

Quando: usuário editou `.claude/picot.toml` (manualmente ou via outra invocação) e quer registrar a mudança.

Passos:

1. **Rodar diff** via `Bash`:

```bash
prumo protocol diff --json
```

Captura JSON da última linha; campo `changes` é lista, `has_structural` é bool.

2. **Se `changes == []`**: nada mudou. Sair informando o usuário.

3. **Se `has_structural == false`** (só campos cosméticos como `last_updated` ou `hypothesis.rationale`): chamar `prumo protocol propagate` e sair sem ADR.

4. **Se `has_structural == true`**:
   - Mostrar diff campo-a-campo.
   - **Perguntar motivação** (livre ou multipla escolha):
     - "novo dataset disponível"
     - "refinamento conceitual após leitura"
     - "feedback de orientador/revisor"
     - "consolidação pré-banca/submissão"
     - "outro: ___"
   - **Bumpar versão** em `picot.toml` (`[picot] version += 1`, `last_updated = hoje`).
   - **Gerar ADR** via `Bash`:

```bash
python3 -c '
from pathlib import Path
from prumo_assist.domains.protocol.api import read_picot, propagate
from prumo_assist.domains.protocol.adr import (
    compose_adr, next_adr_number, find_last_picot_adr,
)
from prumo_assist.domains.protocol.ops import diff_against_last_adr

pj = Path(".")
spec = read_picot(pj)
diff = diff_against_last_adr(pj)
last_adr = find_last_picot_adr(pj)
n = next_adr_number(pj)
body = compose_adr(
    adr_number=n,
    spec=spec,
    diff=diff,
    motivation="<motivação capturada do usuário>",
    supersedes_path=last_adr,
    date="<hoje ISO>",
)
slug = "<slug do motivo>"
adr_path = pj / "docs" / "decisions" / f"adr-{n:04d}-picot-v{spec.version}-{slug}.md"
adr_path.write_text(body, encoding="utf-8")
report = propagate(pj)
print(f"adr={adr_path}, propagate={report}")
'
```

5. **Reportar**: ADR criado, blocos atualizados.

## Boundaries

- Skill **nunca** edita `.claude/picot.toml` sem confirmação do usuário.
- Skill **nunca** edita ADR existente (append-only).
- Skill **nunca** edita prose fora dos blocos `<!-- picot:begin/end -->` em protocol.md/project.md.
- Skill **não** invoca LLM para validar PICOT semanticamente — só estrutura.
- Para escrita acadêmica do `project.md` § não delimitado, delegar à família `write-*` (spec separada).

## Erros comuns

- `picot.toml` corrompido (não-parseable) → reportar erro do `tomllib`, sugerir `git diff .claude/picot.toml`.
- `docs/protocol.md` ou `docs/project.md` ausentes → reportar `missing` e seguir; humano cria depois.
- Nenhum ADR baseline mas `picot.toml` existe → tratar como ADR-0001 inicial; criar.
- `type` mudou (`clinical` → `methodological`) → ADR especial com warning explícito sobre campos abandonados.
