---
name: lint
description: "Health-check do wiki de um pj_*: detecta páginas órfãs, citekeys quebradas, contradições, stale claims, conceitos sem página, links mortos, prefixo de log inválido, múltiplos role:primary. Gera relatório timestamped como finding (type: finding) em docs/studies/<slug>/notes/_lint_<data>.md."
argument-hint: "[--quick]"
allowed-tools: Read Write Edit Glob Grep Bash(prumo wiki lint *) Bash(rg *)
prumo:
  version: 1.1.0
  schema: WikiLintReport/v1
  determinism: hybrid
  agent_compat: [claude-code]
  cost_estimate: ~5-20k tokens (depende do tamanho do wiki)
  inputs:
    quick: optional (pula análises LLM-based)
  requires: [cli]
  phrases:
    - "audita o wiki"
    - "encontra páginas órfãs"
    - "o wiki está consistente?"
  legacy: [wiki-lint]
---

# Wiki Lint — auditar consistência do wiki

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

Aplica as regras de integridade descritas neste checklist, uma por seção. Gera relatório;
não corrige automaticamente.

## Pressupostos

- cwd é um `pj_*` com a estrutura padrão (`docs/_index.md`, `docs/_log.md`, `docs/references/` e
  ao menos um escopo `docs/studies/<escopo>/` com `notes/`, `writing/` e `decisions/`).
- Cada escopo é auditado por vez: a identidade de uma página é o caminho relativo ao escopo, e
  um wikilink só resolve dentro do escopo que o cita — homônimo de outro escopo não resolve.
- Se o wiki é recém-criado e vazio, a skill retorna "Wiki vazio — nada a auditar" e sai.

## Checklist (ordem fixa)

> **Determinístico primeiro.** Rode `prumo wiki lint --json` e leve os achados para as seções
> 1, 2, 3, 8 e 9 do relatório. Gaste orçamento de LLM só nas seções 5, 6 e 7.

### 1–3, 8, 9. Cobertos por `prumo wiki lint --json`

| Código | Seção | Significado |
|---|---|---|
| `orphan_page` | 1. Páginas órfãs | página do escopo sem link de entrada (wikilink ou link Markdown) |
| `broken_citekey` | 2. Citekeys quebradas | `[@foo]` sem entrada no `docs/references/_references.bib` |
| `broken_log_prefix` | 3. Prefixo de log | entrada de `_log.md` fora de `## [YYYY-MM-DD] <ingest\|query\|lint\|decision\|milestone\|note> \| …` |
| `concept_candidate` (info) | 8. Conceitos candidatos | `[[termo]]` citado ≥ 3× no escopo sem nota correspondente |
| `dead_link` | 9. Links mortos | alvo de `links_to`/`sources`/`related` inexistente no mesmo escopo |
| `stat_mismatch` | Evidências | %, IC de Wilson ou q de BH relatado que não bate com o recálculo |

Outros códigos (`ambiguous_link`, `no_frontmatter`, `bib_missing`, `no_index`, `no_log`,
`no_scope`) entram em Evidências como estão.

**Isentos de `orphan_page`**: `README.md`, `protocol.md` e qualquer stem começando com `_`. Para o
ruído de órfã em tabelas, figuras e drafts, sugira `docs/studies/<escopo>/README.md` como MOC
(*map of content*) apontando para elas.

`broken_citekey` só olha a forma marcada (`[@foo]`); narrativa solta (`@foo`) fica de fora de
propósito. Não reimplemente a checagem em grep.

### 4. Múltiplos `role: primary`

Não é coberto pelo `prumo wiki lint`. Em `docs/references/papers/`, o campo `role: primary` deve
aparecer no frontmatter de **exatamente 1** nota.

```
Grep "^role: primary" docs/references/papers/ -c
```

Reportar violação (0 ou ≥2).

### 5. Findings `superseded` sem cross-ref

Finding com `status: superseded` no frontmatter deve ter em `## Ressalvas` a linha `- Superseded by [[<finding-novo>]]`.

Reportar findings em violação.

### 6. Contradições entre páginas (LLM)

Delegar à inteligência do LLM (não é regex):

1. Ler as notas `type: finding` e `type: concept` em `docs/studies/*/notes/*.md` (limite: 30 arquivos por rodada — se maior, reportar "coverage parcial" e listar quais foram analisados).
2. Identificar claims conflitantes entre páginas (ex.: "AUROC >= 0.85 em coorte X" vs "AUROC 0.72 em coorte X").
3. Reportar pares `[[a]] ↔ [[b]]` com o conflito sumarizado.

Esta é a análise mais cara — se o usuário pedir lint rápido, pular esta seção e marcar como `SKIPPED`.

### 7. Stale claims

Claim stale = finding afirma X com base em source S1, mas source S2 **mais recente** contradiz S1 sobre o mesmo ponto.

Heurística:
- Para cada finding, coletar sources em `sources:`.
- Checar se alguma source mais recente (`date:` posterior) linkada a [[conceito]] compartilhado contradiz (novamente, LLM decide).
- Reportar pares.

## Relatório

Gerar como finding (`type: finding`) em `docs/studies/<slug>/notes/_lint_<YYYY-MM-DD>.md`:

```yaml
---
id: _lint_<YYYY-MM-DD>
type: finding
title: "Wiki lint — YYYY-MM-DD"
added: YYYY-MM-DD
status: active
tags: [lint, health-check]
sources: []
---
```

Corpo:

```markdown
## Pergunta
O wiki está consistente em YYYY-MM-DD?

## Resposta curta
<OK | <N> issues encontradas>

## Evidências

### Páginas órfãs (<count>)
- ...

### Citekeys quebradas (<count>)
- `[@foo]` referenciada em [[página-x]] — ausente do .bib

### Prefixo de log quebrado (<count>)
- ...

### role: primary violado
<ok | N primaries>

### Findings superseded sem cross-ref (<count>)
- ...

### Contradições (<count>)
- [[a]] ↔ [[b]]: <resumo>

### Stale claims (<count>)
- [[finding]] baseado em [[source-antigo]] — [[source-novo]] contradiz

### Conceitos candidatos (<count>)
- "focal loss" (citado 4×)
- ...

### Links mortos (<count>)
- [[origem]] → [[destino-inexistente]] no campo `sources:`

## Ressalvas / ameaças à validade
- Contradições e stale claims dependem do julgamento do LLM nesta rodada.
- Coverage parcial para <N> arquivos — lint cheio em outra rodada.
```

Anexar ao topo de `docs/_log.md`:

```
## [YYYY-MM-DD] lint | <N> issues encontradas

- Relatório: [[_lint_YYYY-MM-DD]]
- Principais categorias: órfãs=<n>, citekeys=<n>, contradições=<n>
```

## Saída ao usuário

```
✓ Lint completo — <N> issues encontradas
  Relatório: docs/studies/<slug>/notes/_lint_YYYY-MM-DD.md
  Log:       docs/_log.md atualizado

Sugestão de próximas ações:
  - Órfãs: linkar do _index.md ou deletar
  - Citekeys: rodar /par:paper library sync-bib
  - Conceitos candidatos: /par:wiki ingest para criar páginas
```

## Boundaries

- **Não corrige** — só reporta. Correções vão para o usuário ou para outras skills (`/par:paper library`, `/par:wiki ingest`).
- **Não apaga páginas órfãs** — pode ser que sejam drafts; listar e deixar decisão com o humano.
- **Seções 6/7 (LLM-based)** são caras — respeitar o limite de arquivos por rodada e reportar "coverage parcial" honestamente.
