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

import http.client
import os
import re
import shutil
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


def _zotero_api_root(timeout: float = 2.0) -> int | None:
    """Status HTTP de ``GET {base}/api/``, ou ``None`` se nada respondeu.

    Seam testável. ``/api/`` é o endpoint no-op da API local, e o gate da
    preferência roda ANTES dele: com o app aberto e a API local **desligada**
    responde ``403 Local API is not enabled``; com ela ligada, ``2xx``. É
    também o único endpoint isento da checagem de versão da API, então serve
    de sonda em qualquer major do Zotero.

    Sondar a porta crua ou ``/connector/ping`` não distingue os dois casos: o
    connector server sobe junto com o app, independentemente da API local.
    """
    base = os.environ.get("PRUMO_ZOTERO_BASE", _DEFAULT_ZOTERO_BASE)
    try:
        with urllib.request.urlopen(f"{base}/api/", timeout=timeout) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except (OSError, http.client.HTTPException):
        return None


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
    except (OSError, http.client.HTTPException):
        return None


def zotero_local_api_up(timeout: float = 2.0) -> bool:
    """``True`` se a **API local** do Zotero responde — não só se o app está aberto.

    Sonda o mesmo endpoint que ``check_external_deps`` (o ``doctor``) para que
    doctor e domínios nunca discordem. Só ``2xx`` conta: a API local é opt-in
    (Settings → Advanced) e, desligada, o app aberto responde ``403`` — tratar
    isso como "de pé" fazia o guard passar e os comandos de anotação tomarem
    403 em série.
    """
    code = _zotero_api_root(timeout=timeout)
    return code is not None and 200 <= code < 300


def _zotero_major(version: str | None) -> int | None:
    """Major numérico de ``version`` (ex. ``"9.0.3"`` → 9), ou ``None``."""
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
    api_code = _zotero_api_root()
    responded = api_code is not None
    api_enabled = responded and 200 <= (api_code or 0) < 300
    version = _zotero_version_header(host, port) if responded else None
    major = _zotero_major(version)
    supported = major is None or major >= _SUPPORTED_ZOTERO_MAJOR

    if not responded:
        detail = f"nada escutando em {host}:{port}"
        hint = (
            f"Abra o Zotero {_SUPPORTED_ZOTERO_MAJOR} (com Better BibTeX instalado) — "
            f"ele expõe a API local em {host}:{port}. Só é necessário pros comandos "
            f"que leem anotações/notas; o resto do prumo funciona sem ele."
        )
    elif not api_enabled:
        detail = (
            f"Zotero aberto em {host}:{port}, mas a API local está DESLIGADA "
            f"(HTTP {api_code} em /api/)"
        )
        hint = (
            "Ligue a API local: Zotero → Settings → Advanced → marque "
            '"Allow other applications on this computer to communicate with Zotero", '
            "e rode `prumo doctor` de novo."
        )
    elif not supported:
        detail = (
            f"Zotero {version} rodando em {host}:{port} — abaixo do par "
            f"suportado (Zotero {_SUPPORTED_ZOTERO_MAJOR}+ com Better BibTeX)"
        )
        hint = (
            f"Atualize para o Zotero {_SUPPORTED_ZOTERO_MAJOR}+: baixe em "
            f"https://www.zotero.org/download, instale e reabra o app. Depois "
            f"atualize o Better BibTeX em Tools → Plugins se ele avisar "
            f"(o BBT acompanha o major do Zotero)."
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
            present=api_enabled and supported,
            required_by=["paper sync-annotations", "paper sync-notes", "write export --to docx"],
            detail=detail,
            hint=hint,
            version=version,
        )
    )

    return statuses
