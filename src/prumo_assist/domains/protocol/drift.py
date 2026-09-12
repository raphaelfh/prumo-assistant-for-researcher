"""Drift determinístico entre manuscrito e protocolo/PICOT.

Extrai, linha a linha e por vocabulário fechado bilíngue (pt/en), só fatos
verificáveis sem LLM: janelas de coleta (mês a mês de ano), tamanhos amostrais
``n=N``, testes estatísticos nomeados e afirmações de pré-especificação de
subgrupos/estratificações. Nunca escreve em arquivo algum.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

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
_PRESPEC_RE = re.compile(
    r"pr[eé]-?(?:especifica|declara)|pre-?specifi|pre-?declared", re.IGNORECASE
)
_PRESPEC_NEG_RE = re.compile(
    r"n[aã]o\s+(?:foram\s+|foi\s+|são\s+)?pr[eé]-?(?:especifica|declara)"
    r"|not\s+(?:been\s+)?pre-?(?:specifi|declared)"
    r"|absence\s+of\s+pre-?specifi|sem\s+pr[eé]-?especifica",
    re.IGNORECASE,
)
_SUBGROUP_RE = re.compile(r"group|grupo|estratific|stratif", re.IGNORECASE)

Window = tuple[str, str, str]


@dataclass(frozen=True)
class SourceText:
    """Texto de um arquivo com o rótulo usado nas localizações (``rótulo:linha``)."""

    label: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class Drift:
    """Um fato que diverge entre o lado protocolo e o draft, reportado uma vez."""

    kind: str
    protocol_value: str
    draft_value: str
    protocol_loc: str
    draft_loc: str
    hint: str


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


def _scan(sources: Iterable[SourceText]) -> Iterator[tuple[str, str]]:
    for src in sources:
        for i, line in enumerate(src.lines, start=1):
            yield f"{src.label}:{i}", line


def _collect(
    sources: Iterable[SourceText],
) -> tuple[dict[Window, str], dict[str, str], dict[str, str], dict[bool, str], str]:
    wins: dict[Window, str] = {}
    ns: dict[str, str] = {}
    tests: dict[str, str] = {}
    prespec: dict[bool, str] = {}
    text_parts: list[str] = []
    for loc, line in _scan(sources):
        text_parts.append(line)
        for w in windows(line):
            wins.setdefault(w, loc)
        for m in _N_RE.finditer(line):
            ns.setdefault(m.group(1), loc)
        for t in named_tests(line):
            tests.setdefault(t, loc)
        polarity = prespec_polarity(line)
        if polarity is not None:
            prespec.setdefault(polarity, loc)
    return wins, ns, tests, prespec, "\n".join(text_parts)


def find_drift(protocol_sources: list[SourceText], draft: SourceText) -> list[Drift]:
    """Compara os fatos do lado protocolo (``protocol.md`` antes de ``picot.toml``) com o draft."""
    p_wins, p_ns, p_tests, p_pre, _ = _collect(protocol_sources)
    d_wins, _, d_tests, d_pre, d_text = _collect([draft])
    out: list[Drift] = []
    draft_file = draft.label

    if p_wins:
        p_first = next(iter(p_wins))
        allowed = " ou ".join(_fmt_window(w) for w in p_wins)
        for w, loc in d_wins.items():
            if w not in p_wins:
                out.append(Drift(
                    "window", allowed, _fmt_window(w), p_wins[p_first], loc,
                    "Janela de coleta diverge do protocolo: corrija o draft ou, se o "
                    "protocolo mudou, atualize a PICOT e rode `prumo protocol propagate`.",
                ))  # fmt: skip

    for n, loc in p_ns.items():
        if not re.search(rf"(?<![\d.,]){n}(?![\d]|[.,]\d)", d_text):
            out.append(Drift(
                "sample_size", f"n={n}", "(ausente)", loc, draft_file,
                f"O protocolo declara n={n} e o draft não cita esse número: confira "
                "o fluxo de participantes nos Métodos/Resultados.",
            ))  # fmt: skip

    if p_tests and d_tests:
        d_any = next(iter(d_tests.values()))
        p_any = next(iter(p_tests.values()))
        for t, loc in p_tests.items():
            if t not in d_tests:
                out.append(Drift(
                    "test", t, "(ausente)", loc, d_any,
                    f"Teste {t} previsto no protocolo não aparece no draft: descreva-o "
                    "nos Métodos ou justifique o desvio do plano de análise.",
                ))  # fmt: skip
        for t, loc in d_tests.items():
            if t not in p_tests:
                out.append(Drift(
                    "test", "(ausente)", t, p_any, loc,
                    f"Teste {t} usado no draft não está no protocolo: declare o desvio "
                    "do plano de análise ou atualize o SAP.",
                ))  # fmt: skip

    for p_pol, d_pol in ((True, False), (False, True)):
        if p_pol in p_pre and d_pol in d_pre:
            out.append(Drift(
                "prespecification",
                "pré-especificado" if p_pol else "não pré-especificado",
                "pré-especificado" if d_pol else "não pré-especificado",
                p_pre[p_pol], d_pre[d_pol],
                "Draft e protocolo divergem sobre a pré-especificação dos subgrupos: "
                "alinhe o texto ao protocolo (ou registre o desvio).",
            ))  # fmt: skip
    return out
