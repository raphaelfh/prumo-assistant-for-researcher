"""Tests pra auditoria do wiki."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.wiki.lint import lint


def _setup_wiki(tmp_path: Path, bib_text: str = "") -> Path:
    docs = tmp_path / "docs"
    refs = tmp_path / "references"
    refs.mkdir()
    (refs / "_references.bib").write_text(bib_text)
    docs.mkdir()
    for d in ("concepts", "entities", "findings", "sources"):
        (docs / d).mkdir()
    (docs / "_index.md").write_text("---\n---\n")
    (docs / "_log.md").write_text("# log\n")
    return tmp_path


def test_lint_clean_when_minimal_structure(tmp_path: Path) -> None:
    pj = _setup_wiki(tmp_path)
    report = lint(pj)
    assert report["ok"]


def test_lint_flags_missing_docs(tmp_path: Path) -> None:
    report = lint(tmp_path)
    codes = {i["code"] for i in report["issues"]}
    assert "docs_missing" in codes


def test_lint_flags_missing_index_log(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "references").mkdir()
    (tmp_path / "references" / "_references.bib").write_text("")
    report = lint(tmp_path)
    codes = {i["code"] for i in report["issues"]}
    assert "no_index" in codes
    assert "no_log" in codes


def test_lint_flags_broken_citekey(tmp_path: Path) -> None:
    pj = _setup_wiki(tmp_path, "@article{real,title={X}}\n")
    (pj / "docs" / "findings" / "f1.md").write_text(
        "---\ntype: finding\n---\n\nSee [[@nonexistent]] and [[@real]].\n"
    )
    report = lint(pj)
    codes = {i["code"] for i in report["issues"]}
    assert "broken_citekey" in codes


def test_lint_flags_no_frontmatter_in_typed_dirs(tmp_path: Path) -> None:
    pj = _setup_wiki(tmp_path)
    (pj / "docs" / "concepts" / "c1.md").write_text("# concept without frontmatter\n")
    report = lint(pj)
    codes = {i["code"] for i in report["issues"]}
    assert "no_frontmatter" in codes


def test_lint_flags_orphan_pages(tmp_path: Path) -> None:
    pj = _setup_wiki(tmp_path)
    (pj / "docs" / "concepts" / "alpha.md").write_text("---\ntype: concept\n---\n\nbody\n")
    (pj / "docs" / "concepts" / "beta.md").write_text(
        "---\ntype: concept\n---\n\nLinks to [[alpha]].\n"
    )
    report = lint(pj)
    pages_orphans = [i["page"] for i in report["issues"] if i["code"] == "orphan_page"]
    assert "beta" in pages_orphans
    assert "alpha" not in pages_orphans  # alpha é referenciada por beta
