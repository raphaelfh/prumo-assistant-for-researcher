"""Motor de `prumo paper connect <coleção>` (Fase 4 do zero-friction, escopo A emendado).

Resolve uma coleção do Zotero (com biblioteca e cadeia de pais) e liga o
``references/_references.bib`` do projeto a ela via ``autoexport.add`` do
Better BibTeX (BBT), eliminando a dor #1 do piloto: montar esse fio à mão.

**RISCO central (comprovado por grounding em BBT)**: o método JSON-RPC
``autoexport.add`` **cria** a coleção no Zotero se o ``bbt_path`` informado
não existir — ele não falha, não avisa, apenas materializa uma coleção
fantasma. Por isso ``find_collection`` (que só lê, via ``user.groups``) tem
que confirmar a existência da coleção **antes** de qualquer chamada que
mute o estado do Zotero. Nenhum caminho de código deste módulo pode chegar
em ``autoexport.add`` sem passar por essa validação prévia — e nenhum teste
deste módulo chama o Zotero real: o seam ``_http_post_json`` abaixo é
sempre mockado (o Zotero real do dono da máquina roda em
``127.0.0.1:23119``).

O seam de transporte é o mesmo de ``zotero.py`` (JSON-RPC do BBT, sem
autenticação), mas redefinido localmente como wrapper fino: assim
``monkeypatch.setattr("prumo_assist.domains.paper.connect._http_post_json", ...)``
intercepta as chamadas deste módulo sem afetar ``zotero.py``.
"""

from __future__ import annotations

import difflib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prumo_assist.core import pj_layout
from prumo_assist.core.bib import parse_bib
from prumo_assist.domains.paper import zotero
from prumo_assist.domains.paper.errors import PaperError

BETTER_BIBLATEX_GUID = "f895aa0d-f28e-47fe-b247-2ea77c6ed583"

# Seam módulo-level pro courtesy poll — monkeypatchável em teste
# (`monkeypatch.setattr(".../connect._sleep", lambda _s: None)`).
_sleep = time.sleep

_OFFLINE_MSG = (
    "Zotero não respondeu em 127.0.0.1:23119 — abra o Zotero (com Better BibTeX "
    "instalado) e rode de novo."
)


def _http_post_json(url: str, payload: dict[str, Any], timeout: float = 10.0) -> object:
    """Wrapper fino sobre o seam de ``zotero.py`` — é o seam local deste módulo.

    Existe só pra dar um alvo de monkeypatch estável
    (``prumo_assist.domains.paper.connect._http_post_json``) sem duplicar a
    lógica HTTP, que continua vivendo em ``zotero._http_post_json``.
    """
    return zotero._http_post_json(url, payload, timeout)


def _rpc(method: str, params: list[Any]) -> dict[str, Any]:
    """Chamada JSON-RPC ao BBT: envelope + transporte + tradução de erro.

    Caminho ÚNICO de transporte deste módulo (era duplicado nos dois call
    sites): rede fora (``URLError``/``OSError`` — ``URLError`` é subclasse
    de ``OSError``) e resposta hostil (top-level não-dict) viram
    ``ZoteroOfflineError`` — nunca vaza ``AttributeError`` de shape.
    """
    payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    try:
        resp = _http_post_json(zotero._bbt_rpc(), payload)
    except OSError as exc:
        raise ZoteroOfflineError(_OFFLINE_MSG) from exc
    if not isinstance(resp, dict):
        raise ZoteroOfflineError(_OFFLINE_MSG)
    return resp


@dataclass(frozen=True)
class CollectionRef:
    """Referência resolvida a uma coleção do Zotero."""

    library: str  # ex. "My Library"
    path: str  # ex. "Pesquisa/Colecao do estudo piloto1" (cadeia de pais)
    bbt_path: str  # ex. "/My Library/Pesquisa/Colecao do estudo piloto1"
    segments: tuple[str, ...]  # nomes CRUS: (library, pai, ..., filha)


@dataclass(frozen=True)
class ConnectResult:
    """Resultado de ``connect_collection``."""

    collection: CollectionRef
    bib_path: Path
    exported: bool  # True se o bib deixou de ser placeholder dentro do poll


class ZoteroOfflineError(PaperError):
    """Zotero não respondeu (fechado, sem BBT, ou JSON hostil do seam)."""


