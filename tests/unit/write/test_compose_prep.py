"""Testa `write.compose.prep` (compõe read_inputs + resolve_template)."""

from __future__ import annotations

from pathlib import Path

import pytest

from par.domains.write.compose import WritePrep, prep
from par.domains.write.schemas.v1 import ComposeInputs


def test_prep_returns_inputs_and_template(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / ".claude").mkdir(parents=True)
    (pj / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    scope = pj / "docs" / "studies" / "principal"
    scope.mkdir(parents=True)
    result = prep(scope, kind="paper")
    assert isinstance(result, WritePrep)
    assert isinstance(result.inputs, ComposeInputs)
    assert result.template_path.exists()
    assert result.template_path.name == "manuscript.md"


def _scope(tmp_path: Path) -> Path:
    pj = tmp_path / "pj_exemplo"
    (pj / ".claude").mkdir(parents=True)
    (pj / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    scope = pj / "docs" / "studies" / "principal"
    scope.mkdir(parents=True)
    return scope


def test_prep_sem_pasta_do_usuario(tmp_path: Path) -> None:
    result = prep(_scope(tmp_path), kind="paper")

    assert result.template_source == "plugin_default"
    assert result.guides == ()


def test_prep_com_pasta_do_usuario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "xdg" / "prumo"
    (root / "templates").mkdir(parents=True)
    (root / "templates" / "paper.md").write_text(
        "# Template sintético de teste\n", encoding="utf-8"
    )
    (root / "guides" / "paper").mkdir(parents=True)
    guide = root / "guides" / "paper" / "estilo.md"
    guide.write_text("Guia sintética de teste\n", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    result = prep(_scope(tmp_path), kind="paper")

    assert result.template_source == "user_dir"
    assert result.template_path == root / "templates" / "paper.md"
    assert result.guides == (guide,)
