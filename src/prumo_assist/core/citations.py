"""Gramática única de citekey (Pandoc + legado Obsidian).

Uma citação Pandoc é ``@key`` (narrativa) ou ``[@key]``/``[@a; @b]``
(bracketed). O legado Obsidian usa ``[[@key]]``/``[[@key|alias]]``
(normalizado para ``[@key]`` no export). Este módulo é o ÚNICO lugar
do pacote que reconhece citekeys em texto (spec 2026-07-22; invariante
I7 do spec 2026-07-05): export, compose, wiki lint e paper graph
consomem estas funções — nunca regexes próprios.

Dois níveis de captura:

- ``iter_citekeys``/``scan_citekeys`` — amplo: qualquer ``@key`` fora
  de code block. Para pre-fetch e relatórios (falso positivo é barato).
- ``scan_marked_citekeys`` — conservador: só formas marcadas
  (``[[@key]]``, ou dentro de colchetes ``[...]``). Para lint/validação,
  onde um handle ``@fulano`` em prosa não pode virar warning espúrio.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

# Pandoc citation keys: alphanumeric/underscore start, then internal
# `:.#$%&-+?<>~/` punctuation that must be followed by more word chars
# (so we don't grab trailing sentence punctuation like the `.` in
# `[@key].`). Negative lookbehind on `@\w` skips emails (foo@bar).
CITEKEY_RE = re.compile(r"(?<![@\w])@([A-Za-z0-9_]\w*(?:[:.#$%&+\-?<>~/]\w+)*)")

# Um span entre colchetes sem colchetes internos. Cobre ``[@key]``,
# ``[@a; @b, p. 3]`` e também o miolo de ``[[@key]]`` (o span interno).
_BRACKET_SPAN_RE = re.compile(r"\[[^\[\]]*\]")


def _body_lines(markdown_text: str) -> Iterator[str]:
    """Linhas fora de fenced code blocks."""
    in_code_block = False
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        yield line


def iter_citekeys(markdown_text: str) -> Iterator[str]:
    """Citekeys em ordem de 1ª ocorrência, sem repetição (captura ampla)."""
    seen: set[str] = set()
    for line in _body_lines(markdown_text):
        for match in CITEKEY_RE.finditer(line):
            key = match.group(1)
            if key not in seen:
                seen.add(key)
                yield key


def scan_citekeys(markdown_text: str) -> list[str]:
    """Extrai citekeys ``[@key]`` / ``@key`` do markdown, ordenadas.

    Não tenta substituir o parser do Pandoc — só precisa achar TODAS as
    chaves para pre-fetch/relatório. False positives (ex. nomes de
    variáveis fora de code block) só geram queries extras sem-resultado.
    """
    return sorted(iter_citekeys(markdown_text))


def iter_marked_citation_spans(text: str) -> Iterator[tuple[int, int]]:
    """Spans ``(start, end)`` dos GRUPOS de citação marcada em ``text``, em ordem.

    Um span por bloco ``[...]`` sem colchetes internos que contenha ao menos
    um citekey — ``[@a]`` e ``[@a; @b, p. 3]`` cada um conta como UM span
    (também casa o miolo interno de ``[[@key]]`` legado). É o nível-span da
    mesma gramática de :func:`scan_marked_citekeys`; NÃO filtra code blocks —
    responsabilidade do chamador (linha a linha via :func:`_body_lines`, ou
    por span-map no export).
    """
    for match in _BRACKET_SPAN_RE.finditer(text):
        if CITEKEY_RE.search(match.group(0)):
            yield match.span()


def scan_marked_citekeys(markdown_text: str) -> list[str]:
    """Citekeys em formas MARCADAS, ordenadas: ``[[@key]]`` legado ou
    dentro de colchetes ``[@key]``/``[@a; @b, p. 3]``.

    Narrativa solta (``@key`` fora de colchete) fica de fora de
    propósito — ver docstring do módulo.
    """
    keys: set[str] = set()
    for line in _body_lines(markdown_text):
        for start, end in iter_marked_citation_spans(line):
            for match in CITEKEY_RE.finditer(line[start:end]):
                keys.add(match.group(1))
    return sorted(keys)
