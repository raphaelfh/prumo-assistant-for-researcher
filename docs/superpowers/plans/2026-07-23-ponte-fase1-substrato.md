# Ponte docx↔CriticMarkup — Fase 1: substrato — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar o substrato da ponte: `core/criticmarkup.py` (parse/emit/accept/reject das 5 marcas), span-map lossless no `normalize_markdown`, citemap/occ_id/fingerprint no export docx (sidecars em `reviews/<slug>/`, I8), campos de citação travados (I4) e gramática única de citekey (I7).

**Architecture:** O normalizador vira um **motor de edits de passada única** (regras coletam `(start, end, replacement, kind)` sobre o texto-fonte, aplicadas L→R uma vez) — o mapa norm↔source sai de graça da aritmética de offsets, e o comportamento textual permanece idêntico (testes existentes de `test_obsidian.py` são o contrato de paridade). O citemap é construído **lendo o OOXML do docx gerado** (método I2 — nunca da saída do pandoc), pareado 1:1 em ordem de documento com as citações do texto normalizado; mismatch → hard-fail. Fingerprints são computados em Python (lua só carimba o que o lookup file entrega); `occ_id` nasce no lua (contador próprio no payload). Campos travados via `w:sdt` + `sdtContentLocked` com guarda pós-build própria.

**Tech Stack:** Python 3.11 stdlib + Pydantic (schemas v1), pandoc 3.9 (spike-grade p/ lua), pytest com fixtures zip (padrão de `test_export_docx_validation.py`).

**Spec:** `docs/superpowers/specs/2026-07-05-review-docx-criticmarkup-design.md` (seções "O substrato CriticMarkup", "Export instrumentado", I1–I8; Fase 1 da tabela). Decisão da Fase 0: backend (b) — citação sempre via OOXML próprio.

## Global Constraints

- Release boundary: **MINOR** (export ganha sidecars) — sem release neste plano; CHANGELOG em "Não publicado".
- `mypy --strict` limpo; `from __future__ import annotations`; mensagens pt-BR com comando de correção; identificadores em inglês.
- Layering: `core/criticmarkup.py` NÃO importa de `domains/` (nível-formato puro). `domains/write` importa core.
- Schemas: só ADIÇÕES em `domains/write/schemas/v1.py` (forward-only; nunca remover/renomear campo).
- Paridade de comportamento do normalizador: **todos os testes existentes de `tests/unit/core/test_obsidian.py` passam sem edição** (exceto se um teste assertar detalhe interno como `_protect_code`; nesse caso o ajuste é relatado como desvio).
- Conservação/citemap SEMPRE do OOXML (`word/document.xml`), nunca de stdout do pandoc.
- adeu não participa desta fase.
- Fixtures docx sintéticas com `zipfile` (reusar o padrão `_write_minimal_docx` de `tests/unit/write/test_export_docx_validation.py` — copiar o helper localmente se precisar de campos completos, não importar entre arquivos de teste).
- `uv run pytest` completo verde antes de cada commit (441 hoje; cresce a cada task); `ruff check`/`format --check`; commits convencionais com escopo.
- Verificações spike-grade com pandoc real (lua) rodam em `mktemp -d`; evidência no report da task, artefatos fora do repo.

**Decisões de plano (fecham perguntas abertas do spec):**
- **Pergunta 3 (travamento):** `w:sdt` com `<w:lock w:val="sdtContentLocked"/>` envolvendo os runs do campo (content control), NÃO bookmark — bookmarks não bloqueiam edição. Risco Zotero-Refresh registrado; smoke manual do dono no Word fica como checkbox final não-bloqueante.
- **Pergunta 4 (sidecars):** `reviews/<slug>/` na raiz do projeto consumidor (irmão de `build/`), slug = mesmo `_slugify` do export.
- **occ_id:** gerado no lua (`prumoOcc` = contador `%08d` próprio, independente do `citationID` que o plugin Word pode reescrever); melhor-esforço documentado — se um Refresh do Zotero descartar chaves custom, a conservação degrada para o multiconjunto de citekeys (núcleo do I2), sem quebrar.
- **fingerprint:** por chave, computado em Python: `doi:<valor>` quando o `.bib` tem campo `doi`; senão `sha256:<hex>` de `itemID|uri` do BBT; senão `bib:<sha256 do entry>` (offline). Viaja no lookup file e o lua carimba `prumoFingerprint` no item.

---

### Task 1: `core/criticmarkup.py` — parse e emit das 5 marcas

**Files:**
- Create: `src/prumo_assist/core/criticmarkup.py`
- Test: Create `tests/unit/core/test_criticmarkup.py`

**Interfaces:**
- Produces (consumido pelas Tasks 2 e pela Fase 2 da ponte):

```python
@dataclass(frozen=True)
class Mark:
    kind: Literal["ins", "del", "sub", "highlight", "comment"]
    start: int          # offset no texto COM marcas
    end: int            # fim exclusivo (após a marca inteira)
    a: str              # del/sub: texto removido; highlight: texto; comment/ins: ""
    b: str              # ins/sub: texto inserido; comment: corpo; demais: ""

def parse(text: str) -> list[Mark]: ...
def emit(kind: str, a: str = "", b: str = "") -> str: ...
```

- [ ] **Step 1: Write the failing tests**

Criar `tests/unit/core/test_criticmarkup.py`:

