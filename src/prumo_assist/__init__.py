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

    ``core/cli_op.cli_run`` captura qualquer ``PrumoError`` nas fachadas
    (mensagem limpa + exit code). Aqui na raiz vivem as cross-cutting
    (ConfigError, ManifestError, IntegrationError); domínio com exceções
    próprias define sua base em ``domains/<X>/errors.py`` (WriteError,
    PaperError)."""


class ConfigError(PrumoError):
    """Configuração ausente, mal-formada ou inválida (pj_config.toml, ~/.prumo/...)."""


class ManifestError(PrumoError):
    """SKILL.md / pack.toml / manifest com frontmatter ou metadata inválido."""


class IntegrationError(PrumoError):
    """Falha ao instalar/configurar uma integration (claude_code, cursor, ...)."""
