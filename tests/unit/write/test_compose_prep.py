"""Testa `write.compose.prep` (compõe read_inputs + resolve_template)."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.write.compose import WritePrep, prep
from prumo_assist.domains.write.schemas.v1 import ComposeInputs


def test_prep_returns_inputs_and_template(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    result = prep(pj, kind="paper")
    assert isinstance(result, WritePrep)
    assert isinstance(result.inputs, ComposeInputs)
    assert result.template_path.name.endswith(".md")
