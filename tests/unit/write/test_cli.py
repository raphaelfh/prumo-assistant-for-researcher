"""Integration tests para `prumo write *` (prep/draft)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from prumo_assist.cli import app

runner = CliRunner()


def _last_json(stdout: str) -> dict[str, object]:
    last: dict[str, object] | None = None
    for line in stdout.splitlines():
        try:
            last = json.loads(line)
        except json.JSONDecodeError:
            continue
    assert last is not None, f"nenhum JSON na saída: {stdout!r}"
    return last


def test_write_prep_emits_inputs_and_template(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    result = runner.invoke(app, ["write", "prep", "--kind", "paper", "--path", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    out = _last_json(result.stdout)
    assert "inputs" in out
    assert "template_path" in out


def test_write_prep_invalid_kind_fails(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    result = runner.invoke(app, ["write", "prep", "--kind", "bogus", "--path", str(pj)])
    assert result.exit_code == 1
    assert "--kind" in result.output


def test_write_draft_drafts_mode_writes_file(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    draft = "# Paper\n\n## Introduction\n\nReal-world evidence."
    result = runner.invoke(
        app,
        [
            "write",
            "draft",
            "--kind",
            "paper",
            "--mode",
            "drafts",
            "--date",
            "2026-06-14",
            "--slug",
            "rwe-paper",
            "--sections",
            '["Introduction"]',
            "--path",
            str(pj),
            "--json",
        ],
        input=draft,
    )
    assert result.exit_code == 0, result.output
    out = _last_json(result.stdout)
    written = Path(str(out["output_path"]))
    assert written.exists()
    assert "Real-world evidence." in written.read_text(encoding="utf-8")


def test_write_draft_invalid_mode_fails(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    result = runner.invoke(
        app,
        [
            "write",
            "draft",
            "--kind",
            "paper",
            "--mode",
            "bogus",
            "--date",
            "2026-06-14",
            "--slug",
            "x",
            "--path",
            str(pj),
        ],
        input="conteúdo",
    )
    assert result.exit_code == 1
    assert "--mode" in result.output