```python
"""Parse/emit das 5 marcas CriticMarkup (substrato da ponte docx↔CriticMarkup)."""

from __future__ import annotations

import pytest

from prumo_assist.core.criticmarkup import Mark, emit, parse


def test_parse_insertion() -> None:
    marks = parse("antes {++novo texto++} depois")
    assert marks == [Mark(kind="ins", start=6, end=22, a="", b="novo texto")]


def test_parse_deletion() -> None:
    marks = parse("a {--removido--} b")
    assert marks == [Mark(kind="del", start=2, end=16, a="removido", b="")]


def test_parse_substitution() -> None:
    marks = parse("x {~~velho~>novo~~} y")
    assert marks == [Mark(kind="sub", start=2, end=19, a="velho", b="novo")]


def test_parse_highlight_and_comment() -> None:
    marks = parse("{==destaque==}{>>um comentário<<}")
    assert marks == [
        Mark(kind="highlight", start=0, end=14, a="destaque", b=""),
        Mark(kind="comment", start=14, end=33, a="", b="um comentário"),
    ]


def test_parse_multiline_mark() -> None:
    marks = parse("a {++linha1\nlinha2++} b")
    assert marks[0].b == "linha1\nlinha2"


def test_parse_empty_text_no_marks() -> None:
    assert parse("texto sem marcas") == []


def test_parse_unclosed_mark_raises() -> None:
    with pytest.raises(ValueError, match="marca CriticMarkup não fechada"):
        parse("a {++aberta sem fim")


def test_parse_nested_mark_raises() -> None:
    with pytest.raises(ValueError, match="marcas CriticMarkup aninhadas"):
        parse("{++fora {--dentro--} fim++}")


def test_emit_all_kinds() -> None:
    assert emit("ins", b="x") == "{++x++}"
    assert emit("del", a="x") == "{--x--}"
    assert emit("sub", a="a", b="b") == "{~~a~>b~~}"
    assert emit("highlight", a="x") == "{==x==}"
    assert emit("comment", b="c") == "{>>c<<}"


def test_emit_unknown_kind_raises() -> None:
    with pytest.raises(ValueError, match="kind desconhecido"):
        emit("bogus", a="x")


def test_parse_emit_roundtrip() -> None:
    text = "a " + emit("del", a="x") + emit("ins", b="y") + " b"
    kinds = [m.kind for m in parse(text)]
    assert kinds == ["del", "ins"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/core/test_criticmarkup.py -v`
Expected: FAIL na coleta — `ModuleNotFoundError: No module named 'prumo_assist.core.criticmarkup'`

- [ ] **Step 3: Write the implementation**

Criar `src/prumo_assist/core/criticmarkup.py`:

```python
"""CriticMarkup — parse/emit/accept/reject das 5 marcas.

Substrato da ponte docx↔CriticMarkup (spec 2026-07-05): a camada de revisão
vive inline no ``.md`` como marcas planas (nunca aninhadas). Nível-formato
puro — este módulo NÃO importa de ``domains/``.

Marcas: ``{++ins++}`` ``{--del--}`` ``{~~a~>b~~}`` ``{==destaque==}``
``{>>comentário<<}``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

MarkKind = Literal["ins", "del", "sub", "highlight", "comment"]

_OPENERS: dict[str, MarkKind] = {
    "{++": "ins",
    "{--": "del",
    "{~~": "sub",
    "{==": "highlight",
    "{>>": "comment",
}
_CLOSERS: dict[MarkKind, str] = {
    "ins": "++}",
    "del": "--}",
    "sub": "~~}",
    "highlight": "==}",
    "comment": "<<}",
}
_OPEN_RE = re.compile(r"\{(\+\+|--|~~|==|>>)")


@dataclass(frozen=True)
class Mark:
    """Uma marca CriticMarkup localizada no texto (offsets no texto COM marcas)."""

    kind: MarkKind
    start: int
    end: int
    a: str
    b: str


def parse(text: str) -> list[Mark]:
    """Extrai as marcas planas de ``text``.

    Marcas aninhadas ou não fechadas são erro (o transplante nunca as
    produz — spec: "o parser só vê marcas planas").
    """
    marks: list[Mark] = []
    pos = 0
    while True:
        m = _OPEN_RE.search(text, pos)
        if not m:
            return marks
        opener = m.group(0)
        kind = _OPENERS[opener]
        closer = _CLOSERS[kind]
        body_start = m.end()
        close_at = text.find(closer, body_start)
        if close_at == -1:
            raise ValueError(
                f"marca CriticMarkup não fechada em offset {m.start()}: "
                f"esperava {closer!r}. Corrija a marca ou remova-a."
            )
        body = text[body_start:close_at]
        if _OPEN_RE.search(body):
            raise ValueError(
                f"marcas CriticMarkup aninhadas em offset {m.start()} — "
                "não suportado; resolva o cluster antes (spec: marcas planas)."
            )
        if kind == "sub":
            sep = body.find("~>")
            if sep == -1:
                raise ValueError(
                    f"substituição sem separador '~>' em offset {m.start()}."
                )
            a, b = body[:sep], body[sep + 2 :]
        elif kind in ("del", "highlight"):
            a, b = body, ""
        else:  # ins, comment
            a, b = "", body
        marks.append(Mark(kind=kind, start=m.start(), end=close_at + len(closer), a=a, b=b))
        pos = close_at + len(closer)


def emit(kind: str, a: str = "", b: str = "") -> str:
    """Serializa uma marca. ``a``/``b`` seguem a semântica de :class:`Mark`."""
    if kind == "ins":
        return "{++" + b + "++}"
    if kind == "del":
        return "{--" + a + "--}"
    if kind == "sub":
        return "{~~" + a + "~>" + b + "~~}"
    if kind == "highlight":
        return "{==" + a + "==}"
    if kind == "comment":
        return "{>>" + b + "<<}"
    raise ValueError(f"kind desconhecido: {kind!r} (use ins|del|sub|highlight|comment)")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/core/test_criticmarkup.py -v`
Expected: 11 passed

- [ ] **Step 5: Battery + commit**

Run: `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy`

```bash
git add src/prumo_assist/core/criticmarkup.py tests/unit/core/test_criticmarkup.py
git commit -m "feat(core): criticmarkup — parse e emit das 5 marcas (substrato da ponte)"
```

