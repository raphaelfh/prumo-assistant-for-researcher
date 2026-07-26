"""Motor único dos runners de ferramenta pinada via ``uvx`` (core/uvx.py).

A escada de tradução de erro em 4 degraus vivia duplicada em
``domains/write/review._run_adeu_extract`` e
``domains/paper/verify._run_refchecker`` (achado do passe /simplify,
2026-07-25). Aqui testa-se o MOTOR (subprocess sempre mockado, regra do
repo); o wording por ferramenta é travado nos testes de cada wrapper
(test_review_adeu.py / test_verify.py).
"""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import patch

import pytest

from prumo_assist.core.uvx import PinnedTool, run_pinned


class _ToolDownError(RuntimeError):
    """Erro de domínio fictício — o motor nunca conhece classes de domínio."""


_TOOL = PinnedTool(
    error_cls=_ToolDownError,
    hint="Instale o uv e confirme: `uvx ferramenta==1.0 --version`.",
    missing_label="ferramenta (pinada, `uvx ferramenta==1.0`)",
    timeout_label="ferramenta",
    timeout_detail="rede lenta? Re-rode.",
    exit_label="ferramenta (`uvx ferramenta==1.0`)",
)

_ARGV = ["uvx", "ferramenta==1.0", "--json"]


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> Any:
    return subprocess.CompletedProcess(
        args=_ARGV, returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_run_pinned_success_returns_completed_process() -> None:
    with patch("prumo_assist.core.uvx.subprocess.run", return_value=_completed(stdout="ok")) as run:
        proc = run_pinned(_TOOL, _ARGV, timeout=120)
    assert proc.stdout == "ok"
    run.assert_called_once_with(_ARGV, capture_output=True, text=True, timeout=120)


def test_run_pinned_uvx_missing_raises_error_cls_with_hint() -> None:
    with (
        patch("prumo_assist.core.uvx.subprocess.run", side_effect=FileNotFoundError("uvx")),
        pytest.raises(_ToolDownError) as exc,
    ):
        run_pinned(_TOOL, _ARGV, timeout=120)
    message = str(exc.value)
    assert message == (
        "uv/uvx não encontrado no PATH — ferramenta (pinada, `uvx ferramenta==1.0`) "
        "não pode ser invocado. Instale o uv e confirme: `uvx ferramenta==1.0 --version`."
    )
    assert isinstance(exc.value.__cause__, FileNotFoundError)


def test_run_pinned_timeout_raises_error_cls_with_detail() -> None:
    with (
        patch(
            "prumo_assist.core.uvx.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="uvx", timeout=120),
        ),
        pytest.raises(_ToolDownError) as exc,
    ):
        run_pinned(_TOOL, _ARGV, timeout=120)
    assert str(exc.value) == (
        "ferramenta excedeu 120s — rede lenta? Re-rode. "
        "Instale o uv e confirme: `uvx ferramenta==1.0 --version`."
    )


def test_run_pinned_nonzero_exit_raises_with_stderr_tail() -> None:
    stderr = "x" * 3000 + "FIM"
    with (
        patch("prumo_assist.core.uvx.subprocess.run", return_value=_completed(1, stderr=stderr)),
        pytest.raises(_ToolDownError) as exc,
    ):
        run_pinned(_TOOL, _ARGV, timeout=120)
    message = str(exc.value)
    assert message.startswith("ferramenta (`uvx ferramenta==1.0`) terminou com exit 1. stderr:\n")
    # cauda de 2000 chars do stderr strip-ado, nunca o stderr inteiro
    assert "FIM" in message
    assert stderr.strip()[-2000:] in message
    assert stderr not in message
    assert message.endswith("Instale o uv e confirme: `uvx ferramenta==1.0 --version`.")


def test_run_pinned_zero_exit_never_raises_even_with_stderr() -> None:
    """Exit 0 com stderr barulhento passa direto — quem decide sobre o
    conteúdo é o wrapper (ex.: refchecker sai 0 mesmo com erros)."""
    with patch(
        "prumo_assist.core.uvx.subprocess.run",
        return_value=_completed(0, stdout="{}", stderr="warning: barulho"),
    ):
        proc = run_pinned(_TOOL, _ARGV, timeout=5)
    assert proc.returncode == 0
