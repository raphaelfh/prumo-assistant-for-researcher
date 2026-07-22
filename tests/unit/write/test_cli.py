"""Integration tests para `prumo write *` (prep/draft)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
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


def test_write_draft_into_mode_inserts_block(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    target = pj / "docs" / "existing.md"
    target.write_text("# Existing\n\nSome intro.\n", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "write",
            "draft",
            "--kind",
            "paper",
            "--mode",
            "into",
            "--into",
            str(target),
            "--section",
            "Methods",
            "--date",
            "2026-06-14",
            "--slug",
            "x",
            "--path",
            str(pj),
            "--json",
        ],
        input="Methods content here.",
    )
    assert result.exit_code == 0, result.output
    out = _last_json(result.stdout)
    assert Path(str(out["output_path"])) == target
    text = target.read_text(encoding="utf-8")
    assert "write:begin kind=paper section=Methods" in text
    assert "Methods content here." in text


def test_write_draft_invalid_kind_fails(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    (pj / "docs").mkdir(parents=True)
    result = runner.invoke(
        app,
        [
            "write",
            "draft",
            "--kind",
            "bogus",
            "--mode",
            "drafts",
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
    assert "--kind" in result.output


def test_zettlr_entry_calls_canonical_docx_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = tmp_path / "draft.md"
    page.write_text("x")
    called: dict[str, object] = {}

    def fake_export(*, page: Path, to: str = "docx", **kwargs: object) -> Path:
        called["page"] = page
        called["to"] = to
        return tmp_path / "out.docx"

    monkeypatch.setattr("prumo_assist.domains.write.cli.export.export", fake_export)
    monkeypatch.setattr("sys.argv", ["prumo-zettlr-export", str(page)])
    from prumo_assist.domains.write.cli import zettlr_export_entry

    zettlr_export_entry()
    assert called == {"page": page.resolve(), "to": "docx"}


def test_zettlr_entry_export_error_exits_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = tmp_path / "draft.md"
    page.write_text("x")

    def fake_export(*, page: Path, to: str = "docx", **kwargs: object) -> Path:
        raise FileNotFoundError("bibliografia não encontrada: x")

    monkeypatch.setattr("prumo_assist.domains.write.cli.export.export", fake_export)
    monkeypatch.setattr("sys.argv", ["prumo-zettlr-export", str(page)])
    from prumo_assist.domains.write.cli import zettlr_export_entry

    with pytest.raises(SystemExit) as exc:
        zettlr_export_entry()
    assert exc.value.code == 1


def test_zettlr_entry_usage_error_exits_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["prumo-zettlr-export"])
    from prumo_assist.domains.write.cli import zettlr_export_entry

    with pytest.raises(SystemExit) as exc:
        zettlr_export_entry()
    assert exc.value.code == 1


def test_export_command_reports_citekey_error_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from prumo_assist.domains.write.export import ZoteroCitekeyNotFoundError

    page = tmp_path / "draft.md"
    page.write_text("x")

    def fake_export(**kwargs: object) -> Path:
        raise ZoteroCitekeyNotFoundError(
            "1 citekey(s) não existem no .bib: ghost2020. Rode `make sync-paper`."
        )

    monkeypatch.setattr("prumo_assist.domains.write.cli.export.export", fake_export)
    monkeypatch.setattr(
        "prumo_assist.domains.write.cli.export.detect_project_root", lambda p: tmp_path
    )
    result = runner.invoke(app, ["write", "export", str(page), "--to", "docx"])
    assert result.exit_code == 1
    assert "ghost2020" in result.output
    assert "Traceback" not in result.output
