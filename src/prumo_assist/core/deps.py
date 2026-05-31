"""Detecção de dependências externas do ecossistema prumo.

prumo orquestra ferramentas que vivem fora do pacote Python:

- **qmd** — servidor MCP de busca (BM25+vector+rerank) que as skills
  ``wiki-query``, ``wiki-ingest`` e ``active-learning`` consomem. Binário no PATH.
- **Zotero + Better BibTeX** — fonte de bibliografia/anotações. Expõe API local
  HTTP em ``127.0.0.1:23119`` quando o app está aberto.

Este módulo é puramente declarativo: retorna ``DepStatus`` por dependência.
Quem decide o que fazer (warning, erro, JSON) é o ``doctor``. Centralizar aqui
evita espalhar ``shutil.which`` e checagem de porta pelo CLI.
"""

from __future__ import annotations

import shutil
import socket
from dataclasses import dataclass

ZOTERO_HOST = "127.0.0.1"
ZOTERO_PORT = 23119


@dataclass
class DepStatus:
    """Estado de uma dependência externa."""

    name: str
    present: bool
    required_by: list[str]
    detail: str
    hint: str

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "present": self.present,
            "required_by": self.required_by,
            "detail": self.detail,
            "hint": self.hint,
        }


def _binary_on_path(name: str) -> str | None:
    """Caminho do binário no PATH, ou ``None``. Seam testável."""
    return shutil.which(name)


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """``True`` se há algo escutando em ``host:port``. Seam testável."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_external_deps() -> list[DepStatus]:
    """Audita dependências externas. Nunca levanta — sempre retorna a lista."""
    statuses: list[DepStatus] = []

    qmd_path = _binary_on_path("qmd")
    statuses.append(
        DepStatus(
            name="qmd",
            present=qmd_path is not None,
            required_by=["wiki-query", "wiki-ingest", "active-learning"],
            detail=f"qmd em {qmd_path}" if qmd_path else "qmd não está no PATH",
            hint=(
                "Instale o qmd (servidor MCP de busca): `bun install -g @tobilu/qmd` "
                "— repo https://github.com/tobi/qmd. Depois confirme que está no PATH."
            ),
        )
    )

    zotero_up = _port_open(ZOTERO_HOST, ZOTERO_PORT)
    statuses.append(
        DepStatus(
            name="zotero",
            present=zotero_up,
            required_by=["paper sync-annotations", "paper sync-notes", "write export --to docx"],
            detail=(
                f"API local respondendo em {ZOTERO_HOST}:{ZOTERO_PORT}"
                if zotero_up
                else f"nada escutando em {ZOTERO_HOST}:{ZOTERO_PORT}"
            ),
            hint=(
                f"Abra o Zotero 9 (com Better BibTeX instalado) — ele expõe a API "
                f"local em {ZOTERO_HOST}:{ZOTERO_PORT}. Só é necessário pros comandos "
                f"que leem anotações/notas; o resto do prumo funciona sem ele."
            ),
        )
    )

    return statuses
