"""Tests para extract_missing_refs e validação de citekey."""

from __future__ import annotations

from prumo_assist.domains.write.compose import (
    _extract_citekeys_used,
    extract_missing_refs,
)


def test_extract_missing_refs_finds_one() -> None:
    text = "Claim X [REF FALTANTE: difusão latente]."
    assert extract_missing_refs(text) == ["difusão latente"]


def test_extract_missing_refs_finds_multiple() -> None:
    text = "[REF FALTANTE: a]. Outra. [REF FALTANTE: b multi-word]."
    assert extract_missing_refs(text) == ["a", "b multi-word"]


def test_extract_missing_refs_strips_whitespace() -> None:
    text = "[REF FALTANTE:  with spaces  ]"
    assert extract_missing_refs(text) == ["with spaces"]


def test_extract_missing_refs_empty() -> None:
    assert extract_missing_refs("texto sem placeholders") == []


def test_extract_citekeys_simple() -> None:
    text = "...claim [[@smith2024]]. Outro [[@doe2025]]."
    assert _extract_citekeys_used(text) == ["doe2025", "smith2024"]


def test_extract_citekeys_with_alias() -> None:
    text = "[[@smith2024|Smith et al., 2024]] mostra X."
    assert _extract_citekeys_used(text) == ["smith2024"]


def test_extract_citekeys_dedup() -> None:
    text = "[[@a]] foo [[@a]] bar [[@b]]."
    assert _extract_citekeys_used(text) == ["a", "b"]


def test_extract_citekeys_empty() -> None:
    assert _extract_citekeys_used("sem citekeys") == []
