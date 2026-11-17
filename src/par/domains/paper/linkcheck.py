"""Conferência do vínculo gravado pelo pull export do Better BibTeX (emenda da ADR-0044).

O ``.claude/zotero.toml`` diz qual coleção o ``connect`` ligou, mas envelhece: trocar o
autoexport na UI do Better BibTeX não o atualiza. O pull export
``/better-bibtex/export/collection?/<libraryID>/<KEY>.biblatex`` devolve, na hora e só lendo, o
``.bib`` da coleção endereçada pela chave (pelo nome, não acha). Comparar as citekeys dele com as
do ``.bib`` do projeto diz se o vínculo ainda vale.

Usado pelo ``prumo doctor``. Exige o Zotero aberto; sem ele, ``unreachable`` e nada mais. O seam
de transporte é ``_http_get``, sempre mockado nos testes.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from par.core import pj_layout
from par.core.bib import parse_bib
from par.core.deps import zotero_base
from par.domains.paper.link import read_link

__all__ = ["LinkCheck", "check_link", "pull_url"]

LinkState = Literal["ok", "drift", "missing", "unreachable", "unverifiable"]

_RECORD_CMD = "prumo paper connect --selected --record"


@dataclass(frozen=True)
class LinkCheck:
    """Resultado da conferência. ``detail`` é a frase para a pesquisadora, com o remédio."""

    state: LinkState
    detail: str
    only_zotero: int = 0
    only_bib: int = 0


def pull_url(library_id: int, collection_key: str) -> str:
    """URL do pull export da coleção, endereçada pela chave."""
    key = urllib.parse.quote(collection_key, safe="")
    return f"{zotero_base()}/better-bibtex/export/collection?/{library_id}/{key}.biblatex"


def _http_get(url: str, timeout: float = 5.0) -> tuple[int, str]:
    """GET devolvendo ``(status, corpo)``, inclusive em erro HTTP. Seam dos testes."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return int(resp.status), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace")


def check_link(pj_path: Path, *, timeout: float = 5.0) -> LinkCheck | None:
    """Confere o vínculo do projeto com a coleção. ``None`` quando não há vínculo gravado."""
    saved = read_link(pj_path)
    if saved is None:
        return None
    where = f"{saved.library} › {saved.collection}"
    if saved.collection_key is None or saved.library_id is None:
        return LinkCheck(
            "unverifiable",
            f"o vínculo com {where} não tem a chave da coleção, e sem ela não dá para "
            f"conferir. Clique na coleção do projeto no Zotero e rode: {_RECORD_CMD}",
        )
    try:
        status, body = _http_get(pull_url(saved.library_id, saved.collection_key), timeout)
    except (OSError, ValueError):
        return LinkCheck("unreachable", "o Zotero não respondeu; o vínculo não foi conferido.")
    if status == 404 and body.startswith("Could not export"):
        return LinkCheck(
            "missing",
            f"o Better BibTeX não acha mais a coleção {where} (chave {saved.collection_key}): "
            "ela foi apagada ou mudou de biblioteca? Confira no Zotero e, se a bibliografia "
            f"vem de outra coleção, clique nela e rode: {_RECORD_CMD}",
        )
    if status != 200:
        return LinkCheck(
            "unreachable",
            f"o Better BibTeX respondeu HTTP {status}; o vínculo não foi conferido.",
        )
    in_zotero = {e.citekey for e in parse_bib(body)}
    bib = pj_layout.bib_path(pj_path)
    in_bib = (
        {e.citekey for e in parse_bib(bib.read_text(encoding="utf-8"))} if bib.exists() else set()
    )
    if in_zotero == in_bib:
        return LinkCheck("ok", f"a bibliografia bate com a coleção {where} no Zotero.")
    only_zotero, only_bib = len(in_zotero - in_bib), len(in_bib - in_zotero)
    return LinkCheck(
        "drift",
        f"o .bib do projeto difere da coleção {where} no Zotero: {only_zotero} só no Zotero, "
        f"{only_bib} só no .bib. Pode ser só o export automático atrasado; se continuar, "
        "confira em Zotero → Settings → Better BibTeX → Automatic export qual coleção "
        f"alimenta o .bib e, se for outra, clique nela e rode: {_RECORD_CMD}",
        only_zotero=only_zotero,
        only_bib=only_bib,
    )
