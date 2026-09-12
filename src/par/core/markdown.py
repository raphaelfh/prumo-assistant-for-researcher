"""Normalizador do Markdown do wiki (wikilink, embed, callout, block ID) → Pandoc Markdown.

Citação é gramática Pandoc pura (``[@key]``/``@key`` — ver
``core/citations``); este módulo não tem nenhuma regra de citação, só o
wikilink de página e os demais átomos de wiki abaixo (spec 2026-07-22,
retirada do legado ``[[@key]]``). Regras (ver spec sec. 4.2 do export
pipeline):

- ``[[file]]`` → ``file`` (texto plano)
- ``[[file|alias]]`` → ``alias``
- ``![[img.png]]`` → ``![](caminho_resolvido)`` (busca relativa)
- ``![[paper.pdf#page=N]]`` → ``""`` + warning (Pandoc não suporta)
- ``> [!tipo] [titulo]`` / ``> corpo`` → ``> **titulo**`` / ``> corpo``
- ``^anchor`` (block ID) → removido
- Code blocks, footnotes, tags: passthrough.

``normalize_markdown_with_map`` roda um motor de edits (coleta única sobre o
texto-fonte) e devolve, junto do texto normalizado, um span-map lossless
norm↔source (``SpanFragment``); ``normalize_markdown`` é o wrapper textual.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from par.core import pj_layout

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?\n?", re.DOTALL)
_CODE_FENCE_RE = re.compile(r"(```.*?\n.*?\n```)", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"(`[^`\n]+`)")

# O charset do alvo NÃO exclui `@` — de propósito, e sem reintroduzir
# suporte ao legado. Enquanto excluía (resíduo do reconhecedor legado), um
# `[[@smith2020]]` remanescente passava INTACTO pelo normalizador e o pandoc
# entregava `[(Smith 2020)]` no docx; com alias, `[[@jones2021|Jones et al.]]`
# virava `[(Jones 2021, |Jones et al.)]` — texto corrompido DENTRO da
# citação, sem erro nenhum. Caindo na regra normal de wikilink, `[[@key]]`
# degrada para `@key`, que é citação narrativa Pandoc VÁLIDA: o pior caso
# passa a ser uma citação correta em vez de docx corrompido.
_WIKILINK_RE = re.compile(r"\[\[([^\]\|]+)(?:\|([^\]]+))?\]\]")
_IMAGE_EMBED_RE = re.compile(r"!\[\[([^\]]+)\]\]")
_BLOCK_ID_RE = re.compile(r"\s\^[A-Za-z0-9-]+\b")
_CALLOUT_HEADER_RE = re.compile(r"^>\s*\[!(\w+)\](?:\s+(.+))?\s*$")


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Separa YAML frontmatter do corpo. Retorna ``({}, body)`` se ausente."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta = yaml.safe_load(match.group(1)) or {}
    return meta, text[match.end() :]


def split_frontmatter_raw(text: str) -> tuple[str, str]:
    """Separa o BLOCO de frontmatter VERBATIM (delimitadores ``---`` inclusos)
    do corpo — sem passar por ``yaml.safe_load``/``yaml.safe_dump``.

    Diferente de :func:`split_frontmatter` (que parseia o YAML e portanto
    perde comentários e formatação num eventual re-dump), esta função devolve
    ``raw_block`` byte a byte tal como aparece na fonte — usada pela ponte
    docx↔CriticMarkup (``domains/write/review.py``) para write-back
    byte-fiel de frontmatter (Fix pós-review da Fase 2/Task 9, achado
    Crítico 1: reserializar via ``yaml.safe_dump`` deletava comentários YAML
    e reformatava o bloco).

    Retorna ``(raw_block, body)``; ``("", text)`` se não houver frontmatter
    — ``raw_block + body == text`` sempre (round-trip exato), pela mesma
    razão que ``split_frontmatter`` reusa: ``text[match.end():]`` é o
    complemento exato de ``match.group(0)``.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return "", text
    return match.group(0), text[match.end() :]


