"""Templates write-* prontos pro Zettlr (frontmatter bibliography + refs div)."""

from __future__ import annotations

from prumo_assist.core.paths import resolve_resource

KINDS = ("paper", "projeto-cep", "statistics", "scientific")


def test_all_write_templates_declare_bibliography() -> None:
    skills = resolve_resource("skills")
    for kind in KINDS:
        text = (skills / f"write-{kind}" / "template.md").read_text(encoding="utf-8")
        assert "bibliography: ../../references/_references.bib" in text, kind


def test_manuscript_templates_have_refs_placeholder() -> None:
    skills = resolve_resource("skills")
    for kind in ("paper", "projeto-cep"):
        text = (skills / f"write-{kind}" / "template.md").read_text(encoding="utf-8")
        assert "::: {#refs}" in text, kind
