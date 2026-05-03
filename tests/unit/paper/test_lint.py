"""Tests pra auditoria do paper."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.paper.lint import lint, set_primary


def _setup_project(tmp_path: Path, bib_text: str = "") -> Path:
    refs = tmp_path / "references"
    (refs / "notes").mkdir(parents=True)
    (refs / "pdfs").mkdir(parents=True)
    (refs / "_references.bib").write_text(bib_text)
    return tmp_path


def test_lint_clean_when_consistent(tmp_path: Path) -> None:
    pj = _setup_project(tmp_path, "@article{a,title={x}}\n@article{b,title={y}}\n")
    notes = pj / "references" / "notes"
    (notes / "a.md").write_text("---\nid: a\n---\n\n")
    (notes / "b.md").write_text("---\nid: b\n---\n\n")
    report = lint(pj)
    assert report["ok"]
    assert report["summary"]["errors"] == 0


def test_lint_flags_orphan_note(tmp_path: Path) -> None:
    pj = _setup_project(tmp_path, "@article{a,title={x}}\n")
    notes = pj / "references" / "notes"
    (notes / "a.md").write_text("---\nid: a\n---\n\n")
    (notes / "orphan.md").write_text("---\nid: orphan\n---\n\n")
    report = lint(pj)
    codes = {i["code"] for i in report["issues"]}
    assert "orphan_note" in codes


def test_lint_flags_id_mismatch(tmp_path: Path) -> None:
    pj = _setup_project(tmp_path, "@article{realkey,title={x}}\n")
    notes = pj / "references" / "notes"
    (notes / "realkey.md").write_text("---\nid: WRONG\n---\n\n")
    report = lint(pj)
    codes = {i["code"] for i in report["issues"]}
    assert "id_mismatch" in codes
    assert not report["ok"]  # id_mismatch é error


def test_lint_flags_broken_pdf_link(tmp_path: Path) -> None:
    pj = _setup_project(tmp_path, "@article{a,title={x}}\n")
    notes = pj / "references" / "notes"
    (notes / "a.md").write_text("---\nid: a\n---\n\n")
    pdfs = pj / "references" / "pdfs"
    (pdfs / "a.pdf").symlink_to("/nonexistent/file.pdf")
    report = lint(pj)
    codes = {i["code"] for i in report["issues"]}
    assert "broken_pdf_link" in codes


def test_lint_flags_multiple_primaries(tmp_path: Path) -> None:
    pj = _setup_project(tmp_path, "@article{a,title={x}}\n@article{b,title={y}}\n")
    notes = pj / "references" / "notes"
    (notes / "a.md").write_text("---\nid: a\nrole: primary\n---\n\n")
    (notes / "b.md").write_text("---\nid: b\nrole: primary\n---\n\n")
    report = lint(pj)
    codes = {i["code"] for i in report["issues"]}
    assert "multiple_primaries" in codes


def test_lint_bib_missing_returns_error(tmp_path: Path) -> None:
    report = lint(tmp_path)
    assert not report["ok"]
    codes = {i["code"] for i in report["issues"]}
    assert "bib_missing" in codes


def test_set_primary_clears_others(tmp_path: Path) -> None:
    pj = _setup_project(tmp_path, "@article{a,title={x}}\n@article{b,title={y}}\n")
    notes = pj / "references" / "notes"
    (notes / "a.md").write_text("---\nid: a\nrole: primary\n---\n\nbody\n")
    (notes / "b.md").write_text('---\nid: b\nrole: ""\n---\n\nbody\n')

    report = set_primary(pj, "b")
    assert report["primary"] == "b"
    assert "a" in report["cleared_from"]

    import yaml

    a_meta = yaml.safe_load((notes / "a.md").read_text().split("---")[1])
    b_meta = yaml.safe_load((notes / "b.md").read_text().split("---")[1])
    assert a_meta["role"] == ""
    assert b_meta["role"] == "primary"


def test_set_primary_raises_if_note_missing(tmp_path: Path) -> None:
    pj = _setup_project(tmp_path)
    import pytest

    with pytest.raises(FileNotFoundError):
        set_primary(pj, "nonexistent")
