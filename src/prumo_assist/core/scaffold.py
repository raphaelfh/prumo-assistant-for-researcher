"""Scaffold compartilhado: overlay de templates + descoberta de módulos.

Extraído do ``cli.py`` para que ``init`` e ``add`` reusem a mesma lógica
(regra da ARCHITECTURE: ``cli.py`` é fachada fina, sem lógica de negócio).
"""

from __future__ import annotations

import shutil
from pathlib import Path


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
