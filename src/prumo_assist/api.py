"""API Python pública — superfície estável a partir de v0.2.0.

Hoje é praticamente vazia (PR0 só tem fundação). A medida que os domínios
forem migrados, expomos:

    from prumo_assist import api

    api.paper.list(project="pj_x")
    api.paper.extract("@key", project="pj_x")
    api.wiki.lint(project="pj_x")
    api.write.export("ch3.qmd", to="pdf")

**Garantia de API**: tudo que está exposto aqui segue SemVer. Quebras só em
major bumps; deprecations sempre com 1 minor de antecedência. Tudo dentro de
módulos com prefixo ``_`` é interno e pode mudar sem aviso.

No PR0 expomos apenas o necessário pra notebooks descobrirem o registry de
skills sem importar do CLI.
"""

from __future__ import annotations

from pathlib import Path

from prumo_assist._version import __version__
from prumo_assist.core.skills import SkillRegistry, load_skill_registry
from prumo_assist.domains.paper import api as paper

__all__ = ["__version__", "paper", "skills"]


def skills(skills_dir: Path | None = None, *, strict: bool = False) -> SkillRegistry:
    """Retorna o ``SkillRegistry`` da fonte do plugin.

    Modo tolerante por default (``strict=False``): skills malformadas são
    silenciosamente ignoradas — notebooks costumam querer "o que dá pra usar
    agora" mais do que falhar fechado. Use ``strict=True`` em CI/evals.

    Args:
        skills_dir: override pra testes; default detecta automaticamente.
        strict: se ``True``, qualquer ``SKILL.md`` malformado levanta
            ``ManifestError``.
    """
    if skills_dir is None:
        # Mesmo locator do CLI; mantido aqui pra evitar import circular.
        pkg_root = Path(__file__).resolve().parent
        candidates = [
            pkg_root.parent.parent / "skills",
            pkg_root / "_skills",
        ]
        for c in candidates:
            if c.is_dir():
                skills_dir = c
                break
        else:
            return SkillRegistry(skills={})
    registry, _warnings = load_skill_registry(skills_dir, strict=strict)
    return registry
