# Citação Pandoc de primeira classe — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer todo ponto do código que reconhece, protege, conta ou valida citação tratar as duas gramáticas (Pandoc `[@key]`/`@key` e legado `[[@key]]`), fechando as 8 divergências verificadas na spec `docs/superpowers/specs/2026-07-26-citacao-pandoc-cidada-primeira-classe-design.md`.

**Architecture:** O reconhecedor canônico é `core/citations.py` (Princípio I7). Cada correção substitui um literal/regex legado local por consumo da gramática única — sempre por **união** com o que já existe, nunca por substituição, porque `iter_marked_citation_spans` casa o miolo de `[[@key]]` (1 caractere adentro) e trocar moveria fronteiras de span. Duas restrições atravessam o plano: `CITEKEY_RE` mantém **exatamente 1 grupo de captura** (`review.py` alimenta `Counter` via `findall`), e nenhuma mudança reescreve conteúdo legado existente.

**Tech Stack:** Python 3.13, `uv`, pytest, mypy --strict, ruff, Typer, Pydantic v1 schemas versionados.

## Global Constraints

- **Baseline verde antes de começar:** 782 testes, `mypy --strict` limpo em 161 arquivos, `ruff check` + `ruff format --check` limpos.
- **Bateria completa antes de CADA commit:** `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy`. Nas tasks que tocam `skills/` ou `docs/`, também `uv run python .github/scripts/gen_indexes.py --check`.
- **`CITEKEY_RE.groups == 1` é inegociável.** `review.py` usa `CITEKEY_RE.findall(...)` para alimentar `Counter`; com 2+ grupos, `findall` devolve tuplas e o multiconjunto compara lixo **silenciosamente**. Alargar só com grupos não-capturantes `(?:...)`.
- **Nunca substituir `_PROPOSAL_CITATION_SPAN_RE` por `iter_marked_citation_spans`** — só unir. A primeira dá o span EXTERNO do legado; a segunda casa o miolo.
- **Não mexer no span-map** (`core.obsidian.normalize_markdown_with_map`): fazer emitir `kind="citation"` para Pandoc fatiaria toda prosa hoje contida num único fragment `identity`.
- **Não alargar `scan_marked_citekeys`** em `core/citations.py` para resolver o `verify-refs`: o contrato conservador é consumido por 2 domínios e `domains/wiki/lint.py:86` depende dele. Corrigir no call site.
- **Layering:** `core/` NUNCA importa de `domains/`. Docstrings e mensagens de usuário em pt-BR com comando de correção embutido; identificadores em inglês.
- **Nenhuma migração de conteúdo legado.** As 231 ocorrências de `[[@` no repo continuam válidas como fixture e leitura (decisão 5 do spec 2026-07-22).
- **`from __future__ import annotations`** em todo módulo novo/tocado.

## File Structure

| Arquivo | Responsabilidade | Tasks |
|---|---|---|
| `src/prumo_assist/core/citations.py` | Gramática única. Ganha `CITEKEY_BODY` (corpo compartilhado) e `iter_narrative_citation_spans` | 2, 3, 7 |
| `src/prumo_assist/domains/write/review.py` | Guardas I1/I3b. Terceira checagem de conservação + narrativa no átomo | 1, 2 |
| `src/prumo_assist/domains/capture/route.py` | Roteador heurístico. Passa a derivar de `CITEKEY_BODY` | 3 |
| `src/prumo_assist/domains/paper/verify.py` | `verify_refs`. Duas varreduras + achado `empty-page-scope` | 4 |
| `src/prumo_assist/domains/wiki/lint.py` | `_check_dead_frontmatter_links` bifurcada | 6 |
| `skills/paper-manager/SKILL.md`, `skills/wiki-lint/SKILL.md` | Buscas embutidas | 5 |
| `templates/modules/clinical/docs/templates/data_dictionary_skeleton.md` | `[[citekey]]` → `[@citekey]`, célula a célula | 5 |
| `src/prumo_assist/domains/write/zettlr.py` + specs | Docstrings com fato invertido | 8 |

---

### Task 1: Terceira checagem de conservação de citação (D1)

Fecha F1: agente compõe citação em Pandoc inserindo só `[`, e as duas sub-checagens existentes passam.

**Files:**
- Modify: `src/prumo_assist/domains/write/review.py:3108-3144` (`_reject_citation_divergence`)
- Test: `tests/unit/write/test_review_apply.py`

**Interfaces:**
- Consumes: `_citation_atom_spans(body: str) -> Iterator[tuple[int, int]]` (já existe, `review.py:3190`); `_reject_composed_result(detail: str) -> NoReturn` (`review.py:3095`)
- Produces: nada novo exportado. `_reject_citation_divergence(before_text: str, after_text: str) -> None` mantém a assinatura.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar ao fim de `tests/unit/write/test_review_apply.py`:

