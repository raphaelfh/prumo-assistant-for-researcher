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


def test_paper_sync_creates_notes(tmp_path: Path) -> None:
    pj = _bootstrap_project(
        tmp_path,
        "@article{smith2024,\n  title = {Combinado Fusion},\n  year = 2024\n}\n",
    )
    result = runner.invoke(app, ["paper", "sync", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    payload = _last_json(result.stdout)
    assert payload["created"] == 1
    assert (pj / "references" / "notes" / "smith2024.md").is_file()


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
