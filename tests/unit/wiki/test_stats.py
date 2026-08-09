"""Tests pra contagem de páginas do wiki, por escopo (``docs/studies/<slug>/``)."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.wiki.stats import stats


def _project(root: Path) -> Path:
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / ".claude" / "pj_config.toml").write_text("", encoding="utf-8")
    return root


def _scope(root: Path, slug: str) -> Path:
    s = root / "docs" / "studies" / slug
    for sub in ("notes", "writing", "decisions"):
        (s / sub).mkdir(parents=True, exist_ok=True)
    return s


def test_stats_returns_zero_for_missing_dirs(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    report = stats(tmp_path)
    assert report["totals"]["pages"] == 0


def test_stats_mantem_by_type_e_ganha_by_scope(tmp_path: Path) -> None:
    root = _project(tmp_path)
    a = _scope(root, "a")
    (a / "notes" / "n.md").write_text("x" * 10, encoding="utf-8")
    d = root / "docs" / "references" / "papers" / "silva2020"
    d.mkdir(parents=True)
    (d / "_meta.md").write_text("y" * 20, encoding="utf-8")

    out = stats(root)
    assert out["by_type"]["references"]["pages"] == 1
    assert out["by_scope"]["a"]["notes"]["pages"] == 1


def test_stats_by_scope_cobre_writing_e_decisions(tmp_path: Path) -> None:
    root = _project(tmp_path)
    a = _scope(root, "a")
    (a / "writing" / "draft.md").write_text("w" * 5, encoding="utf-8")
    (a / "decisions" / "d1.md").write_text("d" * 5, encoding="utf-8")

    out = stats(root)
    assert out["by_scope"]["a"]["writing"]["pages"] == 1
    assert out["by_scope"]["a"]["decisions"]["pages"] == 1
    assert out["totals"]["pages"] == 2


def test_stats_references_sem_diretorio_e_zero(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _scope(root, "a")
    out = stats(root)
    assert out["by_type"]["references"] == {"pages": 0, "bytes": 0}


def test_stats_multiplos_escopos_agregam_totals(tmp_path: Path) -> None:
    root = _project(tmp_path)
    a = _scope(root, "a")
    b = _scope(root, "b")
    (a / "notes" / "n1.md").write_text("x" * 3, encoding="utf-8")
    (b / "notes" / "n2.md").write_text("y" * 4, encoding="utf-8")

    out = stats(root)
    assert out["by_scope"]["a"]["notes"]["pages"] == 1
    assert out["by_scope"]["b"]["notes"]["pages"] == 1
    assert out["totals"]["pages"] == 2
    assert out["totals"]["bytes"] == 7
