"""Tests pro grafo passivo de citação."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.paper.graph import extract_wikilinks, update_graph


def test_extract_wikilinks_dedups_and_orders() -> None:
    body = "See [[@a]] then [[@b]] then [[@a]] again."
    out = extract_wikilinks(body, known={"a", "b", "c"})
    assert out == ["a", "b"]


def test_extract_wikilinks_filters_unknown() -> None:
    body = "Cite [[@a]] and [[@nonexistent]]."
    out = extract_wikilinks(body, known={"a"})
    assert out == ["a"]


def test_extract_wikilinks_excludes_self() -> None:
    body = "Cite [[@self]] and [[@other]]."
    out = extract_wikilinks(body, known={"self", "other"}, self_citekey="self")
    assert out == ["other"]


def test_update_graph_populates_cites(tmp_path: Path) -> None:
    notes = tmp_path / "references" / "notes"
    notes.mkdir(parents=True)
    (notes / "a.md").write_text("---\nid: a\n---\n\nSee [[@b]] and [[@c]].\n")
    (notes / "b.md").write_text("---\nid: b\n---\n\nNothing here.\n")
    (notes / "c.md").write_text("---\nid: c\n---\n\nReplies to [[@b]].\n")

    report = update_graph(tmp_path)
    assert report["edges_added"] == 3  # a→b, a→c, c→b
    assert report["edges_removed"] == 0

    import yaml

    a_meta = yaml.safe_load((notes / "a.md").read_text().split("---")[1])
    assert sorted(a_meta["cites"]) == ["b", "c"]
