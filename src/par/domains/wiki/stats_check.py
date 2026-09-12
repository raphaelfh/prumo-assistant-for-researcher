"""Recálculo determinístico das estatísticas relatadas numa página do wiki.

Alimenta o código ``stat_mismatch`` de ``prumo wiki lint``. Só os padrões que um
draft real usa (Princípio VI):

- ``x of n (p%)`` / ``x of n, p%`` — porcentagem contra ``100·x/n``, meia unidade
  de tolerância na precisão relatada.
- ``x of n (p%, 95% CI a to b)`` — IC de Wilson, uma unidade de tolerância.
- Tabela Markdown com uma coluna ``p`` e colunas ``q`` — Benjamini-Hochberg por
  família (a tabela, ou o valor da coluna ``Família``); coluna ``q`` com
  ``global`` no cabeçalho agrupa as homônimas de todas as tabelas da página.
  BH é monótono em cada p, então recalcular com todos os p em ``p ± ½unidade``
  cerca o arredondamento do p exibido.

O que não parseia é pulado em silêncio, nunca adivinhado; tabela com célula p/q
não numérica é pulada inteira (o ``m`` ficaria errado). Supõe que a tabela traz
a família inteira. Só divergência vira mensagem.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from statistics import NormalDist

from par.core.citations import body_lines

_NUM = r"\d+(?:[.,]\d+)?"
_PROPORTION_RE = re.compile(
    rf"\b(\d+) (?:of|de) (\d+)(?: [^\W\d_]+)?(?: \(|, )({_NUM})%"
    rf"(?:, 95% CI ({_NUM}) to ({_NUM}))?"
)
_CELL_NUM_RE = re.compile(rf"^{_NUM}$")
_SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|?$")
_FAMILY_HEADERS = frozenset({"família", "familia", "family"})
_Z95 = NormalDist().inv_cdf(0.975)
_EPS = 1e-9


def wilson_interval(x: int, n: int, z: float = _Z95) -> tuple[float, float]:
    """IC de Wilson para a proporção ``x/n`` (em fração, não em %)."""
    p = x / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return center - half, center + half


def benjamini_hochberg(pvalues: list[float]) -> list[float]:
    """Valores q de Benjamini-Hochberg (step-up), na ordem de entrada, limitados a 1."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    q = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, pvalues[i] * m / rank)
        q[i] = running
    return q


@dataclass(frozen=True)
class _QCell:
    group: tuple[str, ...]
    where: str
    label: str
    column: str
    p: str
    q: str


def _value(raw: str) -> float:
    return float(raw.replace(",", "."))


def _decimals(raw: str) -> int:
    sep = max(raw.find("."), raw.find(","))
    return len(raw) - sep - 1 if sep >= 0 else 0


def _unit(raw: str) -> float:
    return float(10.0 ** -_decimals(raw))


def _fmt(value: float, like: str) -> str:
    return f"{value:.{_decimals(like)}f}"


def _show(raw: str) -> str:
    return raw.replace(",", ".")


def _check_proportions(line: str) -> list[str]:
    found: list[str] = []
    for m in _PROPORTION_RE.finditer(line):
        x, n, pct = int(m[1]), int(m[2]), m[3]
        if n == 0 or x > n:
            continue
        exact = 100 * x / n
        if abs(_value(pct) - exact) > _unit(pct) / 2 + _EPS:
            found.append(f'"{m[0]}": relatado {_show(pct)}%, recalculado {_fmt(exact, pct)}%')
        if m[4] is None or m[5] is None:
            continue
        lo, hi = (100 * v for v in wilson_interval(x, n))
        if (
            abs(_value(m[4]) - lo) > _unit(m[4]) + _EPS
            or abs(_value(m[5]) - hi) > _unit(m[5]) + _EPS
        ):
            found.append(
                f'"{m[0]}": IC 95% de Wilson relatado {_show(m[4])} a {_show(m[5])}, '
                f"recalculado {_fmt(lo, m[4])} a {_fmt(hi, m[5])}"
            )
    return found


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _table_cells(heading: str, index: int, lines: list[str]) -> list[_QCell]:
    header = _split_row(lines[0])
    first = [re.split(r"[\s(]", h.lower(), maxsplit=1)[0] for h in header]
    p_cols = [i for i, token in enumerate(first) if token == "p"]
    q_cols = [i for i, token in enumerate(first) if token == "q"]
    if len(p_cols) != 1 or not q_cols:
        return []
    p_col = p_cols[0]
    family = next((i for i, h in enumerate(header) if h.lower() in _FAMILY_HEADERS), None)
    where = f'tabela "{heading}", ' if heading else "tabela, "
    cells: list[_QCell] = []
    for row in map(_split_row, lines[2:]):
        if len(row) != len(header) or not _CELL_NUM_RE.match(row[p_col]):
            return []
        for q_col in q_cols:
            if not _CELL_NUM_RE.match(row[q_col]):
                return []
            column = header[q_col]
            if "global" in column.lower():
                group: tuple[str, ...] = ("global", column.lower())
            else:
                fam = row[family] if family is not None else ""
                group = ("table", str(index), column, fam)
            cells.append(_QCell(group, where, row[0], column, row[p_col], row[q_col]))
    return cells


def _check_q_values(cells: list[_QCell]) -> list[str]:
    groups: dict[tuple[str, ...], list[_QCell]] = {}
    for cell in cells:
        groups.setdefault(cell.group, []).append(cell)
    found: list[str] = []
    for members in groups.values():
        ps = [_value(c.p) for c in members]
        halves = [_unit(c.p) / 2 for c in members]
        low = benjamini_hochberg([max(0.0, p - h) for p, h in zip(ps, halves, strict=True)])
        high = benjamini_hochberg([min(1.0, p + h) for p, h in zip(ps, halves, strict=True)])
        exact = benjamini_hochberg(ps)
        for c, lo, hi, q in zip(members, low, high, exact, strict=True):
            tol = _unit(c.q) / 2 + _EPS
            if not lo - tol <= _value(c.q) <= hi + tol:
                found.append(
                    f'{c.where}linha "{c.label}", {c.column}: relatado {_show(c.q)}, '
                    f"recalculado {_fmt(q, c.q)} (BH, m={len(members)})"
                )
    return found


def stat_mismatches(text: str) -> list[str]:
    """Mensagem única de ``stat_mismatch`` para a página, ou lista vazia se tudo bate."""
    found: list[str] = []
    cells: list[_QCell] = []
    heading = ""
    table: list[str] = []
    tables = 0
    for line in [*body_lines(text), ""]:
        if line.lstrip().startswith("|"):
            table.append(line)
            continue
        if len(table) >= 3 and _SEPARATOR_RE.match(table[1].strip()):
            cells.extend(_table_cells(heading, tables, table))
            tables += 1
        table = []
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            continue
        found.extend(_check_proportions(line))
    found.extend(_check_q_values(cells))
    if not found:
        return []
    return [
        f"{len(found)} estatística(s) relatada(s) não batem com o recálculo: "
        + "; ".join(found)
        + ". Corrija o texto (ou refaça a análise) e rode `prumo wiki lint` de novo."
    ]
