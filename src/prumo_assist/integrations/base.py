"""Interface ``BaseIntegration`` — contrato pra adapters de agent-host.

DRY: toda a lógica de "qual skill, em que versão, com qual prompt" vive em
``core/skills.py`` (registry universal). A integration é só um **transformador**:

    SkillRegistry  ──[install(target_dir)]──>  layout específico do host

Adicionar Cursor amanhã = subclassar isto, escrever em ``.cursor/rules/``,
registrar em ``integrations/__init__.py::REGISTRY``. Zero mudança em
``domains/``, ``core/``, ou nas próprias skills.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from prumo_assist.core.skills import SkillRegistry


@dataclass(frozen=True)
class InstallReport:
    """Resultado da instalação de um conjunto de skills num agent-host."""

    integration: str
    target_dir: Path
    installed: list[str]
    skipped: list[tuple[str, str]]  # [(skill_name, reason)]


class BaseIntegration(ABC):
    """Contrato comum a todos os agent-hosts (claude_code, cursor, codex, ...)."""

    name: str  # subclasses devem definir

    @abstractmethod
    def install(self, target_dir: Path, registry: SkillRegistry) -> InstallReport:
        """Escreve skills do ``registry`` no layout específico do host.

        Args:
            target_dir: diretório raiz do projeto (``pj_*``).
            registry: skills disponíveis pra instalar.
        """
        raise NotImplementedError

    @abstractmethod
    def doctor(self, target_dir: Path) -> list[str]:
        """Health-check: retorna lista de problemas encontrados (vazia = OK)."""
        raise NotImplementedError
