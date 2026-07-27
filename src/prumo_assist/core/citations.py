"""Gramática única de citekey (Pandoc).

Uma citação Pandoc é ``@key`` (narrativa) ou ``[@key]``/``[@a; @b]``
(bracketed). Este módulo é o ÚNICO lugar do pacote que reconhece citekeys
em texto (spec 2026-07-22; invariante I7 do spec 2026-07-05): export,
compose, wiki lint, paper graph, paper verify, write review e capture
route consomem estas funções ou o ``CITEKEY_BODY`` — nunca regexes
próprios.

Dois níveis de captura:

- ``iter_citekeys``/``scan_citekeys`` — amplo: qualquer ``@key`` fora
  de code block. Para pre-fetch e relatórios (falso positivo é barato).
- ``scan_marked_citekeys`` — conservador: só formas marcadas (dentro de
  colchetes ``[...]``). Para lint/validação, onde um handle ``@fulano``
  em prosa não pode virar warning espúrio.

Fora da cobertura (registrado, não implementado): a forma CHAVEADA
``@{...}`` — recomendada pelo manual do Pandoc para chave com ``://`` —
exigiria um segundo grupo de captura, e ``CITEKEY_RE.findall`` tem contrato
de ``list[str]`` com os consumidores de ``domains/write/review.py``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

# Corpo do citekey Pandoc, SEM o `@` e sem âncora — compartilhado por quem
# precisa ancorar de outro jeito (ex.: `domains/capture/route.py`, que casa
# um token inteiro). Manter ÚNICO: um segundo reconhecedor divergente é
# exatamente o que o Princípio I7 proíbe.
#
# Âncora inicial `\w` (Unicode-aware, coerente com o `\w` do resto): o
# Pandoc aceita citekey iniciada por letra não-ASCII — `@Ünal2024`,
# `@Иванов2020` — e a versão ASCII-only criava assimetria silenciosa
# (`@unÜal2024` passava, `@Ünal2024` sumia). Pontuação interna
# `:.#$%&-+?<>~/` precisa ser seguida de word char, para não engolir o
# `.` final de `[@key].`.
CITEKEY_BODY = r"\w(?:\w|[:.#$%&+\-?<>~/]\w)*"

# Lookbehind: barra e-mail (`foo@bar`) exigindo que o caractere anterior não
# seja letra/dígito. `_` é PERMITIDO antes de propósito — `_@lima2018 mostrou_`
# é ênfase Markdown com citação dentro, ASCII puro e caminho default, e o
# `(?<![@\w])` original a perdia porque `_` é word char.
CITEKEY_RE = re.compile(r"(?<![@0-9A-Za-z])@(" + CITEKEY_BODY + r")")

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
    um citekey — ``[@a]`` e ``[@a; @b, p. 3]`` cada um conta como UM span.
    É o nível-span da mesma gramática de :func:`scan_marked_citekeys`; NÃO
    filtra code blocks — responsabilidade do chamador (linha a linha via
    :func:`_body_lines`, ou por span-map no export).
    """
    for match in _BRACKET_SPAN_RE.finditer(text):
        if CITEKEY_RE.search(match.group(0)):
            yield match.span()


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


def scan_marked_citekeys(markdown_text: str) -> list[str]:
    """Citekeys em formas MARCADAS, ordenadas: dentro de colchetes
    ``[@key]``/``[@a; @b, p. 3]``.

    Narrativa solta (``@key`` fora de colchete) fica de fora de
    propósito — ver docstring do módulo.
    """
    keys: set[str] = set()
    for line in _body_lines(markdown_text):
        for start, end in iter_marked_citation_spans(line):
            for match in CITEKEY_RE.finditer(line[start:end]):
                keys.add(match.group(1))
    return sorted(keys)
