"""Motor de `prumo paper connect <coleção>` (Fase 4 do zero-friction, escopo A emendado).

Resolve uma coleção do Zotero (com biblioteca e cadeia de pais) e liga o
``references/_references.bib`` do projeto a ela via ``autoexport.add`` do
Better BibTeX (BBT), eliminando a dor #1 do piloto: montar esse fio à mão.

**RISCO central (comprovado por grounding em BBT)**: o método JSON-RPC
``autoexport.add`` **cria** a coleção no Zotero se o ``bbt_path`` informado
não existir — ele não falha, não avisa, apenas materializa uma coleção
fantasma (e a cadeia de pais inteira junto). Por isso a resolução prévia
(que só lê, via ``user.groups``) tem que confirmar a existência da coleção
**antes** de qualquer chamada que mute o estado do Zotero.

ADR-0028 emenda o ADR-0020 e promove esse efeito colateral a capacidade
**opt-in explícito**: com ``create=True`` (a flag ``--create`` do CLI), uma
coleção inexistente passa a ser criada de propósito, e ``ConnectPlan`` diz
de antemão QUAIS segmentos do caminho já existem e quais nascerão — para
que um typo não vire coleção fantasma silenciosa. Sem ``create=True`` nada
muda: ``CollectionNotFoundError`` com sugestões e a garantia "NADA foi
criado". Nenhum caminho de código chega em ``autoexport.add`` sem passar
por ``plan_connection`` — e nenhum teste deste módulo chama o Zotero real:
o seam ``_http_post_json`` abaixo é sempre mockado (o Zotero real do dono
da máquina roda em ``127.0.0.1:23119``).

Criar é **efeito colateral** de ``autoexport.add``, não API dedicada: não
existe "criar coleção vazia" neste canal, criar e conectar são a mesma
chamada. Por isso a capacidade vive aqui e não vira um ``prumo paper
new-collection``. E não há desfazer: o BBT desta versão não expõe
``autoexport.remove`` nem ``autoexport.list`` (``-32601 Method not found``),
e a API local do Zotero recusa ``DELETE`` de coleção (``501``) — remover é
manual, na UI do Zotero.

O seam de transporte é ``_http_post_json`` (JSON-RPC do BBT em
``core.deps.bbt_rpc_url()``, sem autenticação, ``urllib`` da stdlib —
ADR-0007); os testes fazem
``monkeypatch.setattr("par.domains.paper.connect._http_post_json", ...)``.
"""

from __future__ import annotations

import difflib
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from par.core import pj_layout
from par.core.bib import parse_bib
from par.core.deps import (
    SANDBOX_EXCLUDE_HINT,
    ZOTERO_NO_BBT_HINT,
    bbt_rpc_url,
    in_claude_sandbox,
    zotero_base,
)
from par.domains.paper.errors import PaperError

BETTER_BIBLATEX_GUID = "f895aa0d-f28e-47fe-b247-2ea77c6ed583"

#: ``id`` da biblioteca pessoal ("My Library") no Zotero — grupos têm ids
#: próprios (2, 5, 6, ...). É o alvo default de ``--create`` sem ``--library``:
#: criar no acervo pessoal é sempre menos invasivo que criar num grupo
#: compartilhado com outras pessoas.
PERSONAL_LIBRARY_ID = 1

# Seam módulo-level pro courtesy poll — monkeypatchável em teste
# (`monkeypatch.setattr(".../connect._sleep", lambda _s: None)`).
_sleep = time.sleep

#: Dica de ``exported=False`` (E17, Spec B §Erros): o BBT agendou o export,
#: mas o ``.bib`` ainda não apareceu dentro do poll.
EXPORT_PENDING_HINT = (
    "O Better BibTeX ainda não gravou o .bib (pode levar alguns segundos). Se ele não "
    "aparecer, atualize o Better BibTeX para 9.0.65 ou mais novo (Tools → Plugins; as "
    "versões anteriores não exportam itens novos com a janela do Zotero fechada), "
    "confira em Settings → Better BibTeX → Automatic export e rode: prumo paper sync"
)


