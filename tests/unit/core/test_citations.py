"""Tests da gramática única de citekey (core/citations)."""

from __future__ import annotations

from prumo_assist.core.citations import (
    CITEKEY_RE,
    iter_citekeys,
    iter_narrative_citation_spans,
    scan_citekeys,
    scan_marked_citekeys,
)


def test_scan_catches_all_pandoc_autocomplete_forms() -> None:
    text = (
        "Bracketed [@Author2015, p. 123] e narrativa @Author2016 "
        "e narrativa com locator @Author2017 [p. 9]."
    )
    assert scan_citekeys(text) == ["Author2015", "Author2016", "Author2017"]


def test_scan_does_not_truncate_composite_keys() -> None:
    # Regressão: o regex antigo do compose ([a-zA-Z0-9._+-]+) truncava
    # chaves com pontuação interna que o Pandoc aceita.
    text = "[@vanDijk2019:pt2] e [@key.sub/part]"
    assert scan_citekeys(text) == ["key.sub/part", "vanDijk2019:pt2"]


def test_scan_skips_emails_and_code_blocks() -> None:
    text = "contato foo@bar.com\n```\n[@dentro_de_code]\n```\n[@real2024]"
    assert scan_citekeys(text) == ["real2024"]


def test_iter_preserves_first_occurrence_order() -> None:
    text = "[@zeta2020] então [@alpha2019] e de novo [@zeta2020]"
    assert list(iter_citekeys(text)) == ["zeta2020", "alpha2019"]


def test_marked_accepts_bracketed_forms_only() -> None:
    text = (
        "Marcada [@smith2024] e grupo [@a2020; @b2021, p. 3]. "
        "Handle solto @twitter_user fica de fora."
    )
    assert scan_marked_citekeys(text) == ["a2020", "b2021", "smith2024"]


def test_marked_skips_code_blocks() -> None:
    text = "```\n[@fake]\n```\n[@real]"
    assert scan_marked_citekeys(text) == ["real"]


def test_iter_narrative_citation_spans_cobre_narrativa_e_pula_marcada() -> None:
    text = "Como @smith2024 mostrou, ver tambem [@jones2020]."
    spans = list(iter_narrative_citation_spans(text))
    assert [text[s:e] for s, e in spans] == ["@smith2024"]


def test_iter_narrative_citation_spans_inclui_o_arroba() -> None:
    """O span começa no `@` — usar `match.span(1)` deixaria o `@` desprotegido
    e uma âncora poderia encostar nele."""
    text = "Ver @key2020 aqui."
    ((start, end),) = iter_narrative_citation_spans(text)
    assert text[start] == "@"
    assert text[start:end] == "@key2020"


def test_citekey_re_tem_exatamente_um_grupo_de_captura() -> None:
    """Contrato duro: `review.py` faz `Counter(CITEKEY_RE.findall(...))`, que
    só devolve `list[str]` com UM grupo. Com dois, `findall` devolve tuplas e
    o multiconjunto de conservação passa a comparar lixo SILENCIOSAMENTE."""
    assert CITEKEY_RE.groups == 1
    assert CITEKEY_RE.findall("Cita [@a2020] e [@b2021].") == ["a2020", "b2021"]
