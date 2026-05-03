"""Resolução de recursos empacotados (templates, skills, ...).

Os mesmos arquivos podem ser acessados em duas formas:

- **Pacote instalado**: ``prumo_assist/_<name>/`` dentro do wheel (via
  ``[tool.hatch.build.targets.wheel.force-include]``).
- **Dev / editable**: ``<repo_root>/<name>/`` ao lado de ``src/``.

Esta função encontra o path certo nas duas formas, pra que cada caller
(CLI, API pública) não reimplemente o lookup.
"""

from __future__ import annotations

import importlib.resources as ir
from pathlib import Path

from prumo_assist import ConfigError


def resolve_resource(name: str) -> Path:
    """Localiza ``<name>/`` empacotado ou no worktree. Levanta se ausente."""
    found = find_resource(name)
    if found is None:
        raise ConfigError(
            f"Recurso '{name}' não encontrado (nem empacotado nem no worktree). "
            "Reinstale o pacote ou rode a partir do repo de desenvolvimento."
        )
    return found


def find_resource(name: str) -> Path | None:
    """Como ``resolve_resource`` mas retorna ``None`` quando o recurso não existe.

    Útil pra fluxos opcionais — ``skills/`` é opcional (CLI deve seguir mesmo
    que esteja ausente), ``templates/`` é obrigatório.
    """
    # 1. Pacote instalado: prumo_assist/_<name>/
    try:
        packaged = ir.files("prumo_assist") / f"_{name}"
        if packaged.is_dir():
            return Path(str(packaged))
    except (ModuleNotFoundError, AttributeError, NotADirectoryError):
        pass

    # 2. Fallback dev: <repo_root>/<name>/
    pkg_root = Path(__file__).resolve().parent.parent  # src/prumo_assist
    candidates = [
        pkg_root.parent.parent / name,  # src/prumo_assist/../../<name>
        pkg_root.parent / name,  # editable layouts mais rasos
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None
