---
title: Citação Pandoc como cidadã de primeira classe — fechar as divergências de gramática
date: 2026-07-26
status: draft
tags: [citations, I7, review, guards, wiki, paper, skills, zettlr-front]
---

# Citação Pandoc como cidadã de primeira classe

## Resumo executivo

O spec 2026-07-22 (Zettlr front) tornou o **Pandoc puro** (`[@key]`, `@key`
narrativa, `[@a; @b]`) a sintaxe **mandatória** de projeto novo, e o legado
Obsidian (`[[@key]]`) passou a ser só leitura de projeto antigo. O código,
porém, não acompanhou por igual: em vários pontos que **reconhecem, protegem,
contam ou validam** citação, o repo ainda localiza o objeto por um literal da
forma legada.

O efeito é uma **inversão**: a sintaxe que o produto obriga a escrever é a
menos protegida e a menos validada. Guardas de segurança escritas contra
agente adversário recusam em `[[@key]]` e aceitam em `[@key]`; `verify-refs`
deixa de checar retratação; buscas embutidas em skills reportam "ninguém cita
este paper" para acervos inteiros.

Esta spec fecha essas divergências. O eixo é único:

> **Todo lugar do código que reconhece citação consome `core/citations.py`
> (Princípio I7) e trata as duas gramáticas — e, dentro da Pandoc, as duas
> formas (bracketed e narrativa).**

Escopo: 8 correções de comportamento, verificadas por repro, mais a
higiene documental. A prioridade é **empírica**, não estética: o que foi
medido no acervo real do usuário vem antes do que é teórico.

## Contexto e problema

Um fix já entrou nesta linha de trabalho (commit `813d230`): a guarda I1
(`_reject_anchor_tangent_to_citation`) localizava o "átomo citação" apenas por
`_PROPOSAL_CITATION_SPAN_RE = r"\[\[@[^\]]+\]\]"` e, em projeto Pandoc puro,
protegia **zero spans**. Foi corrigida pela união com
`core.citations.iter_marked_citation_spans`.

A varredura subsequente mostrou que **aquele fix era necessário mas
incompleto**, e que o padrão se repete em mais 7 lugares. O defeito tem forma
constante: *código que localiza citação por literal legado em vez de consumir
a gramática única*. O sintoma é sempre o mesmo — comportamento divergente
entre um documento em sintaxe Pandoc e o mesmo documento em legado.

## Fatos verificados (2026-07-26, neste worktree, sobre `9041810` + `813d230`)

Todos reproduzidos rodando código, não por leitura. Baseline: 782 testes
verdes, `mypy --strict` e `ruff` limpos.

### F1 — Guarda de conservação de citação aceita composição em Pandoc

`_reject_citation_divergence` (`review.py:3108`) faz duas sub-checagens e
**nenhuma enxerga a gramática mandatória**:

| entrada | `[[@k]]` legado | `[@k]` Pandoc |
|---|---|---|
| agente insere `b='['` sobre `@silva2020` | **recusado** | **aceito** |

Medição das sub-checagens no par narrativa→bracketed
(`"Como discute @silva2020,"` → `"Como discute [@silva2020],"`):

- (i) spans legados: `[]` → `[]` (iguais, passa)
- (ii) `Counter(CITEKEY_RE.findall(...))`: `{'silva2020': 1}` → `{'silva2020': 1}` (iguais, passa)

A informação que distinguiria os dois estados **já existe** em
`core/citations.py` e não é consumida: `scan_marked_citekeys` vai de `[]` para
`['silva2020']`, e `iter_marked_citation_spans` de `[]` para `[(13, 25)]`.

