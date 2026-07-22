"""Tests da gramática única de citekey (core/citations)."""

from __future__ import annotations

from prumo_assist.core.citations import iter_citekeys, scan_citekeys, scan_marked_citekeys


def test_scan_catches_all_pandoc_autocomplete_forms() -> None:
    text = (
        "Bracketed [@Author2015, p. 123] e narrativa @Author2016 "
        "e narrativa com locator @Author2017 [p. 9]."
    )
    assert scan_citekeys(text) == ["Author2015", "Author2016", "Author2017"]


def test_scan_catches_legacy_wikilink_and_alias() -> None:
    text = "Veja [[@smith2024cohort]] e [[@jones2023trial|Jones et al.]]."
    assert scan_citekeys(text) == ["jones2023trial", "smith2024cohort"]


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


def test_marked_accepts_bracketed_and_wikilink_only() -> None:
    text = (
        "Marcada [@smith2024] e legado [[@jones2023]] e grupo [@a2020; @b2021, p. 3]. "
        "Handle solto @twitter_user fica de fora."
    )
    assert scan_marked_citekeys(text) == ["a2020", "b2021", "jones2023", "smith2024"]


def test_marked_skips_code_blocks() -> None:
    text = "```\n[@fake]\n```\n[@real]"
    assert scan_marked_citekeys(text) == ["real"]
