"""Checagem `[dado_versionavel]`: dado bruto e `.prumo/` fora do git."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import pytest

from par.core import safe_outputs


def _fake_git(
    *, repo: bool = True, ignored: set[str] | None = None, tracked: list[str] | None = None
) -> Callable[..., str | None]:
    ignorados = ignored if ignored is not None else {"content", ".prumo"}
    rastreados = tracked or []

    def fake(root: Path, *args: str, ok_codes: tuple[int, ...] = (0,)) -> str | None:
        if not repo:
            return None
        if args[0] == "check-ignore":
            assert ok_codes == (0, 1)
            return "\n".join(p for p in args[1:] if p.split("/")[0] in ignorados)
        if args[0] == "ls-files":
            return "\n".join(rastreados)
        raise AssertionError(args)

    return fake


def _issues(tmp_path: Path, fake: Callable[..., str | None]) -> list[str]:
    with patch.object(safe_outputs, "_git", side_effect=fake):
        return safe_outputs.safe_outputs_issues(tmp_path)


@pytest.mark.parametrize(
    "fake",
    [
        pytest.param(_fake_git(repo=False, ignored=set()), id="fora_de_git_silencia"),
        pytest.param(_fake_git(), id="ignorado_e_limpo_passa"),
        pytest.param(
            _fake_git(tracked=["content/01_raw/.gitkeep", "content/02_processed/.gitkeep"]),
            id="gitkeep_rastreado_e_tolerado",
        ),
    ],
)
def test_sem_issue(tmp_path: Path, fake: Callable[..., str | None]) -> None:
    assert _issues(tmp_path, fake) == []


def test_nao_ignorado_falha(tmp_path: Path) -> None:
    issues = _issues(tmp_path, _fake_git(ignored={"content"}))
    assert len(issues) == 1
    assert issues[0].startswith("[dado_versionavel]")
    assert "`.prumo/`" in issues[0]
    assert ".gitignore" in issues[0]


def test_rastreado_falha_com_comando_de_correcao(tmp_path: Path) -> None:
    issues = _issues(tmp_path, _fake_git(tracked=["content/01_raw/coorte.csv"]))
    assert len(issues) == 1
    assert "content/01_raw/coorte.csv" in issues[0]
    assert "`git rm -r --cached content`" in issues[0]


def test_git_real_ausente_devolve_none(tmp_path: Path) -> None:
    with patch("par.core.safe_outputs.subprocess.run", side_effect=FileNotFoundError):
        assert safe_outputs._git(tmp_path, "ls-files") is None
