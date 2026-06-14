"""Testa os helpers de I/O de CLI (leitura de stdin + parse de array JSON)."""

from __future__ import annotations

import io

import pytest

from prumo_assist import PrumoError
from prumo_assist.core import cli_io


def test_read_stdin_text_retorna_corpo() -> None:
    assert cli_io.read_stdin_text(io.StringIO("# título\n\ncorpo")) == "# título\n\ncorpo"


def test_read_stdin_text_vazio_e_permitido() -> None:
    assert cli_io.read_stdin_text(io.StringIO("")) == ""


def test_read_stdin_json_parseia_objeto() -> None:
    assert cli_io.read_stdin_json(io.StringIO('{"a": 1}')) == {"a": 1}


def test_read_stdin_json_vazio_levanta_prumoerror() -> None:
    with pytest.raises(PrumoError, match="payload JSON ausente"):
        cli_io.read_stdin_json(io.StringIO("  \n "))


def test_read_stdin_json_invalido_levanta_prumoerror() -> None:
    with pytest.raises(PrumoError, match="JSON inválido"):
        cli_io.read_stdin_json(io.StringIO("{nao é json}"))


def test_read_stdin_json_nao_objeto_levanta_prumoerror() -> None:
    with pytest.raises(PrumoError, match="objeto"):
        cli_io.read_stdin_json(io.StringIO("[1, 2, 3]"))


def test_parse_json_list_ok() -> None:
    assert cli_io.parse_json_list('["[[@a]]", "[[@b]]"]', "--sources") == ["[[@a]]", "[[@b]]"]


def test_parse_json_list_default_vazio() -> None:
    assert cli_io.parse_json_list("[]", "--tags") == []


def test_parse_json_list_nao_array_levanta_prumoerror() -> None:
    with pytest.raises(PrumoError, match="--tags deve ser um array JSON"):
        cli_io.parse_json_list('{"x": 1}', "--tags")
