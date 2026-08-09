"""Tests para archive_as_finding (extraído de wiki-query SKILL.md).

Finding não tem diretório próprio: é uma nota com procedência em
``<escopo>/notes/``, distinguida pelo ``type: finding`` do frontmatter
(ADR-0023). ``_index.md``/``_log.md`` continuam do PROJETO, resolvidos a
partir do escopo via ``find_pj_root``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from prumo_assist.core.pj_layout import PjRootNotFoundError
from prumo_assist.domains.wiki.findings import archive_as_finding


def _project(root: Path) -> Path:
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "_index.md").write_text("# Wiki\n\n## Findings\n\n_(vazio)_\n")
    (root / "docs" / "_log.md").write_text("# Log\n")
    return root


def _scope(root: Path, slug: str) -> Path:
    s = root / "docs" / "studies" / slug
    for sub in ("notes", "writing", "decisions"):
        (s / sub).mkdir(parents=True, exist_ok=True)
    return s


def test_finding_nasce_em_notes_com_type(tmp_path: Path) -> None:
    root = _project(tmp_path)
    scope = _scope(root, "a")
    out = archive_as_finding(
        scope=scope,
        slug="auc-subgrupo",
        title="AUC",
        body="corpo",
        sources=["[@silva2020]"],
        date="2026-08-09",
    )
    assert out == scope / "notes" / "auc-subgrupo.md"
    assert "type: finding" in out.read_text(encoding="utf-8")
    assert not (root / "docs" / "findings").exists()
    assert not (root / "docs" / "wiki").exists()


def test_archive_creates_finding_with_frontmatter(tmp_path: Path) -> None:
    root = _project(tmp_path)
    scope = _scope(root, "a")
    out = archive_as_finding(
        scope=scope,
        slug="curvas-roc-limiar",
        title="Curvas ROC e escolha de limiar",
        body="Sintetiza que exchangeability quebra; a correção C compensa.",
        sources=["[@hanley1982roc]", "[[concepts/curvas-roc]]"],
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


def test_archive_updates_index(tmp_path: Path) -> None:
    root = _project(tmp_path)
    scope = _scope(root, "a")
    archive_as_finding(
        scope=scope,
        slug="my-finding",
        title="My Finding",
        body="B",
        sources=[],
        date="2026-05-03",
    )
    index_text = (root / "docs" / "_index.md").read_text()
    assert "[[my-finding]]" in index_text


def test_archive_appends_log(tmp_path: Path) -> None:
    root = _project(tmp_path)
    scope = _scope(root, "a")
    archive_as_finding(
        scope=scope,
        slug="my-finding",
        title="My Finding",
        body="B",
        sources=["[@a]"],
        date="2026-05-03",
        generator="active-learning",
    )
    log_text = (root / "docs" / "_log.md").read_text()
    assert "2026-05-03" in log_text
    assert "active-learning" in log_text
    assert "my-finding" in log_text


def test_archive_yaml_includes_tags(tmp_path: Path) -> None:
    root = _project(tmp_path)
    scope = _scope(root, "a")
    out = archive_as_finding(
        scope=scope,
        slug="z",
        title="T",
        body="B",
        sources=[],
        date="2026-05-03",
        tags=["curvas-roc", "mnar"],
    )
    assert "tags:" in out.read_text()


def test_archive_idempotent_overwrite(tmp_path: Path) -> None:
    root = _project(tmp_path)
    scope = _scope(root, "a")
    archive_as_finding(scope=scope, slug="x", title="T1", body="B1", sources=[], date="2026-05-03")
    archive_as_finding(scope=scope, slug="x", title="T2", body="B2", sources=[], date="2026-05-03")
    out = scope / "notes" / "x.md"
    text = out.read_text()
    assert "T2" in text
    assert "B2" in text
    assert "T1" not in text


def test_archive_raises_when_scope_sem_pj_root(tmp_path: Path) -> None:
    # tmp_path não tem .claude/pj_config.toml em nenhum ancestral -> raiz não resolve.
    with pytest.raises(PjRootNotFoundError):
        archive_as_finding(
            scope=tmp_path / "nope",
            slug="x",
            title="T",
            body="B",
            sources=[],
            date="2026-05-03",
        )


def test_archive_stamps_generator_in_frontmatter(tmp_path: Path) -> None:
    import yaml

    root = _project(tmp_path)
    scope = _scope(root, "a")
    out = archive_as_finding(
        scope=scope,
        slug="q1",
        title="Q1",
        body="body",
        sources=["[@a]"],
        date="2026-05-30",
        generator="wiki-query",
    )
    text = out.read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("---", 2)[1])
    assert fm["generator"] == "wiki-query"
