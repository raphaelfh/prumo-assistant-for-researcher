"""Testa `write.compose.prep` (compõe read_inputs + resolve_template)."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.write.compose import WritePrep, prep
from prumo_assist.domains.write.schemas.v1 import ComposeInputs


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
    assert result.template_path.name == "template.md"