---

### Task 2: `accept`/`reject` com semântica por marca

**Files:**
- Modify: `src/prumo_assist/core/criticmarkup.py`
- Test: Modify `tests/unit/core/test_criticmarkup.py` (append)

**Interfaces:**
- Produces: `accept(text: str) -> str` e `reject(text: str) -> str` (aplicam TODAS as marcas); `apply(text: str, decisions: dict[int, bool]) -> str` (por marca: chave = índice na ordem de `parse`, `True`=aceitar, `False`=rejeitar; marca sem decisão permanece intacta).
- Semântica: aceitar — ins→`b`, del→`""`, sub→`b`, highlight→`a` (vira texto), comment→`""`; rejeitar — ins→`""`, del→`a`, sub→`a`, highlight→`a`, comment→`""` (comentário some nos dois casos — o conteúdo vive no sidecar, spec "Comentários").

- [ ] **Step 1: Write the failing tests**

Append em `tests/unit/core/test_criticmarkup.py`:

```python
from prumo_assist.core.criticmarkup import accept, apply, reject


def test_accept_all_kinds() -> None:
    text = "a {++X++} b {--Y--} c {~~v~>n~~} d {==H==} e {>>C<<} f"
    assert accept(text) == "a X b  c n d H e  f"


def test_reject_all_kinds() -> None:
    text = "a {++X++} b {--Y--} c {~~v~>n~~} d {==H==} e {>>C<<} f"
    assert reject(text) == "a  b Y c v d H e  f"


def test_apply_per_mark_decisions() -> None:
    text = "{--um--} {++dois++} {~~a~>b~~}"
    out = apply(text, {0: False, 1: True, 2: True})
    assert out == "um dois b"


def test_apply_partial_keeps_undecided_marks() -> None:
    text = "{--um--} {++dois++}"
    out = apply(text, {0: True})
    assert out == " {++dois++}"


def test_accept_idempotent_on_clean_text() -> None:
    assert accept("sem marcas") == "sem marcas"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/core/test_criticmarkup.py -v`
Expected: FAIL na coleta — `ImportError: cannot import name 'accept'`

- [ ] **Step 3: Write the implementation**

Append em `criticmarkup.py`:

```python
def _resolve(mark: Mark, accepted: bool) -> str:
    if mark.kind == "ins":
        return mark.b if accepted else ""
    if mark.kind == "del":
        return "" if accepted else mark.a
    if mark.kind == "sub":
        return mark.b if accepted else mark.a
    if mark.kind == "highlight":
        return mark.a
    return ""  # comment: some nos dois casos; conteúdo vive no sidecar


def apply(text: str, decisions: dict[int, bool]) -> str:
    """Aplica decisões por marca (índice na ordem de :func:`parse`).

    Marca sem decisão permanece intacta no texto de saída.
    """
    marks = parse(text)
    out: list[str] = []
    cursor = 0
    for i, mark in enumerate(marks):
        out.append(text[cursor : mark.start])
        if i in decisions:
            out.append(_resolve(mark, decisions[i]))
        else:
            out.append(text[mark.start : mark.end])
        cursor = mark.end
    out.append(text[cursor:])
    return "".join(out)


def accept(text: str) -> str:
    """Aceita todas as marcas."""
    return apply(text, dict.fromkeys(range(len(parse(text))), True))


def reject(text: str) -> str:
    """Rejeita todas as marcas."""
    return apply(text, dict.fromkeys(range(len(parse(text))), False))
```

- [ ] **Step 4: Run + battery + commit**

Run: `uv run pytest tests/unit/core/test_criticmarkup.py -v` → 16 passed; bateria completa.

```bash
git add src/prumo_assist/core/criticmarkup.py tests/unit/core/test_criticmarkup.py
git commit -m "feat(core): criticmarkup — accept/reject/apply por marca"
```

---

### Task 3: Motor de edits + span-map no `normalize_markdown`

**Files:**
- Modify: `src/prumo_assist/core/obsidian.py` (reescrita interna; API pública preservada)
- Test: Create `tests/unit/core/test_obsidian_spanmap.py`; `tests/unit/core/test_obsidian.py` existente DEVE passar sem edição

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class SpanFragment:
    source_start: int
    source_end: int
    norm_start: int
    norm_end: int
    kind: str  # "identity" | "citation" | "wikilink" | "image" | "callout" | "block-id" | "code"

def normalize_markdown_with_map(
    text: str, page_dir: Path | None = None
) -> tuple[str, list[SpanFragment]]: ...
```

`normalize_markdown(text, page_dir)` passa a ser wrapper: `return normalize_markdown_with_map(text, page_dir)[0]` — comportamento textual idêntico.

**Arquitetura da reescrita (obrigatória):** substituir o pipeline de 6 passes `re.sub` por **coleta única de edits sobre o texto-fonte**:

1. Localizar spans de código (`_CODE_FENCE_RE`, `_INLINE_CODE_RE`) → viram fragments `kind="code"` intocáveis (edits de outras regras que intersectem código são descartados).
2. Rodar `finditer` de cada regra SOBRE O TEXTO-FONTE original, coletando `_Edit(start, end, replacement, kind)`:
   - imagem: `_IMAGE_EMBED_RE` → replacement via lógica atual de `_resolve_image` (incl. warning e `""` para `#page=`), `kind="image"`;
   - citação: `_CITATION_RE` → `[@key]`, `kind="citation"`;
   - wikilink: `_WIKILINK_RE` → alias ou target, `kind="wikilink"` (pular matches que comecem com `!` já consumidos pela regra de imagem — a regra de imagem roda antes e seus spans têm precedência);
   - callout header: por linha, `_CALLOUT_HEADER_RE` sobre cada linha (offset da linha calculado). COM título: **par de edits** — prefixo `> [!tipo] ` → `> **` e sufixo (espaços finais do título até o fim da linha) → `**` — para que citação/wikilink/block-id DENTRO do título continuem sendo edits independentes (paridade com o pipeline sequencial antigo; corrigido após review da T3). SEM título: remoção da linha inteira (incluindo o `\n`). `kind="callout"` nos dois casos;
   - block-id: `_BLOCK_ID_RE` → `""`, `kind="block-id"`.
