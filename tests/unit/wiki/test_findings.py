"""Tests para archive_as_finding (extraído de wiki-query SKILL.md).

Finding não tem diretório próprio: é uma nota com procedência em
``<escopo>/notes/``, distinguida pelo ``type: finding`` do frontmatter
(ADR-0023). ``_index.md``/``_log.md`` continuam do PROJETO, resolvidos a
partir do escopo via ``find_pj_root``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from par.core.pj_layout import PjRootNotFoundError
from par.domains.wiki.findings import archive_as_finding


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
        slug="conformal-prediction-mnar",
        title="Conformal prediction sob MNAR",
        body="Sintetiza que exchangeability quebra; IPW corrige.",
        sources=["[@vovk2005algorithmic]", "[[conformal-prediction]]"],
        date="2026-05-03",
    )
    assert out.exists()
    assert out.name == "conformal-prediction-mnar.md"
    text = out.read_text()
    assert text.startswith("---\n")
    assert "id: conformal-prediction-mnar" in text
    assert "type: finding" in text
    assert "Conformal prediction sob MNAR" in text
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
        tags=["conformal", "mnar"],
    )
    assert "tags:" in out.read_text()


def test_archive_idempotent_overwrite(tmp_path: Path) -> None:
    root = _project(tmp_path)
    scope = _scope(root, "a")
    archive_as_finding(
        scope=scope,
        slug="x",
        title="titulo-antigo",
        body="corpo-antigo",
        sources=[],
        date="2026-05-03",
    )
    archive_as_finding(
        scope=scope,
        slug="x",
        title="titulo-novo",
        body="corpo-novo",
        sources=[],
        date="2026-05-03",
    )
    text = (scope / "notes" / "x.md").read_text()
    assert "titulo-novo" in text
    assert "corpo-novo" in text
    assert "titulo-antigo" not in text
    assert "corpo-antigo" not in text


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


def test_archive_stamps_meta_in_frontmatter(tmp_path: Path) -> None:
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
        generator="wiki/study",
    )
    text = out.read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("---", 2)[1])
    assert "generator" not in fm
    assert fm["_meta"]["skill"] == "wiki/study"
    assert fm["_meta"]["schema"] == "finding"
    assert {"run_id", "timestamp_utc", "prumo_version"} <= fm["_meta"].keys()


def test_default_generator_e_log_passam_no_wiki_lint(tmp_path: Path) -> None:
    import yaml

    from par.domains.wiki.lint import LOG_PREFIX_RE

    root = _project(tmp_path)
    scope = _scope(root, "a")
    out = archive_as_finding(
        scope=scope, slug="d1", title="D1", body="b", sources=[], date="2026-09-12"
    )
    fm = yaml.safe_load(out.read_text(encoding="utf-8").split("---", 2)[1])
    assert fm["_meta"]["skill"] == "wiki/query"
    entradas = [
        ln
        for ln in (root / "docs" / "_log.md").read_text(encoding="utf-8").splitlines()
        if ln.startswith("## ")
    ]
    assert entradas and all(LOG_PREFIX_RE.match(ln) for ln in entradas), entradas
