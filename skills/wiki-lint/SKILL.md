---
name: wiki-lint
description: "Health-check do wiki de um pj_*: detecta páginas órfãs, citekeys quebradas, contradições, stale claims, conceitos sem página, links mortos, prefixo de log inválido, múltiplos role:primary. Gera relatório timestamped em docs/wiki/findings/_lint_<data>.md (fallback: docs/findings/)."
when_to_use: |
  Quando o usuário pedir "audite o wiki", "health check", "encontre páginas órfãs",
  "o wiki está consistente?", "o que está quebrado?", ou periodicamente após
  ingests em lote.
argument-hint: "[--quick]"
allowed-tools: Read Write Edit Glob Grep Bash(rg *)
prumo:
  version: 1.1.0
  schema: WikiLintReport/v1
  determinism: hybrid
  agent_compat: [claude-code]
  cost_estimate: ~5-20k tokens (depende do tamanho do wiki)
  inputs:
    quick: optional (pula análises LLM-based)
---

# Wiki Lint — auditar consistência do wiki

Aplica as regras de integridade listadas em `/docs/wiki-schema.md` do monorepo. Gera relatório; não corrige automaticamente.

## Pressupostos

- cwd é um `pj_*` com a estrutura padrão do wiki (`docs/_index.md`, `docs/_log.md`, subdirs, `references/`).
- Se o wiki é recém-criado e vazio, a skill retorna "Wiki vazio — nada a auditar" e sai.

## Checklist (ordem fixa)

> **Determinístico vs. agêntico.** As seções 2, 3, 4, 8 e 9 agora são cobertas
> por `prumo wiki lint` (Python, reprodutível, custo zero de LLM). Rode-o
> primeiro e gaste orçamento de LLM apenas nas seções **6 (contradições)** e
> **7 (stale claims)**, que exigem julgamento semântico. Códigos emitidos:
> `broken_citekey`, `orphan_page`, `broken_log_prefix`, `multiple_primary`,
> `dead_link`, `concept_candidate` (severity `info`).

### 1. Páginas órfãs

Uma página é órfã se está em `docs/{concepts,entities,findings,sources}/` mas **não** é linkada de nenhum lugar.

```bash
# Universo: todos os arquivos markdown do wiki (exceto _index, _log, README, protocol).
# Conjunto "linkado": união de
#   - entradas em _index.md
#   - wikilinks [[nome]] em outras páginas
```

Implementação sugerida:

```bash
# Listar todos os slugs (stem sem .md)
Glob docs/{concepts,entities,findings,sources}/*.md

# Conjunto linkado via rg (não usar Grep direto — usar a ferramenta Grep)
Grep "\\[\\[([^@][^\\]]+)\\]\\]" docs/ references/notes/ -o --multiline
# + parse de _index.md
```

Reportar lista de órfãs com caminho relativo.

### 2. Citekeys quebradas

Toda `[[@foo]]` deve ter entrada `@<tipo>{foo,…}` em `references/_references.bib`.

```
# Coletar citekeys referenciadas:
Grep "\\[\\[@[^\\]]+\\]\\]" docs/ references/notes/ -o

# Coletar citekeys definidas:
Grep "^@\\w+\\{([^,]+)," references/_references.bib -o

# Diff: referenciadas \ definidas
```

Reportar citekeys referenciadas sem definição (e, se útil, o inverso — definidas mas nunca usadas).

### 3. Prefixo de log quebrado

Toda entrada em `_log.md` deve casar `^## \[\d{4}-\d{2}-\d{2}\] (ingest|query|lint|decision|milestone|note) \| .+$`.

```
Grep "^## " docs/_log.md
```

Reportar linhas que não batem o regex.

### 4. Múltiplos `role: primary`

Em `references/notes/`, o campo `role: primary` deve aparecer no frontmatter de **exatamente 1** nota.

```
Grep "^role: primary" references/notes/ -c
```

Reportar violação (0 ou ≥2).

### 5. Findings `superseded` sem cross-ref

Finding com `status: superseded` no frontmatter deve ter em `## Ressalvas` a linha `- Superseded by [[<finding-novo>]]`.

Reportar findings em violação.

### 6. Contradições entre páginas (LLM)

Delegar à inteligência do LLM (não é regex):

1. Ler `docs/wiki/findings/*.md` (ou `docs/findings/*.md` como fallback) e `docs/concepts/*.md` (limite: 30 arquivos por rodada — se maior, reportar "coverage parcial" e listar quais foram analisados).
2. Identificar claims conflitantes entre páginas (ex.: "AUROC >= 0.85 em coorte X" vs "AUROC 0.72 em coorte X").
3. Reportar pares `[[a]] ↔ [[b]]` com o conflito sumarizado.

Esta é a análise mais cara — se o usuário pedir lint rápido, pular esta seção e marcar como `SKIPPED`.

### 7. Stale claims

Claim stale = finding afirma X com base em source S1, mas source S2 **mais recente** contradiz S1 sobre o mesmo ponto.

Heurística:
- Para cada finding, coletar sources em `sources:`.
- Checar se alguma source mais recente (`date:` posterior) linkada a [[conceito]] compartilhado contradiz (novamente, LLM decide).
- Reportar pares.

### 8. Conceitos candidatos a página

Conceito mencionado em wikilinks `[[termo]]` **sem** arquivo correspondente em `docs/concepts/` e **citado ≥ 3 vezes**.

```
Grep "\\[\\[[^@][^\\]]+\\]\\]" docs/ -o   # todos wikilinks não-citekey
# Agregar, filtrar por frequência >=3, remover os que já têm arquivo.
```

Reportar lista ordenada por frequência descendente.

### 9. Links mortos em `links_to` / `sources`

Frontmatter com lista de wikilinks (`links_to`, `sources`, `related`) cujo alvo não existe no vault.

```
Para cada página com esses campos:
  Para cada wikilink no campo:
    Verificar se o arquivo destino existe.
```

Reportar pares (página origem, link morto).

## Relatório

Gerar `docs/wiki/findings/_lint_<YYYY-MM-DD>.md`:

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
- `[[@foo]]` referenciada em [[página-x]] — ausente do .bib

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
  Relatório: docs/wiki/findings/_lint_YYYY-MM-DD.md
  Log:       docs/_log.md atualizado

Sugestão de próximas ações:
  - Órfãs: linkar do _index.md ou deletar
  - Citekeys: rodar /prumo-assist:paper-manager sync-bib
  - Conceitos candidatos: /prumo-assist:wiki-ingest para criar páginas
```

## Boundaries

- **Não corrige** — só reporta. Correções vão para o usuário ou para outras skills (`/prumo-assist:paper-manager`, `/prumo-assist:wiki-ingest`).
- **Não apaga páginas órfãs** — pode ser que sejam drafts; listar e deixar decisão com o humano.
- **Seções 6/7 (LLM-based)** são caras — respeitar o limite de arquivos por rodada e reportar "coverage parcial" honestamente.
