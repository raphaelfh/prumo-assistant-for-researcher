---
title: Família de skills `write-*` (paper / projeto-cep / statistics / scientific)
date: 2026-05-03
status: approved
tags: [skill, write-family, write-paper, write-projeto-cep, write-statistics, write-scientific]
---

# Família de skills `write-*`

## Resumo executivo

Quatro skills agênticas que **geram** drafts acadêmicos a partir de inputs estruturados do projeto (PicotSpec, callouts de paper, protocol.md, project.md, findings). Cada skill é especializada num *kind* de documento (paper acadêmico IMRaD, projeto CEP brasileiro, métodos estatísticos, escrita científica genérica). Backbone Python compartilhado (`domains/write/compose.py`) cuida de carregar inputs e resolver paths; as 4 SKILL.md cuidam só do agêntico (geração de prose conforme template). Citação **strict**: só citekeys do acervo; claim sem evidência vira `[REF FALTANTE: ...]`. Output em 3 modos (`drafts/` gerenciado, `--into` bloco delimitado, `--out` arquivo livre).

## Contexto e problema

Hoje a geração de texto acadêmico no projeto é totalmente manual:
- Pesquisador junta mentalmente PICOT + papers lidos + protocolo + decisões de ADRs.
- Escreve prose direto em `docs/project.md` ou exporta `_extract.md` linha-a-linha.
- Cada finalidade (CEP brasileiro, paper internacional, plano estatístico, draft genérico) tem template diferente que ele copia-cola entre projetos.
- Citações são inseridas à mão; é fácil citar paper que não está no acervo (e depois não conseguir exportar bib).

**Falhas observadas em projetos reais** (`pj_piloto_ml`):
- `qualification/projeto.md` tem `[REF FALTANTE difusão latente cross-modal em imagem médica]` em 4+ lugares — mostra que o autor manualmente sinaliza claims sem evidência, mas não há ferramenta que automatize esse pattern.
- Estrutura IMRaD do paper acaba sendo replicada de paper anterior; não há template canônico do prumo.
- O CEP é um documento brasileiro com seções específicas (Plataforma Brasil, TCLE, riscos, benefícios, conformidade LGPD) que difere fundamentalmente de paper internacional.
- Plano de análise estatística (sample size, sensitivity analyses, splits) é seção que requer fundamentação em literatura específica de método — input distinto de "paper completo".

**Objetivo da família**: dar a cada finalidade de escrita um agente especializado, com inputs canônicos do projeto, citação rigorosa (zero alucinação), e template customizável.

## Decisões arquiteturais

### D1 — 4 skills com backend compartilhado

Não 1 skill com flag `--kind`. Não 4 skills duplicadas. Cada SKILL.md é fina (~80 linhas) com `description` específica que ajuda LLM auto-select do plugin. Toda lógica de input/output mora em `src/prumo_assist/domains/write/compose.py` (compartilhado).

Razão: cada kind tem mental model próprio (CEP é regulatório brasileiro, paper é IMRaD venue-aware, statistics é metodologia, scientific é genérico) — descrições específicas pro LLM matter. Mas a infra (ler PicotSpec, ler papers, validar citações, escrever output) é idêntica.

### D2 — Templates customizáveis com fallback chain

Templates em Markdown skeleton com HTML comments instruindo o agente (mesmo padrão do `.claude/paper_extraction.md` existente). Default ships no plugin; pode ser sobrescrito.

Resolução (ordem de precedência):

```
--template <path>                                    (highest)
  ↓
pj_<nome>/.claude/writing_templates/<kind>.md        (project override)
  ↓
<plugin>/templates/writing/<kind>.md                 (default shipped)
```

Se nenhum existe e usuário não passou `--template`, skill aborta com mensagem explicando como criar.

### D3 — Output em 3 modos com default seguro

```
default              → docs/drafts/<kind>-<YYYY-MM-DD>-<slug>.md
--into <path>        → bloco <!-- write:begin kind=<k> section=<s> --> em <path>
--out <path>         → arquivo único em <path>
```

`<slug>` = derivado de `picot.hypothesis.statement` (slugify ≤30 chars); `--slug <text>` override. `<YYYY-MM-DD>` = hoje (ISO).

