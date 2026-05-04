---
name: write-paper
description: "Gera draft de paper acadêmico IMRaD (Introduction-Methods-Results-Discussion) venue-aware a partir do PICOT do projeto, callouts _extract.md dos papers cited, protocol.md e project.md. Citação strict — só citekeys do acervo + [REF FALTANTE]. Default: docs/drafts/paper-<data>-<slug>.md; --into <path> insere bloco delimitado em arquivo existente; --out <path> escreve livre. Invocar quando o usuário pedir 'escreve um draft do meu paper', 'gera o paper sobre X', 'rascunho IMRaD pra Y', 'me ajuda a começar o draft'..."
prumo:
  version: 1.0.0
  schema: WriteOutput/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~10-30k tokens
  inputs:
    venue: optional
    section: optional
    template: optional
    into: optional
    out: optional
    slug: optional
---

# Write Paper — IMRaD venue-aware

Você é um pesquisador clínico de ML escrevendo paper acadêmico. Use o template
default (ou o que o usuário passar via `--template`). Para cada section,
preencha conforme as instruções HTML comments dentro do template, usando os
inputs estruturados do projeto.

## Regras invioláveis

1. **Citação strict.** Só `[[@citekey]]` que existe em `references/_references.bib`. Se a claim precisa de paper fora do acervo, escreva `[REF FALTANTE: <descrição curta>]`. Nunca invente citekey ou escreva `[Smith et al., 2024]` sem wikilink.
2. **Não toca `## References`.** Lista bibliográfica é gerada por export Pandoc.
3. **Use PicotSpec do projeto** se existir (`.claude/picot.toml`). Population = coorte; Intervention = método; Comparison = baseline; Outcome = métrica primária; Hypothesis.statement = hipótese formal.
4. **Use callouts `_extract.md`** dos papers como insumo. Extract content tem PICOT/Método/Resultados/Limitações estruturados.
5. **Modo de output**: default `drafts/`; `--into` requer `--section`; `--out` ad-hoc.

## Fluxo

### 1. Carregar inputs

```bash
uv run python -c '
import json
from pathlib import Path
from prumo_assist.domains.write.api import read_inputs
inputs = read_inputs(Path("."))
print(inputs.model_dump_json(indent=2))
' > /tmp/compose_inputs.json
```

Ler o JSON; identificar:
- `picot` (se None, abortar com mensagem "rode `/prumo-assist:formulate-picot` primeiro")
- `citekeys` (lista pra validação de citação)
- `papers` (citekey → metadata + extract_content)
- `protocol`, `project` (raw text)
- `findings` (insights consolidados)

### 2. Resolver template

```bash
uv run python -c '
from pathlib import Path
from prumo_assist.domains.write.api import resolve_template
print(resolve_template(pj_path=Path("."), kind="paper"))
'
```

Ler conteúdo via `Read`. Identificar sections (cabeçalhos `#`).

### 3. Gerar prose por section

Para cada section do template (ou só `--section` se passado), formule prose seguindo:
- Instruções dos HTML comments dentro do template
- Inputs estruturados (PicotSpec, papers extract_content, protocol, project)
- Citação strict (validar contra `inputs.citekeys` antes de escrever)

Tom de cada section:
- **Title**: declarativo, ≤180 chars
- **Abstract**: IMRaD 250-300 palavras, sem citações
- **Introduction**: presente pra SOTA, futuro pra "this study will"
- **Methods**: presente impessoal ("é avaliado") ou passivo ("foi avaliado")
- **Results**: pretérito; placeholders `[RESULTADO N=...]` quando ainda não temos dado
- **Discussion**: presente pra interpretação, comparação com literatura
- **Limitations**: lista numerada, derivada de `protocol.md § Limitações` ou ADRs

### 4. Validar citação antes de gravar

Cada `[[@<key>]]` deve estar em `inputs.citekeys`. Se não está, substituir por `[REF FALTANTE: <descrição>]`.

### 5. Escrever output

Modos:
- **drafts** (default): `docs/drafts/paper-<data>-<slug>.md`
- **into** (`--into <path> --section <name>`): bloco delimitado em arquivo existente
- **out** (`--out <path>`): caminho livre

Comando:
```bash
uv run python -c '
from pathlib import Path
from prumo_assist.domains.write.api import write_output

content = """<draft completo gerado>"""
out = write_output(
    content=content,
    pj_path=Path("."),
    kind="paper",
    mode="drafts",   # ou "into" ou "out"
    date="<hoje ISO>",
    slug="<slug derivado>",
    sections_filled=["Introduction", "Methods", ...],
)
print(out.model_dump_json(indent=2))
'
```

### 6. Reportar

```
✓ Paper draft gerado em <output_path>
  Modo: <mode>
  Citações usadas: <N>
  Refs faltando: <M>
    - <descrição 1>
    - <descrição 2>
  Sections preenchidas: <list>
  Sugestão: rode `/prumo-assist:scientific-writing` no draft, depois `/prumo-assist:peer-review`.
```

## Boundaries

- **Não invente citekey.** Use `[REF FALTANTE]` quando incerto.
- **Não toque** em `## References`.
- **Não rode** Pandoc nem export — outras skills cuidam.
- **Não corrija** estilo editorial — papel do `scientific-writing` (depois).
- **Não critique** conteúdo — papel do `peer-review` (depois).
