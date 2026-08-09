"""Scaffold compartilhado: overlay de templates + descoberta de módulos.

Extraído do ``cli.py`` para que ``init`` e ``add`` reusem a mesma lógica
(regra da ARCHITECTURE: ``cli.py`` é fachada fina, sem lógica de negócio).
"""

from __future__ import annotations

import shutil
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prumo_assist import PrumoError
from prumo_assist.core import pj_layout
from prumo_assist.core.paths import resolve_resource

#: Formas do placeholder de nome usadas em ``templates/pj_base/``
#: (``pj-NOME`` no pyproject.toml, ``pj_<NOME>`` nos títulos markdown).
_NAME_PLACEHOLDERS: tuple[str, ...] = ("pj_<NOME>", "pj-NOME")

#: Segmento de caminho usado por módulos cujo payload é por-escopo (ex.:
#: ``clinical``). ``overlay`` substitui esse segmento pelo slug real antes de
#: copiar; ``is_applied`` faz o mesmo antes de checar o anchor. Ver ADR-0024
#: (escopo é resolvido por posição em ``docs/studies/<slug>/``, sem sentinela).
SCOPE_MARKER = "__scope__"


def _substitute_scope(rel: Path, scope: str) -> Path:
    """Troca o segmento ``__scope__`` de ``rel`` pelo slug real do escopo."""
    return Path(*(scope if part == SCOPE_MARKER else part for part in rel.parts))


def overlay(
    template: Path, target: Path, *, scope: str | None = None
) -> tuple[list[str], list[str]]:
    """Copia ``template/*`` para ``target/`` sem sobrescrever arquivos existentes.

    Retorna ``(copied, skipped)`` com paths relativos ao target. Cria
    diretórios faltantes; ignora arquivos cujo destino já existe.

    Quando o payload do template usa o marcador :data:`SCOPE_MARKER` no
    caminho (módulos por-escopo, ex. ``clinical``), ``scope`` é obrigatório
    — o chamador resolve o slug real (via CLI ou pelo escopo recém-criado no
    ``init``) antes de chamar ``overlay``.
    """
    copied: list[str] = []
    skipped: list[str] = []
    for src in template.rglob("*"):
        rel = src.relative_to(template)
        if scope is not None:
            rel = _substitute_scope(rel, scope)
        elif SCOPE_MARKER in rel.parts:
            raise PrumoError(
                f"{src} usa o marcador de escopo `{SCOPE_MARKER}` mas nenhum escopo foi "
                "resolvido antes do overlay (defeito interno do chamador)."
            )
        dst = target / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        if dst.exists():
            skipped.append(str(rel))
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(str(rel))
    return copied, skipped


def apply_project_name(target: Path, name: str, rel_paths: Iterable[str]) -> list[str]:
    """Substitui os placeholders de nome do template pelo nome real do projeto.

    Opera apenas sobre ``rel_paths`` (arquivos recém-copiados do scaffold) —
    arquivos preservados do usuário em ``--merge`` nunca são reescritos.
    Arquivos binários são ignorados. Retorna os paths relativos alterados.
    """
    changed: list[str] = []
    for rel in rel_paths:
        path = target / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        new_text = text
        for placeholder in _NAME_PLACEHOLDERS:
            new_text = new_text.replace(placeholder, name)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed.append(rel)
    return changed


@dataclass(frozen=True)
class ModuleInfo:
    name: str
    description: str
    when_to_use: str
    anchor: str | None
    path: Path


def _modules_root() -> Path:
    return resolve_resource("templates") / "modules"


def discover_modules() -> list[ModuleInfo]:
    """Lista módulos em ``templates/modules/`` lendo cada ``_module.toml``."""
    root = _modules_root()
    if not root.is_dir():
        return []
    out: list[ModuleInfo] = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        meta: dict[str, Any] = {}
        meta_path = d / "_module.toml"
        if meta_path.is_file():
            with meta_path.open("rb") as f:
                meta = tomllib.load(f)
        out.append(
            ModuleInfo(
                name=d.name,
                description=meta.get("description", ""),
                when_to_use=meta.get("when_to_use", ""),
                anchor=meta.get("anchor"),
                path=d,
            )
        )
    return out


def get_module(name: str) -> ModuleInfo | None:
    for m in discover_modules():
        if m.name == name:
            return m
    return None


def module_requires_scope(module: ModuleInfo) -> bool:
    """``True`` se o payload do módulo usa :data:`SCOPE_MARKER` no caminho.

    Módulos assim (ex. ``clinical``) precisam de um escopo resolvido
    (``docs/studies/<slug>/``) antes de ``overlay`` — ver ``add_command``.
    """
    return any(SCOPE_MARKER in p.relative_to(module.path).parts for p in module.path.rglob("*"))


def is_applied(target: Path, module: ModuleInfo) -> bool:
    """``True`` se o ``anchor`` declarado do módulo existe em ``target``.

    Quando o anchor usa :data:`SCOPE_MARKER`, verifica em QUALQUER escopo
    existente sob ``target/docs/studies/`` — não importa o slug escolhido
    pelo usuário (Task 10 deriva o slug do nome do projeto, não de
    ``"principal"``).
    """
    if not module.anchor:
        return False
    anchor = Path(module.anchor)
    if SCOPE_MARKER not in anchor.parts:
        return (target / anchor).exists()
    return any(
        (target / _substitute_scope(anchor, s.name)).exists() for s in pj_layout.iter_scopes(target)
    )
