"""Carregador de ``pj_*/.claude/pj_config.toml`` com defaults e validação leve.

Transformado de ``monorepo-anterior/.claude/scripts/_project_config.py``. Mudanças:

- ``ValueError`` → ``ConfigError`` (entra na hierarquia ``PrumoError``).
- Função ``load_project_config`` (nome mais descritivo do que ``load_config``).

Regras de cascata (escala futura, não implementada no MVP):
``CLI flags > pj_config.toml > ~/.config/prumo/config.toml > DEFAULTS``.
Por enquanto só cobrimos os 2 últimos níveis — o que existe hoje.
"""

from __future__ import annotations

import copy
import tomllib
from pathlib import Path
from typing import Any

from prumo_assist import ConfigError

DEFAULTS: dict[str, Any] = {
    "paper_extract": {
        "language": "pt-BR",
        "template": ".claude/paper_extraction.md",
        "batch": {
            "default_limit": 20,
            "subagents_per_wave": 8,
        },
    },
    "wiki": {},
    "citation": {},
}

VALID_LANGUAGES = frozenset({"pt-BR", "en", "es"})


def load_project_config(pj_path: Path) -> dict[str, Any]:
    """Carrega ``pj_*/.claude/pj_config.toml`` mesclado com ``DEFAULTS``.

    Raises:
        ConfigError: se ``paper_extract.language`` não estiver em ``VALID_LANGUAGES``.
    """
    cfg_path = pj_path / ".claude" / "pj_config.toml"
    if not cfg_path.exists():
        return copy.deepcopy(DEFAULTS)
    with cfg_path.open("rb") as f:
        user_cfg = tomllib.load(f)
    merged = _deep_merge(DEFAULTS, user_cfg)
    _validate(merged, cfg_path)
    return merged


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in base.items():
        if isinstance(v, dict):
            overlay_val = overlay.get(k, {})
            out[k] = _deep_merge(v, overlay_val if isinstance(overlay_val, dict) else {})
        else:
            out[k] = v
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            continue
        out[k] = v
    return out


def _validate(cfg: dict[str, Any], source: Path) -> None:
    lang = cfg["paper_extract"]["language"]
    if lang not in VALID_LANGUAGES:
        raise ConfigError(
            f"{source}: paper_extract.language='{lang}' inválido; "
            f"use um de {sorted(VALID_LANGUAGES)}"
        )
