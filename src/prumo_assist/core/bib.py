"""Parser tolerante de ``_references.bib`` no formato Better BibTeX.

Transformado de ``monorepo-anterior/.claude/scripts/_bib.py`` sem mudança
de comportamento. Decisões de design preservadas:

- Tolera ``@string{}`` / ``@preamble{}`` / ``@comment{}`` (pulados).
- Suporta os 3 delimitadores BibTeX: ``{...}``, ``"..."`` e literal nu.
- Faz contagem de chaves (depth counter) pra aceitar valores com chaves
  aninhadas (``title = {{Combi-Nado} Fusion}`` e similares).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

NON_ENTRY_TYPES = frozenset({"string", "preamble", "comment"})


@dataclass(frozen=True)
class BibEntry:
    """Uma entrada bibliográfica crua: ``@type{citekey, body}``.

    ``body`` é o conteúdo entre ``{`` e ``}`` do entry, **sem** a vírgula
    inicial (já comida pelo parser). Pra extrair campos, use ``extract_field``.
    """

    entry_type: str
    citekey: str
    body: str


def parse_bib(text: str) -> list[BibEntry]:
    """Quebra o texto em entradas BBT tolerando chaves aninhadas no body."""
    entries: list[BibEntry] = []
    i = 0
    n = len(text)
    while i < n:
        at = text.find("@", i)
        if at == -1:
            break
        brace = text.find("{", at)
        if brace == -1:
            break
        entry_type = text[at + 1 : brace].strip().lower()

        depth = 1
        j = brace + 1
        while j < n and depth > 0:
            c = text[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            j += 1

        if entry_type in NON_ENTRY_TYPES:
            i = j
            continue

        comma = text.find(",", brace)
        if comma == -1 or comma >= j:
            i = j
            continue

        citekey = text[brace + 1 : comma].strip()
        body = text[comma + 1 : j - 1]
        entries.append(BibEntry(entry_type=entry_type, citekey=citekey, body=body))
        i = j
    return entries


def extract_field(body: str, field: str) -> str | None:
    """Retorna o valor bruto do campo, tolerando os 3 delimitadores BibTeX.

    - ``field = {value}`` — chaves; valor pode ter chaves aninhadas.
    - ``field = "value"`` — aspas; respeita escape ``\\"``.
    - ``field = literal`` — sem delimitador (numérico ou string macro;
      BBT exporta ``year = 2024`` desse jeito).
    """
    pattern = re.compile(rf"\b{re.escape(field)}\s*=\s*", re.IGNORECASE)
    m = pattern.search(body)
    if not m:
        return None
    start = m.end()
    if start >= len(body):
        return None
    delim = body[start]
    if delim == "{":
        depth = 1
        i = start + 1
        while i < len(body) and depth > 0:
            c = body[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            i += 1
        return body[start + 1 : i - 1]
    if delim == '"':
        i = start + 1
        while i < len(body):
            if body[i] == "\\" and i + 1 < len(body):
                i += 2
                continue
            if body[i] == '"':
                break
            i += 1
        return body[start + 1 : i]
    i = start
    while i < len(body) and body[i] not in ",}\n":
        i += 1
    return body[start:i].strip()


_LEADING_YEAR_RE = re.compile(r"^\d{4}(?!\d)")


def extract_year(body: str) -> str:
    """Retorna o ano numérico da entrada, ou ``""`` se não for determinável.

    Cobre os dois dialetos que o Better BibTeX exporta:

    - Better BibTeX (legado): ``year = 2025`` — vence sempre que for puramente
      numérico. A checagem é ``str.isdigit()``, e NÃO "exatamente 4 dígitos", para
      não estreitar o comportamento anterior a este helper: ``year = {999}`` (ano
      999) continua valendo, como valia antes.
    - Better BibLaTeX: nunca emite ``year``, só ``date = {2025-09-01}`` — o ano
      vem do prefixo de 4 dígitos do ``date``.

    O ``date`` do BibLaTeX é EDTF, não ISO: tolera ``1999-uu``, ``1897/1913``,
    ``2016-07-18T20:26:06``, ``2020-21`` e o ``~`` de aproximação (que o BBT
    reescreve como NBSP). Quando não há ano determinável (``19uu``, ``y-51234``,
    ``year = {n.d.}``) devolve ``""`` — nunca inventa. O ``\\b`` do
    ``extract_field`` impede que ``urldate``/``origdate`` sejam confundidos com
    ``date``.

    Ano NÃO-numérico (``n.d.``, ``2024a``, ``in press``) não é representável aqui e
    sai como ``""``. Quem indexa texto — e não precisa de um inteiro — deve
    preservar o valor cru; ver ``domains/paper/find.py``.
    """
    year = (extract_field(body, "year") or "").strip()
    if year.isdigit():
        return year
    date = (extract_field(body, "date") or "").strip()
    m = _LEADING_YEAR_RE.match(date)
    return m.group(0) if m else ""