**Alcance honesto (verificado, e menor que o alarme inicial):** a citação
fabricada **não chega à página**. `apply_review` hard-falha com
`CitationConservationError` (I5) e `pagina.md` fica byte-idêntico. O dano real
é duplo: (a) a guarda anunciada como conservação de citação vale só no legado;
(b) a proposta ilegítima é **gravada no worklist**, e o `apply_review` do lote
inteiro passa a hard-falhar com mensagem que **culpa o humano** ("confira se
`review.md` foi editado incorretamente") — envenenamento de worklist e trava
da revisão.

### F2 — A guarda I1 corrigida ainda não cobre citação narrativa

O fix `813d230` uniu legado + bracketed, mas a forma **narrativa** `@key` —
legítima e mandatória na gramática Pandoc — não gera span protegido. No mesmo
documento:

```
"Como @smith2024 mostrou, ver tambem [@jones2020]."
   ins ' [sic]' colado em @smith2024   -> ACEITO   (chega à página)
   ins ' [sic]' colado em [@jones2020] -> RECUSADO
```

Violação direta de I1 ("qualquer edição que encoste na citação é decisão
humana") por um caminho que o legado bloqueia — a gramática legada não tem
forma narrativa. Aqui a mudança **chega ao artefato** após
`apply_review(by_author='agente', author_decision=True)`.

### F3 — `verify-refs --page` não checa retratação de citação narrativa

O escopo de `--page` vem de `scan_marked_citekeys`, que por contrato exclui
narrativa. Página cujas citações são narrativas sai com `scope=[]`,
`checked=0`, **exit 0** e o texto verde "✓ 0 referência(s) verificada(s)" —
indistinguível de página sem citação. Com paper **retratado** no acervo, as
formas legada e bracketed imprimem `✗ [error] known2020: retracted` e saem com
exit 1 (gate do ADR-0018); a narrativa sai calada.

Assimetria interna do domínio: `paper/graph.py` usa a captura ampla
`iter_citekeys`, então uma narrativa **cria aresta** no grafo de citação mas
**não é verificada** contra retratação.

### F4 — A segunda gramática do `route.py` rejeita 5% do acervo REAL

`domains/capture/route.py:18` mantém `CITEKEY_RE = ^@?([a-z][\w-]*\d{4}[\w-]*)$`,
um segundo reconhecedor com gramática mais estrita que a canônica. Medido
contra os `.bib` reais dos 4 `pj_*` do usuário (**173 citekeys únicas**):

| reconhecedor | falha/trunca |
|---|---|
| `core.citations.CITEKEY_RE` | **0/173** |
| `capture.route.CITEKEY_RE` | **10/173 (5%)** |

Chaves reais rejeitadas: `collins2024tripod+ai`, `2023attentionbased`,
`benjamind.simon2024future`, `integrative`, `collins2024tripod+aia`… Efeito
visível: `prumo capture collins2024tripod+ai` responde *"Não consegui detectar
o tipo"* para uma citekey da bibliografia do próprio usuário.

Isto contradiz a ADR-0016, que afirma em texto aceito que "o tokenizador
divergente que descartava chaves compostas foi eliminado". O I7 nunca foi
fechado — seu escopo declarado cobria só `compose.py`.

### F5 — Buscas embutidas em skills divergem da gramática canônica

- `skills/paper-manager/SKILL.md:178` — `rg "\[\[@<citekey>\]\]"` casa **zero**
  em nota Pandoc. O grafo reverso sai vazio e o agente reporta "nenhum paper do
  acervo cita este", conclusão falsa indistinguível do caso legítimo. O
  fallback `rg "cites:.*<citekey>"` **não compensa**: o YAML é serializado em
  bloco (`cites:\n- key`), então não casa em nenhuma das gramáticas.
- `skills/wiki-lint/SKILL.md:89` — o grep captura o **colchete inteiro** como
  se fosse um citekey único, então `[@a; @b]` e `[@k, p. 3]` viram falso
  positivo `broken_citekey` para chaves que **existem**. A forma quebrada é
  justamente a que `scientific-writing/SKILL.md:64` **manda** escrever.

### F6 — `dead_link` de frontmatter não valida alvo de página em link markdown

`_check_dead_frontmatter_links` (`wiki/lint.py:191`, ramo `target not in
page_stems` em `:227`) depende de `_WIKILINK_TARGET_RE` (`:188`) e só enxerga
`[[pagina]]`. Em `related:`/`links_to:` escritos como link markdown
(`'[ghostpage](ghostpage.md)'`) — a forma que o próprio `wiki/lint.py:33-35`
reconhece como esperada em projeto Pandoc-puro, já tendo `MD_LINK_RE` (`:35`)
para o corpo —
nenhum `dead_link` é emitido. Diferente do ramo de citekey, aqui **não há rede
de segurança**: `scan_marked_citekeys` não cobre alvo de página.

### F7 — Template clínico prescreve uma TERCEIRA forma

`templates/modules/clinical/docs/templates/data_dictionary_skeleton.md`
declara `[[citekey]]` (sem `@`) como âncora bibliográfica, repetida em ~18
células. Não é Pandoc nem legado: nenhum consumidor de citação a enxerga
(`wiki lint` não emite `broken_citekey`, `verify-refs` não verifica, o export
não gera entrada de bibliografia). Pior: `PAGE_LINK_RE` **casa** `[[key]]`, e o
lint passa a tratar citekeys como candidatas a página (`concept_candidate`).

### F8 — Falso-negativos do `CITEKEY_RE` canônico são reais, porém teóricos hoje

Verificado contra Pandoc 3.9.0.2 (que aceita e renderiza todos):
inicial Unicode (`@Ünal2024`), forma chaveada `@{...}` (recomendada pelo manual
do Pandoc), ênfase com underscore (`_@key_`), `://` não chaveado. Todos
devolvem captura vazia ou truncada.

**Porém**: `0/173` chaves do acervo real caem nessas classes — os únicos
caracteres não-alfanuméricos presentes são `-` (6), `+` (2), `.` (1), todos já
cobertos. É correção de robustez, não de dor atual. Protótipo validado como
**superset estrito** (zero regressão em 7 famílias de caso) e com **1 grupo de
captura preservado**:

```python
CITEKEY_RE = re.compile(r"(?<![@0-9A-Za-z])@(\w(?:\w|[:.#$%&+\-?<>~/]\w)*)")
```

Cobre inicial Unicode e ênfase-underscore. A forma chaveada `@{...}` **não**
cabe sem segundo grupo — fica para o nível de função.

## Decisões

### D1 — `_reject_citation_divergence` ganha uma terceira checagem (F1)

Adicionar checagem que consuma a gramática única, **mantendo as duas
existentes** (mesma estratégia de união do `813d230`):

```python
Counter(t[s:e] for s, e in _citation_atom_spans(t))  # before vs after
```

Comparação simétrica de **textos** de span, então a sobreposição
legado-externo + Pandoc-interno é inofensiva. Recusa os dois cenários de F1
porque `[@silva2020]` só existe no `after`.

### D2 — `_citation_atom_spans` passa a cobrir narrativa (F2)

Expor em `core/citations.py`:

```python
def iter_narrative_citation_spans(text: str) -> Iterator[tuple[int, int]]:
```

iterando `CITEKEY_RE.finditer` e devolvendo **`match.span()`** — o span do
match inteiro, começando no `@`; nunca `match.span(1)`, que deixaria o `@`
desprotegido — excluindo matches já contidos em `iter_marked_citation_spans`.
`_citation_atom_spans` passa a unir as **três** fontes.

`_PROPOSAL_CITATION_SPAN_RE` **permanece**: é a única que dá o span externo do
legado.

### D3 — `verify-refs --page` faz duas varreduras (F3)

Corrigir **no call site**, nunca em `core/citations.py`:

- escopo de verificação → captura ampla (`iter_citekeys`), filtrada por
  `k in by_key` (o filtro já existe e já protege contra `@fulano` em prosa);
- achado `missing-citekey` → continua na captura marcada (`scan_marked_citekeys`),
  para não acusar handle de prosa como citekey ausente.

Acrescentar achado `empty-page-scope` (`level='info'`, não muda exit code) para
que "0 verificadas" deixe de ser indistinguível de "nada a verificar".

### D4 — Fechar o I7: `route.py` delega à gramática única (F4)

`domains/capture/route.py` passa a usar `core.citations.CITEKEY_RE`, ancorada
para uso de token único (`fullmatch`). Corrigir a afirmação da **ADR-0016**
sobre o tokenizador divergente ter sido eliminado — via nota de correção, já
que ADR aceito é imutável.

### D5 — Skills consomem a gramática certa (F5)

- `paper-manager/SKILL.md:178` → `rg "@<citekey>"` com **fim de citekey
  ancorado** (colisão de prefixo verificada: `@smith2025reviewX` aparece na
  busca por `@smith2025review`); fallback `cites:` corrigido para o dump em
  bloco (`^\s*-\s*<citekey>\s*$`).
- `wiki-lint/SKILL.md:89` → deixar de reimplementar: `domains/wiki/lint.py:86`
  já faz a checagem certa. A skill chama `prumo wiki lint`.

### D6 — `_check_dead_frontmatter_links` é bifurcada (F6)

A função é **dual-propósito** (citekey **e** página) — substituir o regex mata
o ramo de página em silêncio. Bifurcar:

- ramo citekey → `scan_marked_citekeys` sobre o valor do campo;
- ramo página → reusar `MD_LINK_RE` (já existente para o corpo), preservando o
  `(?<!\!)` de imagem e o skip de esquema (`http`).

**Não** aceitar alvo nu: `sources:` recebe string livre (título de paper, URL,
nome de dataset) e qualquer não-stem viraria `dead_link`, inundando o
relatório.

### D7 — Template clínico migra célula por célula (F7)

`[[citekey]]` → `[@citekey]` **célula por célula**, nunca find/replace cego: o
mesmo arquivo tem wikilinks de página legítimos (`[[decisions/<ADR>]]`,
`[[statistical_analysis_plan]]`) que a troca destruiria.

### D8 — `CITEKEY_RE` endurecido, com contrato travado por teste (F8)

Adotar o protótipo validado. **Restrição inegociável**, travada por
`assert CITEKEY_RE.groups == 1`: `review.py` alimenta `Counter` com
`CITEKEY_RE.findall`, que devolve `list[str]` **só** com exatamente um grupo —
qualquer grupo a mais faz o multiconjunto comparar tuplas **silenciosamente**.

A forma chaveada `@{...}` fica **fora** desta spec (exigiria segundo grupo ou
refatorar os call sites de `findall`) — registrada como trabalho futuro.

### D9 — Higiene documental

- `write/zettlr.py:7-10` — a docstring afirma que `citeproc: true` rodaria
  **depois** dos filtros Lua. Verificado com filtro-sonda: roda **antes** (o
  Lua recebe `(Cercek 2022)`). A decisão do código está certa; só a
  justificativa é falsa — a razão correta é que **só a lista `filters` tem
  ordem garantida pelo manual**. Nunca declarar os dois juntos (citeproc roda
  duas vezes, bibliografia duplicada).
- `write/zettlr.py` e `specs/2026-07-22-zettlr-front-design.md:53` — a
  precedência é a **inversa** da afirmada: `bibliography` de defaults file
  sobrescreve o do frontmatter (verificado com dois `.bib` conflitantes).
- `core/citations.py` — a docstring diz ser o único reconhecedor do pacote;
  qualificar até D4 aterrissar.
- `wiki/findings.py:41` — docstring de `sources` diz "lista de wikilinks
  `[[@key]]`".
- `mcp_server.py:112`, `review.py:3271`, `review-reconcile/SKILL.md:180` —
  guardas documentadas só na gramática legada. **Sem efeito em runtime**
  (verificado: comportamento simétrico desde `813d230`); é alinhamento de
  texto na superfície que o agente lê.

## Fora de escopo

- **Migração de conteúdo legado.** Decisão 5 do spec 2026-07-22 (só projetos
  novos) permanece. Nada de `[[@key]]` existente é reescrito. 231 ocorrências
  no repo continuam válidas como fixture e leitura.
- **Forma chaveada `@{...}`** — ver D8.
- **`cites:`/`sources:` com chave nua.** Era o pedido original desta linha de
  trabalho e continua defensável (frontmatter é machine-owned, `@`/`[` exigem
  aspas em YAML), mas ficou o item de menor valor relativo e mexe em
  `wiki/schemas/v1.py` sob a regra forward-only. Vai para spec própria.
- **`" ".join(step.citations)` em `study.py`.** O contrato do campo é ambíguo
  na skill (`citations` aceita citekey **ou** wikilink) e agrupar quebraria o
  caso misto no Pandoc. O conserto é desambiguar o contrato primeiro.
- **Link de página `[[page]]` vs markdown relativo.** Eixo próprio, toca
  `wiki-ingest` e o grafo do wiki.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| **Contrato do `findall`** (citado por 8 de 9 céticos): grupo a mais quebra `Counter` em silêncio | `assert CITEKEY_RE.groups == 1` como teste; alargamento só com `(?:...)` |
| **Fronteira de span legado**: `iter_marked_citation_spans` casa o miolo de `[[@key]]` | Nunca **substituir** `_PROPOSAL_CITATION_SPAN_RE` — só **unir**. Já documentado em `_citation_atom_spans` |
| **Super-proteção ao incluir narrativa** (D2): `CITEKEY_RE` é captura ampla; `@media`, `@Injectable`, menção a coautor viram átomos intocáveis | Guarda é fail-toward-human: falso positivo vira trabalho manual. Filtrar code fences no `_citation_atom_spans` (hoje não filtra) |
| **Colchete solto** (D1): `[` em prosa distante re-segmenta o corpo e pode virar "citação fabricada" | Comparar **textos** de span, não contagens; teste com `{++[sic]++}` em parágrafo que tem `[@k]` noutro ponto |
| **Exit code do `verify-refs`** (D3): páginas que passam com exit 0 passam a sair com 1 | É o comportamento desejado, mas é **breaking** — "⚠ Breaking" + MINOR pela ADR-0015 |
| **Custo de rede** (D3): escopo maior = mais Crossref/PubMed | Mitigado pelo filtro `k in by_key` e cache TTL 7 dias |
| **Não mexer no span-map**: fazer `normalize_markdown_with_map` emitir `kind="citation"` para Pandoc é tentador e perigoso | Fragment `citation` é não-identity: toda prosa hoje num único `identity` seria fatiada, e `del`/`sub` legítimos que atravessam citação quebrariam |
| **Não alargar `scan_marked_citekeys`** para resolver F3 | Contrato conservador é consumido por 2 domínios; `wiki/lint.py:86` depende dele. Corrigir no call site |
| **Duplicação de issue** no lint: fazer `dead_link` ver `[@key]` leva Pandoc de 1 para 2 issues | Importaria o ruído do legado. Preferir remover a duplicata do legado a criar uma nova |
| **Template clínico**: projetos que já copiaram o skeleton não são corrigidos, mas passam a ter citekeys visíveis ao lint | `broken_citekey` novos vão aparecer onde havia silêncio — avisar no CHANGELOG |
| **`skills/` é releasável** (force-included no wheel) | PATCH pré-1.0; rodar `pytest` + `gen_indexes.py --check`; não editar regiões machine-owned à mão |

## Testes

Cada correção com par **Pandoc vs legado no mesmo documento** — foi
exatamente a ausência disso que deixou o bug da I1 passar. Inventário atual:
32 testes legacy-only, 26 pandoc-only, 14 cobrindo as duas.

- **D1** — par Pandoc de `test_propose_prose_edit_rejects_composition_that_fabricates_citation` (`'Prefixo @fake2020] sufixo'` + `b='['`).
- **D2** — par narrativa-vs-bracketed no MESMO documento: `ins` idêntico colado em `@smith2024` e em `[@jones2020]`, mesmo veredito.
- **D3** — página só-narrativa com paper retratado: exit 1. Caso simétrico: `@fulano` fora do bib **não** gera `missing-citekey`.
- **D4** — as 10 chaves reais que hoje falham (`collins2024tripod+ai` etc.) classificam como `citekey`.
- **D6** — `related: ['[ghost](ghost.md)']` emite `dead_link`; `sources:` com título livre **não** emite.
- **D8** — as 4 classes de falso-negativo + regressão (superset estrito) + `CITEKEY_RE.groups == 1`.
- **Estrutural** — `test_mark_in_citation_fragment_emits_non_identity_span_event` é legacy-only por construção (`next(f for f in span_frags if f.kind == 'citation')` levanta `StopIteration` em fixture Pandoc). Não "consertar" via span-map (ver riscos); documentar como legacy-only deliberado.
- **Guarda de pureza** — `test_init_scaffold_is_pandoc_pure` só varre `*.md` e pula `.claude/skills/**`, então não pegaria F7. Alargar para JSON e `templates/modules/**`.

## Sequenciamento sugerido

1. **D1 + D2** (guardas de revisão) — mesma família, mesmos testes, maior severidade.
2. **D4** (I7 + `route.py`) — 5% do acervo real, isolado, PATCH.
3. **D3** (`verify-refs`) — sozinho, porque é o único **breaking** (MINOR).
4. **D5 + D7** (skills e template) — sem código de produção.
5. **D6** (lint bifurcado) — mexe em contagem de issues; isolar para não poluir o diff das guardas.
6. **D8 + D9** (regex e docs) — encerramento.