3. Ordenar edits por `start`; edits sobrepostos entre regras: manter o que começa primeiro (e maior, em empate) e DESCARTAR o outro — com `logger.debug`. Sobreposição com span de código: descartar o edit.
4. Aplicar uma única vez L→R construindo o texto normalizado E os fragments: trecho entre edits → `identity` (source e norm com mesmo comprimento); cada edit → fragment com `norm_end - norm_start == len(replacement)` (zero-width quando replacement é `""` — âncora).
5. Invariantes do mapa (testadas): fragments cobrem `[0, len(source))` sem buracos nem sobreposição, monotônicos nos dois eixos; concatenação dos slices norm == texto normalizado; para todo `identity`, `source[s0:s1] == norm[n0:n1]`.

- [ ] **Step 1: Write the failing span-map tests**

Criar `tests/unit/core/test_obsidian_spanmap.py`:

```python
"""Span-map lossless do normalizador (Fase 1 da ponte — Export instrumentado §1)."""

from __future__ import annotations

from prumo_assist.core.obsidian import SpanFragment, normalize_markdown, normalize_markdown_with_map


def _check_invariants(source: str, norm: str, frags: list[SpanFragment]) -> None:
    assert frags, "mapa vazio"
    assert frags[0].source_start == 0
    assert frags[-1].source_end == len(source)
    for prev, cur in zip(frags, frags[1:]):
        assert prev.source_end == cur.source_start
        assert prev.norm_end == cur.norm_start
    assert "".join(norm[f.norm_start : f.norm_end] for f in frags) == norm
    for f in frags:
        if f.kind == "identity":
            assert source[f.source_start : f.source_end] == norm[f.norm_start : f.norm_end]


def test_identity_only_text() -> None:
    src = "prosa pura sem nada especial\n"
    norm, frags = normalize_markdown_with_map(src)
    assert norm == src
    _check_invariants(src, norm, frags)
    assert [f.kind for f in frags] == ["identity"]


def test_citation_fragment_mapped() -> None:
    src = "antes [[@smith2020]] depois"
    norm, frags = normalize_markdown_with_map(src)
    assert norm == "antes [@smith2020] depois"
    _check_invariants(src, norm, frags)
    cit = [f for f in frags if f.kind == "citation"]
    assert len(cit) == 1
    assert src[cit[0].source_start : cit[0].source_end] == "[[@smith2020]]"
    assert norm[cit[0].norm_start : cit[0].norm_end] == "[@smith2020]"


def test_wikilink_alias_and_blockid_anchor() -> None:
    src = "veja [[Conceito|o conceito]] aqui ^abc123\n"
    norm, frags = normalize_markdown_with_map(src)
    assert norm == "veja o conceito aqui\n"
    _check_invariants(src, norm, frags)
    kinds = [f.kind for f in frags]
    assert "wikilink" in kinds
    anchor = [f for f in frags if f.kind == "block-id"][0]
    assert anchor.norm_start == anchor.norm_end  # âncora de largura zero


def test_code_block_is_atomic_and_untouched() -> None:
    src = "a\n```\n[[@nao_toca]] [[nem_isto]]\n```\nb"
    norm, frags = normalize_markdown_with_map(src)
    assert "[[@nao_toca]]" in norm
    _check_invariants(src, norm, frags)
    assert any(f.kind == "code" for f in frags)


def test_callout_header_with_and_without_title() -> None:
    src = "> [!note] Titulo\n> corpo\n> [!tip]\n> resto\n"
    norm, frags = normalize_markdown_with_map(src)
    assert norm == "> **Titulo**\n> corpo\n> resto\n"
    _check_invariants(src, norm, frags)


def test_wrapper_behavior_unchanged() -> None:
    src = "x [[@k]] [[A|b]] ^id\n"
    assert normalize_markdown(src) == normalize_markdown_with_map(src)[0]
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/unit/core/test_obsidian_spanmap.py -v`
Expected: FAIL na coleta — `ImportError: cannot import name 'SpanFragment'`

- [ ] **Step 3: Rewrite `obsidian.py` with the edit engine**

Reescrever o corpo de `obsidian.py` mantendo: docstring do módulo (atualizar a lista de regras ao final com uma linha sobre o span-map), regexes existentes, `split_frontmatter`, `_resolve_image` e a API `normalize_markdown`. Substituir `_protect_code`/`_restore_code`/`_normalize_*` pelo motor:

