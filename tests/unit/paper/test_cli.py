"""Integration tests pros subcomandos ``prumo paper *``."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from prumo_assist.cli import app

runner = CliRunner()


def _bootstrap_project(tmp_path: Path, bib_text: str) -> Path:
    pj = tmp_path / "pj_demo"
    refs = pj / "references"
    refs.mkdir(parents=True)
    (refs / "_references.bib").write_text(bib_text)
    return pj


def test_paper_sync_creates_meta_md(tmp_path: Path) -> None:
    pj = _bootstrap_project(
        tmp_path,
        "@article{smith2024,\n  title = {Combinado Fusion},\n  year = 2024\n}\n",
    )
    result = runner.invoke(app, ["paper", "sync", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = _last_json(result.stdout)
    assert payload["created"] == 1
    assert (pj / "references" / "notes" / "smith2024" / "_meta.md").is_file()


def test_paper_find_returns_results(tmp_path: Path) -> None:
    pj = _bootstrap_project(
        tmp_path,
        '@article{smith2024,\n  title = {Combi-Nado Fusion},\n  author = "Smith, J.",\n  year = 2024\n}\n',
    )
    runner.invoke(app, ["paper", "sync", str(pj), "--json"])
    result = runner.invoke(app, ["paper", "find", "combinado", "--path", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = _last_json(result.stdout)
    assert payload["query"] == "combinado"
    results = payload["results"]
    assert isinstance(results, list)
    assert any(r["citekey"] == "smith2024" for r in results)


def test_paper_lint_clean_project(tmp_path: Path) -> None:
    pj = _bootstrap_project(tmp_path, "@article{a,title={X}}\n")
    runner.invoke(app, ["paper", "sync", str(pj), "--json"])
    result = runner.invoke(app, ["paper", "lint", str(pj), "--json"])
    assert result.exit_code == 0
    payload = _last_json(result.stdout)
    assert payload["ok"]


def test_paper_set_primary(tmp_path: Path) -> None:
    pj = _bootstrap_project(tmp_path, "@article{a,title={X}}\n@article{b,title={Y}}\n")
    runner.invoke(app, ["paper", "sync", str(pj), "--json"])
    result = runner.invoke(app, ["paper", "set-primary", "a", "--path", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = _last_json(result.stdout)
    assert payload["primary"] == "a"


def _last_json(stdout: str) -> dict[str, object]:
    last: dict[str, object] | None = None
    for line in stdout.splitlines():
        try:
            last = json.loads(line)
        except json.JSONDecodeError:
            continue
    assert last is not None, f"nenhum JSON na saída: {stdout!r}"
    return last


def test_paper_sync_notes_cli_writes_files(tmp_path: Path) -> None:
    from unittest.mock import patch

    pj = tmp_path / "pj_x"
    refs = pj / "references"
    (refs / "notes" / "smith2024").mkdir(parents=True)
    (refs / "_references.bib").write_text("@article{smith2024, title={X}}\n")
    (refs / "notes" / "smith2024" / "_meta.md").write_text("---\nid: smith2024\n---\n\nbody\n")

    note = {
        "itemType": "note",
        "key": "ABCD1234",
        "note": "<h1>Ideia</h1><p>corpo</p>",
        "dateAdded": "2026-04-30T14:23:00Z",
        "dateModified": "2026-05-02T09:11:00Z",
        "tags": [],
    }
    with (
        patch("prumo_assist.domains.paper.zotero.check_zotero_running", return_value=True),
        patch("prumo_assist.domains.paper.zotero.resolve_citekey", return_value=(1, "P1")),
        patch("prumo_assist.domains.paper.zotero.fetch_children", return_value=[note]),
    ):
        result = runner.invoke(app, ["paper", "sync-notes", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    assert (refs / "notes" / "smith2024" / "note__ABCD1234__ideia.md").is_file()


def test_paper_sync_all_cli_runs_offline_sync(tmp_path: Path) -> None:
    from unittest.mock import patch

    pj = tmp_path / "pj_y"
    refs = pj / "references"
    (refs / "notes").mkdir(parents=True)
    (refs / "_references.bib").write_text("@article{smith2024, title={X}}\n")

    with (
        patch("prumo_assist.domains.paper.zotero.check_zotero_running", return_value=False),
    ):
        result = runner.invoke(app, ["paper", "sync-all", str(pj), "--json"])
    # sync (offline) succeeds; annotations/notes skipped with warnings -> exit 0
    assert result.exit_code == 0, result.output
    assert (refs / "notes" / "smith2024" / "_meta.md").is_file()