def set_frontmatter_key(text: str, key: str, value: Any) -> str:
    """Grava ou substitui UMA chave de topo no frontmatter, sem re-dump do bloco.

    Só as linhas da chave ``key`` (e suas continuações indentadas ou de lista)
    são reescritas, com o valor renderizado por ``yaml.safe_dump``; toda outra
    linha — comentários e ordem de chaves inclusos — fica byte a byte igual
    (ADR-0009). Chave ausente vai ao fim do bloco; sem frontmatter, o bloco é
    criado no topo do texto.
    """
    rendered = yaml.safe_dump({key: value}, sort_keys=False, allow_unicode=True).rstrip("\n")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return f"---\n{rendered}\n---\n\n{text}"
    inner = match.group(1)
    lines = inner.split("\n") if inner.strip() else []
    start = next((i for i, ln in enumerate(lines) if ln.startswith(f"{key}:")), None)
    if start is None:
        lines.append(rendered)
    else:
        end = start + 1
        last = end
        while end < len(lines):
            ln = lines[end]
            if ln.startswith((" ", "\t", "-")):
                last = end = end + 1
            elif not ln.strip():
                end += 1  # linha vazia só conta se uma continuação vier depois
            else:
                break
        lines[start:last] = [rendered]
    return text[: match.start(1)] + "\n".join(lines) + text[match.end(1) :]


@dataclass(frozen=True)
class SpanFragment:
    """Fragmento do mapa norm↔source (offsets absolutos, fim exclusivo).

    ``kind`` é um de ``identity | wikilink | image | callout | block-id |
    code``. Fragmentos são contíguos e cobrem ``[0, len(source))``
    e ``[0, len(norm))`` sem buracos nem sobreposição (ver invariantes em
    ``tests/unit/core/test_markdown_spanmap.py``).
    """

    source_start: int
    source_end: int
    norm_start: int
    norm_end: int
    kind: str


@dataclass(frozen=True)
class _Edit:
    """Substituição pontual coletada sobre o texto-fonte original (não aplicada ainda)."""

    start: int
    end: int
    replacement: str
    kind: str


def _code_spans(text: str) -> list[tuple[int, int]]:
    """Spans intocáveis: fences primeiro; código inline só se não estiver dentro de um fence."""
    spans = [m.span() for m in _CODE_FENCE_RE.finditer(text)]
    for m in _INLINE_CODE_RE.finditer(text):
        if not any(s <= m.start() < e for s, e in spans):
            spans.append(m.span())
    return sorted(spans)


