"""Resolução de recursos empacotados (templates, skills, ...).

Os mesmos arquivos podem ser acessados em duas formas:

- **Pacote instalado**: ``par/_<name>/`` dentro do wheel (via
  ``[tool.hatch.build.targets.wheel.force-include]``).
- **Dev / editable**: ``<repo_root>/<name>/`` ao lado de ``src/``.

``find_resource`` encontra o path certo nas duas formas, pra que cada caller
(CLI, API pública) não reimplemente o lookup.

Fora do plugin existe ainda a **pasta do usuário** (``user_dir``, ADR-0045): a
base de conhecimento pessoal do pesquisador, opcional. Este módulo só diz onde
ela fica; o que há dentro é assunto dos domínios.
"""

from __future__ import annotations

import importlib.resources as ir
import os
from pathlib import Path

from par import ConfigError


def resolve_resource(name: str) -> Path:
    """Localiza ``<name>/`` empacotado ou no worktree. Levanta se ausente."""
    found = find_resource(name)
    if found is None:
        raise ConfigError(
            f"Recurso '{name}' não encontrado (nem empacotado nem na raiz do "
            "plugin). Reinstale o plugin (no app: + → Plugins → Gerenciar plugins; "
            "no terminal: /plugin uninstall par e /plugin install "
            "par@prumo-assistant-for-researcher) e abra uma sessão nova. Em "
            "desenvolvimento, rode a partir do repositório: uv run prumo …"
        )
    return found


def find_resource(name: str) -> Path | None:
    """Como ``resolve_resource`` mas retorna ``None`` quando o recurso não existe.

    Útil pra fluxos opcionais — ``skills/`` é opcional (CLI deve seguir mesmo
    que esteja ausente), ``templates/`` é obrigatório.
    """
    # 1. Pacote instalado: par/_<name>/
    try:
        packaged = ir.files("par") / f"_{name}"
        if packaged.is_dir():
            return Path(str(packaged))
    except (ModuleNotFoundError, AttributeError, NotADirectoryError):
        pass

    # 2. Fallback dev: <repo_root>/<name>/
    pkg_root = Path(__file__).resolve().parent.parent  # src/par
    candidates = [
        pkg_root.parent.parent / name,  # src/par/../../<name>
        pkg_root.parent / name,  # editable layouts mais rasos
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def user_dir_location() -> Path:
    """Onde a pasta do usuário fica, exista ou não: ``$XDG_CONFIG_HOME/prumo`` (padrão ``~/.config/prumo``)."""
    return Path(os.environ.get("XDG_CONFIG_HOME") or "~/.config").expanduser() / "prumo"


def user_dir() -> Path | None:
    """Pasta de conteúdo pessoal (``user_dir_location``), se existir.

    Pode ser um symlink para onde a base de conhecimento já mora (ADR-0045).
    """
    base = user_dir_location()
    return base if base.is_dir() else None
