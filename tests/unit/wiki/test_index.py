"""Tests do wrapper sobre o CLI ``qmd`` (``prumo wiki index``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from par.domains.wiki.index import QmdNotFoundError, reindex


def test_reindex_sem_qmd_ensina_npm(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("par.domains.wiki.index.shutil.which", lambda _: None)
    with pytest.raises(QmdNotFoundError) as exc:
        reindex(tmp_path)
    msg = str(exc.value)
    assert "npm install -g @tobilu/qmd" in msg
    assert "prumo wiki index" in msg