class CollectionNotFoundError(PaperError):
    """Nenhuma coleção do Zotero bate com o nome pedido."""


class AmbiguousCollectionError(PaperError):
    """Mais de uma coleção do Zotero bate com o nome pedido."""


class AlreadyConnectedError(PaperError):
    """O bib do projeto já tem entradas reais — reconectar é perigoso."""


class UnsupportedCollectionNameError(PaperError):
    """Coleção ou biblioteca com '/' no nome — aliasaria uma cadeia fantasma no BBT."""


def _last_segment(path: str) -> str:
    """Último segmento de um ``path`` de coleção (o nome da coleção em si)."""
    return path.rsplit("/", 1)[-1]


def list_collections() -> list[CollectionRef]:
    """Lista todas as coleções (de todas as bibliotecas) via ``user.groups``.

    Cada entrada de ``user.groups`` já vem com a lista FLAT de coleções da
    biblioteca (``parentCollection`` aponta pra chave do pai, ou ``False``
    pra raiz); a cadeia de pais é reconstruída aqui via mapa ``key -> coleção``.

    Pedaços malformados (biblioteca sem ``name``/``collections``, coleção
    sem ``name``) são ignorados sem crashar — só a ausência total de resposta
    útil do seam vira ``ZoteroOfflineError``. Cadeias de pai quebradas
    (``parentCollection`` aponta pra chave ausente), cíclicas (A → B → A) ou
    com algum nome vazio/só espaço (na coleção, num ancestral, ou na própria
    biblioteca) são PULADAS por inteiro — a coleção correspondente não entra
    na lista retornada e vira ``CollectionNotFoundError`` a jusante, em vez
    de aliasar um ``bbt_path`` truncado/duplicado/malformado que
    ``autoexport.add`` materializaria como coleção fantasma.
    """
    resp = _rpc("user.groups", [True])
    groups = resp.get("result")
    if not isinstance(groups, list):
        return []

    out: list[CollectionRef] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        lib_name = group.get("name")
        collections = group.get("collections")
        if not isinstance(lib_name, str) or not isinstance(collections, list):
            continue

        key_map: dict[str, dict[str, Any]] = {}
        for c in collections:
            if isinstance(c, dict) and isinstance(c.get("key"), str):
                key_map[c["key"]] = c

        for c in collections:
            if not isinstance(c, dict):
                continue
            name = c.get("name")
            if not isinstance(name, str):
                continue
            chain = [name]
            parent = c.get("parentCollection")
            seen: set[str] = set()
            broken = False
            while parent and isinstance(parent, str):
                if parent in seen:
                    broken = True  # ciclo: A -> B -> A já visitado
                    break
                seen.add(parent)
                parent_entry = key_map.get(parent)
                if parent_entry is None:
                    broken = True  # ancestral aponta pra chave ausente
                    break
                parent_name = parent_entry.get("name")
                if not isinstance(parent_name, str):
                    broken = True
                    break
                chain.insert(0, parent_name)
                parent = parent_entry.get("parentCollection")
            if broken:
                continue  # cadeia quebrada/cíclica: PULADA por inteiro
            if any(not seg.strip() for seg in (lib_name, *chain)):
                continue  # nome vazio/só espaço em qualquer nível: PULADA
            path = "/".join(chain)
            out.append(
                CollectionRef(
                    library=lib_name,
                    path=path,
                    bbt_path=f"/{lib_name}/{path}",
                    segments=(lib_name, *chain),
                )
            )
    return out


