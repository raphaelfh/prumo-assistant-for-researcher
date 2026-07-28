"""Tests pro grafo passivo de citação."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.paper.graph import extract_citekeys, update_graph


def test_extract_citekeys_dedups_and_orders() -> None:
    body = "See [@a] then [@b] then [@a] again."
    out = extract_citekeys(body, known={"a", "b", "c"})
    assert out == ["a", "b"]


def test_extract_citekeys_filters_unknown() -> None:
    body = "Cite [@a] and [@nonexistent]."
    out = extract_citekeys(body, known={"a"})
    assert out == ["a"]


def test_extract_citekeys_excludes_self() -> None:
    body = "Cite [@self] and [@other]."
    out = extract_citekeys(body, known={"self", "other"}, self_citekey="self")
    assert out == ["other"]


def test_extract_citekeys_accepts_pandoc_forms() -> None:
    body = "Baseia-se em [@a2020] e cita @b2021 [p. 3] além de [@c2022]."
    known = {"a2020", "b2021", "c2022", "unused"}
    assert extract_citekeys(body, known) == ["a2020", "b2021", "c2022"]


def test_extract_citekeys_filters_unknown_and_self() -> None:
    body = "[@self2020] e [@known2021] e [@ghost2022]"
    assert extract_citekeys(body, {"self2020", "known2021"}, "self2020") == ["known2021"]


def test_update_graph_populates_cites(tmp_path: Path) -> None:
    notes = tmp_path / "references" / "notes"
    notes.mkdir(parents=True)
    for key, content in [
        ("a", "---\nid: a\n---\n\nSee [@b] and [@c].\n"),
        ("b", "---\nid: b\n---\n\nNothing here.\n"),
        ("c", "---\nid: c\n---\n\nReplies to [@b].\n"),
    ]:
        note_dir = notes / key
        note_dir.mkdir(parents=True, exist_ok=True)
        (note_dir / "_meta.md").write_text(content)

    report = update_graph(tmp_path)
    assert report["edges_added"] == 3  # a→b, a→c, c→b
    assert report["edges_removed"] == 0

    import yaml

    a_meta = yaml.safe_load((notes / "a" / "_meta.md").read_text().split("---")[1])
    assert sorted(a_meta["cites"]) == ["b", "c"]