```python
@dataclass(frozen=True)
class SpanFragment:
    """Fragmento do mapa norm↔source (offsets absolutos, fim exclusivo)."""

    source_start: int
    source_end: int
    norm_start: int
    norm_end: int
    kind: str


@dataclass(frozen=True)
class _Edit:
    start: int
    end: int
    replacement: str
    kind: str


def _code_spans(text: str) -> list[tuple[int, int]]:
    spans = [m.span() for m in _CODE_FENCE_RE.finditer(text)]
    for m in _INLINE_CODE_RE.finditer(text):
        if not any(s <= m.start() < e for s, e in spans):
            spans.append(m.span())
    return sorted(spans)


def _in_spans(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(s <= pos < e for s, e in spans)


def _collect_edits(text: str, page_dir: Path | None, code: list[tuple[int, int]]) -> list[_Edit]:
    edits: list[_Edit] = []

    def add(start: int, end: int, replacement: str, kind: str) -> None:
        if _in_spans(start, code):
            return
        edits.append(_Edit(start, end, replacement, kind))

    for m in _IMAGE_EMBED_RE.finditer(text):
        ref = m.group(1)
        if "#page=" in ref:
            logger.warning("Embed PDF com page âncora não suportado em export: %s", ref)
            add(m.start(), m.end(), "", "image")
            continue
        path = _resolve_image(ref, page_dir)
        if path is None:
            logger.warning("Imagem não encontrada: %s", ref)
            add(m.start(), m.end(), f"![]({ref})", "image")
        else:
            add(m.start(), m.end(), f"![]({path})", "image")

    for m in _CITATION_RE.finditer(text):
        add(m.start(), m.end(), f"[@{m.group(1)}]", "citation")

    for m in _WIKILINK_RE.finditer(text):
        if m.start() > 0 and text[m.start() - 1] == "!":
            continue  # embed de imagem — já coberto pela regra de imagem
        target, alias = m.group(1), m.group(2)
        add(m.start(), m.end(), alias if alias else target, "wikilink")

    offset = 0
    for line in text.split("\n"):
        m = _CALLOUT_HEADER_RE.match(line)
        if m:
            title = m.group(2)
            if title:
                add(offset, offset + len(line), f"> **{title.strip()}**", "callout")
            else:
                end = offset + len(line)
                if end < len(text) and text[end] == "\n":
                    end += 1  # remove a linha inteira, incluindo o \n
                add(offset, end, "", "callout")
        offset += len(line) + 1

    for m in _BLOCK_ID_RE.finditer(text):
        add(m.start(), m.end(), "", "block-id")

    return edits


def _dedupe(edits: list[_Edit]) -> list[_Edit]:
    picked: list[_Edit] = []
    for e in sorted(edits, key=lambda e: (e.start, -(e.end - e.start))):
        if picked and e.start < picked[-1].end:
            logger.debug("edit sobreposto descartado: %s", e)
            continue
        picked.append(e)
    return picked


def normalize_markdown_with_map(
    text: str, page_dir: Path | None = None
) -> tuple[str, list[SpanFragment]]:
    """Normaliza Obsidian→Pandoc e emite o mapa lossless norm↔source.

    O mapa é a base do transplante da ponte docx↔CriticMarkup: nunca se
    inverte a normalização (many-to-one) — inverte-se o mapa.
    """
    code = _code_spans(text)
    edits = _dedupe(_collect_edits(text, page_dir, code))

    frags: list[SpanFragment] = []
    out: list[str] = []
    cursor = 0
    norm_pos = 0

    def emit_identity(upto: int) -> None:
        nonlocal cursor, norm_pos
        if upto > cursor:
            piece = text[cursor:upto]
            for cs, ce in code:
                if cursor <= cs and ce <= upto:
                    pass  # código fica dentro de identity/code; ver split abaixo
            out.append(piece)
            frags.append(
                SpanFragment(cursor, upto, norm_pos, norm_pos + len(piece), "identity")
            )
            norm_pos += len(piece)
            cursor = upto

    for e in edits:
        emit_identity(e.start)
        out.append(e.replacement)
        frags.append(
            SpanFragment(e.start, e.end, norm_pos, norm_pos + len(e.replacement), e.kind)
        )
        norm_pos += len(e.replacement)
        cursor = e.end
    emit_identity(len(text))

    # Reclassifica identity que coincide exatamente com um span de código
    frags = [
        SpanFragment(
            f.source_start,
            f.source_end,
            f.norm_start,
            f.norm_end,
            "code" if (f.source_start, f.source_end) in {(s, e) for s, e in code} else f.kind,
        )
        for f in frags
    ]
    return "".join(out), frags


def normalize_markdown(text: str, page_dir: Path | None = None) -> str:
    """Aplica todas as regras de normalização Obsidian → Pandoc."""
    return normalize_markdown_with_map(text, page_dir)[0]
```

Nota de implementação: spans de código raramente coincidem 1:1 com um fragment identity (prosa adjacente entra no mesmo fragment). Para o teste `test_code_block_is_atomic_and_untouched`, o motor deve **quebrar** os fragments identity nas bordas dos spans de código (emitir identity até `cs`, depois fragment `code` de `cs..ce`, depois continuar) — implementar `emit_identity` consciente de `code` (iterar spans de código contidos no trecho e fatiar). O snippet acima marca o ponto; a implementação final deve fatiar de verdade e manter as invariantes.

- [ ] **Step 4: Run new + EXISTING obsidian tests**

Run: `uv run pytest tests/unit/core/test_obsidian_spanmap.py tests/unit/core/test_obsidian.py -v`
Expected: todos passam — os testes existentes são o contrato de paridade. Se algum existente falhar, o comportamento divergiu: corrigir o motor, NUNCA o teste (exceção: teste que asserta helper interno removido — relatar como desvio).

- [ ] **Step 5: Battery + commit**

```bash
git add src/prumo_assist/core/obsidian.py tests/unit/core/test_obsidian_spanmap.py
git commit -m "feat(core): normalize_markdown_with_map — motor de edits com span-map lossless"
```

---

### Task 4: Schemas dos sidecars (`SpanMapFile/v1`, `CiteMapFile/v1`)

**Files:**
- Modify: `src/prumo_assist/domains/write/schemas/v1.py` (só adições)
- Test: Modify `tests/unit/write/test_schemas_v1.py` (append)

**Interfaces:**
- Produces:

