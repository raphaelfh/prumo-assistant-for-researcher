"""Tests para archive_as_finding (extraído de wiki-query SKILL.md)."""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist.domains.wiki.findings import archive_as_finding


def _bootstrap(tmp_path: Path) -> Path:
    pj = tmp_path / "pj_demo"
    docs = pj / "docs"
    docs.mkdir(parents=True)
    (docs / "_index.md").write_text("# Wiki\n\n## Findings\n\n_(vazio)_\n")
    (docs / "_log.md").write_text("# Log\n")
    return pj


def test_archive_creates_finding_in_default_location(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    out = archive_as_finding(
        pj_path=pj,
        slug="curvas-roc-limiar",
        title="Curvas ROC e escolha de limiar",
        body="Sintetiza que exchangeability quebra; a correção C compensa.",
        sources=["[[@hanley1982roc]]", "[[concepts/curvas-roc]]"],
        date="2026-05-03",
    )
    assert out.exists()
    assert out.name == "curvas-roc-limiar.md"
    text = out.read_text()
    assert text.startswith("---\n")
    assert "id: curvas-roc-limiar" in text
    assert "type: finding" in text
    assert "Curvas ROC e escolha de limiar" in text
    assert "exchangeability quebra" in text


def test_archive_uses_extended_wiki_when_dir_exists(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    (pj / "docs" / "wiki" / "findings").mkdir(parents=True)
    out = archive_as_finding(
        pj_path=pj,
        slug="x",
        title="T",
        body="B",
        sources=[],
        date="2026-05-03",
    )
    assert "wiki" in out.parts
    assert out == pj / "docs" / "wiki" / "findings" / "x.md"


def test_archive_falls_back_to_docs_findings(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    out = archive_as_finding(
        pj_path=pj,
        slug="y",
        title="T",
        body="B",
        sources=[],
        date="2026-05-03",
    )
    assert out == pj / "docs" / "findings" / "y.md"


def test_archive_updates_index(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    archive_as_finding(
        pj_path=pj,
        slug="my-finding",
        title="My Finding",
        body="B",
        sources=[],
        date="2026-05-03",
    )
    index_text = (pj / "docs" / "_index.md").read_text()
    assert "[[my-finding]]" in index_text or "[[findings/my-finding]]" in index_text


def test_archive_appends_log(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    archive_as_finding(
        pj_path=pj,
        slug="my-finding",
        title="My Finding",
        body="B",
        sources=["[[@a]]"],
        date="2026-05-03",
        generator="active-learning",
    )
    log_text = (pj / "docs" / "_log.md").read_text()
    assert "2026-05-03" in log_text
    assert "active-learning" in log_text
    assert "my-finding" in log_text


def test_archive_yaml_includes_tags(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    out = archive_as_finding(
        pj_path=pj,
        slug="z",
        title="T",
        body="B",
        sources=[],
        date="2026-05-03",
        tags=["curvas-roc", "mnar"],
    )
    assert "tags:" in out.read_text()


def test_archive_idempotent_overwrite(tmp_path: Path) -> None:
    pj = _bootstrap(tmp_path)
    archive_as_finding(
        pj_path=pj,
        slug="x",
        title="T1",
        body="B1",
        sources=[],
        date="2026-05-03",
    )
    archive_as_finding(
        pj_path=pj,
        slug="x",
        title="T2",
        body="B2",
        sources=[],
        date="2026-05-03",
    )
    out = pj / "docs" / "findings" / "x.md"
    text = out.read_text()
    assert "T2" in text
    assert "B2" in text
    assert "T1" not in text


def test_archive_raises_when_pj_invalid(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        archive_as_finding(
            pj_path=tmp_path / "nope",
            slug="x",
            title="T",
            body="B",
            sources=[],
            date="2026-05-03",
        )


def test_archive_stamps_generator_in_frontmatter(tmp_path: Path) -> None:
    import yaml

    from prumo_assist.domains.wiki.findings import archive_as_finding

    (tmp_path / "docs").mkdir()
    out = archive_as_finding(
        pj_path=tmp_path,
        slug="q1",
        title="Q1",
        body="body",
        sources=["[[@a]]"],
        date="2026-05-30",
        generator="wiki-query",
    )
    text = out.read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("---", 2)[1])
    assert fm["generator"] == "wiki-query"