def find_collection(name: str, *, library: str | None = None) -> CollectionRef:
    """Resolve ``name`` (nome da coleção, não o path inteiro) a uma única coleção.

    Match por ``casefold()`` no último segmento do path. Se ``library`` for
    informado, filtra por ela ANTES de contar matches. 0 matches vira
    ``CollectionNotFoundError`` (com sugestões via ``difflib``); mais de 1
    match sem ``library`` vira ``AmbiguousCollectionError``.

    Após selecionar o match único, se qualquer segmento cru (biblioteca ou
    coleção da cadeia) contiver ``"/"`` levanta ``UnsupportedCollectionNameError``
    — sem essa guarda, uma coleção real chamada ``"Foo/Bar"`` bateria com
    ``find_collection("Bar")`` (match por último segmento) e o ``bbt_path``
    resultante aliasaria uma cadeia ``Foo`` → ``Bar`` INEXISTENTE, que
    ``autoexport.add`` criaria como fantasma.
    """
    refs = list_collections()
    if library is not None:
        lib_cf = library.casefold()
        refs = [r for r in refs if r.library.casefold() == lib_cf]

    name_cf = name.casefold()
    matches = [r for r in refs if _last_segment(r.path).casefold() == name_cf]

    if not matches:
        all_names = [_last_segment(r.path) for r in refs]
        suggestions = difflib.get_close_matches(name, all_names, n=3)
        sug_str = ", ".join(suggestions) if suggestions else "(nenhuma)"
        raise CollectionNotFoundError(
            f"coleção '{name}' não existe no Zotero — NADA foi criado. "
            f"Parecidas: {sug_str}. Confira o nome exato no Zotero."
        )

    if len(matches) > 1:
        candidates = ", ".join(r.bbt_path for r in matches)
        if library is None:
            raise AmbiguousCollectionError(
                f"coleção '{name}' é ambígua — encontrada em mais de um lugar: "
                f"{candidates}. Use --library para desambiguar."
            )
        raise AmbiguousCollectionError(
            f"coleção '{name}' é ambígua mesmo dentro de '{library}': {candidates}."
        )

    ref = matches[0]
    for segment in ref.segments:
        if "/" in segment:
            raise UnsupportedCollectionNameError(
                f"o nome '{segment}' contém '/' — que é o separador de caminho do Better "
                f"BibTeX; o export apontaria para uma cadeia INEXISTENTE que o Zotero "
                f"criaria. NADA foi criado. Renomeie a coleção/biblioteca no Zotero (ex.: "
                f"troque '/' por '-') e rode de novo."
            )

    return ref


def bib_is_placeholder(pj_path: Path) -> bool:
    """True se ``references/_references.bib`` ainda é o placeholder do scaffold.

    Condições: arquivo ausente, vazio, ou primeira linha começando com
    ``"% Bibliografia do projeto"`` E ``parse_bib`` não encontra entradas.
    """
    bib = pj_layout.bib_path(pj_path)
    if not bib.exists():
        return True
    text = bib.read_text(encoding="utf-8")
    if text == "":
        return True
    lines = text.splitlines()
    first_line = lines[0] if lines else ""
    return first_line.startswith("% Bibliografia do projeto") and parse_bib(text) == []


def connect_collection(
    pj_path: Path,
    name: str,
    *,
    library: str | None = None,
    poll_timeout: float = 10.0,
    poll_interval: float = 0.5,
) -> ConnectResult:
    """Liga ``references/_references.bib`` a uma coleção do Zotero via BBT.

    Guarda 1: se o bib já tem entradas reais, recusa (``AlreadyConnectedError``)
    — reconectar às cegas duplicaria o autoexport já configurado.

    Guarda 2 (a que importa pro risco de coleção-fantasma): ``find_collection``
    precisa confirmar que a coleção existe ANTES de qualquer chamada que mute
    o Zotero. Só depois disso ``autoexport.add`` é chamado — nunca antes.
    """
    if not bib_is_placeholder(pj_path):
        raise AlreadyConnectedError(
            "docs/references/_references.bib já tem entradas reais — reconectar às cegas "
            "duplicaria o export automático. Confira no Zotero: Preferences → Better "
            "BibTeX → Automatic export."
        )

    ref = find_collection(name, library=library)

    bib = pj_layout.bib_path(pj_path)
    resp = _rpc("autoexport.add", [ref.bbt_path, BETTER_BIBLATEX_GUID, str(bib.resolve())])
    if "error" in resp:
        raise ZoteroOfflineError(
            f"Better BibTeX recusou o autoexport: {resp['error']}. Confira no Zotero: "
            "Preferences → Better BibTeX → Automatic export; corrija e rode "
            "`prumo paper connect` de novo."
        )

    # Uma checagem síncrona ANTES do loop: export instantâneo do BBT conta
    # como `exported=True` mesmo com `poll_timeout=0` (emenda pós-review T1).
    exported = not bib_is_placeholder(pj_path)
    elapsed = 0.0
    while elapsed < poll_timeout:
        if not bib_is_placeholder(pj_path):
            exported = True
            break
        _sleep(poll_interval)
        elapsed += poll_interval

    return ConnectResult(collection=ref, bib_path=bib, exported=exported)
