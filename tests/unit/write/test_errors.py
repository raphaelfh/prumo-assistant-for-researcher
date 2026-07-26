"""Contrato da hierarquia de erros do domínio write (spec 2026-07-26)."""

from __future__ import annotations

import pytest

from prumo_assist import PrumoError
from prumo_assist.domains.write import export, review
from prumo_assist.domains.write.errors import WriteError

_WRITE_LEAVES = (
    export.ZoteroNotRunningError,
    export.PandocFailedError,
    export.ZoteroCitekeyNotFoundError,
    export.MissingBibliographyPlaceholderError,
    export.MissingZoteroPrefsError,
    export.MissingFieldLockError,
    export.CiteMapMismatchError,
    export.CorruptDocxError,
    review.SourceChangedError,
    review.StructuralChangeError,
    review.MarkLostError,
    review.CitationConservationError,
    review.AdeuUnavailableError,
)


@pytest.mark.parametrize("leaf", _WRITE_LEAVES)
def test_leaf_is_write_error_and_prumo_error(leaf: type[Exception]) -> None:
    assert issubclass(leaf, WriteError)
    assert issubclass(leaf, PrumoError)


def test_tool_not_found_stays_builtin() -> None:
    """``ToolNotFoundError`` herda de builtin DE PROPÓSITO — capturada via
    ``catches=(FileNotFoundError,)`` nas fachadas."""
    assert issubclass(export.ToolNotFoundError, FileNotFoundError)
    assert not issubclass(export.ToolNotFoundError, PrumoError)
