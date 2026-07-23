"""Span-map lossless do normalizador (Fase 1 da ponte — Export instrumentado §1)."""

from __future__ import annotations

from itertools import pairwise

from prumo_assist.core.obsidian import SpanFragment, normalize_markdown, normalize_markdown_with_map


def _check_invariants(source: str, norm: str, frags: list[SpanFragment]) -> None:
    assert frags, "mapa vazio"
    assert frags[0].source_start == 0
    assert frags[-1].source_end == len(source)
    for prev, cur in pairwise(frags):
        assert prev.source_end == cur.source_start
        assert prev.norm_end == cur.norm_start
    assert "".join(norm[f.norm_start : f.norm_end] for f in frags) == norm
    for f in frags:
        if f.kind == "identity":
            assert source[f.source_start : f.source_end] == norm[f.norm_start : f.norm_end]


def test_identity_only_text() -> None:
    src = "prosa pura sem nada especial\n"
    norm, frags = normalize_markdown_with_map(src)
    assert norm == src
    _check_invariants(src, norm, frags)
    assert [f.kind for f in frags] == ["identity"]


def test_citation_fragment_mapped() -> None:
    src = "antes [[@smith2020]] depois"
    norm, frags = normalize_markdown_with_map(src)
    assert norm == "antes [@smith2020] depois"
    _check_invariants(src, norm, frags)
    cit = [f for f in frags if f.kind == "citation"]
    assert len(cit) == 1
    assert src[cit[0].source_start : cit[0].source_end] == "[[@smith2020]]"
    assert norm[cit[0].norm_start : cit[0].norm_end] == "[@smith2020]"


def test_wikilink_alias_and_blockid_anchor() -> None:
    src = "veja [[Conceito|o conceito]] aqui ^abc123\n"
    norm, frags = normalize_markdown_with_map(src)
    assert norm == "veja o conceito aqui\n"
    _check_invariants(src, norm, frags)
    kinds = [f.kind for f in frags]
    assert "wikilink" in kinds
    anchor = next(f for f in frags if f.kind == "block-id")
    assert anchor.norm_start == anchor.norm_end  # âncora de largura zero


def test_code_block_is_atomic_and_untouched() -> None:
    src = "a\n```\n[[@nao_toca]] [[nem_isto]]\n```\nb"
    norm, frags = normalize_markdown_with_map(src)
    assert "[[@nao_toca]]" in norm
    _check_invariants(src, norm, frags)
    assert any(f.kind == "code" for f in frags)


def test_callout_header_with_and_without_title() -> None:
    src = "> [!note] Titulo\n> corpo\n> [!tip]\n> resto\n"
    norm, frags = normalize_markdown_with_map(src)
    assert norm == "> **Titulo**\n> corpo\n> resto\n"
    _check_invariants(src, norm, frags)


def test_wrapper_behavior_unchanged() -> None:
    src = "x [[@k]] [[A|b]] ^id\n"
    assert normalize_markdown(src) == normalize_markdown_with_map(src)[0]
