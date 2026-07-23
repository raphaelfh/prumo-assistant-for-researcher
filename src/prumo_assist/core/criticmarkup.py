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
                raise ValueError(f"substituição sem separador '~>' em offset {m.start()}.")
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


def _resolve(mark: Mark, accepted: bool) -> str:
    """Resolve uma marca segundo sua semântica e decisão (aceitar/rejeitar).

    Semântica:
    - aceitar (True): ins→b, del→"", sub→b, highlight→a, comment→""
    - rejeitar (False): ins→"", del→a, sub→a, highlight→a, comment→""
    """
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

    Args:
        text: Texto com marcas CriticMarkup.
        decisions: Dict {índice_marca: True_aceitar_False_rejeitar}.
                   Marcas ausentes permanecem intactas.

    Returns:
        Texto com marcas resolvidas/intactas conforme decisões.
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
    """Aceita todas as marcas no texto.

    Semântica: ins→b, del→"", sub→b, highlight→a, comment→""
    """
    return apply(text, dict.fromkeys(range(len(parse(text))), True))


def reject(text: str) -> str:
    """Rejeita todas as marcas no texto.

    Semântica: ins→"", del→a, sub→a, highlight→a, comment→""
    """
    return apply(text, dict.fromkeys(range(len(parse(text))), False))
