---
name: wiki-query
description: Responde uma pergunta ancorada no wiki do pj_* ativo (docs/ + references/) usando qmd + leitura de páginas, sempre com citações. Oferece arquivar a resposta como novo finding em docs/findings/ quando for útil. Invocar quando o usuário perguntar "o que a literatura diz sobre X", "compare Y e Z", "gere tabela comparativa", "resuma os achados sobre W", "quais decisões tomamos sobre Z", ou qualquer pergunta aberta cujo contexto esteja no wiki. NÃO é a skill para perguntas de código — use as skills específicas de domínio.
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

Se **sim**:

1. Criar `docs/findings/<slug>.md` com frontmatter:

   ```yaml
   ---
   id: <slug>
   type: finding
   title: "<pergunta ou síntese da resposta>"
   added: YYYY-MM-DD
   status: active
   tags: [...]
   sources: [[[página-a]], [[@citekey]], ...]
   notebook: ""           # ou caminho se veio de notebook/reports
   ---
   ```

   Corpo: seções `## Pergunta`, `## Resposta curta`, `## Evidências`, `## Ressalvas / ameaças à validade`.

2. Atualizar `docs/_index.md` → seção `## Findings`.

3. Anexar ao topo de `docs/_log.md`:

   ```
   ## [YYYY-MM-DD] query | <pergunta curta>

   - Arquivado em: [[<slug>]]
   - Páginas consultadas: [[a]], [[b]], [[@citekey]]
   ```

Se **não**: só registrar no log:

   ```
   ## [YYYY-MM-DD] query | <pergunta curta>

   - Respondida sem arquivar.
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
