"""Base das exceções do domínio write.

Toda exceção de negócio do domínio herda de :class:`WriteError` — capturada
automaticamente por ``core/cli_op.cli_run`` nas fachadas (mensagem limpa +
exit code). Erro novo no domínio: herde daqui; nenhuma tupla de catch
precisa ser estendida.
"""

from __future__ import annotations

from prumo_assist import PrumoError


class WriteError(PrumoError):
    """Falha de negócio do domínio write (export, review, compose)."""
