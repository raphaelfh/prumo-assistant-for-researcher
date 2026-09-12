"""Checagem `[dado_versionavel]`: dado bruto e `.prumo/` fora do git."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

from prumo_assist.core import safe_outputs


def _fake_git(
    *, repo: bool = True, ignored: set[str] | None = None, tracked: list[str] | None = None
) -> Callable[..., str | None]:
    ignorados = ignored if ignored is not None else {"content", ".prumo"}
    rastreados = tracked or []

    def fake(root: Path, *args: str) -> str | None:
        if args[0] == "rev-parse":
            return "true" if repo else None
        if args[0] == "check-ignore":
            probe = args[-1]
            return probe if probe.split("/")[0] in ignorados else None
        if args[0] == "ls-files":
            return "\n".join(rastreados)
        raise AssertionError(args)

    return fake


def _issues(tmp_path: Path, fake: Callable[..., str | None]) -> list[str]:
    with patch.object(safe_outputs, "_git", side_effect=fake):
        return safe_outputs.safe_outputs_issues(tmp_path)


def test_fora_de_git_silencia(tmp_path: Path) -> None:
    assert _issues(tmp_path, _fake_git(repo=False, ignored=set())) == []


def test_ignorado_e_limpo_passa(tmp_path: Path) -> None:
    assert _issues(tmp_path, _fake_git()) == []


def test_gitkeep_rastreado_e_tolerado(tmp_path: Path) -> None:
    fake = _fake_git(tracked=["content/01_raw/.gitkeep", "content/02_processed/.gitkeep"])
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
    with patch("prumo_assist.core.safe_outputs.subprocess.run", side_effect=FileNotFoundError):
        assert safe_outputs._git(tmp_path, "rev-parse", "--is-inside-work-tree") is None