def _in_spans(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(s <= pos < e for s, e in spans)


def _resolve_image(name: str, page_dir: Path | None) -> Path | None:
    if page_dir is None:
        return None
    direct = page_dir / name
    if direct.is_file():
        return direct
    parent = page_dir.parent
    for candidate in (
        pj_layout.pdfs_dir(parent) / name,
        pj_layout.pdfs_dir(parent.parent) / name,
    ):
        if candidate.is_file():
            return candidate
    return None


def _collect_edits(text: str, page_dir: Path | None, code: list[tuple[int, int]]) -> list[_Edit]:
    """Roda cada regra via ``finditer`` sobre o texto-fonte original e coleta os edits.

    Edits cujo início cai dentro de um span de código são descartados aqui
    mesmo (o código é intocável). Sobreposições entre regras são resolvidas
    depois, em ``_dedupe``.
    """
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

    for m in _WIKILINK_RE.finditer(text):
        if m.start() > 0 and text[m.start() - 1] == "!":
            continue  # embed de imagem — já coberto pela regra de imagem, que tem precedência
        target, alias = m.group(1), m.group(2)
        add(m.start(), m.end(), alias if alias else target, "wikilink")

    offset = 0
    for line in text.split("\n"):
        callout_match = _CALLOUT_HEADER_RE.match(line)
        if callout_match:
            title = callout_match.group(2)
            if title:
                # Título vira um PAR de edits (prefixo/sufixo), não uma edit única:
                # o interior do título fica de fora, para que padrões aninhados
                # (citação, wikilink, block-id) sobrevivam ao _dedupe e componham.
                add(offset, offset + callout_match.start(2), "> **", "callout")
                title_end = offset + callout_match.start(2) + len(title.rstrip())
                add(title_end, offset + len(line), "**", "callout")
            else:
                end = offset + len(line)
                if end < len(text) and text[end] == "\n":
                    end += 1  # sem título: remove a linha inteira, incluindo o \n
                add(offset, end, "", "callout")
        offset += len(line) + 1

    for m in _BLOCK_ID_RE.finditer(text):
        add(m.start(), m.end(), "", "block-id")

    return edits


def _dedupe(edits: list[_Edit]) -> list[_Edit]:
    """Ordena por início; em sobreposição, mantém quem começa antes (maior, em empate)."""
    picked: list[_Edit] = []
    for edit in sorted(edits, key=lambda e: (e.start, -(e.end - e.start))):
        if picked and edit.start < picked[-1].end:
            logger.debug("edit sobreposto descartado: %s", edit)
            continue
        picked.append(edit)
    return picked


def normalize_markdown_with_map(
    text: str, page_dir: Path | None = None
) -> tuple[str, list[SpanFragment]]:
    """Normaliza Markdown do wiki→Pandoc e emite o mapa lossless norm↔source.

    O mapa é a base do transplante da ponte docx↔CriticMarkup: nunca se
    inverte a normalização (many-to-one) — inverte-se o mapa.

    Motor: localiza spans de código (intocáveis), coleta edits de cada regra
    sobre o texto-fonte original, remove sobreposições (``_dedupe``) e aplica
    tudo em uma única passada esquerda→direita, emitindo fragments.
    """
    code = _code_spans(text)
    edits = _dedupe(_collect_edits(text, page_dir, code))

    frags: list[SpanFragment] = []
    out: list[str] = []
    cursor = 0
    norm_pos = 0
    code_idx = 0

    def emit_verbatim(start: int, end: int, kind: str) -> None:
        """Emite ``text[start:end]`` tal-qual (comprimento norm == comprimento source)."""
        nonlocal norm_pos
        if end <= start:
            return
        piece = text[start:end]
        out.append(piece)
        frags.append(SpanFragment(start, end, norm_pos, norm_pos + len(piece), kind))
        norm_pos += len(piece)

    def emit_identity(upto: int) -> None:
        """Emite ``[cursor, upto)``, fatiando qualquer span de código contido em fragment próprio.

        Sem isto, um code fence adjacente a prosa viraria parte do mesmo
        fragment ``identity`` — o teste ``test_code_block_is_atomic_and_untouched``
        exige que o código apareça como fragment ``kind="code"`` isolado.
        """
        nonlocal cursor, code_idx
        while code_idx < len(code) and code[code_idx][1] <= cursor:
            code_idx += 1  # spans já consumidos por uma chamada anterior
        while cursor < upto:
            if code_idx < len(code) and code[code_idx][0] < upto:
                cs, ce = code[code_idx]
                emit_verbatim(cursor, cs, "identity")
                cursor = cs
                ce_eff = min(ce, upto)
                emit_verbatim(cursor, ce_eff, "code")
                cursor = ce_eff
                if ce_eff >= ce:
                    code_idx += 1
                else:
                    break  # defensivo: um edit não deveria invadir um span de código
            else:
                emit_verbatim(cursor, upto, "identity")
                cursor = upto

    for e in edits:
        emit_identity(e.start)
        out.append(e.replacement)
        frags.append(SpanFragment(e.start, e.end, norm_pos, norm_pos + len(e.replacement), e.kind))
        norm_pos += len(e.replacement)
        cursor = e.end

    emit_identity(len(text))

    if not frags:
        # texto-fonte vazio: nenhum emit disparou, mas o mapa nunca é vazio.
        frags.append(SpanFragment(0, 0, 0, 0, "identity"))

    return "".join(out), frags


def normalize_markdown(text: str, page_dir: Path | None = None) -> str:
    """Aplica todas as regras de normalização do Markdown do wiki → Pandoc.

    Args:
        text: markdown do wiki (sem frontmatter; chame ``split_frontmatter`` antes).
        page_dir: diretório da página-fonte para resolver embeds de imagem.
    """
    return normalize_markdown_with_map(text, page_dir)[0]
