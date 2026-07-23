"""Integration tests para `prumo write *` (prep/draft)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from prumo_assist.cli import app
from prumo_assist.domains.write import export

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


def _pj_with_bib(tmp_path: Path) -> tuple[Path, Path]:
    pj = tmp_path / "pj_demo"
    (pj / "references").mkdir(parents=True)
    (pj / "references" / "_references.bib").write_text("@article{k2020, title={T}}\n")
    page = pj / "docs" / "p.md"
    page.parent.mkdir(parents=True)
    page.write_text("Texto.\n")
    return pj, page


def test_write_export_docx_prints_first_use_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pj, page = _pj_with_bib(tmp_path)
    fake_out = pj / "build" / "exports" / "p.docx"
    monkeypatch.setattr("prumo_assist.domains.write.cli.export.export", lambda **kw: fake_out)
    result = runner.invoke(app, ["write", "export", str(page), "--to", "docx"])
    assert result.exit_code == 0, result.output
    assert "Primeiro uso no Word" in result.output


def test_write_export_html_omits_first_use_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pj, page = _pj_with_bib(tmp_path)
    fake_out = pj / "build" / "exports" / "p.html"
    monkeypatch.setattr("prumo_assist.domains.write.cli.export.export", lambda **kw: fake_out)
    result = runner.invoke(app, ["write", "export", str(page), "--to", "html"])
    assert result.exit_code == 0, result.output
    assert "Primeiro uso no Word" not in result.output


def test_write_export_corrupt_docx_shows_clean_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, page = _pj_with_bib(tmp_path)

    def _boom(**kw: object) -> Path:
        raise export.CorruptDocxError("docx inválido após retry — mensagem teste")

    monkeypatch.setattr("prumo_assist.domains.write.cli.export.export", _boom)
    result = runner.invoke(app, ["write", "export", str(page), "--to", "docx"])
    assert result.exit_code == 1
    assert "mensagem teste" in result.output
    assert "Traceback" not in result.output


def test_write_compose_docx_prints_first_use_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pj, _page = _pj_with_bib(tmp_path)
    index = pj / "docs" / "index.md"
    index.write_text("---\npages: [docs/p.md]\n---\n")
    fake_out = pj / "build" / "exports" / "index.docx"
    monkeypatch.setattr("prumo_assist.domains.write.cli.export.compose", lambda **kw: fake_out)
    result = runner.invoke(app, ["write", "compose", "--index", str(index), "--to", "docx"])
    assert result.exit_code == 0, result.output
    assert "Primeiro uso no Word" in result.output


def test_write_compose_corrupt_docx_shows_clean_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pj, _page = _pj_with_bib(tmp_path)
    index = pj / "docs" / "index.md"
    index.write_text("---\npages: [docs/p.md]\n---\n")

    def _boom(**kw: object) -> Path:
        raise export.CorruptDocxError("compose docx inválido — mensagem teste")

    monkeypatch.setattr("prumo_assist.domains.write.cli.export.compose", _boom)
    result = runner.invoke(app, ["write", "compose", "--index", str(index), "--to", "docx"])
    assert result.exit_code == 1
    assert "mensagem teste" in result.output
    assert "Traceback" not in result.output


def test_write_export_zotero_down_shows_clean_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, page = _pj_with_bib(tmp_path)

    def _boom(**kw: object) -> Path:
        raise export.ZoteroNotRunningError("Zotero fora do ar — mensagem teste")

    monkeypatch.setattr("prumo_assist.domains.write.cli.export.export", _boom)
    result = runner.invoke(app, ["write", "export", str(page), "--to", "docx"])
    assert result.exit_code == 1
    assert "mensagem teste" in result.output
    assert "Traceback" not in result.output


def test_write_compose_missing_refs_placeholder_shows_clean_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pj, _page = _pj_with_bib(tmp_path)
    index = pj / "docs" / "index.md"
    index.write_text("---\npages: [docs/p.md]\n---\n")

    def _boom(**kw: object) -> Path:
        raise export.MissingBibliographyPlaceholderError("sem placeholder — mensagem teste")

    monkeypatch.setattr("prumo_assist.domains.write.cli.export.compose", _boom)
    result = runner.invoke(app, ["write", "compose", "--index", str(index), "--to", "docx"])
    assert result.exit_code == 1
    assert "mensagem teste" in result.output
    assert "Traceback" not in result.output
