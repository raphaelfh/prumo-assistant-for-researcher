"""Integration tests do prumo doctor com seção de dependências externas."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from prumo_assist.cli import app
from prumo_assist.core.deps import DepStatus

runner = CliRunner()


def _project(tmp_path: Path) -> Path:
    pj = tmp_path / "pj_x"
    for d in (".claude", "docs", "references"):
        (pj / d).mkdir(parents=True)
    (pj / ".claude" / "skills").mkdir()
    return pj


def test_doctor_json_includes_external_deps(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    fake = [
        DepStatus(name="qmd", present=True, required_by=["wiki-query"], detail="ok", hint=""),
        DepStatus(name="zotero", present=False, required_by=["paper sync-annotations"],
                  detail="down", hint="abra o Zotero"),
    ]
    with patch("prumo_assist.cli.check_external_deps", return_value=fake):
        result = runner.invoke(app, ["doctor", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    names = {d["name"] for d in payload["external_deps"]}
    assert names == {"qmd", "zotero"}


def test_doctor_missing_dep_does_not_fail_exit_code(tmp_path: Path) -> None:
    """Dep externa ausente é informativa: não derruba o exit code (só estrutura derruba)."""
    pj = _project(tmp_path)
    fake = [
        DepStatus(name="qmd", present=False, required_by=["wiki-query"],
                  detail="missing", hint="instale"),
    ]
    with patch("prumo_assist.cli.check_external_deps", return_value=fake):
        result = runner.invoke(app, ["doctor", str(pj), "--json"])
    # estrutura do projeto está OK → exit 0 mesmo com qmd ausente
    assert result.exit_code == 0, result.output


def test_doctor_human_output_shows_missing_dep_hint(tmp_path: Path) -> None:
    pj = _project(tmp_path)
    fake = [
        DepStatus(name="qmd", present=False, required_by=["wiki-query"],
                  detail="qmd não está no PATH", hint="bun install -g @tobilu/qmd"),
    ]
    with patch("prumo_assist.cli.check_external_deps", return_value=fake):
        result = runner.invoke(app, ["doctor", str(pj)])
    assert "qmd" in result.output
    assert "bun install -g @tobilu/qmd" in result.output
