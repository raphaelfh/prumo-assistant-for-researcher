"""Parse/emit das 5 marcas CriticMarkup (substrato da ponte docx↔CriticMarkup)."""

from __future__ import annotations

import pytest

from prumo_assist.core.criticmarkup import Mark, emit, parse


def test_parse_insertion() -> None:
    marks = parse("antes {++novo texto++} depois")
    assert marks == [Mark(kind="ins", start=6, end=22, a="", b="novo texto")]


def test_parse_deletion() -> None:
    marks = parse("a {--removido--} b")
    assert marks == [Mark(kind="del", start=2, end=16, a="removido", b="")]


def test_parse_substitution() -> None:
    marks = parse("x {~~velho~>novo~~} y")
    assert marks == [Mark(kind="sub", start=2, end=19, a="velho", b="novo")]


def test_parse_highlight_and_comment() -> None:
    marks = parse("{==destaque==}{>>um comentário<<}")
    assert marks == [
        Mark(kind="highlight", start=0, end=14, a="destaque", b=""),
        Mark(kind="comment", start=14, end=33, a="", b="um comentário"),
    ]


def test_parse_multiline_mark() -> None:
    marks = parse("a {++linha1\nlinha2++} b")
    assert marks[0].b == "linha1\nlinha2"


def test_parse_empty_text_no_marks() -> None:
    assert parse("texto sem marcas") == []


def test_parse_unclosed_mark_raises() -> None:
    with pytest.raises(ValueError, match="marca CriticMarkup não fechada"):
        parse("a {++aberta sem fim")


def test_parse_nested_mark_raises() -> None:
    with pytest.raises(ValueError, match="marcas CriticMarkup aninhadas"):
        parse("{++fora {--dentro--} fim++}")


def test_emit_all_kinds() -> None:
    assert emit("ins", b="x") == "{++x++}"
    assert emit("del", a="x") == "{--x--}"
    assert emit("sub", a="a", b="b") == "{~~a~>b~~}"
    assert emit("highlight", a="x") == "{==x==}"
    assert emit("comment", b="c") == "{>>c<<}"


def test_emit_unknown_kind_raises() -> None:
    with pytest.raises(ValueError, match="kind desconhecido"):
        emit("bogus", a="x")


def test_parse_emit_roundtrip() -> None:
    text = "a " + emit("del", a="x") + emit("ins", b="y") + " b"
    kinds = [m.kind for m in parse(text)]
    assert kinds == ["del", "ins"]
