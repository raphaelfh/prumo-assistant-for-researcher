---
name: lint
description: "Health-check do wiki de um pj_*: detecta páginas órfãs, citekeys quebradas, contradições, stale claims, conceitos sem página, links mortos, prefixo de log inválido, múltiplos role:primary. Gera relatório timestamped como finding (type: finding) em docs/studies/<slug>/notes/_lint_<data>.md."
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
  requires: [cli]
  phrases:
    - "audita o wiki"
    - "encontra páginas órfãs"
    - "o wiki está consistente?"
  legacy: [wiki-lint]
---

# Wiki Lint — auditar consistência do wiki

<!-- prumo:preflight:begin -->
> **Preflight (contrato ADR-0019) — execute ANTES de qualquer operação desta skill:**
>
> 1. **CLI:** rode `prumo --version`. Se o comando NÃO existir: não simule NENHUMA
>    operação desta skill; roteie para `/prumo-assist:start` (instalação guiada com
>    consentimento) e pare aqui.
> 2. **Drift CLI×plugin (evidência da Fase 0):** se `$CLAUDE_PLUGIN_ROOT` estiver
>    definido, compare a versão do CLI com o campo `version` de
>    `$CLAUDE_PLUGIN_ROOT/.claude-plugin/plugin.json`. CLI mais antigo → avise
>    ("CLI X < plugin Y — comandos novos podem não existir") e ofereça
>    `uv tool upgrade prumo-assist` (rode SÓ com consentimento). Sem a variável,
>    pule este passo em silêncio.
> 3. **Estrutura:** se o diretório não tiver `docs/references/` de um `pj_*`,
>    oriente `prumo init pj_<nome>` — NUNCA crie o scaffold manualmente (o agente
>    não simula trabalho do CLI) e NUNCA cite tooling do monorepo do autor.
>
> Recusar-se a operar sem dependência NÃO é falha — é o contrato fail-closed (D1):
> operação exata nunca é simulada.
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

> **Determinístico vs. agêntico.** As seções 2, 3, 4, 8 e 9 agora são cobertas
> por `prumo wiki lint` (Python, reprodutível, custo zero de LLM). Rode-o
> primeiro e gaste orçamento de LLM apenas nas seções **6 (contradições)** e
> **7 (stale claims)**, que exigem julgamento semântico. Códigos emitidos:
> `broken_citekey`, `orphan_page`, `broken_log_prefix`, `multiple_primary`,
> `dead_link`, `concept_candidate` (severity `info`), `stat_mismatch` (%, IC de Wilson ou q de
> BH relatado que não bate com o recálculo).

### 1. Páginas órfãs

Uma página é órfã se está sob um escopo (`docs/studies/<escopo>/`) mas **não** é linkada de nenhum lugar.

**Isentos de `orphan_page`**: `README.md`, `protocol.md` e qualquer stem começando com `_`. A isenção é intencional e útil — um `README.md` por escopo funciona como MOC (*map of content*) e sai do relatório. É a saída recomendada para o ruído de órfã em tabelas, figuras e drafts, que nunca terão link de entrada vindo de outra nota: crie `docs/studies/<escopo>/README.md` apontando para elas.

```bash
# Universo: todos os arquivos markdown do wiki (exceto _index, _log, README, protocol).
# Conjunto "linkado": união de
#   - entradas em _index.md
#   - wikilinks [[nome]] em outras páginas
```

Implementação sugerida:

```bash
# Listar todas as páginas do escopo (identidade = caminho relativo ao escopo)
Glob docs/studies/<escopo>/**/*.md

# Conjunto linkado via rg (não usar Grep direto — usar a ferramenta Grep)
Grep "\\[\\[([^@][^\\]]+)\\]\\]" docs/studies/<escopo>/ docs/references/papers/ -o --multiline
# + parse de _index.md
```

Reportar lista de órfãs com caminho relativo.

### 2. Citekeys quebradas

Toda citação `[@foo]` (marcada) ou `@foo` (narrativa) deve ter entrada `@<tipo>{foo,…}` em `docs/references/_references.bib`.

Não reimplemente a extração de citekey em grep: `prumo wiki lint` já usa a
gramática única (`core/citations.py`), tratando corretamente grupo (`[@a; @b]`)
e locator (`[@k, p. 3]`) — que um grep de colchete inteiro transformaria em
falso positivo. Escopo do `broken_citekey`: só as formas MARCADAS (`[@foo]`),
via `scan_marked_citekeys` — narrativa solta (`@foo`) fica de fora de
propósito, para que um handle `@fulano` em prosa não vire warning espúrio. Se
o usuário quiser conferir narrativa, isso é leitura manual da página, não
saída do lint.

Reportar citekeys referenciadas sem definição (e, se útil, o inverso — definidas mas nunca usadas).

### 3. Prefixo de log quebrado

Toda entrada em `_log.md` deve casar `^## \[\d{4}-\d{2}-\d{2}\] (ingest|query|lint|decision|milestone|note) \| .+$`.

```
Grep "^## " docs/_log.md
```

Reportar linhas que não batem o regex.

### 4. Múltiplos `role: primary`

Em `docs/references/papers/`, o campo `role: primary` deve aparecer no frontmatter de **exatamente 1** nota.

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

### 8. Conceitos candidatos a página

Conceito mencionado em wikilinks `[[termo]]` **sem** nota correspondente no `notes/` do escopo
(uma nota `type: concept`) e **citado ≥ 3 vezes** dentro do mesmo escopo.

```
Grep "\\[\\[[^\\]]+\\]\\]" docs/studies/<escopo>/ -o   # todos wikilinks do escopo
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
  - Citekeys: rodar /prumo-assist:paper library sync-bib
  - Conceitos candidatos: /prumo-assist:wiki ingest para criar páginas
```

## Boundaries

- **Não corrige** — só reporta. Correções vão para o usuário ou para outras skills (`/prumo-assist:paper library`, `/prumo-assist:wiki ingest`).
- **Não apaga páginas órfãs** — pode ser que sejam drafts; listar e deixar decisão com o humano.
- **Seções 6/7 (LLM-based)** são caras — respeitar o limite de arquivos por rodada e reportar "coverage parcial" honestamente.