def _offline_msg() -> str:
    """Mensagem de Zotero inalcançável (E15), pela causa real.

    Dentro do sandbox do Bash do Claude Code o Zotero do host nunca responde,
    esteja aberto ou não: a mensagem ensina a sair do sandbox em vez de mandar
    abrir um Zotero que provavelmente já está aberto.
    """
    base = zotero_base()
    if in_claude_sandbox():
        return (
            f"O sandbox do Claude Code não deixa o `prumo paper connect` falar com o "
            f"Zotero em {base}. Peça para repetir o comando fora do sandbox (o Claude "
            f"pede permissão). {SANDBOX_EXCLUDE_HINT}"
        )
    return (
        f"O Zotero não respondeu em {base}. Abra o Zotero (com o Better BibTeX), "
        f"confira com `prumo doctor` e repita o comando."
    )


def _http_error_msg(code: int) -> str:
    """Mensagem de Zotero que respondeu, mas com erro HTTP no JSON-RPC do BBT.

    404 é o caso E12 do doctor (Zotero aberto, Better BibTeX ausente ou ainda
    iniciando) e reusa a mesma dica; outro código pede reiniciar o Zotero.
    """
    base = zotero_base()
    if code == 404:
        return (
            f"O Zotero respondeu em {base}, mas o Better BibTeX não (HTTP 404). "
            f"{ZOTERO_NO_BBT_HINT}"
        )
    return (
        f"O Zotero respondeu HTTP {code} em {base}. Reinicie o Zotero, confira com "
        f"`prumo doctor` e repita o comando."
    )


