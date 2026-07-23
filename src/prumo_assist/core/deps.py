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

import os
import re
import shutil
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse

_DEFAULT_ZOTERO_BASE = "http://127.0.0.1:23119"


@dataclass
class DepStatus:
    """Estado de uma dependência externa."""

    name: str
    present: bool
    required_by: list[str]
    detail: str
    hint: str
    version: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "present": self.present,
            "required_by": self.required_by,
            "detail": self.detail,
            "hint": self.hint,
            "version": self.version,
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


def _zotero_host_port() -> tuple[str, int]:
    """Host/porta da API local do Zotero, honrando ``PRUMO_ZOTERO_BASE``."""
    base = os.environ.get("PRUMO_ZOTERO_BASE", _DEFAULT_ZOTERO_BASE)
    parsed = urlparse(base)
    return parsed.hostname or "127.0.0.1", parsed.port or 23119


_SUPPORTED_ZOTERO_MAJOR = 9


def _zotero_version_header(host: str, port: int, timeout: float = 2.0) -> str | None:
    """Versão do Zotero via header ``X-Zotero-Version`` do connector ping.

    Seam testável. ``None`` = não detectável (fail-safe: não reprova).
    """
    url = f"http://{host}:{port}/connector/ping"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            value = resp.headers.get("X-Zotero-Version")
            return str(value) if value else None
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
        return None


def _zotero_major(version: str | None) -> int | None:
    if not version:
        return None
    m = re.match(r"(\d+)", version)
    return int(m.group(1)) if m else None


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

    host, port = _zotero_host_port()
    zotero_up = _port_open(host, port)
    version = _zotero_version_header(host, port) if zotero_up else None
    major = _zotero_major(version)
    supported = major is None or major >= _SUPPORTED_ZOTERO_MAJOR

    if not zotero_up:
        detail = f"nada escutando em {host}:{port}"
        hint = (
            f"Abra o Zotero 9 (com Better BibTeX instalado) — ele expõe a API "
            f"local em {host}:{port}. Só é necessário pros comandos "
            f"que leem anotações/notas; o resto do prumo funciona sem ele."
        )
    elif not supported:
        detail = (
            f"Zotero {version} rodando em {host}:{port} — abaixo do par "
            f"suportado (Zotero 9+ com Better BibTeX)"
        )
        hint = (
            "Atualize para o Zotero 9+: baixe em https://www.zotero.org/download, "
            "instale e reabra o app. Depois atualize o Better BibTeX em "
            "Tools → Plugins se ele avisar (o BBT acompanha o major do Zotero)."
        )
    elif version is None:
        detail = f"API local respondendo em {host}:{port} (versão não detectada)"
        hint = ""
    else:
        detail = f"API local respondendo em {host}:{port} — Zotero {version}"
        hint = ""

    statuses.append(
        DepStatus(
            name="zotero",
            present=zotero_up and supported,
            required_by=["paper sync-annotations", "paper sync-notes", "write export --to docx"],
            detail=detail,
            hint=hint,
            version=version,
        )
    )

    return statuses
