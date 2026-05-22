---
name: wiki-query
description: "Responde pergunta ancorada no wiki do pj_* (docs/ + references/) usando qmd + leitura de páginas, sempre com citações ([[wikilinks]] e [[@citekeys]]). Oferece arquivar a resposta como finding em docs/findings/ quando útil. NÃO é para perguntas de código."
when_to_use: |
  Quando o usuário perguntar "o que a literatura diz sobre X", "compare Y e Z",
  "gere tabela comparativa", "resuma os achados sobre W", "quais decisões
  tomamos sobre Z", ou qualquer pergunta aberta cujo contexto esteja no wiki.
argument-hint: "<pergunta>"
allowed-tools: Read Glob Grep Bash(qmd *) Bash(prumo paper *) mcp__qmd__query mcp__qmd__search
prumo:
  version: 1.0.0
  schema: WikiQueryResponse/v1
  determinism: agentic
  agent_compat: [claude-code]
  cost_estimate: ~5-15k tokens (depende da cobertura)
  inputs:
    question: required
---

# Wiki Query — responder com citações e arquivar

Opera sobre o wiki estruturado em `/docs/wiki-schema.md` (monorepo). Usa `qmd` (via MCP `mcp__qmd__*` se disponível; senão via `Bash("qmd …")`) para busca híbrida.

## Pressupostos

- cwd é um `pj_*` com `docs/_index.md`, `docs/_log.md` e subdirs.
- qmd está instalado (ver `docs/operations.md` do monorepo) e o wiki foi indexado ao menos uma vez (`qmd collection add . --name <pj>` + `qmd embed`).
- Se não indexado, fluxo ainda funciona usando só `_index.md` + `Grep` + `Read`, mas resposta perde cobertura semântica.

## Fluxo

### 1. Entender a pergunta

Se a pergunta for ambígua ou genérica ("tudo sobre X"), pedir refinamento em **uma** rodada — nunca mais de uma. Se o usuário insistir, prosseguir com a interpretação mais provável e deixar claro na resposta.

### 2. Localizar candidatas

1. **`Read docs/_index.md`** → identificar seções/entidades/conceitos relacionados.
2. **Busca qmd** (se MCP disponível):
   - `mcp__qmd__query "<pergunta>"` (hybrid com rerank) → top 10.
   - Fallback BM25: `mcp__qmd__search`.
3. **Fallback sem qmd**: `Grep` com termos-chave em `docs/ references/notes/`.
4. Se o tópico é bibliográfico puro, considerar também `references/_references.bib` e `/paper-manager list`.

### 3. Ler as páginas mais relevantes

Ler ≤ 5–8 páginas selecionadas na íntegra (não só trechos). Extrair:
- **Claim** (o que cada página afirma sobre a pergunta).
- **Evidência** (fonte citada pela página — paper, source, notebook, decision).
- **Ressalva** (limitações, coorte específica, dataset).

### 4. Sintetizar resposta

Formato padrão (adaptar quando a pergunta pedir tabela/diagrama explícito):

```markdown
**Resposta curta:** <2–3 linhas direto ao ponto>

**Detalhes:**
- <bullet 1> — ver [[página-a]], [[@citekey]]
- <bullet 2> — ver [[página-b]]
- <bullet 3> — ver [[finding-anterior]]

**Ressalvas:**
- <limitação 1>
- <limitação 2>

**Gaps identificados** _(opcional)_:
- <nenhuma página cobre X — candidato a /wiki-ingest ou pergunta a ir buscar na literatura>
```

Regras:
- **Toda afirmação tem citação** (wikilink `[[…]]` ou `[[@citekey]]`). Sem afirmações sem fonte.
- **Nunca inventar citekey** — se uma claim não tem fonte no wiki, marcar explicitamente como gap.
- **Preferir tabelas** quando a pergunta for comparativa (`| modelo | AUROC | coorte | ... |`).

### 5. Oferecer arquivamento

Depois da resposta, perguntar **exatamente uma vez**:

> Quer arquivar essa resposta como finding? (`docs/findings/<slug>.md`) — útil se a síntese for reutilizada.

Se **sim**, executar via `Bash`:

```bash
python3 -c '
from pathlib import Path
from prumo_assist.domains.wiki.findings import archive_as_finding

out = archive_as_finding(
    pj_path=Path("."),
    slug="<slug>",
    title="<pergunta ou síntese>",
    body=(
        "## Pergunta\n\n<pergunta>\n\n"
        "## Resposta consolidada\n\n<resposta>\n\n"
        "## Evidências\n\n<lista de wikilinks>\n\n"
        "## Limitações\n\n<ressalvas>\n"
    ),
    sources=["[[<page-a>]]", "[[@<citekey>]]"],
    date="<hoje ISO>",
    tags=[<tags>],
    generator="wiki-query",
)
print(f"finding: {out}")
'
```

A função cuida de criar o arquivo, atualizar `_index.md` e `_log.md` em uma operação atômica (vide ``prumo_assist.domains.wiki.findings``).

Se **não**: registrar no log via:
```bash
python3 -c '
from pathlib import Path
log = Path("docs/_log.md")
log.write_text(log.read_text() + "\n## [<data>] wiki-query | <pergunta curta>\n\n- Respondida sem arquivar.\n")
'
```

### 6. Visualizações inline

Quando a resposta pedir gráfico (comparação numérica, distribuição, timeline):
- Gerar bloco Python com **seaborn + matplotlib** (ver rule `.claude/rules/coding_style.md`), renderizado em notebook ou salvo em `docs/findings/_assets/<slug>.png` referenciado no markdown do finding.
- Plotly **só** se o usuário pedir explicitamente um dashboard interativo.

## Boundaries

- **Não executa notebooks** nem roda código de modelagem — isso é escopo das skills `clinical-metrics`, `data-cleaning`, etc.
- **Não cria páginas `concept`/`entity`** — isso é `/wiki-ingest`.
- **Limite de leitura**: até 8 páginas por query para manter contexto enxuto. Se a pergunta for enorme, quebrar em sub-perguntas e rodar em sequência.

## Erros comuns

- **qmd retorna 0 resultados** → rodar `qmd embed` antes; ou recair em `Grep` + `Read docs/_index.md`.
- **Usuário pergunta algo que não está no wiki** → responder "Não há páginas sobre isso no wiki" + sugerir `/wiki-ingest` com fontes candidatas + registrar no log como `query | <pergunta> — gap`.
- **Resposta exige mais de 8 páginas** → pedir ao usuário para refinar OU responder em partes e arquivar como 2 findings ligados por `related:`.