**Por que default = `docs/drafts/`**: protege o usuário (nunca sobrescreve trabalho); idempotente (mesmo input + mesma data = sobrescreve mesmo path); user move/edita/integra depois com `git mv` ou edição manual.

**Por que `--into <path>`**: workflow real onde usuário tem `docs/project.md` em construção e quer regenerar a *seção* específica (ex.: `--section=methods --into docs/project.md`) sem perder prose ao redor. Bloco delimitado segue o pattern do `<!-- picot:begin -->`.

**Por que `--out <path>`**: uso ad-hoc (ex.: gerar texto pra grant fora do projeto, ou pra colaborar com colega via DOCX).

### D4 — Citação strict (zero alucinação)

Toda claim que precisa citação deve referenciar citekey existente em `references/_references.bib`. Quando agente não acha citekey adequado, **emite placeholder** `[REF FALTANTE: <descrição curta>]` ao invés de inventar `[Smith et al., 2024]` ou similar.

Razão: princípio de evidência ancorada (constitution §V — Provenance em todo output). Match com o padrão existente em `pj_piloto_ml/qualification/projeto.md` (`[REF FALTANTE ...]` aparece 4+ vezes).

Pós-geração, `compose.extract_missing_refs(text)` varre o draft e popula campo `references_missing: list[str]` no `WriteOutput`. Skill reporta ao usuário com lista + sugestão de ação ("considere ingerir N papers via `prumo paper sync` antes de re-gerar").

### D5 — `domains/write/` ganha `compose.py` (não cria domínio novo)

`domains/write/` já existe com `export.py` (Pandoc), `comments.py` (extract from .docx). Adicionar `compose.py` aqui mantém coerência (todas as operações de geração/exportação de texto num lugar). Não criar `domains/compose/` separado.

## Arquitetura

### Componentes

```
src/prumo_assist/
├── domains/
│   └── write/                                # já existe
│       ├── __init__.py
│       ├── api.py                            # MODIFY: re-export compose
│       ├── cli.py                            # MODIFY: comando opcional `write list-templates`
│       ├── export.py                         # já existe (Pandoc)
│       ├── comments.py                       # já existe (extract from .docx)
│       ├── compose.py                        # NEW: backend compartilhado das 4 skills
│       └── schemas/
│           ├── __init__.py                   # NEW
│           └── v1.py                         # NEW: ComposeInputs, PaperSummary, FindingSummary, WriteOutput

skills/                                       # NEW (4 skills)
├── write-paper/SKILL.md
├── write-projeto-cep/SKILL.md
├── write-statistics/SKILL.md
└── write-scientific/SKILL.md

templates/writing/                            # NEW (4 templates default)
├── paper.md
├── projeto-cep.md
├── statistics.md
└── scientific.md
```

### Fluxo de dados

```
1. Usuário invoca /prumo-assist:write-<kind> [--venue ...] [--section ...] [--into ...] [--out ...]

2. Skill lê inputs via Bash:
   $ python3 -c '
       import json
       from prumo_assist.domains.write.api import read_inputs
       from pathlib import Path
       inputs = read_inputs(Path("."))
       print(inputs.model_dump_json())
   '
   ↓
   ComposeInputs(picot, citekeys, papers, protocol, project, findings)

3. Skill resolve template:
   compose.resolve_template(pj_path, kind="paper", override=args.template)
   ↓
   Path("templates/writing/paper.md")  ou override

4. Skill, pra cada section do template:
   - Lê HTML comment instrutivo
   - Gera prose seguindo o comment, usando ComposeInputs
   - Valida cada claim: match acervo? sim → [[@citekey]]; não → [REF FALTANTE: ...]

5. Skill escreve output (modo drafts | into | out):
   compose.write_output(content, kind, mode, path_args)

6. Skill reporta WriteOutput ao usuário (path, citações usadas, refs missing).
```

### Schema de inputs (`ComposeInputs/v1`)

`src/prumo_assist/domains/write/schemas/v1.py`:

