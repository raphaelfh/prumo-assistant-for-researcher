"""Tests pra contagem de páginas do wiki."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.wiki.stats import stats


def test_stats_returns_zero_for_missing_dirs(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    report = stats(tmp_path)
    assert report["totals"]["pages"] == 0


def test_stats_counts_per_type(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    for d in ("concepts", "findings"):
        (docs / d).mkdir(parents=True)
    (docs / "concepts" / "a.md").write_text("---\n---\n")
    (docs / "concepts" / "b.md").write_text("---\n---\n")
    (docs / "findings" / "f.md").write_text("---\n---\n")
    report = stats(tmp_path)
    assert report["by_type"]["concepts"]["pages"] == 2
    assert report["by_type"]["findings"]["pages"] == 1
    assert report["totals"]["pages"] == 3
