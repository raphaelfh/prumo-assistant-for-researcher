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