```python
class SpanFragmentModel(BaseModel):
    source_start: int
    source_end: int
    norm_start: int
    norm_end: int
    kind: str

class SpanMapFile(BaseModel):
    schema_version: Literal["SpanMapFile/v1"] = "SpanMapFile/v1"
    page: str                      # caminho relativo da página-fonte
    source_sha256: str             # hash do texto-fonte (sem frontmatter)
    fragments: list[SpanFragmentModel]

class CiteOccurrence(BaseModel):
    occ_id: str                    # prumoOcc carimbado pelo lua
    citation_id: str               # citationID do campo (pode ser reescrito pelo Word)
    citekeys: list[str]
    fingerprints: dict[str, str]   # citekey → fingerprint
    formatted: str                 # formattedCitation no momento do export
    norm_start: int
    norm_end: int

class CiteMapFile(BaseModel):
    schema_version: Literal["CiteMapFile/v1"] = "CiteMapFile/v1"
    page: str
    export_git_sha: str
    bib_sha256: str
    docx_sha256: str               # I8: amarra o citemap ao docx gerado
    occurrences: list[CiteOccurrence]
```

- [ ] **Step 1: Write the failing tests**

Append em `tests/unit/write/test_schemas_v1.py`:

```python
from prumo_assist.domains.write.schemas.v1 import (
    CiteMapFile,
    CiteOccurrence,
    SpanFragmentModel,
    SpanMapFile,
)


def test_spanmap_file_roundtrip() -> None:
    f = SpanMapFile(
        page="docs/page.md",
        source_sha256="ab" * 32,
        fragments=[
            SpanFragmentModel(source_start=0, source_end=5, norm_start=0, norm_end=5, kind="identity")
        ],
    )
    assert SpanMapFile.model_validate_json(f.model_dump_json()) == f
    assert f.schema_version == "SpanMapFile/v1"


def test_citemap_file_roundtrip() -> None:
    f = CiteMapFile(
        page="docs/page.md",
        export_git_sha="deadbee",
        bib_sha256="cd" * 32,
        docx_sha256="ef" * 32,
        occurrences=[
            CiteOccurrence(
                occ_id="00000001",
                citation_id="00000001",
                citekeys=["smith2020"],
                fingerprints={"smith2020": "doi:10.1000/x"},
                formatted="(Smith, 2020)",
                norm_start=6,
                norm_end=18,
            )
        ],
    )
    assert CiteMapFile.model_validate_json(f.model_dump_json()) == f
```

- [ ] **Step 2–5:** rodar (FAIL ImportError) → implementar os modelos exatamente como acima em `v1.py` (após `WriteOutput`) → rodar (2 novos passed + existentes) → bateria → commit:

```bash
git add src/prumo_assist/domains/write/schemas/v1.py tests/unit/write/test_schemas_v1.py
git commit -m "feat(write): schemas v1 dos sidecars da ponte (SpanMapFile, CiteMapFile)"
```

---

### Task 5: I7 — gramática única de citekey

**Files:**
- Modify: `src/prumo_assist/domains/write/export.py` (expor `CITEKEY_BODY`)
- Modify: `src/prumo_assist/domains/write/compose.py:265-268` (`_extract_citekeys_used`)
- Test: Modify `tests/unit/write/test_compose_refs.py` (append)

**Interfaces:**
- Produces em `export.py` (acima de `_CITEKEY_RE`, reusando-o):

```python
CITEKEY_BODY = r"[A-Za-z0-9_]\w*(?:[:.#$%&+\-?<>~/]\w+)*"
```
e `_CITEKEY_RE` passa a ser construído dele: `re.compile(r"(?<![@\w])@(" + CITEKEY_BODY + r")")`.
- `compose._extract_citekeys_used` passa a usar:

```python
from prumo_assist.domains.write.export import CITEKEY_BODY

_WIKILINK_CITEKEY_RE = re.compile(r"\[\[@(?P<key>" + CITEKEY_BODY + r")(?:\|[^\]]+)?\]\]")


def _extract_citekeys_used(text: str) -> list[str]:
    """Captura ``[[@<citekey>]]`` em ``text``; retorna lista única ordenada."""
    return sorted({m.group("key") for m in _WIKILINK_CITEKEY_RE.finditer(text)})
```

- [ ] **Step 1: Failing test** — append em `tests/unit/write/test_compose_refs.py`:

```python
from prumo_assist.domains.write.compose import _extract_citekeys_used


def test_extract_citekeys_composite_key_not_truncated() -> None:
    text = "cita [[@smith2020:aha-guideline]] e [[@plain2021|alias]]."
    assert _extract_citekeys_used(text) == ["plain2021", "smith2020:aha-guideline"]
```

- [ ] **Step 2:** rodar → FAIL (hoje trunca `smith2020:aha-guideline` → `smith2020`... verificar: o regex atual `[a-zA-Z0-9._+-]+` para no `:` e o `]]` não casa, então a chave composta é DESCARTADA — registrar o comportamento observado no report).
- [ ] **Step 3:** implementar como acima (import no topo de `compose.py`; `export.py` ganha `CITEKEY_BODY` e `_CITEKEY_RE` derivado — rodar também `tests/unit/write/test_export_pandoc_cmd.py` e a suíte de write inteira para provar que `_CITEKEY_RE` não mudou de comportamento).
- [ ] **Step 4:** `uv run pytest tests/unit/write/ -v` → verde; bateria completa.
- [ ] **Step 5:**

```bash
git add src/prumo_assist/domains/write/export.py src/prumo_assist/domains/write/compose.py tests/unit/write/test_compose_refs.py
git commit -m "fix(write): I7 — gramática única de citekey (CITEKEY_BODY compartilhado)"
```

---

### Task 6: Lua — `prumoOcc` + `prumoFingerprint`; Python — fingerprints no lookup

**Files:**
- Modify: `src/prumo_assist/_filters/zotero_live_docx.lua` (função `build_csl_citation` e contador)
- Modify: `src/prumo_assist/domains/write/export.py` (`fetch_bbt_zotero_metadata` ganha wrapper de fingerprint; novo helper `_fingerprint_for`)
- Test: Modify `tests/unit/write/test_export_docx_validation.py` (append — helper de fixture com payload completo) e novo teste do fingerprint

