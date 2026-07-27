"""Base das exceções do domínio paper.

Toda exceção de negócio do domínio herda de :class:`PaperError` — capturada
automaticamente por ``core/cli_op.cli_run`` nas fachadas (mensagem limpa +
exit code). Erro novo no domínio: herde daqui; nenhuma tupla de catch
precisa ser estendida.
"""

from __future__ import annotations

from prumo_assist import PrumoError


class PaperError(PrumoError):
    """Falha de negócio do domínio paper (sync, connect, verify, ...)."""


class ZoteroApiError(PaperError):
    """A API local do Zotero respondeu com erro HTTP (403, 400, 404, ...).

    Existe para que ``HTTPError`` **nunca** vire lista vazia: "0 anotações"
    indistinguível de "sem anotações" foi o defeito que escondeu o
    ``sync-annotations`` quebrado. A mensagem carrega o comando de correção.
    """
