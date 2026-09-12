"""Templates de escrita prontos pro Zettlr (frontmatter bibliography + refs div)."""

from __future__ import annotations

from par.core.paths import resolve_resource

# kind → template do modo que declara ``prumo.write_kind``.
TEMPLATES = {
    "paper": "write/templates/manuscript.md",
    "projeto-cep": "protocol/templates/cep.md",
    "statistics": "protocol/templates/sap.md",
    "scientific": "write/templates/section.md",
}


def test_all_write_templates_declare_bibliography() -> None:
    skills = resolve_resource("skills")
    for kind, rel in TEMPLATES.items():
        text = (skills / rel).read_text(encoding="utf-8")
        assert "bibliography: ../../../references/_references.bib" in text, kind


def test_manuscript_templates_have_refs_placeholder() -> None:
    skills = resolve_resource("skills")
    for kind in ("paper", "projeto-cep"):
        text = (skills / TEMPLATES[kind]).read_text(encoding="utf-8")
        assert "::: {#refs}" in text, kind