**Interfaces:**
- `_fingerprint_for(citekey: str, bib_entry_raw: str | None, lookup: dict[str, object] | None) -> str` — `doi:<v>` se o entry do `.bib` tem `doi = {...}`; senão `sha256:<hex(itemID|uri)>` quando lookup presente; senão `bib:<sha256(entry_raw)>`; senão `none` (chave sem entry — o export já falha antes por outros caminhos).
- Lookup file passa a ser `{citekey: {itemID, uri, fingerprint}}`; o lua carimba `item.prumoFingerprint = lookup.fingerprint` e cada citação ganha `prumoOcc` (contador `%08d` próprio, independente de `citationID`).
- Lua: adicionar `local occ_counter = 0` e em `build_csl_citation`, após `citationID`: `occ_counter = occ_counter + 1` e campo `prumoOcc = string.format('%08d', occ_counter)` no objeto retornado.

- [ ] **Step 1: Failing tests (Python)** — append em `tests/unit/write/test_export_docx_validation.py`:

```python
from prumo_assist.domains.write.export import _fingerprint_for


def test_fingerprint_prefers_doi() -> None:
    entry = "@article{k, title={T}, doi={10.1000/xyz}}"
    assert _fingerprint_for("k", entry, {"itemID": 1, "uri": "u"}) == "doi:10.1000/xyz"


def test_fingerprint_falls_back_to_lookup_hash() -> None:
    fp = _fingerprint_for("k", "@article{k, title={T}}", {"itemID": 7, "uri": "http://z/7"})
    assert fp.startswith("sha256:") and len(fp) == len("sha256:") + 64


def test_fingerprint_offline_uses_bib_entry() -> None:
    fp = _fingerprint_for("k", "@article{k, title={T}}", None)
    assert fp.startswith("bib:")
```

- [ ] **Step 2:** rodar → FAIL ImportError.
- [ ] **Step 3:** implementar `_fingerprint_for` em `export.py` (regex `re.search(r"doi\s*=\s*[{\"]([^}\"]+)", entry, re.I)`; `hashlib.sha256`; import `hashlib` no topo) e estender o bloco docx de `export()`/`compose()`: após `lookup = fetch_bbt_zotero_metadata(...)`, enriquecer cada entry com `fingerprint` usando o texto cru do `.bib` (`bib.read_text()` + split simples por `@` para achar o entry da chave; helper `_raw_bib_entry(bib_text, citekey) -> str | None` com teste próprio). No lua: `occ_counter` + `prumoOcc` + `prumoFingerprint` (3 linhas; manter comentário I2b).
- [ ] **Step 4: verificação spike-grade do lua** (mktemp -d, mesmo protocolo da Fase 0 Task 2 com lookup contendo `fingerprint`): grep no `word/document.xml` por `prumoOcc` e `prumoFingerprint` — outputs no report.
- [ ] **Step 5:** bateria completa; commit:

```bash
git add src/prumo_assist/_filters/zotero_live_docx.lua src/prumo_assist/domains/write/export.py tests/unit/write/test_export_docx_validation.py
git commit -m "feat(write): occ_id (prumoOcc) e fingerprint por chave no payload do campo Zotero"
```

---

### Task 7: Export emite sidecars (`reviews/<slug>/`) com pareamento hard-fail

**Files:**
- Modify: `src/prumo_assist/domains/write/export.py` (novo helper `_emit_review_sidecars`; chamada no bloco docx de `export()`)
- Test: Modify `tests/unit/write/test_export_docx_validation.py` (append)

**Interfaces:**
- `_read_docx_citations(docx_path: Path) -> list[dict[str, object]]` — parseia `word/document.xml`, decodifica cada `w:instrText` com `ADDIN ZOTERO_ITEM CSL_CITATION` (unescape XML + `json.loads`), retorna na ordem do documento: `{"occ_id", "citation_id", "citekeys", "fingerprints", "formatted"}`. MÉTODO I2 — única fonte de verdade.
- `_norm_citation_spans(norm_text: str) -> list[tuple[int, int]]` — spans `[@...]`/grupos `[@a; @b]` em ordem (regex sobre `_CITEKEY_RE`/`CITEKEY_BODY`, agrupando por colchetes).
- `_emit_review_sidecars(*, page, project_root, norm_text, span_frags, docx_path, bib) -> Path` — constrói `CiteMapFile` (pareando docx-occurrences × norm-spans 1:1 na ordem; **contagem divergente → `CiteMapMismatchError(RuntimeError)` hard-fail** com as duas contagens na mensagem) + `SpanMapFile`, grava em `reviews/<slug>/{citemap.json,span-map.json}`, retorna o diretório.
- `export()` (só docx): passa a usar `normalize_markdown_with_map`, e após as validações existentes chama `_emit_review_sidecars`. `CiteMapMismatchError` entra em `_EXPORT_CATCHES` no CLI (`domains/write/cli.py`).

- [ ] **Step 1: Failing tests** — append (usar `_write_minimal_docx` estendido com payload real de campo: adicionar parâmetro `payloads: list[str] | None = None` que escreve cada payload como `ADDIN ZOTERO_ITEM CSL_CITATION <json escapado>` no body):

```python
def test_read_docx_citations_orders_and_decodes(tmp_path: Path) -> None:
    payload = (
        '{"citationID":"00000001","prumoOcc":"00000001",'
        '"citationItems":[{"id":"smith2020","prumoFingerprint":"doi:10.1/x"}],'
        '"properties":{"formattedCitation":"(Smith, 2020)"}}'
    )
    docx = _write_minimal_docx_with_payloads(tmp_path / "c.docx", [payload])
    occs = export_mod._read_docx_citations(docx)
    assert len(occs) == 1
    assert occs[0]["citekeys"] == ["smith2020"]
    assert occs[0]["occ_id"] == "00000001"


def test_emit_sidecars_mismatch_hard_fails(tmp_path: Path) -> None:
    docx = _write_minimal_docx_with_payloads(tmp_path / "c.docx", [])  # 0 campos
    with pytest.raises(export_mod.CiteMapMismatchError):
        export_mod._emit_review_sidecars(
            page=tmp_path / "p.md",
            project_root=tmp_path,
            norm_text="texto [@smith2020] aqui",   # 1 citação no norm
            span_frags=[],
            docx_path=docx,
            bib=_bib(tmp_path),
        )
```

