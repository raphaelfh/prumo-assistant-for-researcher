"""Scaffold compartilhado: overlay de templates + descoberta de módulos.

Extraído do ``cli.py`` para que ``init`` e ``add`` reusem a mesma lógica
(regra da ARCHITECTURE: ``cli.py`` é fachada fina, sem lógica de negócio).
"""

from __future__ import annotations

import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

from prumo_assist.core.paths import resolve_resource


def overlay(template: Path, target: Path) -> tuple[list[str], list[str]]:
    """Copia ``template/*`` para ``target/`` sem sobrescrever arquivos existentes.

    Retorna ``(copied, skipped)`` com paths relativos ao target. Cria
    diretórios faltantes; ignora arquivos cujo destino já existe.
    """
    copied: list[str] = []
    skipped: list[str] = []
    for src in template.rglob("*"):
        rel = src.relative_to(template)
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
        meta: dict = {}
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
