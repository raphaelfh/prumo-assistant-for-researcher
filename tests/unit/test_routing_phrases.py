"""A lista-ouro de roteamento aponta só para modos que existem (spec 2026-09-12, F1).

O roteamento em si é medido à mão no Desktop — este teste só impede que a lista
apodreça quando um modo muda de nome, e que ela vire eco das frases do frontmatter.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from par.core.paths import resolve_resource
from par.core.skills import load_skill_registry

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "routing_phrases.toml"


def test_lista_ouro_cobre_todos_os_modos_com_frases_ineditas() -> None:
    casos = tomllib.loads(_FIXTURE.read_text(encoding="utf-8"))["case"]
    registry, _ = load_skill_registry(resolve_resource("skills"))
    frases_frontmatter = {p for _, m in registry.iter_modes() for p in m.phrases}

    assert len(casos) == 30
    assert sum(1 for c in casos if c.get("needs_mode_file")) == 5
    for caso in casos:
        assert registry.resolve(caso["expected"]) is not None, caso
        assert caso["phrase"] not in frases_frontmatter, caso["phrase"]
    cobertos = {c["expected"] for c in casos}
    assert cobertos == {ref.slug for ref, _ in registry.iter_modes()}