(o helper `_write_minimal_docx_with_payloads` e `_bib` são definidos no mesmo arquivo de teste; payloads embutidos como `w:instrText` com escaping `&quot;` — o teste é a fixture de referência do leitor OOXML.)

- [ ] **Step 2:** rodar → FAIL. 
- [ ] **Step 3:** implementar (regex sobre o XML para capturar conteúdo de cada `<w:instrText ...>...</w:instrText>` contendo `ADDIN ZOTERO_ITEM CSL_CITATION`; unescape com `xml.sax.saxutils` ou `html.unescape`; hard-fail com mensagem pt-BR + comando). Integrar em `export()` e `_EXPORT_CATCHES`. Wiring test: monkeypatch nos seams (padrão de `test_export_docx_fails_loud_after_retry`) com fake_run escrevendo docx com 1 payload e página com 1 citação → sidecars existem, `CiteMapFile` validável, `docx_sha256` bate com o arquivo.
- [ ] **Step 4:** `uv run pytest tests/unit/write/ -v` verde; bateria completa.
- [ ] **Step 5:**

```bash
git add src/prumo_assist/domains/write/export.py src/prumo_assist/domains/write/cli.py tests/unit/write/test_export_docx_validation.py
git commit -m "feat(write): sidecars citemap/span-map em reviews/<slug>/ com pareamento hard-fail (I2/I8)"
```

---

### Task 8: Campos travados (I4) — `w:sdt` + guarda pós-build

**Files:**
- Modify: `src/prumo_assist/_filters/zotero_live_docx.lua` (`wrap_cite_in_field` embrulha em sdt)
- Modify: `src/prumo_assist/domains/write/export.py` (`_assert_fields_locked`)
- Test: Modify `tests/unit/write/test_export_docx_validation.py` (append)

**Interfaces:**
- Lua: o retorno de `wrap_cite_in_field` passa a ser `<w:sdt><w:sdtPr><w:alias w:val="prumo-citation"/><w:lock w:val="sdtContentLocked"/></w:sdtPr><w:sdtContent>` + runs do campo + `</w:sdtContent></w:sdt>`.
- Python: `_assert_fields_locked(docx_path: Path) -> None` — se `ZOTERO_ITEM` count > 0, exige count igual de `sdtContentLocked` no `document.xml`; senão `MissingFieldLockError(RuntimeError)` (mensagem pt-BR + comando; entra em `_EXPORT_CATCHES`). Chamada no bloco docx após `_assert_zotero_prefs_present`.

- [ ] **Step 1: Failing tests** — fixtures com/sem `sdtContentLocked` (estender o helper de payloads com flag `locked: bool = True`); testes: locked ok; unlocked com campos → raises; sem campos → ok.
- [ ] **Step 2:** FAIL → **Step 3:** implementar lua + assert + wiring (fake_run passa a escrever payload COM sdt para os happy-paths existentes — ajustar o helper, não os asserts). Spike-grade: export real via pandoc no mktemp -d; grep `sdtContentLocked` == nº de citações; abrir**ia** no Word — registrar como smoke manual pendente do dono (não-bloqueante).
- [ ] **Step 4:** suíte + bateria. — **Step 5:**

```bash
git add src/prumo_assist/_filters/zotero_live_docx.lua src/prumo_assist/domains/write/export.py tests/unit/write/test_export_docx_validation.py
git commit -m "feat(write): campos de citação travados (sdtContentLocked) com guarda pós-build (I4)"
```

---

### Task 9: ADR + CHANGELOG + bateria final

**Files:**
- Create: `docs/adr/adr-0016-criticmarkup-conservacao-ooxml.md` (MADR minimal; próximo número livre — CONFERIR `docs/adr/_index.md` antes: se 0015 já existir aqui, usar o próximo)
- Modify: `CHANGELOG.md`; regenerar índices

- [ ] **Step 1: ADR** (MADR minimal, imutável após aceito): título "CriticMarkup como representação de revisão + conservação de citações contada no OOXML"; contexto (spec da ponte, decisão (b) da Fase 0); decisão (substrato desta fase: marcas planas em `.md`, span-map, citemap OOXML-only, campos travados); consequências; referencia ADR-0009 como precedente máquina-possui-região. Registrar no índice via gerador.
- [ ] **Step 2: CHANGELOG** em "Não publicado" (### Adicionado): criticmarkup core, span-map, sidecars `reviews/<slug>/`, campos travados, occ_id/fingerprint; (### Corrigido): I7 chave composta não truncada.
- [ ] **Step 3: Bateria completa** — `uv run pytest` (todos), `ruff check`/`format --check`, `mypy`, `uv run python .github/scripts/gen_indexes.py --check` (após rodar o gerador para o ADR novo).
- [ ] **Step 4: Commit**

```bash
git add docs/adr/ docs/_index.md docs/adr/_index.md CHANGELOG.md
git commit -m "docs(adr): ADR-0016 criticmarkup + conservação OOXML; changelog da Fase 1 do substrato"
```

## Verificação final

- [ ] Todos os checkboxes marcados; bateria verde no commit final; testes existentes de obsidian intactos (paridade).
- [ ] Smoke manual pendente do dono (não-bloqueante, registrar ao arquivar): abrir um export real no Word — campo travado não-editável, Zotero Refresh funcional.
- [ ] Arquivar o plano (frontmatter implemented/verified + archive/) apenas após review final da fase.