```python
from pathlib import Path
from typing import Literal
from pydantic import BaseModel
from prumo_assist.domains.protocol.schemas.v1 import PicotSpec


class PaperSummary(BaseModel):
    """Resumo de 1 paper do acervo (citekey + metadata + extract callout)."""

    citekey: str
    title: str
    year: int | None = None
    authors: str = ""
    extract_content: str | None = None  # corpo de _extract.md, se existir


class FindingSummary(BaseModel):
    """Achado do wiki (docs/wiki/findings/*.md ou docs/findings/*.md)."""

    path: Path
    title: str
    body: str


class ComposeInputs(BaseModel):
    """Tudo que a skill write-* precisa pra gerar prose."""

    schema_version: Literal["ComposeInputs/v1"] = "ComposeInputs/v1"
    picot: PicotSpec | None = None
    citekeys: list[str] = []                         # de _references.bib
    papers: dict[str, PaperSummary] = {}             # citekey → resumo
    protocol: str | None = None                      # docs/protocol.md raw
    project: str | None = None                       # docs/project.md raw
    findings: list[FindingSummary] = []              # docs/wiki/findings/*.md ou docs/findings/*.md
```

### Schema de output (`WriteOutput/v1`)

```python
class WriteOutput(BaseModel):
    """Resultado da geração — reportado ao usuário e usável programaticamente."""

    schema_version: Literal["WriteOutput/v1"] = "WriteOutput/v1"
    output_path: Path
    mode: Literal["drafts", "into", "out"]
    kind: Literal["paper", "projeto-cep", "statistics", "scientific"]
    sections_filled: list[str]
    sections_skipped: list[str]                      # se --section foi usado
    citations_used: list[str]                        # citekeys efetivamente usados
    references_missing: list[str]                    # [REF FALTANTE: ...] capturados
    words_generated: int
```

### API pública (`domains/write/api.py`)

```python
from prumo_assist.domains.write.compose import (
    compose_path,
    extract_missing_refs,
    read_inputs,
    resolve_template,
    write_output,
)
from prumo_assist.domains.write.schemas.v1 import (
    ComposeInputs,
    FindingSummary,
    PaperSummary,
    WriteOutput,
)

# (existentes preservadas)
from prumo_assist.domains.write.comments import extract_to_file as extract_comments
from prumo_assist.domains.write.export import compose, export, list_styles
```

### Especialização por kind

| Kind | Inputs obrigatórios | Sections default (template) |
|---|---|---|
| `write-paper` | `picot`, ≥1 paper em acervo, `target_venue` (default `general`) | Title, Abstract, Introduction, Methods, Results, Discussion, Limitations, References |
| `write-projeto-cep` | `picot`, `protocol` populado (coorte+critérios+governança) | Resumo, Pergunta de pesquisa, Justificativa, Hipótese, Coorte e critérios, Métodos, Riscos e benefícios, TCLE, Cronograma, Orçamento, Conformidade ética |
| `write-statistics` | `picot` (outcome+metrics), `protocol` (splits) | Plano de análise estatística, Definição operacional do outcome, Sample size, Métricas primárias e secundárias, Análises de sensibilidade, Splits e anti-leakage |
| `write-scientific` | seed text ou `--section <name>`; flexível | (segue template do venue ou `--template`) |

Skill `write-scientific` é o "fallback genérico" — quando o usuário tem texto em mãos e quer gerar/expandir uma seção sem se prender à estrutura formal de paper/CEP/statistics.

### Formato de template

Markdown skeleton com YAML frontmatter customizável + HTML comments instrutivos por seção. Mesmo padrão do `.claude/paper_extraction.md`.

Exemplo (`templates/writing/paper.md`):

