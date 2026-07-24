"""Integration tests pros subcomandos ``prumo paper *``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
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


def test_paper_extract_prep_emits_language(tmp_path: Path) -> None:
    from tests.unit.paper.test_prep import _bootstrap

    pj = _bootstrap(tmp_path)
    result = runner.invoke(app, ["paper", "extract-prep", "smith2020", str(pj), "--json"])
    assert result.exit_code == 0, result.output
    out = _last_json(result.stdout)
    assert out["language"] == "pt-BR"
    assert Path(str(out["meta_path"])).exists()


def test_paper_extract_applies_content_from_stdin(tmp_path: Path) -> None:
    from tests.unit.paper.test_prep import _bootstrap

    pj = _bootstrap(tmp_path)
    # template com 1 seção pra apply_extraction popular (### = nível que o parser reconhece):
    (pj / ".claude" / "paper_extraction.md").write_text(
        "### Resumo\n<!-- instrução -->\n", encoding="utf-8"
    )
    body = json.dumps({"Resumo": "Estudo de coorte sobre RWE."})
    result = runner.invoke(
        app,
        [
            "paper",
            "extract",
            "smith2020",
            "--model",
            "claude-x",
            "--date",
            "2026-06-14",
            str(pj),
            "--json",
        ],
        input=body,
    )
    assert result.exit_code == 0, result.output
    out = _last_json(result.stdout)
    assert out["changed"] is True
    extract_md = pj / "references" / "notes" / "smith2020" / "_extract.md"
    assert extract_md.exists()
    assert "Estudo de coorte" in extract_md.read_text(encoding="utf-8")


def test_paper_extract_idempotent_second_apply_reports_unchanged(tmp_path: Path) -> None:
    from tests.unit.paper.test_prep import _bootstrap

    pj = _bootstrap(tmp_path)
    (pj / ".claude" / "paper_extraction.md").write_text(
        "### Resumo\n<!-- instrução -->\n", encoding="utf-8"
    )
    body = json.dumps({"Resumo": "Estudo de coorte sobre RWE."})
    args = [
        "paper",
        "extract",
        "smith2020",
        "--model",
        "claude-x",
        "--date",
        "2026-06-14",
        str(pj),
        "--json",
    ]
    first = runner.invoke(app, args, input=body)
    assert first.exit_code == 0, first.output
    assert _last_json(first.stdout)["changed"] is True
    second = runner.invoke(app, args, input=body)
    assert second.exit_code == 0, second.output
    assert _last_json(second.stdout)["changed"] is False


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
    # Verify JSON payload has null sub-reports for offline syncs
    payload = _last_json(result.stdout)
    assert payload["annotations"] is None
    assert payload["notes"] is None
    assert isinstance(payload["warnings"], list) and payload["warnings"]


def _fake_report(pj: Path, **overrides: Any) -> dict[str, Any]:
    report: dict[str, Any] = {
        "pj": str(pj),
        "page": None,
        "scope": ["a1"],
        "checked": 1,
        "findings": [],
        "summary": {"errors": 0, "warnings": 0, "infos": 0},
        "deep": False,
    }
    report.update(overrides)
    return report


def test_verify_refs_ok_exit_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = _fake_report(tmp_path)

    def fake(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return report

    monkeypatch.setattr("prumo_assist.domains.paper.verify.verify_refs", fake)
    result = runner.invoke(app, ["paper", "verify-refs", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "verificada" in result.output


def test_verify_refs_erro_exit_um(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = _fake_report(
        tmp_path,
        findings=[
            {
                "citekey": "a1",
                "level": "error",
                "kind": "retracted",
                "message": "RETRATADO: reavalie a citação.",
                "source": "crossref",
            },
        ],
        summary={"errors": 1, "warnings": 0, "infos": 0},
    )

    def fake(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return report

    monkeypatch.setattr("prumo_assist.domains.paper.verify.verify_refs", fake)
    result = runner.invoke(app, ["paper", "verify-refs", str(tmp_path)])
    assert result.exit_code == 1
    assert "a1" in result.output and "retracted" in result.output


def test_verify_refs_repassa_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake(
        pj_path: Path,
        *,
        page: Path | None = None,
        deep: bool = False,
        refresh: bool = False,
        cache_path: Path | None = None,
    ) -> dict[str, Any]:
        captured.update(pj=pj_path, page=page, deep=deep, refresh=refresh)
        return _fake_report(pj_path, scope=[], checked=0, deep=deep)

    monkeypatch.setattr("prumo_assist.domains.paper.verify.verify_refs", fake)
    pagina = tmp_path / "p.md"
    pagina.write_text("x", encoding="utf-8")
    result = runner.invoke(
        app,
        ["paper", "verify-refs", str(tmp_path), "--page", str(pagina), "--deep", "--refresh"],
    )
    assert result.exit_code == 0, result.output
    assert captured["deep"] is True and captured["refresh"] is True
    assert captured["page"] == pagina.resolve()


def test_verify_refs_bib_ausente_mensagem_limpa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise FileNotFoundError("_references.bib não existe — Better BibTeX export?")

    monkeypatch.setattr("prumo_assist.domains.paper.verify.verify_refs", fake)
    result = runner.invoke(app, ["paper", "verify-refs", str(tmp_path)])
    assert result.exit_code == 1
    assert "Better BibTeX" in result.output
