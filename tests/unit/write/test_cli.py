"""Integration tests para `prumo write *` (prep/draft)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from prumo_assist.cli import app
from prumo_assist.domains.write import export, review
from prumo_assist.domains.write.schemas.v1 import (
    ReviewComment,
    ReviewCommentsFile,
    ReviewEvent,
    ReviewEventsFile,
)

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


def _fake_ingest_result(review_md: Path) -> review.IngestResult:
    events = ReviewEventsFile(
        page="docs/p.md",
        events=[
            ReviewEvent(
                kind="citation-drop",
                detail="citação (occ occ1, citekeys k2020) deletada no Word — confirme no apply.",
                occ_id="occ1",
                citekeys=["k2020"],
            ),
            ReviewEvent(kind="non-identity-span", detail="marca não localizada."),
        ],
    )
    comments = ReviewCommentsFile(
        page="docs/p.md",
        comments=[ReviewComment(id="c1", author="Alice", text="ver isso")],
    )
    return review.IngestResult(
        review_md=review_md,
        marks_applied=3,
        events=events,
        comments=comments,
        deleted=[],
    )


def test_write_review_ingest_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pj = tmp_path / "pj_demo"
    page = pj / "docs" / "p.md"
    page.parent.mkdir(parents=True)
    page.write_text("Texto revisado.\n")
    docx = tmp_path / "reviewed.docx"
    docx.write_bytes(b"PK\x03\x04")
    review_md = pj / "reviews" / "p" / "review.md"

    def fake_ingest(
        reviewed_docx: Path, page_arg: Path, project_root: Path | None = None
    ) -> review.IngestResult:
        return _fake_ingest_result(review_md)

    monkeypatch.setattr("prumo_assist.domains.write.cli.review.ingest", fake_ingest)
    monkeypatch.setenv("COLUMNS", "300")  # evita quebra de linha do Rich no path longo

    plain = runner.invoke(app, ["write", "review", "ingest", str(docx), "--page", str(page)])
    assert plain.exit_code == 0, plain.output
    assert f"ingerido: {review_md}" in plain.output
    assert "3" in plain.output  # marcas aplicadas
    assert "apply" in plain.output  # próximo passo menciona o comando apply

    result = runner.invoke(
        app, ["write", "review", "ingest", str(docx), "--page", str(page), "--json"]
    )
    assert result.exit_code == 0, result.output
    out = _last_json(result.stdout)
    assert out["marks_applied"] == 3
    assert out["events"] == 2
    assert out["comments"] == 1
    assert out["pending_drops"] == 1
    assert out["review_md"] == str(review_md)


def test_write_review_ingest_source_changed_shows_clean_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = tmp_path / "p.md"
    page.write_text("Texto.\n")
    docx = tmp_path / "reviewed.docx"
    docx.write_bytes(b"PK\x03\x04")

    def fake_ingest(*args: object, **kwargs: object) -> review.IngestResult:
        raise review.SourceChangedError("fonte mudou desde o export — mensagem teste")

    monkeypatch.setattr("prumo_assist.domains.write.cli.review.ingest", fake_ingest)
    result = runner.invoke(app, ["write", "review", "ingest", str(docx), "--page", str(page)])
    assert result.exit_code == 1
    assert "mensagem teste" in result.output
    assert "Traceback" not in result.output


def test_write_review_apply_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    page = tmp_path / "p.md"
    page.write_text("Texto.\n")

    def fake_apply(page_arg: Path, **kwargs: object) -> review.ApplyResult:
        return review.ApplyResult(page=page_arg, applied=2, rejected=1, drops_confirmed=["occ1"])

    monkeypatch.setattr("prumo_assist.domains.write.cli.review.apply_review", fake_apply)
    result = runner.invoke(
        app,
        ["write", "review", "apply", "--page", str(page), "--accept-all", "--json"],
    )
    assert result.exit_code == 0, result.output
    out = _last_json(result.stdout)
    assert out["applied"] == 2
    assert out["rejected"] == 1
    assert out["drops_confirmed"] == ["occ1"]


def test_write_review_apply_missing_drop_confirmation_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = tmp_path / "p.md"
    page.write_text("Texto.\n")

    def fake_apply(*args: object, **kwargs: object) -> review.ApplyResult:
        raise ValueError(
            "Evento(s) `citation-drop` pendente(s) sem confirmação explícita "
            "(I6 — decisão humana explícita em Git): occ occ1."
        )

    monkeypatch.setattr("prumo_assist.domains.write.cli.review.apply_review", fake_apply)
    result = runner.invoke(app, ["write", "review", "apply", "--page", str(page), "--accept-all"])
    assert result.exit_code == 1
    assert "citation-drop" in result.output
    assert "Traceback" not in result.output


def test_write_review_apply_accept_and_reject_conflict_exits_cleanly(
    tmp_path: Path,
) -> None:
    page = tmp_path / "p.md"
    page.write_text("Texto.\n")

    result = runner.invoke(
        app,
        ["write", "review", "apply", "--page", str(page), "--mark", "0", "--accept", "--reject"],
    )
    assert result.exit_code == 1
    assert "mutuamente exclusivos" in result.output
    assert "Traceback" not in result.output


def test_write_review_apply_mark_without_decision_exits_cleanly(
    tmp_path: Path,
) -> None:
    page = tmp_path / "p.md"
    page.write_text("Texto.\n")

    result = runner.invoke(app, ["write", "review", "apply", "--page", str(page), "--mark", "0"])
    assert result.exit_code == 1
    assert "--mark exige" in result.output
    assert "Traceback" not in result.output


def test_write_review_events_list_plain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pj = tmp_path / "pj_demo"
    page = pj / "docs" / "p.md"
    page.parent.mkdir(parents=True)
    page.write_text("Texto.\n")
    # Create project root marker
    (pj / "references").mkdir()
    (pj / "references" / "_references.bib").write_text("")
    review_dir = pj / "reviews" / "p"
    review_dir.mkdir(parents=True)
    (review_dir / "events.yaml").write_text(
        "page: docs/p.md\nevents:\n  - kind: citation-drop\n    detail: 'citação (occ occ1, citekeys k2020) deletada no Word — confirme no apply.'\n    occ_id: occ1\n    citekeys: [k2020]\n  - kind: unanchored\n    detail: 'marca não localizada no corpo normalizado — edite manualmente ou aguarde'\n  - kind: citation-touched\n    detail: 'decisão humana: edite a fonte'\n"
    )
    monkeypatch.setenv("COLUMNS", "300")

    result = runner.invoke(app, ["write", "review", "events", "--page", str(page)])
    assert result.exit_code == 0, result.output
    assert "citation-drop" in result.output
    assert "unanchored" in result.output
    assert "citation-touched" in result.output
    # Verify detail resumido is present and truncated (~80 chars)
    assert "deletada no Word" in result.output
    assert "não localizada" in result.output


def test_write_review_events_checklist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pj = tmp_path / "pj_demo"
    page = pj / "docs" / "p.md"
    page.parent.mkdir(parents=True)
    page.write_text("Texto.\n")
    # Create project root marker
    (pj / "references").mkdir()
    (pj / "references" / "_references.bib").write_text("")
    review_dir = pj / "reviews" / "p"
    review_dir.mkdir(parents=True)
    (review_dir / "events.yaml").write_text(
        "page: docs/p.md\nevents:\n  - kind: citation-drop\n    detail: 'citação (occ occ1, citekeys k2020) deletada'\n    occ_id: occ1\n    citekeys: [k2020]\n  - kind: unanchored\n    detail: 'marca não localizada'\n  - kind: ambiguous\n    detail: 'múltiplas localizações possíveis'\n  - kind: citation-touched\n    detail: 'decisão humana'\n"
    )

    result = runner.invoke(app, ["write", "review", "events", "--page", str(page), "--checklist"])
    assert result.exit_code == 0, result.output
    # Verify checklist format: numbered, pt-BR, with ACÇÃOs per kind
    assert "1." in result.output or "1 " in result.output  # Numbered
    assert "citation-drop" in result.output
    assert "--confirm-citation-drops" in result.output
    assert "unanchored" in result.output
    assert "edite review.md" in result.output or "review-reconcile" in result.output
    assert "ambiguous" in result.output
    assert "citation-touched" in result.output
    assert "decisão humana" in result.output


def test_write_review_events_missing_sidecars_exits_cleanly(tmp_path: Path) -> None:
    pj = tmp_path / "pj_demo"
    page = pj / "docs" / "p.md"
    page.parent.mkdir(parents=True)
    page.write_text("Texto.\n")
    # Create project root marker
    (pj / "references").mkdir()
    (pj / "references" / "_references.bib").write_text("")
    # No review dir created, so events.yaml is missing

    result = runner.invoke(app, ["write", "review", "events", "--page", str(page)])
    assert result.exit_code == 1
    assert "Traceback" not in result.output  # Clean error
    assert "events.yaml" in result.output or "ausente" in result.output
