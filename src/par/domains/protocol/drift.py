"""Drift determinístico entre manuscrito e protocolo/PICOT.

Extrai, linha a linha e por vocabulário fechado bilíngue (pt/en), só fatos
verificáveis sem LLM: janelas de coleta (mês a mês de ano), tamanhos amostrais
``n=N``, testes estatísticos nomeados e afirmações de pré-especificação de
subgrupos/estratificações. Nunca escreve em arquivo algum.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import TypeVar

_MONTHS: dict[str, str] = {
    "janeiro": "01", "january": "01",
    "fevereiro": "02", "february": "02",
    "março": "03", "marco": "03", "march": "03",
    "abril": "04", "april": "04",
    "maio": "05", "may": "05",
    "junho": "06", "june": "06",
    "julho": "07", "july": "07",
    "agosto": "08", "august": "08",
    "setembro": "09", "september": "09",
    "outubro": "10", "october": "10",
    "novembro": "11", "november": "11",
    "dezembro": "12", "december": "12",
}  # fmt: skip
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))
_WINDOW_RE = re.compile(
    rf"\b({_MONTH_RE})\s+(?:and|to|through|e|a|até)\s+({_MONTH_RE})\s*,?\s+(?:de\s+|of\s+)?(\d{{4}})\b",
    re.IGNORECASE,
)
_N_RE = re.compile(r"\bn\s*=\s*(\d+)", re.IGNORECASE)
_DASH = r"[\s\-–—]+"
TEST_VOCABULARY: dict[str, re.Pattern[str]] = {
    "chi-square": re.compile(r"qui-?quadrado|chi-?squared?|χ²", re.IGNORECASE),
    "fisher": re.compile(r"\bfisher\b", re.IGNORECASE),
    "mann-whitney": re.compile(rf"\bmann{_DASH}whitney\b", re.IGNORECASE),
    "cochran-armitage": re.compile(rf"\bcochran{_DASH}armitage\b", re.IGNORECASE),
    "wilcoxon": re.compile(r"\bwilcoxon\b", re.IGNORECASE),
    "kruskal-wallis": re.compile(r"\bkruskal\b", re.IGNORECASE),
    "shapiro-wilk": re.compile(r"\bshapiro\b", re.IGNORECASE),
    "t-test": re.compile(r"\bteste t\b|\bt[\s-]test\b|\bstudent'?s? t\b", re.IGNORECASE),
    "anova": re.compile(r"\banova\b", re.IGNORECASE),
    "mcnemar": re.compile(r"\bmcnemar\b", re.IGNORECASE),
}
_PRESPEC = r"(?:pr[eé]-?(?:especifica|declara)|pre-?(?:specifi|declared))"
_PRESPEC_RE = re.compile(_PRESPEC, re.IGNORECASE)
_PRESPEC_NEG_RE = re.compile(
    r"(?:n[aã]o\s+(?:foram\s+|foi\s+|são\s+)?|not\s+(?:been\s+)?|absence\s+of\s+|sem\s+)"
    + _PRESPEC,
    re.IGNORECASE,
)
_SUBGROUP_RE = re.compile(r"group|grupo|estratific|stratif", re.IGNORECASE)

Window = tuple[str, str, str]
_K = TypeVar("_K")


@dataclass(frozen=True)
class SourceText:
    """Texto de um arquivo com o rótulo usado nas localizações (``rótulo:linha``)."""

    label: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class Drift:
    """Um fato que o draft afirma contra o protocolo; reportado uma vez, com todas as
    localizações nos drafts."""

    kind: str
    protocol_value: str
    draft_value: str
    protocol_loc: str
    draft_locs: tuple[str, ...]
    hint: str

    def message(self) -> str:
        """Linha de aviso legível do drift (modo texto do CLI)."""
        return (
            f"drift {self.kind}: protocolo {self.protocol_value} ({self.protocol_loc}) "
            f"≠ draft {self.draft_value} ({', '.join(self.draft_locs)}). {self.hint}"
        )


@dataclass(frozen=True)
class Facts:
    """Fatos verificáveis de um conjunto de textos, cada um com sua 1ª localização."""

    windows: dict[Window, str]
    sample_sizes: dict[str, str]
    tests: dict[str, str]
    prespec: dict[bool, str]


def merge_drift(drifts: Iterable[Drift]) -> list[Drift]:
    """Funde drifts iguais em ``(kind, protocol_value, draft_value)``, somando as
    localizações dos drafts na ordem de aparição."""
    merged: dict[tuple[str, str, str], Drift] = {}
    for d in drifts:
        key = (d.kind, d.protocol_value, d.draft_value)
        prev = merged.get(key)
        if prev is None:
            merged[key] = d
        else:
            locs = prev.draft_locs + tuple(x for x in d.draft_locs if x not in prev.draft_locs)
            merged[key] = replace(prev, draft_locs=locs)
    return list(merged.values())


def windows(line: str) -> list[Window]:
    """Janelas ``(mês_início, mês_fim, ano)`` citadas na linha."""
    return [
        (_MONTHS[m.group(1).lower()], _MONTHS[m.group(2).lower()], m.group(3))
        for m in _WINDOW_RE.finditer(line)
    ]


def named_tests(line: str) -> set[str]:
    """Nomes canônicos dos testes do vocabulário fechado citados na linha."""
    return {name for name, pattern in TEST_VOCABULARY.items() if pattern.search(line)}


def prespec_polarity(line: str) -> bool | None:
    """``True``/``False`` se a linha afirma/nega pré-especificação de subgrupo; senão ``None``."""
    if not _SUBGROUP_RE.search(line) or not _PRESPEC_RE.search(line):
        return None
    return _PRESPEC_NEG_RE.search(line) is None


def _fmt_window(w: Window) -> str:
    return f"{w[0]}–{w[1]}/{w[2]}"


def _first_loc(facts: Mapping[_K, str]) -> str:
    return next(iter(facts.values()))


def collect(sources: Iterable[SourceText]) -> Facts:
    """Fatos das fontes, na ordem dada, guardando a primeira localização de cada um."""
    facts = Facts(windows={}, sample_sizes={}, tests={}, prespec={})
    for src in sources:
        for i, line in enumerate(src.lines, start=1):
            loc = f"{src.label}:{i}"
            for w in windows(line):
                facts.windows.setdefault(w, loc)
            for m in _N_RE.finditer(line):
                facts.sample_sizes.setdefault(m.group(1), loc)
            for t in named_tests(line):
                facts.tests.setdefault(t, loc)
            polarity = prespec_polarity(line)
            if polarity is not None:
                facts.prespec.setdefault(polarity, loc)
    return facts


def _drift(
    kind: str, protocol_value: str, draft_value: str, protocol_loc: str, draft_loc: str, hint: str
) -> Drift:
    return Drift(kind, protocol_value, draft_value, protocol_loc, (draft_loc,), hint)


def find_drift(protocol: Facts, draft: SourceText) -> list[Drift]:
    """Compara os fatos do lado protocolo (``collect`` de ``protocol.md`` antes de
    ``picot.toml``) com o draft.

    Ausência não é drift: só o que o draft afirma (janela, ``n=``, testes nomeados,
    pré-especificação) é comparado.
    """
    d = collect([draft])
    out: list[Drift] = []

    if protocol.windows:
        p_loc = _first_loc(protocol.windows)
        allowed = " ou ".join(_fmt_window(w) for w in protocol.windows)
        for w, loc in d.windows.items():
            if w not in protocol.windows:
                out.append(
                    _drift(
                        "window",
                        allowed,
                        _fmt_window(w),
                        p_loc,
                        loc,
                        "Janela de coleta diverge do protocolo: corrija o draft ou, se o "
                        "protocolo mudou, atualize a PICOT e rode `prumo protocol propagate`.",
                    )
                )

    if protocol.sample_sizes:
        p_loc = _first_loc(protocol.sample_sizes)
        allowed = " ou ".join(f"n={n}" for n in protocol.sample_sizes)
        max_n = max(int(n) for n in protocol.sample_sizes)
        for n, loc in d.sample_sizes.items():
            # n menor é subgrupo/denominador de item; só total acima do protocolo contradiz.
            if int(n) > max_n:
                out.append(
                    _drift(
                        "sample_size",
                        allowed,
                        f"n={n}",
                        p_loc,
                        loc,
                        f"O draft declara n={n}, fora dos tamanhos do protocolo: confira o "
                        "fluxo de participantes ou atualize a PICOT (`prumo protocol propagate`).",
                    )
                )

    if protocol.tests and d.tests:
        p_loc = _first_loc(protocol.tests)
        d_loc = _first_loc(d.tests)
        for t, loc in protocol.tests.items():
            if t not in d.tests:
                out.append(
                    _drift(
                        "test",
                        t,
                        "(ausente)",
                        loc,
                        d_loc,
                        f"Teste {t} previsto no protocolo não aparece no draft: descreva-o "
                        "nos Métodos ou justifique o desvio do plano de análise.",
                    )
                )
        for t, loc in d.tests.items():
            if t not in protocol.tests:
                out.append(
                    _drift(
                        "test",
                        "(ausente)",
                        t,
                        p_loc,
                        loc,
                        f"Teste {t} usado no draft não está no protocolo: declare o desvio "
                        "do plano de análise ou atualize o SAP.",
                    )
                )

    for p_pol, d_pol in ((True, False), (False, True)):
        if p_pol in protocol.prespec and d_pol in d.prespec:
            out.append(
                _drift(
                    "prespecification",
                    "pré-especificado" if p_pol else "não pré-especificado",
                    "pré-especificado" if d_pol else "não pré-especificado",
                    protocol.prespec[p_pol],
                    d.prespec[d_pol],
                    "Draft e protocolo divergem sobre a pré-especificação dos subgrupos: "
                    "alinhe o texto ao protocolo (ou registre o desvio).",
                )
            )
    return out