```markdown
---
title: ""
target_venue: "general"   # general | NEJM | Lancet | Nature-Med | NPJ-DigitMed | ...
authors: []
---

# Title

<!-- 1 frase, ≤180 caracteres, declarativa.
     Usa PicotSpec.hypothesis.statement como base. -->

# Abstract

<!-- Estrutura IMRaD em 250-300 palavras (ajustar pra venue):
     Background (PicotSpec.population + gap), Methods (PicotSpec.intervention),
     Results (placeholders [RESULTADO N=...] se ainda não temos), Conclusion
     (hipótese + implicação clínica). Sem citações no abstract. -->

# Introduction

<!-- 4-6 parágrafos:
     1. Contexto clínico (PicotSpec.population). Cite ≥2 papers do acervo.
     2. Gap metodológico/clínico. Cite ≥3 papers que mostram limites.
     3. Nossa abordagem (PicotSpec.intervention). Cite trabalhos correlatos.
     4. Hipótese formal (PicotSpec.hypothesis.statement). Sem citação.
     Tom: presente pra SOTA, futuro pra "this study will". -->

# Methods

<!-- Subsections: Population, Data, Model architecture, Training, Evaluation,
     Statistical analysis. Use PicotSpec + protocol.md raw como insumo. -->

# Results

<!-- Placeholders [RESULTADO ...] se ainda em desenho.
     Caso já tenha valores em docs/findings/, reutilizar. -->

# Discussion

<!-- 4-6 parágrafos: principais achados, comparação com literatura,
     limitações (use protocol.md § Limitações), implicações,
     trabalho futuro. -->

# Limitations

<!-- Lista numerada, derivada de protocol.md ou ADRs. -->

# References

<!-- NÃO gerar; lista é responsabilidade do export Pandoc + CSL. -->
```

Para `projeto-cep`, structure brasileira (Resumo, Pergunta, Justificativa, Hipótese, Coorte, Métodos, Riscos e benefícios, TCLE, Cronograma, Orçamento, Conformidade). Para `statistics`, structure metodológica. Para `scientific`, structure mínima genérica.

### Rigor de citação (mecanismo)

1. Skill carrega `inputs.citekeys` (lista de citekeys do `.bib`).
2. Pra cada claim que precisa citação:
   - Se um `citekey` adequado existe → `[[@citekey]]`
   - Senão → `[REF FALTANTE: <descrição>]`
3. **Skill nunca**:
   - Inventa citekey (ex.: `[[@plausible2024fake]]`)
   - Escreve `[Smith et al., 2024]` em prosa sem wikilink
4. Pós-geração, `extract_missing_refs(text)`:
   ```python
   import re
   _RE = re.compile(r"\[REF FALTANTE:\s*(?P<desc>[^\]]+)\]")
   def extract_missing_refs(text: str) -> list[str]:
       return [m.group("desc").strip() for m in _RE.finditer(text)]
   ```
5. Report final inclui `references_missing` + sugestão.

## CLI ergonômico (opcional, fora do MVP)

`prumo write list-templates` — lista templates resolvíveis (default + project-level + cwd `--template <path>` candidates). Útil pra debug e descoberta. Implementação trivial:

```python
@write_app.command("list-templates")
def list_templates_command(
    path: Annotated[Path, typer.Argument()] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Lista templates disponíveis (plugin defaults + project overrides)."""
    ...
```

## Casos de borda

| Caso | Comportamento |
|---|---|
| `picot.toml` ausente | `write-paper` / `write-projeto-cep` / `write-statistics` abortam com mensagem "rode `/prumo-assist:formulate-picot` primeiro". `write-scientific` segue (não exige PICOT). |
| Acervo vazio (`citekeys` vazio) | Skill avisa; gera draft com **todas** claims marcadas como `[REF FALTANTE]`. Útil pra esqueleto inicial. |
| `protocol.md` vazio (CEP) | `write-projeto-cep` aborta com mensagem indicando seções obrigatórias (coorte, critérios, governança). |
| `--section` que não existe no template | Skill lista as sections válidas e aborta. |
| `--into` aponta pra arquivo sem bloco `<!-- write:begin kind=... section=... -->` | Skill insere o bloco no fim do arquivo (warn). Mesma heurística do `picot:begin`. |
| `--out` aponta pra arquivo existente com conteúdo | Skill aborta a menos que `--force`. |
| Template tem `{{placeholder}}` que skill não preenche | Deixa literal `{{placeholder}}` + adiciona à lista `sections_skipped` no report. |
| Slug em conflito (mesmo path em `docs/drafts/`) | Skill sobrescreve em modo default (idempotente). Se quiser preservar, use `--slug <novo>`. |

## Fora do escopo (deliberado)