```python
# --- 24. composição de citação em sintaxe Pandoc -> recusa (D1) -------------


def test_propose_prose_edit_rejects_pandoc_composition_that_fabricates_citation(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """Par Pandoc de `test_..._rejects_composition_that_fabricates_citation`.

    O agente insere só `[` para embrulhar a narrativa `@fake2020` num grupo
    `[@fake2020]` — citação que humano nenhum cunhou. As duas sub-checagens
    antigas passam (spans legados `[]`→`[]`; multiconjunto `CITEKEY_RE`
    `{fake2020:1}`→`{fake2020:1}`), então só a terceira recusa.
    """
    page_body = "Prefixo @fake2020] sufixo."
    project_root, page = init_project(body=page_body)
    review_dir = write_review_artifacts(project_root, page, review_md=page_body)

    with pytest.raises(ValueError) as exc:
        propose_prose_edit(
            page=page,
            anchor_excerpt="Prefixo ",
            position="after",
            kind="ins",
            b="[",
            project_root=project_root,
        )

    assert "citaç" in str(exc.value).lower()
    assert (review_dir / "review.md").read_text() == page_body
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/write/test_review_apply.py::test_propose_prose_edit_rejects_pandoc_composition_that_fabricates_citation -q`
Expected: FAIL com `DID NOT RAISE <class 'ValueError'>` (a proposta é aceita hoje).

- [ ] **Step 3: Implementar a terceira checagem**

Em `review.py`, dentro de `_reject_citation_divergence`, **depois** do bloco `before_keys`/`after_keys` (mantendo os dois existentes intactos):

```python
    before_spans = Counter(before_text[s:e] for s, e in _citation_atom_spans(before_text))
    after_spans = Counter(after_text[s:e] for s, e in _citation_atom_spans(after_text))
    if before_spans != after_spans:
        _reject_composed_result(
            "o multiconjunto de GRUPOS de citação (gramática única de "
            "`core.citations`, as duas sintaxes) mudou entre antes e depois "
            f"da composição — antes: {dict(before_spans)}, depois: {dict(after_spans)}"
        )
```

Comparar **textos** de span (não contagens) é o que torna a sobreposição
legado-externo + Pandoc-interno inofensiva: as duas fontes contribuem o mesmo
texto nos dois lados, então só uma diferença real diverge.

- [ ] **Step 4: Atualizar a docstring (hoje mente)**

Em `_reject_citation_divergence`, trocar a frase
`(i) `[[@chave]]` marcadas (`_PROPOSAL_CITATION_SPAN_RE`); (ii) citekeys crus (`CITEKEY_RE`, a mesma gramática de `core.citations`).`
por:

```
    (i) ``[[@chave]]`` marcadas (``_PROPOSAL_CITATION_SPAN_RE``, span externo
    do legado); (ii) citekeys crus (``CITEKEY_RE``); (iii) GRUPOS de citação
    nas duas gramáticas (``_citation_atom_spans``). A (iii) existe porque as
    duas primeiras são cegas à composição em sintaxe Pandoc: embrulhar
    ``@key`` em ``[@key]`` não muda span legado nem multiconjunto de chave —
    só o conjunto de grupos marcados.
```

- [ ] **Step 5: Rodar o teste novo e a suíte**

Run: `uv run pytest tests/unit/write/test_review_apply.py -q`
Expected: PASS, 26 passed (25 antigos + 1 novo).

- [ ] **Step 6: Teste de não-regressão do falso positivo do colchete**

O risco registrado na spec: colchete solto em prosa distante re-segmenta o corpo. Acrescentar:

```python
# --- 25. colchete legítimo longe de citação NÃO é "citação fabricada" ------


def test_propose_prose_edit_allows_bracket_far_from_citation(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """Guarda D1 compara grupos de citação, não colchetes: `[sic]` num
    parágrafo que tem `[@k2020]` noutro ponto é edição legítima de prosa."""
    page_body = "Primeira frase com [@k2020] aqui. Segunda frase separada."
    project_root, page = init_project(body=page_body)
    write_review_artifacts(project_root, page, review_md=page_body)

    propose_prose_edit(
        page=page,
        anchor_excerpt="Segunda frase",
        position="after",
        kind="ins",
        b=" [sic]",
        project_root=project_root,
    )
```

Run: `uv run pytest tests/unit/write/test_review_apply.py -q`
Expected: PASS. Se falhar, a checagem está sensível demais — reveja o Step 3 antes de seguir.

- [ ] **Step 7: Bateria completa e commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy
git add src/prumo_assist/domains/write/review.py tests/unit/write/test_review_apply.py
git commit -m "fix(write): conservação de citação enxerga composição em sintaxe Pandoc

As duas sub-checagens de \`_reject_citation_divergence\` são cegas à gramática
mandatória: embrulhar \`@key\` em \`[@key]\` não muda o span legado nem o
multiconjunto de \`CITEKEY_RE\`. Terceira checagem compara o multiconjunto de
GRUPOS de citação via \`_citation_atom_spans\` (as duas gramáticas).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Citação narrativa entra no átomo protegido (D2)

Fecha F2: o fix `813d230` cobriu bracketed e deixou `@key` narrativa de fora — ali a edição do agente **chega à página**.

**Files:**
- Modify: `src/prumo_assist/core/citations.py` (nova função pública)
- Modify: `src/prumo_assist/domains/write/review.py:3190-3211` (`_citation_atom_spans`)
- Test: `tests/unit/core/test_citations.py`, `tests/unit/write/test_review_apply.py`

**Interfaces:**
- Consumes: `CITEKEY_RE`, `iter_marked_citation_spans` de `core/citations.py`
- Produces: `iter_narrative_citation_spans(text: str) -> Iterator[tuple[int, int]]` em `core/citations.py` — devolve `match.span()` (span do match INTEIRO, começando no `@`), pulando matches já contidos num span marcado.

- [ ] **Step 1: Escrever o teste que falha (core)**

Acrescentar a `tests/unit/core/test_citations.py`:

```python
def test_iter_narrative_citation_spans_cobre_narrativa_e_pula_marcada() -> None:
    text = "Como @smith2024 mostrou, ver tambem [@jones2020]."
    spans = list(iter_narrative_citation_spans(text))
    assert [text[s:e] for s, e in spans] == ["@smith2024"]


def test_iter_narrative_citation_spans_inclui_o_arroba() -> None:
    """O span começa no `@` — usar `match.span(1)` deixaria o `@` desprotegido
    e uma âncora poderia encostar nele."""
    text = "Ver @key2020 aqui."
    (start, end), = iter_narrative_citation_spans(text)
    assert text[start] == "@"
    assert text[start:end] == "@key2020"
```

Acrescentar o import no topo do arquivo de teste:
`from prumo_assist.core.citations import iter_narrative_citation_spans`

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/core/test_citations.py -q`
Expected: FAIL com `ImportError: cannot import name 'iter_narrative_citation_spans'`.

- [ ] **Step 3: Implementar em `core/citations.py`**

Depois de `iter_marked_citation_spans`:

```python
def iter_narrative_citation_spans(text: str) -> Iterator[tuple[int, int]]:
    """Spans ``(start, end)`` das citações NARRATIVAS (``@key`` solta) de ``text``.

    Complementa :func:`iter_marked_citation_spans`: devolve só os matches que
    NÃO estão dentro de um grupo marcado. O span começa no ``@`` (span do
    match inteiro, nunca ``span(1)``) — quem protege citação como átomo
    precisa do sigilo dentro do intervalo.

    Captura AMPLA por construção (``CITEKEY_RE``): ``@fulano`` em prosa entra.
    Consumidor que não tolere falso positivo deve filtrar (ver docstring do
    módulo); num guard de hard-fail o custo do falso positivo é trabalho
    manual, o do falso negativo é edição silenciosa de citação.
    """
    marked = list(iter_marked_citation_spans(text))
    for match in CITEKEY_RE.finditer(text):
        start, end = match.span()
        if any(ms <= start and end <= me for ms, me in marked):
            continue
        yield start, end
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/core/test_citations.py -q`
Expected: PASS.

- [ ] **Step 5: Escrever o teste que falha (guarda I1)**

Acrescentar a `tests/unit/write/test_review_apply.py`:

```python
# --- 26. Guarda I1 protege narrativa igual a bracketed (D2) ----------------


def test_propose_prose_edit_rejects_anchor_tangent_to_narrative_citation(
    init_project: InitProject, write_review_artifacts: WriteReviewArtifacts
) -> None:
    """Par narrativa-vs-bracketed no MESMO documento: a MESMA edição colada
    no fim de cada átomo tem de ter o MESMO veredito. Antes deste fix, a
    narrativa era aceita e chegava à página."""
    page_body = "Como @smith2024 mostrou, ver tambem [@jones2020]."
    project_root, page = init_project(body=page_body)
    review_dir = write_review_artifacts(project_root, page, review_md=page_body)

    with pytest.raises(ValueError) as exc:
        propose_prose_edit(
            page=page,
            anchor_excerpt="Como @smith2024",
            position="after",
            kind="ins",
            b=" [sic]",
            project_root=project_root,
        )

    assert "I1" in str(exc.value)
    assert (review_dir / "review.md").read_text() == page_body
```

- [ ] **Step 6: Rodar e ver falhar**

Run: `uv run pytest tests/unit/write/test_review_apply.py::test_propose_prose_edit_rejects_anchor_tangent_to_narrative_citation -q`
Expected: FAIL com `DID NOT RAISE`.

- [ ] **Step 7: Unir a terceira fonte em `_citation_atom_spans`**

Em `review.py`, trocar o import da linha 53 para incluir a função nova:

```python
from prumo_assist.core.citations import (
    CITEKEY_RE,
    iter_marked_citation_spans,
    iter_narrative_citation_spans,
)
```

e acrescentar ao corpo de `_citation_atom_spans`, depois do `yield from iter_marked_citation_spans(body)`:

```python
    yield from iter_narrative_citation_spans(body)
```

Atualizar a docstring da função para "União de TRÊS fontes", acrescentando o bullet:

```
    - ``iter_narrative_citation_spans`` — cobre ``@key`` narrativa, forma
      legítima da gramática Pandoc que nenhuma das duas primeiras enxerga
      (o legado não tem forma narrativa). Sem ela, a MESMA edição é recusada
      em ``[@k]`` e aplicada em ``@k`` — e nesse caminho chega à página.
```

- [ ] **Step 8: Rodar e ver passar**

Run: `uv run pytest tests/unit/write/test_review_apply.py -q`
Expected: PASS, 28 passed.

- [ ] **Step 9: Medir o custo do falso positivo**

Risco registrado na spec: `CITEKEY_RE` é captura ampla, então `@media`, `@Injectable`, menção a coautor viram átomos intocáveis.

Run: `uv run pytest -q`
Expected: PASS em toda a suíte. **Se algum teste de `test_review_*` passar a falhar por recusa nova, PARE** — significa que o falso positivo mordeu caso legítimo já coberto. Reporte antes de ajustar.

- [ ] **Step 10: Bateria completa e commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy
git add src/prumo_assist/core/citations.py src/prumo_assist/domains/write/review.py tests/unit/core/test_citations.py tests/unit/write/test_review_apply.py
git commit -m "fix(write): Guarda I1 protege citação narrativa \`@key\`

O fix 813d230 uniu legado + bracketed, mas a forma narrativa — legítima e
mandatória na gramática Pandoc — não gerava span protegido. No mesmo
documento, \`ins ' [sic]'\` colado em \`@smith2024\` era ACEITO e chegava à
página, enquanto o mesmo edit em \`[@jones2020]\` era recusado.

\`core/citations.py\` ganha \`iter_narrative_citation_spans\` (span do match
INTEIRO, começando no \`@\`) e \`_citation_atom_spans\` passa a unir as três
fontes.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Fechar o I7 — `CITEKEY_BODY` compartilhado e `route.py` (D4)

Fecha F4: a segunda gramática rejeita **10 de 173 citekeys do acervo real** (5%).

**Files:**
- Modify: `src/prumo_assist/core/citations.py:24-28`
- Modify: `src/prumo_assist/domains/capture/route.py:18` e `:94`
- Test: `tests/unit/capture/test_route.py`, `tests/unit/core/test_citations.py`

**Interfaces:**
- Produces: `CITEKEY_BODY: str` em `core/citations.py` — o corpo do citekey **sem** o `@` e sem lookbehind, para quem precisa ancorar de outro jeito. `CITEKEY_RE` passa a ser construído dele.
- Consumes: `route.py` monta `^@?(CITEKEY_BODY)$`.

**Nota de independência:** esta task usa o corpo **atual**, sem alargamento. Verificado: sozinha ela já leva as 173 chaves reais a `0` falhas. O alargamento é a Task 7 e mexe só no valor de `CITEKEY_BODY`.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar a `tests/unit/capture/test_route.py`:

```python
def test_classify_citekey_com_pontuacao_composta() -> None:
    """Chaves REAIS do acervo do usuário que a 2ª gramática rejeitava.

    `route.py` tinha `^@?([a-z][\\w-]*\\d{4}[\\w-]*)$`, que exige inicial
    minúscula e 4 dígitos — 10 de 173 chaves reais caíam em `unknown`.
    """
    for key in (
        "collins2024tripod+ai",
        "2023attentionbased",
        "benjamind.simon2024future",
        "integrative",
        "smith2020:aha-guideline",
    ):
        assert classify(key).kind == "citekey", key
        assert classify(f"@{key}").kind == "citekey", key
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/capture/test_route.py::test_classify_citekey_com_pontuacao_composta -q`
Expected: FAIL com `AssertionError: collins2024tripod+ai`.

- [ ] **Step 3: Extrair `CITEKEY_BODY` em `core/citations.py`**

Trocar a linha 28 e o comentário acima dela por:

```python
# Corpo do citekey Pandoc, SEM o `@` e sem âncora — compartilhado por quem
# precisa ancorar de outro jeito (ex.: `domains/capture/route.py`, que casa
# um token inteiro). Manter ÚNICO: um segundo reconhecedor divergente é
# exatamente o que o Princípio I7 proíbe.
CITEKEY_BODY = r"[A-Za-z0-9_]\w*(?:[:.#$%&+\-?<>~/]\w+)*"

# Pandoc citation keys: alphanumeric/underscore start, then internal
# `:.#$%&-+?<>~/` punctuation that must be followed by more word chars
# (so we don't grab trailing sentence punctuation like the `.` in
# `[@key].`). Negative lookbehind on `@\w` skips emails (foo@bar).
CITEKEY_RE = re.compile(r"(?<![@\w])@(" + CITEKEY_BODY + r")")
```

- [ ] **Step 4: Travar o contrato de grupo único**

Acrescentar a `tests/unit/core/test_citations.py`:

```python
def test_citekey_re_tem_exatamente_um_grupo_de_captura() -> None:
    """Contrato duro: `review.py` faz `Counter(CITEKEY_RE.findall(...))`, que
    só devolve `list[str]` com UM grupo. Com dois, `findall` devolve tuplas e
    o multiconjunto de conservação passa a comparar lixo SILENCIOSAMENTE."""
    assert CITEKEY_RE.groups == 1
    assert CITEKEY_RE.findall("Cita [@a2020] e [@b2021].") == ["a2020", "b2021"]
```

- [ ] **Step 5: Rodar — o comportamento não pode ter mudado**

Run: `uv run pytest tests/unit/core/ tests/unit/write/ tests/unit/paper/ -q`
Expected: PASS. A extração é pura refatoração; qualquer falha aqui significa que o corpo foi transcrito errado.

- [ ] **Step 6: `route.py` passa a derivar da gramática única**

Em `route.py`, remover a linha 18 e acrescentar, junto aos outros imports:

```python
from prumo_assist.core.citations import CITEKEY_BODY
```

e no lugar da constante antiga:

```python
# Citekey como TOKEN INTEIRO. Deriva de `core.citations.CITEKEY_BODY`
# (Princípio I7 — um único reconhecedor no pacote). Heurística de
# roteamento, não validador: a checagem roda por ÚLTIMO em `classify`,
# depois de PDF/arXiv/DOI/URL, então um DOI nunca cai aqui.
CITEKEY_RE = re.compile(r"^@?(" + CITEKEY_BODY + r")$")
```

A linha 94 (`if CITEKEY_RE.match(s.lstrip("@")):`) continua funcionando sem mudança.

- [ ] **Step 7: Rodar e ver passar**

Run: `uv run pytest tests/unit/capture/test_route.py -q`
Expected: o teste novo PASSA e `test_classify_unknown` **FALHA** — `"randomgarbage"` agora é citekey válida (é um corpo legal). Esperado e desejado.

- [ ] **Step 8: Ajustar o teste de `unknown` (mudança de comportamento deliberada)**

Trocar a fixture de `test_classify_unknown` em `tests/unit/capture/test_route.py`:

```python
def test_classify_unknown() -> None:
    """Palavra nua agora roteia para `citekey` (é um corpo Pandoc legal, e
    `prumo paper find <palavra>` é sugestão inócua e mais útil que "não sei").
    `unknown` fica para o que não é token único."""
    out = classify("not a citekey!!")
    assert out.kind == "unknown"
```

- [ ] **Step 9: Confirmar que a ordem de precedência salva DOI/arXiv**

Run: `uv run pytest tests/unit/capture/test_route.py -q`
Expected: PASS, todos. Confirma que `10.1234/foo` (que casa o corpo de citekey) continua classificado como `doi`, porque a checagem de citekey é a última de `classify`.

- [ ] **Step 10: Corrigir a docstring de `core/citations.py` que hoje mente**

O módulo afirma ser "o ÚNICO lugar do pacote que reconhece citekeys em texto: export, compose, wiki lint e paper graph consomem estas funções". Atualizar a lista de consumidores para incluir os que entraram depois:

```
do pacote que reconhece citekeys em texto (spec 2026-07-22; invariante
I7 do spec 2026-07-05): export, compose, wiki lint, paper graph, paper
verify, write review e capture route consomem estas funções ou o
``CITEKEY_BODY`` — nunca regexes próprios.
```

- [ ] **Step 11: Nota de correção na ADR-0016**

A ADR-0016 afirma que "o tokenizador divergente que descartava chaves compostas foi eliminado" — era falso: `route.py` sobreviveu. ADR aceito é imutável (CLAUDE.md), então acrescentar ao **fim** do arquivo `docs/adr/adr-0016-criticmarkup-conservacao-ooxml.md`:

```markdown

## Nota de correção (2026-07-26)

A afirmação "o tokenizador divergente que descartava chaves compostas foi
eliminado" era incompleta quando esta ADR foi aceita. O escopo declarado do
I7 cobria apenas `domains/write/compose.py`; `domains/capture/route.py:18`
manteve um segundo reconhecedor (`^@?([a-z][\w-]*\d{4}[\w-]*)$`) que rejeitava
10 de 173 citekeys de um acervo real (5%) — chave sem 4 dígitos, com inicial
maiúscula, com `.` ou `+`. Fechado no plano 2026-07-26 (Task 3): `route.py`
passa a derivar de `core.citations.CITEKEY_BODY`. A decisão desta ADR não
muda; só o registro de que o invariante ainda não estava fechado.
```

- [ ] **Step 12: Bateria completa e commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run python .github/scripts/gen_indexes.py --check
git add src/prumo_assist/core/citations.py src/prumo_assist/domains/capture/route.py tests/unit/capture/test_route.py tests/unit/core/test_citations.py docs/adr/adr-0016-criticmarkup-conservacao-ooxml.md
git commit -m "fix(capture): fecha o I7 — route.py deriva da gramática única

\`domains/capture/route.py\` mantinha um segundo reconhecedor de citekey
(\`^@?([a-z][\\\\w-]*\\\\d{4}[\\\\w-]*)\$\`) que exige inicial minúscula e 4 dígitos.
Medido contra os .bib reais de 4 pj_*: rejeitava 10 de 173 chaves (5%) —
\`collins2024tripod+ai\`, \`2023attentionbased\`, \`integrative\`. Efeito visível:
\`prumo capture <chave>\` respondia \"Não consegui detectar o tipo\" para
citekey da própria bibliografia do usuário.

\`core/citations.py\` passa a expor \`CITEKEY_BODY\` e \`CITEKEY_RE\` é construído
dele; \`route.py\` monta \`^@?(CITEKEY_BODY)\$\`. Contrato de grupo único travado
por teste. ⚠ Mudança de comportamento: palavra nua (\`randomgarbage\`) passa a
rotear como citekey em vez de unknown.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: `verify-refs --page` verifica citação narrativa (D3) ⚠ Breaking

Fecha F3: página com citação narrativa sai com exit 0 e "0 verificadas" mesmo com paper **retratado** no acervo.

**Files:**
- Modify: `src/prumo_assist/domains/paper/verify.py:587-601`
- Test: `tests/unit/paper/test_verify.py`

**Interfaces:**
- Consumes: `iter_citekeys` e `scan_marked_citekeys` de `core/citations.py`; `Finding(citekey: str, level: str, kind: str, message: str, source: str)` (`verify.py:212`)
- Produces: novo `kind="empty-page-scope"` com `level="info"` (não altera exit code — só `error` deriva exit 1, ADR-0018).

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar a `tests/unit/paper/test_verify.py`, no nível de módulo (o arquivo
já importa `verify` como módulo, então use `verify._page_scope_citekeys`):

```python
def test_page_scope_cobre_citacao_narrativa() -> None:
    """Citação narrativa (`@key`, sem colchete) tem de entrar no escopo.
    `scan_marked_citekeys` a exclui por contrato, e por isso uma página
    só-narrativa saía com `checked=0` e exit 0 — mesmo com paper retratado."""
    body = "Como @known2020 demonstrou, o efeito existe.\n"

    assert verify._page_scope_citekeys(body, {"known2020"}) == ["known2020"]


def test_page_scope_ignora_handle_de_prosa() -> None:
    """Simétrico: o filtro por `known` é o que torna a captura ampla segura —
    `@fulano` não está no bib e cai fora."""
    body = "Conversei com @fulano sobre @known2020.\n"

    assert verify._page_scope_citekeys(body, {"known2020"}) == ["known2020"]


def test_page_scope_cobre_as_duas_gramaticas_marcadas() -> None:
    body = "Ver [[@legado2019]], [@bracket2020] e @narrativa2021.\n"
    known = {"legado2019", "bracket2020", "narrativa2021"}

    assert sorted(verify._page_scope_citekeys(body, known)) == [
        "bracket2020",
        "legado2019",
        "narrativa2021",
    ]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/paper/test_verify.py -q -k narrativa`
Expected: FAIL com `ImportError: cannot import name '_page_scope_citekeys'`.

- [ ] **Step 3: Extrair o helper em `verify.py`**

Acrescentar antes de `verify_refs`:

```python
def _page_scope_citekeys(body: str, known: set[str]) -> list[str]:
    """Citekeys de ``body`` que existem em ``known``, para o escopo de ``--page``.

    Usa a captura AMPLA (``iter_citekeys``), não a marcada: citação narrativa
    ``@key`` é forma legítima da gramática Pandoc e precisa ser verificada
    contra retratação como qualquer outra. O filtro por ``known`` é o que
    torna a captura ampla segura aqui — ``@fulano`` em prosa não está no bib
    e cai fora.
    """
    return [k for k in iter_citekeys(body) if k in known]
```

E acrescentar `iter_citekeys` ao import de `core.citations` no topo do módulo.

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/paper/test_verify.py -q -k "narrativa or handle"`
Expected: PASS.

- [ ] **Step 5: Ligar o helper no `verify_refs`**

Em `verify_refs`, trocar as duas linhas do bloco `--page`:

```python
        page_body = page.read_text(encoding="utf-8")
        scope = _page_scope_citekeys(page_body, set(by_key))
        page_keys = scan_marked_citekeys(page_body)
```

O `findings.extend(...)` de `missing-citekey` **continua** iterando `page_keys`
(captura marcada): acusar `@fulano` de prosa como "citekey ausente do bib"
seria falso positivo. Só o **escopo de verificação** alarga.

- [ ] **Step 6: Acrescentar o achado `empty-page-scope`**

Logo depois, ainda dentro do `if page is not None:`:

```python
        if not scope:
            findings.append(
                Finding(
                    citekey="-",
                    level="info",
                    kind="empty-page-scope",
                    message=(
                        "nenhuma citação desta página consta do bib — nada foi "
                        "verificado. Confira se a página cita com `[@chave]` ou "
                        "`@chave` e se o bib está sincronizado (`prumo paper sync`)."
                    ),
                    source="local",
                )
            )
```

Isto tira o falso conforto do "✓ 0 referência(s) verificada(s)" sem mudar exit code (`level="info"`).

- [ ] **Step 7: Teste de ponta a ponta pelo `verify_refs` real**

Este vai na classe que já tem `test_escopo_por_pagina_e_missing_citekey`
(`tests/unit/paper/test_verify.py:352`), reusando `self._pj` e `_fake_http` —
o seam de mock dos vizinhos, sem rede:

```python
    def test_escopo_por_pagina_cobre_citacao_narrativa(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Página cuja única citação é narrativa entra no escopo. Antes, o
        `scan_marked_citekeys` a excluía por contrato e a página saía com
        `checked=0` e exit 0 — mesmo com paper retratado no acervo."""
        pj = self._pj(tmp_path)
        pagina = tmp_path / "draft.md"
        pagina.write_text(
            "Como @guan2020clinical demonstrou, o efeito existe.\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify._http_get_json",
            _fake_http(
                {
                    "api.crossref.org/works?filter=updates": _UPDATES_EMPTY,
                    "api.crossref.org/works/": _WORKS_OK,
                }
            ),
        )
        report = verify.verify_refs(pj, page=pagina, cache_path=tmp_path / "c.json")

        assert report["scope"] == ["guan2020clinical"]
        assert report["checked"] == 1
        # narrativa NÃO gera missing-citekey (senão `@fulano` de prosa viraria achado)
        assert [f for f in report["findings"] if f["kind"] == "missing-citekey"] == []

    def test_escopo_vazio_emite_empty_page_scope(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """"0 verificadas" deixa de ser indistinguível de "nada a verificar"."""
        pj = self._pj(tmp_path)
        pagina = tmp_path / "draft.md"
        pagina.write_text("Prosa sem citação nenhuma.\n", encoding="utf-8")
        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify._http_get_json",
            _fake_http({"api.crossref.org/works?filter=updates": _UPDATES_EMPTY}),
        )
        report = verify.verify_refs(pj, page=pagina, cache_path=tmp_path / "c.json")

        assert report["scope"] == []
        kinds = [f["kind"] for f in report["findings"]]
        assert "empty-page-scope" in kinds
        # `info` não deriva exit 1 (gate do ADR-0018)
        assert report["summary"]["errors"] == 0
```

Confira o citekey usado por `self._pj` antes de rodar (`rg "_pj" -A 12 tests/unit/paper/test_verify.py`) — o exemplo acima assume `guan2020clinical` e `semid2024`, os mesmos do teste vizinho.

- [ ] **Step 8: Rodar a suíte de paper**

Run: `uv run pytest tests/unit/paper/ -q`
Expected: PASS. **Se algum teste existente passar a falhar por contagem de `checked`**, é o efeito esperado do escopo maior — atualize a expectativa e registre no CHANGELOG.

- [ ] **Step 9: CHANGELOG com o aviso de breaking**

Em `CHANGELOG.md`, no bloco `## [Não publicado]`, seção `### Corrigido`:

```markdown
- **⚠ Breaking — `prumo paper verify-refs --page` passa a verificar citação
  narrativa.** O escopo vinha de `scan_marked_citekeys`, que exclui `@key`
  solta por contrato: página cujas citações são narrativas saía com
  `checked=0`, exit 0 e "✓ 0 referência(s) verificada(s)" — indistinguível de
  página sem citação, mesmo com paper RETRATADO no acervo. O escopo passa a
  usar a captura ampla filtrada pelo bib (`@fulano` de prosa continua fora), e
  um achado `empty-page-scope` (`info`, não muda exit code) substitui o falso
  conforto. Páginas que hoje passam com exit 0 podem passar a sair com 1 —
  que é o gate correto do ADR-0018.
```

- [ ] **Step 10: Bateria completa e commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy
git add src/prumo_assist/domains/paper/verify.py tests/unit/paper/test_verify.py CHANGELOG.md
git commit -m "fix(paper): verify-refs --page verifica citação narrativa

⚠ Breaking. O escopo de --page vinha de \`scan_marked_citekeys\`, que exclui
\`@key\` narrativa por contrato: página só-narrativa saía com checked=0 e
exit 0 mesmo com paper retratado no acervo — a classe de falso conforto que
a guarda empty-bib existe para impedir.

Escopo passa a usar captura ampla filtrada pelo bib; \`missing-citekey\`
continua na captura marcada (senão \`@fulano\` de prosa viraria achado). Novo
\`empty-page-scope\` (info) distingue \"nada a verificar\" de \"nada verificado\".

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Skills e template clínico (D5 + D7)

Fecha F5 e F7. Sem código de produção — mas `skills/` e `templates/` são force-included no wheel, então **é releasável** (PATCH pré-1.0, ADR-0015).

**Files:**
- Modify: `skills/paper-manager/SKILL.md:178`
- Modify: `skills/wiki-lint/SKILL.md:89`
- Modify: `templates/modules/clinical/docs/templates/data_dictionary_skeleton.md` (linhas 26, 97, 126, 213, 222, 227, 231, 238, 244, 250, 253, 273, 286, 298, 299, 310, 317, 323)
- Test: `tests/unit/test_cli_init.py`

- [ ] **Step 1: Provar o defeito do `paper-manager` antes de mexer**

```bash
mkdir -p /tmp/d5/{pandoc,legado}/references/notes/x
printf -- '---\nid: x\n---\n\nCita [@smith2025review].\n' > /tmp/d5/pandoc/references/notes/x/_meta.md
printf -- '---\nid: x\n---\n\nCita [[@smith2025review]].\n' > /tmp/d5/legado/references/notes/x/_meta.md
rg '\[\[@smith2025review\]\]' /tmp/d5/pandoc/references/notes/ -l || echo "  PANDOC: zero resultados <- o defeito"
rg '\[\[@smith2025review\]\]' /tmp/d5/legado/references/notes/ -l
```

Expected: o projeto Pandoc devolve zero — o agente reportaria "nenhum paper cita este".

- [ ] **Step 2: Corrigir `skills/paper-manager/SKILL.md:178`**

Trocar a linha do passo 2 do comando `graph <citekey>`:

```markdown
2. `rg "@<citekey>\b" references/notes/ -l` (as duas gramáticas: `[@k]`, `@k` e `[[@k]]`) + `rg "^\s*-\s*<citekey>\s*$" references/notes/ -l` (campo `cites:`, que o `_NotaDumper` serializa em bloco) → quem cita este paper.
```

Acrescentar logo abaixo a nota:

```markdown
> O `\b` final evita colisão de prefixo (`@smith2025review` casaria também
> `@smith2025reviewX`). Citekey Pandoc admite `-`, `.`, `:` e `_`, então
> `\b` não é infalível — confira a lista antes de reportar.
```

- [ ] **Step 3: Corrigir `skills/wiki-lint/SKILL.md:89`**

O grep captura o colchete inteiro como se fosse um citekey, então `[@a; @b]` e `[@k, p. 3]` viram falso positivo. Substituir o bloco por delegação ao CLI, que já faz a checagem certa (`domains/wiki/lint.py:86`):

```markdown
Não reimplemente a extração de citekey em grep: `prumo wiki lint` já usa a
gramática única (`core/citations.py`) e reporta `broken_citekey` para as duas
sintaxes, tratando corretamente grupo (`[@a; @b]`) e locator (`[@k, p. 3]`) —
que um grep de colchete inteiro transformaria em falso positivo.
```

- [ ] **Step 4: Migrar o template clínico célula a célula**

Em `templates/modules/clinical/docs/templates/data_dictionary_skeleton.md`, trocar `[[<citekey>]]` → `[@<citekey>]` **apenas** nas células da coluna `Fonte` e no callout "Por que duas camadas".

**NÃO usar find/replace cego:** o mesmo arquivo tem wikilinks de página legítimos (`[[decisions/<ADR>]]`, `[[statistical_analysis_plan]]`, `[[decisions/001_cohort_definition]]`, `spec: "[[<link para spec/ADR>]]"`) que a troca destruiria — `PAGE_LINK_RE` deixaria de contá-los e páginas hoje ligadas passariam a acusar `orphan_page`.

Verificar depois:

```bash
rg '\[\[' templates/modules/clinical/docs/templates/data_dictionary_skeleton.md
```

Expected: só os wikilinks de PÁGINA restam; nenhuma âncora bibliográfica.

- [ ] **Step 5: Alargar a guarda de pureza do scaffold**

`tests/unit/test_cli_init.py::test_init_scaffold_is_pandoc_pure` só varre `*.md` e pula `.claude/skills/**`, então não teria pego o `[[citekey]]` do template clínico. Acrescentar a asserção:

```python
def test_templates_nao_usam_ancora_bibliografica_sem_arroba() -> None:
    """`[[citekey]]` (sem `@`) não é Pandoc nem legado: nenhum consumidor de
    citação a enxerga, e `PAGE_LINK_RE` a confunde com wikilink de página
    (vira `concept_candidate` no lint)."""
    import re
    from prumo_assist.core.paths import resolve_resource

    ofensores: list[str] = []
    for path in resolve_resource("templates").rglob("*.md"):
        for m in re.finditer(r"\[\[([^\]|@#]+)\]\]", path.read_text(encoding="utf-8")):
            alvo = m.group(1)
            if "citekey" in alvo.lower():
                ofensores.append(f"{path}: [[{alvo}]]")
    assert not ofensores, "âncora bibliográfica sem `@`: " + "; ".join(ofensores)
```

`resolve_resource("templates")` é o helper real (`core/paths.py:21`) — verificado:
resolve para `<repo>/templates` no worktree e para `prumo_assist/_templates/` no
wheel instalado.

- [ ] **Step 6: Rodar**

Run: `uv run pytest tests/unit/test_cli_init.py -q && uv run python .github/scripts/gen_indexes.py --check`
Expected: PASS e "tudo em dia".

- [ ] **Step 7: CHANGELOG (efeito que parece regressão)**

```markdown
- Template clínico (`data_dictionary_skeleton.md`) prescrevia `[[citekey]]`
  (sem `@`) como âncora bibliográfica — forma que não é Pandoc nem legada e
  que nenhum consumidor de citação enxerga, enquanto `PAGE_LINK_RE` a
  confundia com wikilink de página. Migrado para `[@citekey]`. Projetos que
  já copiaram o skeleton não são corrigidos pela edição do template, mas
  passam a ter as citekeys VISÍVEIS ao lint: espere `broken_citekey` novos
  onde antes havia silêncio, e o sumiço dos `concept_candidate` com nome de
  citekey.
- Buscas embutidas em `paper-manager` (quem-cita) e `wiki-lint` (citekeys
  quebradas) divergiam da gramática única: a primeira casava zero em nota
  Pandoc (reportando "nenhum paper cita este"), a segunda tratava o colchete
  inteiro como citekey e acusava `[@a; @b]` de quebrada.
```

- [ ] **Step 8: Bateria completa e commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run python .github/scripts/gen_indexes.py --check
git add skills/ templates/ tests/unit/test_cli_init.py CHANGELOG.md
git commit -m "fix(skills): buscas e template clínico falam a gramática mandatória

paper-manager buscava quem-cita só em \`[[@k]]\` (zero resultados em nota
Pandoc, conclusão falsa) e o fallback \`cites:\` estava morto nas duas
gramáticas (YAML é dump em bloco). wiki-lint capturava o colchete inteiro
como citekey, transformando \`[@a; @b]\` e \`[@k, p. 3]\` em falso positivo —
justamente as formas que scientific-writing manda escrever.

Template clínico prescrevia \`[[citekey]]\` sem \`@\`: invisível às duas
gramáticas e confundido com wikilink de página. Migrado célula a célula
(find/replace cego destruiria os wikilinks de página do mesmo arquivo).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: `_check_dead_frontmatter_links` bifurcada (D6)

Fecha F6: link markdown de página em `related:`/`links_to:` não gera `dead_link` — e aqui **não há rede de segurança**.

**Files:**
- Modify: `src/prumo_assist/domains/wiki/lint.py:188-240`
- Test: `tests/unit/wiki/test_lint.py`

**Interfaces:**
- Consumes: `MD_LINK_RE` (`wiki/lint.py:35`, já existe), `scan_marked_citekeys` (`core/citations.py`)
- Produces: `_check_dead_frontmatter_links(texts, pj_path, page_stems, bib_keys) -> list[WikiIssue]` mantém a assinatura.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar a `tests/unit/wiki/test_lint.py`:

Reusa `_setup_wiki` (`tests/unit/wiki/test_lint.py:10`) e o padrão de
`test_lint_flags_dead_frontmatter_links` (`:115`). **Atenção:** a chave do
issue é `code`, não `kind`.

```python
def test_lint_flags_dead_markdown_link_in_frontmatter(tmp_path: Path) -> None:
    """`related:` com link markdown para página inexistente. É a forma que o
    próprio lint.py:33-35 reconhece como esperada em projeto Pandoc-puro, e o
    ramo de página não tem rede de segurança (`scan_marked_citekeys` não
    cobre alvo de página)."""
    pj = _setup_wiki(tmp_path)
    (pj / "docs" / "concepts" / "alpha.md").write_text(
        "---\ntype: concept\n---\n\nbody\n", encoding="utf-8"
    )
    (pj / "docs" / "concepts" / "beta.md").write_text(
        "---\ntype: concept\nrelated:\n  - '[alpha](alpha.md)'\n"
        "  - '[fantasma](ghostpage.md)'\n---\n\n"
        "Links to [[alpha]] so beta is not orphan.\n",
        encoding="utf-8",
    )
    report = lint(pj)
    dead = [i["message"] for i in report["issues"] if i["code"] == "dead_link"]
    assert any("ghostpage" in m for m in dead)
    assert not any("alpha" in m for m in dead)  # existe


def test_lint_nao_acusa_texto_livre_em_sources(tmp_path: Path) -> None:
    """`sources:` recebe string livre (título de paper, URL, nome de
    dataset). Aceitar alvo NU inundaria o relatório."""
    pj = _setup_wiki(tmp_path, "@article{real,title={X}}\n")
    (pj / "docs" / "concepts" / "alpha.md").write_text(
        "---\ntype: concept\n---\n\nbody\n", encoding="utf-8"
    )
    (pj / "docs" / "concepts" / "beta.md").write_text(
        "---\ntype: concept\nsources:\n"
        "  - 'Combinado learning in practice (Nature, 2024)'\n"
        "  - 'https://example.com/artigo'\n---\n\n"
        "Links to [[alpha]] so beta is not orphan.\n",
        encoding="utf-8",
    )
    report = lint(pj)
    dead = [i["message"] for i in report["issues"] if i["code"] == "dead_link"]
    assert dead == []
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/wiki/test_lint.py -q -k "markdown_link or texto_livre"`
Expected: o primeiro FALHA (nenhum `dead_link` emitido), o segundo passa.

- [ ] **Step 3: Bifurcar a função**

A função é **dual-propósito** (citekey **e** página) — substituir o regex mataria o ramo de página em silêncio. Em `wiki/lint.py`, dentro do laço `for raw in value:`, trocar o corpo por:

```python
                texto = str(raw)
                for key in scan_marked_citekeys(texto):
                    if bib_keys and key not in bib_keys:
                        issues.append(
                            WikiIssue(
                                "warning",
                                "dead_link",
                                f"{field}: @{key} ausente do .bib",
                                page=rel,
                            )
                        )
                for alvo in _frontmatter_page_targets(texto):
                    if alvo not in page_stems:
                        issues.append(
                            WikiIssue(
                                "warning",
                                "dead_link",
                                f"{field}: {alvo} não existe no vault",
                                page=rel,
                            )
                        )
```

e acrescentar o helper acima da função:

```python
def _frontmatter_page_targets(value: str) -> Iterator[str]:
    """Alvos de PÁGINA num item de ``links_to``/``sources``/``related``.

    Duas formas: wikilink ``[[pagina]]`` (legado) e link markdown
    ``[texto](pagina.md)`` — a esperada em projeto Pandoc-puro (ver
    ``MD_LINK_RE``, já usado no corpo). Alvo NU não entra de propósito:
    ``sources`` recebe string livre (título de paper, URL, nome de dataset)
    e qualquer não-stem viraria ``dead_link``, inundando o relatório.
    Citekey é responsabilidade do outro ramo — aqui ``@`` é filtrado.
    """
    for match in _WIKILINK_TARGET_RE.finditer(value):
        alvo = match.group(1).strip()
        if not alvo.startswith("@"):
            yield _link_stem(alvo)
    for match in MD_LINK_RE.finditer(value):
        alvo = match.group(1).strip()
        if "://" in alvo:
            continue
        yield _link_stem(alvo)
```

Confirme antes a assinatura real de `_link_stem` (`wiki/lint.py:125`): ela aceita `str | tuple[str, ...]`.

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/wiki/test_lint.py -q`
Expected: PASS.

- [ ] **Step 5: Conferir a contagem de issues**

Risco registrado: mudança em `summary.warnings`/`total` quebra testes que contam issues.

Run: `uv run pytest tests/unit/wiki/ -q`
Expected: PASS. Se algum teste contar issues por número, atualize com o valor novo **e** confira que a diferença é só o que esta task pretendia mudar.

- [ ] **Step 6: Bateria completa e commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy
git add src/prumo_assist/domains/wiki/lint.py tests/unit/wiki/test_lint.py
git commit -m "fix(wiki): dead_link de frontmatter enxerga link markdown de página

\`_check_dead_frontmatter_links\` dependia de \`_WIKILINK_TARGET_RE\` e só via
\`[[pagina]]\`. Em \`related:\`/\`links_to:\` com link markdown — a forma que o
próprio lint reconhece como esperada em projeto Pandoc-puro — nenhum
dead_link era emitido, e aqui não há rede de segurança (scan_marked_citekeys
não cobre alvo de página).

Função BIFURCADA, não substituída: é dual-propósito (citekey e página), e
trocar o regex mataria o ramo de página em silêncio. Alvo nu continua fora —
\`sources:\` recebe string livre.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: Endurecer `CITEKEY_BODY` (D8)

Fecha F8 parcialmente: inicial Unicode e ênfase-underscore. **Robustez, não dor atual** — 0/173 chaves do acervo real caem nessas classes.

**Files:**
- Modify: `src/prumo_assist/core/citations.py` (só o valor de `CITEKEY_BODY` e o lookbehind de `CITEKEY_RE`)
- Test: `tests/unit/core/test_citations.py`

**Interfaces:** nenhuma mudança de assinatura. `CITEKEY_RE.groups` continua `1`.

- [ ] **Step 1: Escrever o teste que falha**

```python
def test_citekey_re_aceita_inicial_unicode() -> None:
    """Pandoc 3.9 aceita e renderiza `@Ünal2024` (verificado contra o binário).
    O regex exigia `[A-Za-z0-9_]` na âncora mas usava `\\w` (Unicode) no resto,
    então `@unÜal2024` passava e `@Ünal2024` sumia — assimetria silenciosa."""
    assert CITEKEY_RE.findall("Cita [@Ünal2024].") == ["Ünal2024"]
    assert CITEKEY_RE.findall("Cita [@ünal2024b].") == ["ünal2024b"]


def test_citekey_re_ve_citacao_em_enfase_underscore() -> None:
    """`_@lima2018 mostrou_` é ASCII puro, caminho default, e o Pandoc trata
    como citação. O lookbehind `(?<![@\\w])` a perdia porque `_` é word char."""
    assert CITEKEY_RE.findall("_@lima2018 mostrou_ isso.") == ["lima2018"]


def test_citekey_re_continua_ignorando_email() -> None:
    assert CITEKEY_RE.findall("mande para foo@bar.com") == []


def test_citekey_re_alargado_e_superset_do_anterior() -> None:
    """Regressão: tudo que a gramática antiga casava, a nova casa igual."""
    amostras = [
        ("Veja [@smith2024cohort] e [@jones2023trial].", ["smith2024cohort", "jones2023trial"]),
        ("narrativa @lee2025core e @Author2015 [p. 123]", ["lee2025core", "Author2015"]),
        ("composta @smith2020:aha-guideline", ["smith2020:aha-guideline"]),
        ("sufixo @key2020. Fim.", ["key2020"]),
        ("@_priv2024 e @2024smith", ["_priv2024", "2024smith"]),
    ]
    for texto, esperado in amostras:
        assert CITEKEY_RE.findall(texto) == esperado, texto
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `uv run pytest tests/unit/core/test_citations.py -q -k "unicode or enfase"`
Expected: FAIL — `[] != ['Ünal2024']`.

- [ ] **Step 3: Alargar**

Em `core/citations.py`, trocar o valor de `CITEKEY_BODY` e o lookbehind:

```python
# Corpo do citekey Pandoc, SEM o `@` e sem âncora. Âncora inicial `\w`
# (Unicode-aware, coerente com o `\w` do resto): o Pandoc aceita citekey
# iniciada por letra não-ASCII — `@Ünal2024`, `@Иванов2020` — e a versão
# ASCII-only criava assimetria silenciosa (`@unÜal2024` passava,
# `@Ünal2024` sumia). Pontuação interna `:.#$%&-+?<>~/` precisa ser
# seguida de word char, para não engolir o `.` final de `[@key].`.
CITEKEY_BODY = r"\w(?:\w|[:.#$%&+\-?<>~/]\w)*"

# Lookbehind: barra e-mail (`foo@bar`) exigindo que o caractere anterior não
# seja letra/dígito. `_` é PERMITIDO antes de propósito — `_@lima2018 mostrou_`
# é ênfase Markdown com citação dentro, ASCII puro e caminho default, e o
# `(?<![@\w])` original a perdia porque `_` é word char.
CITEKEY_RE = re.compile(r"(?<![@0-9A-Za-z])@(" + CITEKEY_BODY + r")")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `uv run pytest tests/unit/core/test_citations.py -q`
Expected: PASS, incluindo `test_citekey_re_tem_exatamente_um_grupo_de_captura` da Task 3.

- [ ] **Step 5: Suíte completa — o alargamento toca 6 consumidores**

Run: `uv run pytest -q`
Expected: PASS. `CITEKEY_RE` alimenta `export`, `compose`, `wiki lint`, `paper graph`, `paper verify` e as guardas de `review` — se algo falhar aqui, o superset não é estrito e o Step 3 precisa voltar.

- [ ] **Step 6: Registrar o que ficou de fora**

Acrescentar à docstring do módulo `core/citations.py`:

```
Fora da cobertura (registrado, não implementado): a forma CHAVEADA
``@{...}`` — recomendada pelo manual do Pandoc para chave com ``://`` —
exigiria um segundo grupo de captura, e ``CITEKEY_RE.findall`` tem contrato
de ``list[str]`` com os consumidores de ``domains/write/review.py``.
```

- [ ] **Step 7: Bateria completa e commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy
git add src/prumo_assist/core/citations.py tests/unit/core/test_citations.py
git commit -m "fix(core): CITEKEY_RE cobre inicial Unicode e ênfase com underscore

Verificado contra pandoc 3.9.0.2: \`@Ünal2024\` e \`_@lima2018 mostrou_\` são
citações que o Pandoc aceita e renderiza, e o regex não via nenhuma das duas.
A âncora era ASCII-only enquanto o resto usava \\w Unicode, então
\`@unÜal2024\` passava e \`@Ünal2024\` sumia.

Superset estrito (regressão coberta por teste) e grupo único preservado —
contrato de \`Counter(CITEKEY_RE.findall(...))\` em review.py.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: Higiene documental (D9)

Corrige afirmações que a verificação empírica derrubou. Sem mudança de comportamento.

**Files:**
- Modify: `src/prumo_assist/domains/write/zettlr.py:7-10` e `:40`
- Modify: `docs/superpowers/specs/2026-07-22-zettlr-front-design.md:53`
- Modify: `src/prumo_assist/domains/wiki/findings.py:41`
- Modify: `src/prumo_assist/mcp_server.py:112`, `src/prumo_assist/domains/write/review.py:3271`, `skills/review-reconcile/SKILL.md:180`
- Test: `tests/unit/write/test_zettlr_profile.py` (só o comentário)

- [ ] **Step 1: Reproduzir o fato antes de escrever a correção**

```bash
cd /tmp && mkdir -p d9 && cd d9
printf '@article{k1, title={T}, author={A, B}, year={2001}, journal={J}}\n' > r.bib
printf 'Cita [@k1].\n' > p.md
printf 'function Cite(c)\n  io.stderr:write(">>> Lua vê: " .. pandoc.utils.stringify(c.content) .. "\\n")\nend\n' > probe.lua
printf 'bibliography: r.bib\nciteproc: true\nfilters: [probe.lua]\n' > d.yaml
pandoc p.md -d d.yaml -t plain 2>&1 >/dev/null
```

Expected: `>>> Lua vê: (A 2001)` — o citeproc rodou **ANTES**, ao contrário do que a docstring afirma.

- [ ] **Step 2: Corrigir a docstring do módulo `zettlr.py`**

Trocar as linhas 7-10 (`ATENÇÃO: num defaults file, ``citeproc: true`` rodaria o citeproc DEPOIS dos lua filters e quebraria o filtro — por isso o citeproc entra como item da lista ``filters``, na frente.`) por:

```
o citeproc entra como item da lista ``filters`` porque só a ordem DENTRO de
``filters:`` é garantida pelo manual do Pandoc ("Filters are run in the order
specified"). ``citeproc: true`` não oferece controle de ordem — na prática é
prependado à cadeia (verificado com filtro-sonda em pandoc 3.9.0.2: o Lua
recebe ``(Autor 2001)``, ou seja o citeproc já rodou), mas isso é detalhe de
implementação não documentado. NUNCA declarar os dois juntos: o citeproc roda
duas vezes e a bibliografia sai duplicada.
```

- [ ] **Step 3: Corrigir a precedência de `bibliography`**

Reproduzir primeiro:

```bash
cd /tmp/d9
printf '@article{k1, title={VEIO DO FRONTMATTER}, author={F, A}, year={2001}, journal={J}}\n' > A.bib
printf '@article{k1, title={VEIO DO DEFAULTS}, author={D, B}, year={2002}, journal={J}}\n' > B.bib
printf -- '---\nbibliography: A.bib\n---\n\nCita [@k1].\n' > pp.md
printf 'bibliography: B.bib\n' > db.yaml
pandoc pp.md -d db.yaml --citeproc -t plain | head -2
```

Expected: `(D 2002)` — o defaults file **vence**.

Em `zettlr.py:40`, trocar `` ``bibliography`` não entra aqui: viaja no frontmatter de cada draft, que tem precedência sobre o defaults file.`` por:

```
``bibliography`` não entra aqui: viaja no frontmatter de cada draft. ATENÇÃO
à precedência real — ``bibliography`` num defaults file equivale a
``--bibliography`` e SOBRESCREVE o metadata do documento (verificado com dois
.bib conflitantes). O frontmatter do draft só prevalece enquanto o campo
"Citation database" das preferências do Zettlr estiver VAZIO: o exporter do
Zettlr injeta a biblioteca global em qualquer defaults file importado.
```

- [ ] **Step 4: Corrigir o spec do Zettlr front**

Em `docs/superpowers/specs/2026-07-22-zettlr-front-design.md:53`, trocar `e frontmatter tem precedência sobre defaults file` por:

```
e o frontmatter só prevalece enquanto Citation Database e CSL globais do
Zettlr estiverem vazios — a precedência do Pandoc é a INVERSA (defaults file
= `--bibliography`/`--csl`, sobrescreve metadata do documento), e o exporter
do Zettlr injeta os globais em qualquer defaults file importado. **Correção
de fato registrada em 2026-07-26**; a decisão do spec não muda.
```

- [ ] **Step 5: Corrigir o comentário do teste do perfil**

Em `tests/unit/write/test_zettlr_profile.py`, o comentário de `test_profile_runs_citeproc_before_lua_filter` afirma o mesmo fato invertido. A **asserção continua válida** — trocar só o comentário para "a lista é usada porque é o único mecanismo com ordem garantida pelo manual, não porque `citeproc: true` rodaria depois".

- [ ] **Step 6: Corrigir a docstring de `sources` em `findings.py:41`**

```
    ``sources`` é lista de âncoras: citação (``"[@key]"`` Pandoc ou
    ``"[[@key]]"`` legado) ou página (``"[[page]]"``, ``"[texto](page.md)"``).
```

- [ ] **Step 7: Alinhar as superfícies que o agente lê**

Em `mcp_server.py:112`, `review.py:3271` e `skills/review-reconcile/SKILL.md:180`, as guardas são descritas só na gramática legada. **Sem efeito em runtime** (verificado: comportamento simétrico), mas é a única menção de sintaxe que o agente vê. Trocar `` `[[@key]]` `` por `` citação (`[@key]`, `@key` ou `[[@key]]`) `` nos três.

Atenção: `mcp_server.py:112` é **contrato publicado** — clientes MCP leem essa description. Mudança de texto é segura; mudança de nome/assinatura não.

- [ ] **Step 8: Bateria completa e commit**

```bash
uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy
uv run python .github/scripts/gen_indexes.py --check
git add src/ docs/ skills/ tests/
git commit -m "docs: corrige fatos invertidos sobre citeproc e precedência de bibliography

Dois fatos afirmados no código e no spec foram derrubados por verificação
empírica contra pandoc 3.9.0.2:

- \`citeproc: true\` num defaults file roda o citeproc ANTES dos filtros Lua,
  não depois (filtro-sonda: o Lua recebe \`(Autor 2001)\`). A decisão do código
  está certa — só a lista \`filters\` tem ordem garantida pelo manual — mas a
  justificativa escrita estava invertida.
- \`bibliography\` de defaults file SOBRESCREVE o do frontmatter (testado com
  dois .bib conflitantes), o inverso do que zettlr.py e o spec afirmavam.

Também alinha as superfícies que o agente lê (description MCP, docstring de
propose_prose_edit, SKILL de review-reconcile), que descreviam as guardas só
na gramática legada — sem efeito em runtime desde 813d230.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Verificação final

- [ ] `uv run pytest` — 782 + ~14 testes novos, todos verdes
- [ ] `uv run mypy` — limpo
- [ ] `uv run ruff check . && uv run ruff format --check .` — limpo
- [ ] `uv run python .github/scripts/gen_indexes.py --check` — tudo em dia
- [ ] Repro da spec fechadas: rodar os snippets de F1, F2, F3 e F4 e confirmar que o comportamento Pandoc agora **iguala** o legado
- [ ] CHANGELOG com o "⚠ Breaking" da Task 4 e as notas de efeito-que-parece-regressão da Task 5
- [ ] Mover este plano para `docs/superpowers/plans/archive/` com frontmatter `status: implemented` + `verified` + `release`