def _http_post_json(url: str, payload: dict[str, Any], timeout: float = 10.0) -> object:
    """POST JSON-RPC no Better BibTeX; devolve o JSON decodificado.

    Seam de transporte deste módulo: os testes fazem monkeypatch de
    ``par.domains.paper.connect._http_post_json``."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _rpc(method: str, params: list[Any]) -> dict[str, Any]:
    """Chamada JSON-RPC ao BBT: envelope + transporte + tradução de erro.

    Caminho ÚNICO de transporte deste módulo (era duplicado nos dois call
    sites): erro HTTP (``HTTPError``, testado antes por ser subclasse de
    ``OSError``) vira mensagem pela causa (404 = Better BibTeX ausente); rede
    fora (``URLError``/``OSError``) e resposta hostil (corpo não-JSON —
    ``JSONDecodeError`` é ``ValueError`` — ou top-level não-dict) viram
    ``ZoteroOfflineError`` — nunca vaza ``JSONDecodeError`` nem
    ``AttributeError`` de shape.
    """
    payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    try:
        resp = _http_post_json(bbt_rpc_url(), payload)
    except urllib.error.HTTPError as exc:
        raise ZoteroOfflineError(_http_error_msg(exc.code)) from exc
    except (OSError, ValueError) as exc:
        raise ZoteroOfflineError(_offline_msg()) from exc
    if not isinstance(resp, dict):
        raise ZoteroOfflineError(_offline_msg())
    return resp


@dataclass(frozen=True)
class CollectionRef:
    """Referência a uma coleção do Zotero — resolvida OU planejada.

    ``plan_connection`` usa o mesmo tipo para os dois casos; quem distingue
    "já existe" de "vai nascer" é o :class:`ConnectPlan` que a carrega.
    """

    library: str  # ex. "My Library"
    path: str  # ex. "GynOb/Gestational drug research" (cadeia de pais)
    bbt_path: str  # ex. "/My Library/GynOb/Gestational drug research"
    segments: tuple[str, ...]  # nomes CRUS: (library, pai, ..., filha)


@dataclass(frozen=True)
class LibraryRef:
    """Biblioteca do Zotero (pessoal ou grupo), como alvo possível de criação.

    Vem de ``user.groups`` como :class:`CollectionRef`, mas por um caminho
    próprio: biblioteca SEM coleção nenhuma não produz ``CollectionRef``
    algum e mesmo assim continua sendo um alvo válido pra ``--create``.
    """

    name: str
    is_personal: bool  # ``id == PERSONAL_LIBRARY_ID``


@dataclass(frozen=True)
class SegmentPlan:
    """Um segmento do ``bbt_path`` e seu destino: já existe ou vai nascer."""

    name: str
    exists: bool


@dataclass(frozen=True)
class ConnectPlan:
    """O que ``connect_collection`` fará ANTES de fazer — para eco e confirmação.

    ``segments`` cobre o caminho inteiro, biblioteca primeiro, para que o
    eco mostre exatamente quantas coleções nascem: um typo num pai
    materializaria a cadeia toda, e o pesquisador precisa ver isso antes de
    confirmar.
    """

    collection: CollectionRef
    segments: tuple[SegmentPlan, ...]
    will_create: bool


@dataclass(frozen=True)
class ConnectResult:
    """Resultado de ``connect_collection``."""

    collection: CollectionRef
    bib_path: Path
    exported: bool  # True se o bib deixou de ser placeholder dentro do poll
    created: bool = False  # True se a coleção nasceu nesta chamada (`--create`)


class ZoteroOfflineError(PaperError):
    """Zotero não respondeu (fechado, sem BBT, erro HTTP ou resposta hostil)."""


class CollectionNotFoundError(PaperError):
    """Nenhuma coleção do Zotero bate com o nome pedido."""


class AmbiguousCollectionError(PaperError):
    """Mais de uma coleção do Zotero bate com o nome pedido."""


class AlreadyConnectedError(PaperError):
    """O bib do projeto já tem entradas reais — conectar poderia sobrescrevê-lo."""


class UnsupportedCollectionNameError(PaperError):
    """Coleção ou biblioteca com '/' no nome — aliasaria uma cadeia fantasma no BBT."""


class LibraryNotFoundError(PaperError):
    """A biblioteca alvo da criação não existe (ou não dá pra escolher sozinho)."""


class CreationDeclinedError(PaperError):
    """O usuário viu o plano de criação e recusou."""


def _last_segment(path: str) -> str:
    """Último segmento de um ``path`` de coleção (o nome da coleção em si)."""
    return path.rsplit("/", 1)[-1]


def _fetch_groups() -> list[Any]:
    """Resposta crua de ``user.groups(true)`` — a ÚNICA leitura deste módulo.

    Existe para que coleções e bibliotecas saiam do MESMO round-trip:
    ``plan_connection`` precisa das duas listas e não deve bater duas vezes
    no Zotero (nem arriscar ler dois estados diferentes).
    """
    resp = _rpc("user.groups", [True])
    groups = resp.get("result")
    return groups if isinstance(groups, list) else []


def _libraries_from(groups: list[Any]) -> list[LibraryRef]:
    """Bibliotecas utilizáveis como alvo, ignorando pedaços malformados.

    Nome vazio/só espaço é PULADO (não dá pra montar ``bbt_path``); nome com
    ``"/"`` é MANTIDO de propósito, pra que a guarda de ``"/"`` produza a
    mensagem certa em vez de um enganoso "biblioteca não existe".
    """
    out: list[LibraryRef] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        name = group.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        gid = group.get("id")
        is_personal = (
            isinstance(gid, int) and not isinstance(gid, bool) and gid == PERSONAL_LIBRARY_ID
        )
        out.append(LibraryRef(name=name, is_personal=is_personal))
    return out


def _collections_from(groups: list[Any]) -> list[CollectionRef]:
    """Coleções de todas as bibliotecas, com a cadeia de pais reconstruída.

    Cada entrada de ``user.groups`` já vem com a lista FLAT de coleções da
    biblioteca (``parentCollection`` aponta pra chave do pai, ou ``False``
    pra raiz); a cadeia de pais é reconstruída aqui via mapa ``key -> coleção``.

    Pedaços malformados (biblioteca sem ``name``/``collections``, coleção
    sem ``name``) são ignorados sem crashar. Cadeias de pai quebradas
    (``parentCollection`` aponta pra chave ausente), cíclicas (A → B → A) ou
    com algum nome vazio/só espaço (na coleção, num ancestral, ou na própria
    biblioteca) são PULADAS por inteiro — a coleção correspondente não entra
    na lista retornada e vira ``CollectionNotFoundError`` a jusante, em vez
    de aliasar um ``bbt_path`` truncado/duplicado/malformado que
    ``autoexport.add`` materializaria como coleção fantasma.
    """
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


def list_collections() -> list[CollectionRef]:
    """Lista todas as coleções (de todas as bibliotecas) via ``user.groups``."""
    return _collections_from(_fetch_groups())


def list_libraries() -> list[LibraryRef]:
    """Lista as bibliotecas (pessoal + grupos) via ``user.groups``."""
    return _libraries_from(_fetch_groups())


def _scoped_refs(refs: list[CollectionRef], library: str | None) -> list[CollectionRef]:
    """Filtra por biblioteca ANTES de contar matches (``--library`` desambigua)."""
    if library is None:
        return refs
    lib_cf = library.casefold()
    return [r for r in refs if r.library.casefold() == lib_cf]


def _reject_slash_in_segments(segments: tuple[str, ...] | list[str]) -> None:
    """Recusa qualquer segmento CRU com ``"/"`` — o separador de path do BBT.

    Sem essa guarda, uma coleção real chamada ``"Foo/Bar"`` bateria com
    ``find_collection("Bar")`` (match por último segmento) e o ``bbt_path``
    resultante aliasaria uma cadeia ``Foo`` → ``Bar`` INEXISTENTE, que
    ``autoexport.add`` criaria como fantasma.
    """
    for segment in segments:
        if "/" in segment:
            raise UnsupportedCollectionNameError(
                f"o nome '{segment}' contém '/' — que é o separador de caminho do Better "
                f"BibTeX; o export apontaria para uma cadeia INEXISTENTE que o Zotero "
                f"criaria. NADA foi criado. Renomeie a coleção/biblioteca no Zotero (ex.: "
                f"troque '/' por '-') e rode de novo."
            )


def _match_unique(
    refs: list[CollectionRef], name: str, *, library: str | None
) -> CollectionRef | None:
    """Match único por ``casefold()`` no último segmento, ou ``None`` se 0 matches.

    Ambiguidade (mais de 1 match) e ``"/"`` cru na cadeia do match levantam;
    "não achei" NÃO levanta aqui — quem decide entre erro e plano de criação
    é o chamador (``find_collection`` vs ``plan_connection``).
    """
    name_cf = name.casefold()
    matches = [r for r in refs if _last_segment(r.path).casefold() == name_cf]

    if not matches:
        return None

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
    _reject_slash_in_segments(ref.segments)
    return ref


def _not_found_error(name: str, refs: list[CollectionRef]) -> CollectionNotFoundError:
    """``CollectionNotFoundError`` com sugestões via ``difflib`` e o comando de saída."""
    all_names = [_last_segment(r.path) for r in refs]
    suggestions = difflib.get_close_matches(name, all_names, n=3)
    sug_str = ", ".join(suggestions) if suggestions else "(nenhuma)"
    return CollectionNotFoundError(
        f"coleção '{name}' não existe no Zotero — NADA foi criado. "
        f"Parecidas: {sug_str}. Confira o nome exato no Zotero, ou crie a coleção "
        f'no ato com: prumo paper connect "{name}" --create'
    )


def find_collection(name: str, *, library: str | None = None) -> CollectionRef:
    """Resolve ``name`` (nome da coleção, não o path inteiro) a uma única coleção.

    Match por ``casefold()`` no último segmento do path. Se ``library`` for
    informado, filtra por ela ANTES de contar matches. 0 matches vira
    ``CollectionNotFoundError`` (com sugestões via ``difflib``); mais de 1
    match sem ``library`` vira ``AmbiguousCollectionError``.

    Só LÊ o Zotero: nunca cria nada, com ou sem ``--create`` (a criação é
    decidida em ``plan_connection``, que é quem chama isto).
    """
    refs = _scoped_refs(_collections_from(_fetch_groups()), library)
    ref = _match_unique(refs, name, library=library)
    if ref is None:
        raise _not_found_error(name, refs)
    return ref


def _validate_new_name(name: str) -> None:
    """Guarda de INPUT do ``--create``: só nomes que viram UM segmento.

    ``--create`` não aceita path: ``"GynOb/Nova"`` seria interpretado pelo
    BBT como a cadeia ``GynOb`` → ``Nova`` e materializaria as duas — que é
    exatamente o modo de falha que este comando existe para evitar. Roda
    ANTES de qualquer round-trip: recusar um typo não precisa de rede.
    """
    if not name.strip():
        raise UnsupportedCollectionNameError(
            "nome de coleção vazio — NADA foi criado. Informe o nome: "
            'prumo paper connect "<nome da coleção>" --create'
        )
    if "/" in name:
        raise UnsupportedCollectionNameError(
            f"o nome '{name}' contém '/' — que é o separador de caminho do Better BibTeX; "
            f"com --create o Zotero criaria uma coleção para CADA segmento. NADA foi "
            f"criado. Use um nome sem '/' (ex.: troque '/' por '-'); para pendurar a "
            f"coleção sob um pai, crie-a na UI do Zotero e rode `prumo paper connect` "
            f"sem --create."
        )


def _target_library(libs: list[LibraryRef], library: str | None) -> LibraryRef:
    """Biblioteca onde a coleção nova vai nascer.

    Com ``--library``, exige que ela exista (criar numa biblioteca que o
    Zotero não conhece é um modo de falha novo, não um default). Sem
    ``--library``, usa a pessoal — criar no acervo próprio é sempre menos
    invasivo que criar num grupo compartilhado com outras pessoas.
    """
    available = ", ".join(lib.name for lib in libs) or "(nenhuma)"
    if library is not None:
        lib_cf = library.casefold()
        for lib in libs:
            if lib.name.casefold() == lib_cf:
                return lib
        raise LibraryNotFoundError(
            f"biblioteca '{library}' não existe no Zotero — NADA foi criado. "
            f"Disponíveis: {available}."
        )

    for lib in libs:
        if lib.is_personal:
            return lib
    if len(libs) == 1:
        return libs[0]
    raise LibraryNotFoundError(
        f"não dá pra escolher a biblioteca sozinho — NADA foi criado. Diga qual com "
        f"--library. Disponíveis: {available}."
    )


def plan_connection(name: str, *, library: str | None = None, create: bool = False) -> ConnectPlan:
    """Decide, SEM mutar nada, qual ``bbt_path`` o ``autoexport.add`` receberá.

    É a separação que o ``--create`` exige: "resolver uma referência
    existente" (o que ``find_collection`` sempre fez) e "montar um
    ``bbt_path`` novo a partir do nome" (o que só ``--create`` autoriza)
    passaram a ser dois caminhos distintos com o mesmo formato de saída.

    Ordem das guardas — todas antes de qualquer coisa mutante:

    1. ``--create`` com nome inválido (vazio ou com ``"/"``) morre local,
       sem sequer ler o Zotero;
    2. ambiguidade morre igual com ou sem ``--create``: ``--create`` não
       desempata nada, e criar uma terceira "GynOb" ao lado de duas já
       existentes seria o pior desfecho possível;
    3. coleção inexistente sem ``--create`` continua ``CollectionNotFoundError``.
    """
    if create:
        _validate_new_name(name)

    groups = _fetch_groups()
    refs = _scoped_refs(_collections_from(groups), library)
    ref = _match_unique(refs, name, library=library)

    if ref is not None:
        return ConnectPlan(
            collection=ref,
            segments=tuple(SegmentPlan(name=seg, exists=True) for seg in ref.segments),
            will_create=False,
        )

    if not create:
        raise _not_found_error(name, refs)

    target = _target_library(_libraries_from(groups), library)
    _reject_slash_in_segments((target.name,))
    new_ref = CollectionRef(
        library=target.name,
        path=name,
        bbt_path=f"/{target.name}/{name}",
        segments=(target.name, name),
    )
    return ConnectPlan(
        collection=new_ref,
        segments=(SegmentPlan(name=target.name, exists=True), SegmentPlan(name=name, exists=False)),
        will_create=True,
    )


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
    create: bool = False,
    confirm: Callable[[ConnectPlan], bool] | None = None,
    poll_timeout: float = 10.0,
    poll_interval: float = 0.5,
) -> ConnectResult:
    """Liga ``references/_references.bib`` a uma coleção do Zotero via BBT.

    Guarda 1: se o bib já tem entradas reais, recusa (``AlreadyConnectedError``)
    — conectar poderia sobrescrever, com a coleção, um ``.bib`` que já tem
    entradas. É local: nem ``user.groups`` chega a ser chamado.

    Guarda 2 (a que importa pro risco de coleção-fantasma): ``plan_connection``
    decide o ``bbt_path`` lendo o Zotero, e só devolve um caminho INEXISTENTE
    quando ``create=True`` — opt-in explícito, nunca inferido de "não achei".

    Guarda 3, só quando o plano cria algo: ``confirm`` recebe o
    :class:`ConnectPlan` e pode abortar (``CreationDeclinedError``). O
    callback existe porque o eco/prompt é I/O de CLI e não pode morar no
    domínio; quando o plano não cria nada, ``confirm`` sequer é consultado.

    Só depois disso ``autoexport.add`` é chamado — nunca antes. Não há
    desfazer: ver o docstring do módulo.
    """
    if not bib_is_placeholder(pj_path):
        raise AlreadyConnectedError(
            "docs/references/_references.bib já tem entradas: conectar agora poderia "
            "sobrescrevê-lo com a coleção. Se ele já vem do Better BibTeX (confira no "
            "Zotero: Settings → Better BibTeX → Automatic export), rode: prumo paper sync"
        )

    plan = plan_connection(name, library=library, create=create)

    if plan.will_create and confirm is not None and not confirm(plan):
        raise CreationDeclinedError(
            f"criação de '{plan.collection.bbt_path}' cancelada — NADA foi criado."
        )

    ref = plan.collection
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

    return ConnectResult(collection=ref, bib_path=bib, exported=exported, created=plan.will_create)