- **Tradução EN ↔ PT-BR** — assume usuário escreve em PT-BR; venues internacionais usam EN. Trocar idioma é skill separada (futura).
- **Geração de figuras / tabelas em si** — apenas placeholders `[TABELA: <descrição>]` / `[FIGURA: <descrição>]`. Geração real é responsabilidade de notebooks/scripts (não skill).
- **Geração de PDF / DOCX final** — papel do `prumo write export` (já existe, consome o draft markdown gerado por essa família).
- **Aplicação de convenções editoriais** (pontuação, citação posicional, atenuação de superlativos) — papel do `/prumo-assist:scientific-writing` (rodar **depois** desta família).
- **Crítica de conteúdo** — papel do `/prumo-assist:peer-review` (rodar **depois** do scientific-writing).
- **Workflow paper-to-PDF end-to-end** — composição de skills é responsabilidade do usuário; não há skill orquestradora.
- **Multi-language outputs** — não há flag `--lang`; venue determina idioma via convenção (CEP em PT-BR, paper internacional em EN — mas geração é o que o template diz).
- **Templates por venue** dentro do plugin — só `target_venue: general` ships default; venue-specific (NEJM/Lancet/etc.) é spec separada futura (`venue-clinical` pack do roadmap).

## Quando re-avaliar

| Trigger | Resposta |
|---|---|
| Volume de `[REF FALTANTE: ...]` >50% das claims | Acervo está fraco demais; sugerir RSL antes; skill talvez precise modo `--draft-only` (gera esqueleto sem citações pra revisão antes de ingest) |
| Usuário pedir flag `--lang en/pt` | Aceitável adicionar — começou como YAGNI mas vira uso real |
| Template default não cobre venue específico | Spec separada de `venue-clinical` pack |
| Skill gera placeholder inventado (ex.: `[Smith et al.]`) em prod | Bug crítico — schema do prompt em SKILL.md precisa de reforço |

## Plano de implementação (alto nível, 6 PRs)

1. **PR-W1** — `domains/write/schemas/v1.py` (ComposeInputs/PaperSummary/FindingSummary/WriteOutput) + tests de schema
2. **PR-W2** — `domains/write/compose.py::read_inputs` (lê de `pj_*` cobrindo PicotSpec + .bib + papers + protocol + project + findings) + tests com fixtures
3. **PR-W3** — `compose.py::resolve_template` + `compose_path` + `write_output` + tests (3 modos drafts/into/out)
4. **PR-W4** — `compose.py::extract_missing_refs` + helper de validação de citekey + tests
5. **PR-W5** — Templates default em `templates/writing/{paper,projeto-cep,statistics,scientific}.md` (4 arquivos Markdown skeleton com HTML comments)
6. **PR-W6** — Skills agênticas em `skills/write-{paper,projeto-cep,statistics,scientific}/SKILL.md` (4 arquivos) + atualizações em README, actions-by-context, plugin manifests

Cada PR independente; PR-W1 e PR-W2 podem rodar em paralelo. PR-W5 (templates) pode ir antes de PR-W6 (skills) pra que cada SKILL.md possa referenciar a estrutura concreta.

## Referências

- [`docs/canvas/journey.canvas`](../../canvas/journey.canvas) — Fase 3 ESCRITA p3-prumo-finalidade "Família `/prumo-assist:write-*`"
- [`docs/canvas/project-flow.canvas`](../../canvas/project-flow.canvas) — sub-fluxo agente especializado em escrita acadêmica
- [`docs/actions-by-context.md`](../../actions-by-context.md) — gatilhos "Vou submeter pro CEP", "Vou montar artigo pra venue", "Vou escrever a seção de métodos estatísticos"
- [`docs/superpowers/specs/2026-05-03-formulate-picot-design.md`](2026-05-03-formulate-picot-design.md) — produtor da PicotSpec consumida por essa família
- [`docs/superpowers/specs/2026-05-03-zotero-notes-integration-design.md`](2026-05-03-zotero-notes-integration-design.md) — produtor de `_extract.md` consumido por essa família
- [`skills/scientific-writing/SKILL.md`](../../../skills/scientific-writing/SKILL.md) — passe editorial (pós-geração)
- [`skills/peer-review/SKILL.md`](../../../skills/peer-review/SKILL.md) — crítica de conteúdo (pós-geração)
- [`docs/constitution.md`](../../constitution.md) — princípios I (Lógica em um lugar só), V (Provenance em todo output), VI (YAGNI militante)
