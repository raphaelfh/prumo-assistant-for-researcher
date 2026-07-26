"""Contrato da hierarquia de erros do domínio paper (spec 2026-07-26)."""

from __future__ import annotations

import pytest

from prumo_assist import PrumoError
from prumo_assist.domains.paper import connect, verify
from prumo_assist.domains.paper.errors import PaperError

_PAPER_LEAVES = (
    connect.ZoteroOfflineError,
    connect.CollectionNotFoundError,
    connect.AmbiguousCollectionError,
    connect.AlreadyConnectedError,
    connect.UnsupportedCollectionNameError,
    verify.RefcheckerUnavailableError,
)


@pytest.mark.parametrize("leaf", _PAPER_LEAVES)
def test_leaf_is_paper_error_and_prumo_error(leaf: type[Exception]) -> None:
    assert issubclass(leaf, PaperError)
    assert issubclass(leaf, PrumoError)
