"""A coleção selecionada no Zotero aberto, pelo servidor do conector (emenda da ADR-0044).

``POST /connector/getSelectedCollection`` é o endpoint que o Zotero Connector do navegador usa
para saber onde salvar. Responde sem o toggle "Allow other applications" (que a ADR-0037 deixou
de pedir) e devolve a biblioteca, o ``id`` numérico local da coleção selecionada (nulo com a
biblioteca inteira selecionada) e ``targets``: a árvore de bibliotecas e coleções em ordem de
profundidade, com ``id`` (``L<libraryID>``, ``C<id>``) e ``level``.

Dois usos:

- ``prumo paper connect --selected``: a pesquisadora clica na coleção do projeto no Zotero em vez
  de digitar o nome. :func:`resolve_selected` casa a seleção com o ``user.groups`` do Better
  BibTeX (que dá a chave, mas não o ``id``) pelo caminho da coleção na mesma biblioteca. Só
  coleção que existe sai daqui, então não há coleção-fantasma no ``autoexport.add``.
- :func:`selection_mismatch`: o ``status`` avisa quando o Zotero está em outra coleção, porque é
  nela que o Connector salva os papers.

Só lê o Zotero. O seam de transporte é ``_http_post_json``, sempre mockado nos testes.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any

from par.core.deps import zotero_base
from par.domains.paper.connect import (
    AmbiguousCollectionError,
    CollectionNotFoundError,
    CollectionRef,
    ZoteroOfflineError,
    _offline_msg,
    _reject_slash_in_segments,
    list_collections,
)
from par.domains.paper.errors import PaperError
from par.domains.paper.schemas.v1 import ZoteroLink

__all__ = [
    "NoCollectionSelectedError",
    "SelectedCollection",
    "resolve_selected",
    "selected_collection",
    "selection_mismatch",
]


class NoCollectionSelectedError(PaperError):
    """No Zotero está selecionada a biblioteca inteira, não uma coleção."""


@dataclass(frozen=True)
class SelectedCollection:
    """O que está selecionado na coluna da esquerda do Zotero."""

    library_id: int
    library: str
    #: Caminho da coleção (``pai/filha``); ``None`` com a biblioteca inteira selecionada.
    path: str | None


def _http_post_json(url: str, payload: dict[str, Any], timeout: float = 3.0) -> object:
    """POST JSON no servidor do conector; devolve o JSON decodificado. Seam dos testes."""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _path_from_targets(targets: object, target_id: str) -> str | None:
    """Caminho ``pai/filha`` de ``target_id`` pela árvore ``targets`` (ordem de profundidade).

    Sobe a lista a partir do alvo: cada item anterior com ``level`` menor é o próximo ancestral,
    até a biblioteca (``level`` 0), que não entra no caminho.
    """
    if not isinstance(targets, list):
        return None
    items = [t for t in targets if isinstance(t, dict)]
    index = next((i for i, t in enumerate(items) if t.get("id") == target_id), None)
    if index is None:
        return None
    level = items[index].get("level")
    name = items[index].get("name")
    if not isinstance(level, int) or not isinstance(name, str):
        return None
    chain = [name]
    for item in reversed(items[:index]):
        item_level = item.get("level")
        if not isinstance(item_level, int) or item_level >= level:
            continue
        if item_level == 0:
            break
        item_name = item.get("name")
        if not isinstance(item_name, str):
            return None
        chain.insert(0, item_name)
        level = item_level
    return "/".join(chain)


def selected_collection(*, timeout: float = 3.0) -> SelectedCollection:
    """Lê a seleção atual do Zotero. ``ZoteroOfflineError`` se o Zotero não responde."""
    url = f"{zotero_base()}/connector/getSelectedCollection"
    try:
        resp = _http_post_json(url, {}, timeout=timeout)
    except (OSError, ValueError) as exc:  # URLError/HTTPError são OSError; JSON ruim é ValueError
        raise ZoteroOfflineError(_offline_msg()) from exc
    if not isinstance(resp, dict):
        raise ZoteroOfflineError(_offline_msg())
    library_id = resp.get("libraryID")
    library = resp.get("libraryName")
    if (
        not isinstance(library_id, int)
        or isinstance(library_id, bool)
        or not isinstance(library, str)
    ):
        raise ZoteroOfflineError(_offline_msg())
    collection_id = resp.get("id")
    path = None
    if isinstance(collection_id, int) and not isinstance(collection_id, bool):
        path = _path_from_targets(resp.get("targets"), f"C{collection_id}")
        if path is None:
            raise ZoteroOfflineError(
                "o Zotero respondeu, mas não consegui ler a coleção selecionada. Clique de "
                'novo nela e repita, ou conecte pelo nome: prumo paper connect "<nome da coleção>"'
            )
    return SelectedCollection(library_id=library_id, library=library, path=path)


def resolve_selected() -> CollectionRef:
    """A coleção selecionada no Zotero como :class:`CollectionRef` com chave. Só lê.

    Casa pelo caminho na mesma biblioteca contra o ``user.groups``. Sem match ou com duas
    irmãs de mesmo caminho, recusa: nada é adivinhado, nada é criado.
    """
    sel = selected_collection()
    if sel.path is None:
        raise NoCollectionSelectedError(
            f"no Zotero está selecionada a biblioteca '{sel.library}' inteira, não uma coleção: "
            "clique na coleção do projeto na coluna da esquerda do Zotero e repita: "
            "prumo paper connect --selected"
        )
    matches = [
        ref
        for ref in list_collections()
        if ref.library_id == sel.library_id and ref.path == sel.path
    ]
    where = f"{sel.library} › {sel.path}"
    if not matches:
        raise CollectionNotFoundError(
            f"o Better BibTeX não achou a coleção selecionada ({where}) — NADA foi criado. "
            "Espere o Zotero terminar de carregar e repita, ou conecte pelo nome: "
            f'prumo paper connect "{sel.path.rsplit("/", 1)[-1]}"'
        )
    if len(matches) > 1:
        raise AmbiguousCollectionError(
            f"há mais de uma coleção {where} no Zotero, e o PAR não sabe qual está "
            "selecionada. Renomeie uma delas no Zotero e repita: prumo paper connect --selected"
        )
    ref = matches[0]
    _reject_slash_in_segments(ref.segments)
    return ref


def selection_mismatch(link: ZoteroLink, *, timeout: float = 1.0) -> str | None:
    """Aviso quando o Zotero aberto está fora da coleção do projeto; ``None`` se bate ou se não
    dá para saber (Zotero fechado, sandbox). Nunca levanta."""
    try:
        sel = selected_collection(timeout=timeout)
    except ZoteroOfflineError:
        return None
    if link.library_id is not None:
        same_library = sel.library_id == link.library_id
    else:
        same_library = sel.library.casefold() == link.library.casefold()
    if same_library and sel.path == link.collection:
        return None
    where = f"{sel.library} › {sel.path}" if sel.path else f"{sel.library} (sem coleção)"
    return (
        f"o Zotero está em {where}, não em {link.library} › {link.collection}: o Zotero "
        "Connector do navegador salvaria lá. Clique na coleção do projeto no Zotero antes de salvar"
    )
