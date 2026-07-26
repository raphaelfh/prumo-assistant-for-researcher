"""Contrato de ``cli_run``: captura, exit codes e o mapa ``exit_codes`` (spec 2026-07-26)."""

from __future__ import annotations

import pytest
import typer

from prumo_assist import PrumoError
from prumo_assist.core.cli_op import cli_run


class _DomainError(PrumoError):
    """Erro de domínio fake pro contrato."""


class _ChildError(_DomainError):
    """Subclasse pra provar a semântica de primeiro-match por ordem de inserção."""


def test_exit_codes_maps_class_to_code() -> None:
    with pytest.raises(typer.Exit) as excinfo, cli_run(exit_codes={_DomainError: 2}):
        raise _DomainError("zotero fechado")
    assert excinfo.value.exit_code == 2


def test_unmapped_prumo_error_uses_default_exit_code() -> None:
    with pytest.raises(typer.Exit) as excinfo, cli_run(exit_codes={_ChildError: 2}):
        raise _DomainError("erro comum")
    assert excinfo.value.exit_code == 1


def test_mapped_class_is_caught_even_outside_catches() -> None:
    """Classe no mapa entra no conjunto capturado sem precisar repetir em ``catches``."""
    with pytest.raises(typer.Exit) as excinfo, cli_run(exit_codes={ConnectionError: 3}):
        raise ConnectionError("rede caiu")
    assert excinfo.value.exit_code == 3


def test_first_match_wins_by_insertion_order() -> None:
    with (
        pytest.raises(typer.Exit) as excinfo,
        cli_run(exit_codes={_DomainError: 4, _ChildError: 3}),
    ):
        raise _ChildError("filho")
    assert excinfo.value.exit_code == 4


def test_per_command_exit_code_still_applies() -> None:
    """Caso sync-annotations: ``exit_code=2`` pro comando inteiro continua valendo."""
    with pytest.raises(typer.Exit) as excinfo, cli_run(catches=(ConnectionError,), exit_code=2):
        raise ConnectionError("zotero fechado")
    assert excinfo.value.exit_code == 2


def test_unrelated_exception_leaks() -> None:
    """Exceção fora do contrato vaza — é bug, queremos traceback."""
    with pytest.raises(KeyError), cli_run():
        raise KeyError("bug real")
