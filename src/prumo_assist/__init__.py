"""prumo-assist — knowledge, bibliography & academic writing for clinical research.

API pública (estável a partir de v0.2.0):

    from prumo_assist import api
    api.paper.list(project="pj_x")

Tudo dentro de submódulos com prefixo `_` é interno e pode mudar sem aviso.
"""

from __future__ import annotations

from prumo_assist._version import __version__

__all__ = ["ConfigError", "IntegrationError", "ManifestError", "PrumoError", "__version__"]


class PrumoError(Exception):
    """Raiz da hierarquia de exceções de prumo-assist.

    Subclasses específicas por domínio (ConfigError, ManifestError, ...) facilitam
    handlers mais granulares. Quando um domínio crescer pra ≥3 exceções próprias,
    extrai pra `core/errors.py` (ainda não justifica)."""


class ConfigError(PrumoError):
    """Configuração ausente, mal-formada ou inválida (pj_config.toml, ~/.prumo/...)."""


class ManifestError(PrumoError):
    """SKILL.md / pack.toml / manifest com frontmatter ou metadata inválido."""


class IntegrationError(PrumoError):
    """Falha ao instalar/configurar uma integration (claude_code, cursor, ...)."""
