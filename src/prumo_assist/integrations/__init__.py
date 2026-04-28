"""Integrations — adapters que instalam skills/comandos em agent-hosts.

Cada agent-host (Claude Code, Cursor, Codex, Gemini, ...) tem convenções
diferentes de onde colocar skills e como registrar slash commands. Esses
adapters traduzem o **único formato canônico** (``SKILL.md`` em ``skills/``)
pra cada um, sem que a lógica de domínio precise saber.

Padrão (spec-kit-style): a CLI sempre conhece todas as integrations
disponíveis via ``REGISTRY``; ``prumo init`` aceita ``--integration <key>``.

No MVP só ``claude_code`` está implementado. Cursor/Codex/Gemini entram em
fase 4 quando houver demanda real (YAGNI até lá).
"""

from __future__ import annotations

from prumo_assist.integrations.base import BaseIntegration
from prumo_assist.integrations.claude_code import ClaudeCodeIntegration

REGISTRY: dict[str, type[BaseIntegration]] = {
    "claude_code": ClaudeCodeIntegration,
}

__all__ = ["REGISTRY", "BaseIntegration", "ClaudeCodeIntegration"]
