"""Sincroniza annotations + child notes do Zotero → ``references/notes/<citekey>/_annotations.md``.

Migrado de ``sync_zotero_annotations.py``. Layout α: cada paper tem uma pasta
``references/notes/<citekey>/`` e as annotations vão pro arquivo dedicado
``_annotations.md`` com YAML frontmatter próprio.

Usa **stdlib apenas** pra não acrescentar dependência (``urllib`` cobre HTTP).
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any

from prumo_assist.core.bib import parse_bib
from prumo_assist.core.deps import zotero_local_api_up
from prumo_assist.core.note_paths import annotations_path, meta_path
from prumo_assist.domains.paper.errors import ZoteroApiError

_DEFAULT_ZOTERO_BASE = "http://127.0.0.1:23119"


def _zotero_base() -> str:
    """Base URL da API local do Zotero. Override via ``PRUMO_ZOTERO_BASE``.

    Default ``http://127.0.0.1:23119`` — unifica com os filtros Lua e evita
    surpresas de resolução IPv6 (``::1``) que ``localhost`` às vezes traz.
    """
    return os.environ.get("PRUMO_ZOTERO_BASE", _DEFAULT_ZOTERO_BASE)


def _bbt_rpc() -> str:
    """Endpoint JSON-RPC do Better BibTeX."""
    return f"{_zotero_base()}/better-bibtex/json-rpc"


def _zotero_api() -> str:
    """Base da API local do Zotero (``/api``)."""
    return f"{_zotero_base()}/api"


BEGIN = "<!-- BEGIN ZOTERO ANNOTATIONS -->"
END = "<!-- END ZOTERO ANNOTATIONS -->"

NOTE_BEGIN = "<!-- BEGIN ZOTERO -->"
NOTE_END = "<!-- END ZOTERO -->"

COLOR_EMOJI = {
    "#ffd400": "🟡",
    "#ff6666": "🔴",
    "#5fb236": "🟢",
    "#2ea8e5": "🔵",
    "#a28ae9": "🟣",
    "#e56eee": "💗",
    "#f19837": "🟠",
    "#aaaaaa": "⚪",
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _http_get_json(url: str, timeout: float = 10.0) -> object:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_post_json(url: str, payload: dict[str, Any], timeout: float = 10.0) -> object:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_zotero_running() -> bool:
    """``True`` se Zotero 9 está expondo a API local em ``localhost:23119``.

    Delega pro seam único de ``core.deps`` — doctor e paper têm de concordar
    sobre "o Zotero está de pé". A raiz (``/``) responde 404 com o Zotero
    rodando, então sondá-la aqui produzia falso-negativo.
    """
    return zotero_local_api_up()


# ---------------------------------------------------------------------------
# Resolução citekey → (library_path, itemKey) via BBT JSON-RPC
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ZoteroRef:
    """Identidade de um item na API local do Zotero.

    ``library_path`` é o segmento de caminho da API (``users/13049353`` ou
    ``groups/5772858``), não o ``libraryID`` do Better BibTeX: o BBT numera
    My Library como ``1`` e ``/api/users/1/...`` responde HTTP 400. Os dois
    campos saem da ``uri`` que o BBT devolve
    (``http://zotero.org/users/13049353/items/UGJ7VBQ8``).
    """

    library_path: str
    item_key: str


_ZOTERO_URI_RE = re.compile(r"^https?://zotero\.org/(users|groups)/(\d+)/items/([A-Za-z0-9]+)$")


def _bbt_rpc_call(method: str, params: list[Any]) -> object | None:
    """Chama um método do JSON-RPC do BBT e devolve ``result`` (``None`` em falha).

    O BBT sinaliza erro de aplicação com **HTTP 200 + ``error`` no corpo**
    (ex.: ``-32603 library.get ... not found`` quando a library é vazia);
    olhar só exceção de rede não basta.
    """
    payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    try:
        resp = _http_post_json(_bbt_rpc(), payload)
    except (urllib.error.URLError, TimeoutError):
        return None
    if not isinstance(resp, dict) or resp.get("error") is not None:
        return None
    return resp.get("result")


def _search_library_name(citekey: str) -> str | None:
    """Nome da biblioteca que contém ``citekey``, via ``item.search``.

    O BBT devolve ``library`` como **string** (``'My Library'``) e não expõe
    ``itemKey`` — daí só o nome sair daqui; ele é o parâmetro que
    ``item.pandoc_filter`` exige para devolver a ``uri``.
    """
    result = _bbt_rpc_call("item.search", [citekey])
    if not isinstance(result, list):
        return None
    items = [it for it in result if isinstance(it, dict)]
    for it in items:
        ck = it.get("citekey") or it.get("citation-key") or it.get("citationKey")
        lib = it.get("library")
        if ck == citekey and isinstance(lib, str) and lib:
            return lib
    for it in items:
        lib = it.get("library")
        if isinstance(lib, str) and lib:
            return lib
    return None


def _pandoc_filter_uri(citekey: str, library: str) -> str | None:
    """URI Zotero do item (``http://zotero.org/users/<id>/items/<KEY>``).

    Usa ``item.pandoc_filter`` — a mesma API que o ``zotero.lua`` chama — e lê
    ``result.items[<citekey>].custom.uri``.
    """
    result = _bbt_rpc_call("item.pandoc_filter", [[citekey], True, library])
    if not isinstance(result, dict):
        return None
    items = result.get("items")
    if not isinstance(items, dict):
        return None
    data = items.get(citekey)
    custom = data.get("custom") if isinstance(data, dict) else None
    uri = custom.get("uri") if isinstance(custom, dict) else None
    return str(uri) if uri else None


def _ref_from_uri(uri: str) -> ZoteroRef | None:
    """Converte a ``uri`` do BBT em :class:`ZoteroRef` (``None`` se não casar)."""
    m = _ZOTERO_URI_RE.match(uri.strip())
    if m is None:
        return None
    return ZoteroRef(library_path=f"{m.group(1)}/{m.group(2)}", item_key=m.group(3))


def resolve_citekey(citekey: str) -> ZoteroRef | None:
    """Resolve ``citekey`` → :class:`ZoteroRef`, ou ``None`` se o BBT não achar.

    Dois passos, ambos no JSON-RPC do BBT: ``item.search`` dá o **nome** da
    biblioteca e ``item.pandoc_filter`` dá a ``uri``, de onde saem o caminho de
    library da API e o itemKey. O ``libraryID`` numérico do BBT não serve —
    ``/api/users/1/...`` responde HTTP 400.
    """
    library = _search_library_name(citekey)
    if library is None:
        return None
    uri = _pandoc_filter_uri(citekey, library)
    if uri is None:
        return None
    return _ref_from_uri(uri)


# ---------------------------------------------------------------------------
# Fetch children (annotations + child notes) via API local
# ---------------------------------------------------------------------------


_ANNOTATIONS_PAGE_SIZE = 100
_ANNOTATIONS_MAX_PAGES = 200


def _zotero_http_error(exc: urllib.error.HTTPError, url: str) -> ZoteroApiError:
    """Traduz ``HTTPError`` da API local em erro de domínio acionável (pt-BR)."""
    if exc.code == 403:
        return ZoteroApiError(
            f"A API local do Zotero está desligada (HTTP 403 em {url}). "
            "Ligue em Zotero → Settings → Advanced → marque "
            '"Allow other applications on this computer to communicate with Zotero" '
            "e rode `prumo paper sync-annotations <pj>` de novo."
        )
    return ZoteroApiError(
        f"A API local do Zotero recusou {url} (HTTP {exc.code} {exc.reason}). "
        "Confirme que o Zotero 9 está aberto e que o item ainda existe na "
        "biblioteca; rode `prumo doctor` para diagnosticar."
    )


def _fetch_item_data(url: str) -> list[dict[str, Any]]:
    """GET numa coleção de items da API local → lista dos dicts ``data``.

    ``HTTPError`` (403/400/404) vira :class:`ZoteroApiError`: engoli-lo produzia
    "0 anotações" indistinguível de "sem anotações". ``URLError`` puro (rede
    fora) continua vazando pro chamador decidir.
    """
    try:
        resp = _http_get_json(url)
    except urllib.error.HTTPError as exc:
        raise _zotero_http_error(exc, url) from exc
    if not isinstance(resp, list):
        return []
    out: list[dict[str, Any]] = []
    for entry in resp:
        data = entry.get("data") if isinstance(entry, dict) else None
        if isinstance(data, dict):
            out.append(data)
    return out


def fetch_children(ref: ZoteroRef) -> list[dict[str, Any]]:
    """Filhos DIRETOS do item ``ref`` (attachments e child notes).

    ``/children`` **nunca** devolve annotation — elas penduram no anexo, não no
    item top-level (medido: o anexo ``9JUI5P4Q`` tem 8 annotations e
    ``/items/9JUI5P4Q/children`` responde n=0). Para as annotations use
    :func:`fetch_annotations_index` + :func:`annotations_for_item`.
    """
    url = f"{_zotero_api()}/{ref.library_path}/items/{ref.item_key}/children?format=json&limit=200"
    try:
        return _fetch_item_data(url)
    except urllib.error.URLError:  # HTTPError já virou ZoteroApiError acima
        return []


def fetch_annotations_index(library_path: str) -> dict[str, list[dict[str, Any]]]:
    """Todas as annotations da biblioteca, indexadas por ``parentItem``.

    Uma varredura resolve a biblioteca inteira — não faça uma chamada por paper.
    ``/items/<key>/annotations`` responde 404 e o filtro ``?parentItem=<key>`` é
    **ignorado** pela API local (devolve tudo), então indexar no cliente é a
    única via.

    A paginação usa ``start`` mas não confia nele: annotations já vistas são
    descartadas e a varredura para quando uma página não traz nada novo. Se a
    API ignorasse ``start`` (como ignora ``parentItem``), repetiríamos a
    primeira página em vez de duplicar anotações.
    """
    index: dict[str, list[dict[str, Any]]] = {}
    seen: set[str] = set()
    start = 0
    for _ in range(_ANNOTATIONS_MAX_PAGES):
        url = (
            f"{_zotero_api()}/{library_path}/items?itemType=annotation"
            f"&format=json&limit={_ANNOTATIONS_PAGE_SIZE}&start={start}"
        )
        page = _fetch_item_data(url)
        fresh = 0
        for data in page:
            key = data.get("key")
            if isinstance(key, str) and key:
                if key in seen:
                    continue
                seen.add(key)
            parent = data.get("parentItem")
            if isinstance(parent, str) and parent:
                index.setdefault(parent, []).append(data)
                fresh += 1
        if len(page) < _ANNOTATIONS_PAGE_SIZE or fresh == 0:
            break
        start += len(page)
    return index


def annotations_for_item(
    children: list[dict[str, Any]],
    index: Mapping[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Annotations de um item top-level: netas via ``top → attachment → annotation``.

    Casa a ``key`` de cada attachment vindo de :func:`fetch_children` com o
    ``parentItem`` das annotations de :func:`fetch_annotations_index`.
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for d in children:
        if d.get("itemType") != "attachment":
            continue
        key = str(d.get("key") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        out.extend(index.get(key, []))
    return out


def split_children(
    children: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Separa em ``(annotations, notes)``, descartando attachments e outros."""
    annotations: list[dict[str, Any]] = []
    notes: list[dict[str, Any]] = []
    for d in children:
        itype = d.get("itemType")
        if itype == "annotation":
            annotations.append(d)
        elif itype == "note":
            notes.append(d)
    return annotations, notes


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def html_to_markdown(html: str) -> str:
    """Conversão minimalista das notes do Zotero (HTML → markdown)."""
    s = html
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"</p>\s*", "\n\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<p[^>]*>", "", s, flags=re.IGNORECASE)
    s = re.sub(r"<(strong|b)>", "**", s, flags=re.IGNORECASE)
    s = re.sub(r"</(strong|b)>", "**", s, flags=re.IGNORECASE)
    s = re.sub(r"<(em|i)>", "*", s, flags=re.IGNORECASE)
    s = re.sub(r"</(em|i)>", "*", s, flags=re.IGNORECASE)
    s = re.sub(
        r"<h(\d)[^>]*>",
        lambda m: "\n" + "#" * int(m.group(1)) + " ",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"</h\d>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<li[^>]*>", "- ", s, flags=re.IGNORECASE)
    s = re.sub(r"</li>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", "", s)
    s = unescape(s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def note_title_from_html(html: str) -> str:
    """Deriva um título legível da child note: primeiro heading ou primeira linha.

    Retorna ``"(sem título)"`` se vazia. Usado pro YAML ``title`` e pro slug.
    """
    md = html_to_markdown(html)
    for line in md.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped
    return "(sem título)"


def render_child_note(note: dict[str, Any]) -> str:
    """Conteúdo delimitado de uma child note: ``BEGIN ZOTERO`` … ``END ZOTERO``."""
    body = html_to_markdown(note.get("note") or "")
    return f"{NOTE_BEGIN}\n\n{body or '_(vazia)_'}\n\n{NOTE_END}"


def _yaml_sq(s: str) -> str:
    """Escapa uma string pra YAML single-quoted (aspas internas duplicadas)."""
    return "'" + s.replace("'", "''") + "'"


def _note_tags(note: dict[str, Any]) -> list[str]:
    """Extrai tags do formato Zotero ``[{'tag': 'x'}, ...]`` → ``['x', ...]``."""
    raw = note.get("tags") or []
    out: list[str] = []
    for t in raw:
        if isinstance(t, dict) and t.get("tag"):
            out.append(str(t["tag"]))
    return out


def compose_child_note_file(citekey: str, note: dict[str, Any]) -> str:
    """Conteúdo completo de ``note__<itemKey>__<slug>.md``: YAML estável + bloco.

    O contrato de YAML (``paper``, ``zotero_item_key``, ``source``,
    ``date_added``, ``date_modified``, ``tags``, ``title``) é consumido pelas
    skills ``write-*`` — não remover nem renomear campos sem coordenar.
    """
    item_key = str(note.get("key") or "")
    title = note_title_from_html(note.get("note") or "")
    date_added = str(note.get("dateAdded") or "")
    date_modified = str(note.get("dateModified") or "")
    tags = _note_tags(note)
    tags_yaml = "[]" if not tags else "[" + ", ".join(_yaml_sq(t) for t in tags) + "]"
    fm = (
        f"---\n"
        f"paper: {citekey}\n"
        f"zotero_item_key: {item_key}\n"
        f"source: zotero-child-note\n"
        f"date_added: '{date_added}'\n"
        f"date_modified: '{date_modified}'\n"
        f"tags: {tags_yaml}\n"
        f"title: {_yaml_sq(title)}\n"
        f"---\n\n"
    )
    return fm + render_child_note(note) + "\n"


def render_annotation(d: dict[str, Any]) -> list[str]:
    color = (d.get("annotationColor") or "").lower()
    emoji = COLOR_EMOJI.get(color, "•")
    page = d.get("annotationPageLabel") or "?"
    atype = d.get("annotationType") or "highlight"
    text = (d.get("annotationText") or "").strip()
    comment = (d.get("annotationComment") or "").strip()
    out = [f"### {emoji} p. {page} — {atype}"]
    if text:
        for line in text.splitlines():
            out.append(f"> {line}".rstrip())
        if not text.splitlines():
            out.append(f"> {text}")
    if comment:
        out.append("")
        out.append(comment)
    return out


def render_note(d: dict[str, Any]) -> list[str]:
    md = html_to_markdown(d.get("note") or "")
    title = next((ln.strip("# ").strip() for ln in md.splitlines() if ln.strip()), "")
    title = title or "(sem título)"
    if len(title) > 80:
        title = title[:77] + "…"
    return [f"### 📝 Nota — {title}", "", md or "_(vazia)_"]


def render_block(annotations: list[dict[str, Any]], notes: list[dict[str, Any]]) -> str:
    """Conteúdo completo do bloco regenerável, incluindo BEGIN/END."""
    _notice = (
        "_⚠ Bloco regenerado por `prumo paper sync-annotations`. "
        "Edite no Zotero (não aqui) — alterações manuais serão perdidas no próximo sync._"
    )
    lines = [BEGIN, "", _notice, ""]
    if not annotations and not notes:
        lines.append("_(sem anotações ou child notes no Zotero)_")
        lines.append("")
    else:
        annotations_sorted = sorted(annotations, key=lambda d: d.get("annotationSortIndex") or "")
        for a in annotations_sorted:
            lines.extend(render_annotation(a))
            lines.append("")
        notes_sorted = sorted(notes, key=lambda d: d.get("dateAdded") or "")
        for n in notes_sorted:
            lines.extend(render_note(n))
            lines.append("")
    lines.append(END)
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Compose dedicated annotations file
# ---------------------------------------------------------------------------


def compose_annotations_file(
    citekey: str,
    annotations: list[dict[str, Any]],
    notes: list[dict[str, Any]],
) -> str:
    """Conteúdo completo de _annotations.md: YAML + bloco delimitado."""
    fm = f"---\npaper: {citekey}\nsource: prumo-zotero-annotations\n---\n\n"
    block = render_block(annotations, notes)
    return fm + block


def sync_annotations(pj_path: Path) -> dict[str, Any]:
    """Sincroniza annotations do Zotero pra ``<key>/_annotations.md``.

    Pré-requisitos: Zotero 9 aberto + Better BibTeX instalado. Falha cedo
    com mensagem clara se faltar algum.

    O diretório de anotações é garantido por ``_meta.md``: se ele existe,
    o pai (``<key>/``) já existe e podemos escrever ``_annotations.md``
    sem precisar de ``mkdir``. Reordenar o guard quebra essa invariante.
    """
    bib = pj_path / "references" / "_references.bib"
    notes_dir = pj_path / "references" / "notes"

    if not bib.exists():
        raise FileNotFoundError(f"{bib} não encontrado.")
    if not notes_dir.exists():
        raise FileNotFoundError(f"{notes_dir} não existe. Rode `prumo paper sync` primeiro.")
    if not check_zotero_running():
        raise ConnectionError(
            f"Zotero não está rodando em {_zotero_base()}. Abra o Zotero 9 e tente de novo."
        )

    citekeys = [e.citekey for e in parse_bib(bib.read_text(encoding="utf-8"))]
    inserted = updated = unchanged = 0
    no_meta: list[str] = []
    no_resolve: list[str] = []
    no_children: list[str] = []
    errors: list[tuple[str, str]] = []
    indexes: dict[str, dict[str, list[dict[str, Any]]]] = {}

    for citekey in citekeys:
        meta = meta_path(pj_path, citekey)
        if not meta.exists():
            no_meta.append(citekey)
            continue
        ref = resolve_citekey(citekey)
        if ref is None:
            no_resolve.append(citekey)
            continue
        try:
            children = fetch_children(ref)
            index = indexes.get(ref.library_path)
            if index is None:
                index = fetch_annotations_index(ref.library_path)
                indexes[ref.library_path] = index
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            errors.append((citekey, str(exc)))
            continue

        annots, notes_lst = split_children(children)
        annots.extend(annotations_for_item(children, index))
        if not annots and not notes_lst:
            no_children.append(citekey)
            continue

        new_text = compose_annotations_file(citekey, annots, notes_lst)
        annot_file = annotations_path(pj_path, citekey)
        if annot_file.exists():
            old = annot_file.read_text(encoding="utf-8")
            if old == new_text:
                unchanged += 1
                continue
            annot_file.write_text(new_text, encoding="utf-8")
            updated += 1
        else:
            annot_file.write_text(new_text, encoding="utf-8")
            inserted += 1

    return {
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "no_meta": no_meta,
        "no_resolve": no_resolve,
        "no_children": no_children,
        "errors": errors,
    }


def _replace_note_block(existing: str, new_file_text: str) -> str:
    """Regenera YAML + bloco ``BEGIN/END ZOTERO``, preservando texto humano após o END.

    ``new_file_text`` é o output de ``compose_child_note_file`` (YAML + bloco).
    Qualquer conteúdo no arquivo existente após ``NOTE_END`` é mantido.

    Se o arquivo existente não contém ``NOTE_END`` (corrompido ou criado à mão
    sem o marcador), não há tail confiável a preservar: o arquivo é regenerado
    integralmente a partir de ``new_file_text``. Texto fora do contrato é perdido
    nesse caso — documentado intencionalmente.
    """
    idx = existing.find(NOTE_END)
    if idx == -1:
        return new_file_text
    human_tail = existing[idx + len(NOTE_END) :]
    return new_file_text.rstrip("\n") + human_tail


def sync_notes(pj_path: Path) -> dict[str, Any]:
    """Sincroniza child notes do Zotero pra ``<key>/note__<itemKey>__<slug>.md``.

    Read-only Zotero → repo. Um arquivo por child note. Só o bloco
    ``BEGIN/END ZOTERO`` é regenerado; texto humano após o END é preservado.
    Pré-requisitos: Zotero 9 aberto + Better BibTeX. Falha cedo se faltar.
    """
    from prumo_assist.core.note_paths import child_note_path, meta_path, slugify

    bib = pj_path / "references" / "_references.bib"
    notes_dir = pj_path / "references" / "notes"

    if not bib.exists():
        raise FileNotFoundError(f"{bib} não encontrado.")
    if not notes_dir.exists():
        raise FileNotFoundError(f"{notes_dir} não existe. Rode `prumo paper sync` primeiro.")
    if not check_zotero_running():
        raise ConnectionError(
            f"Zotero não está rodando em {_zotero_base()}. Abra o Zotero 9 e tente de novo."
        )

    citekeys = [e.citekey for e in parse_bib(bib.read_text(encoding="utf-8"))]
    inserted = updated = unchanged = 0
    no_meta: list[str] = []
    no_resolve: list[str] = []
    errors: list[tuple[str, str]] = []

    for citekey in citekeys:
        if not meta_path(pj_path, citekey).exists():
            no_meta.append(citekey)
            continue
        ref = resolve_citekey(citekey)
        if ref is None:
            no_resolve.append(citekey)
            continue
        try:
            children = fetch_children(ref)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            errors.append((citekey, str(exc)))
            continue

        _annots, notes_lst = split_children(children)
        for note in notes_lst:
            note_key = str(note.get("key") or "")
            if not note_key:
                continue
            slug = slugify(note_title_from_html(note.get("note") or ""))
            target = child_note_path(pj_path, citekey, note_key, slug)
            target.parent.mkdir(parents=True, exist_ok=True)
            new_text = compose_child_note_file(citekey, note)
            if target.exists():
                old = target.read_text(encoding="utf-8")
                merged = _replace_note_block(old, new_text)
                if old == merged:
                    unchanged += 1
                    continue
                target.write_text(merged, encoding="utf-8")
                updated += 1
            else:
                target.write_text(new_text, encoding="utf-8")
                inserted += 1

    return {
        "inserted": inserted,
        "updated": updated,
        "unchanged": unchanged,
        "no_meta": no_meta,
        "no_resolve": no_resolve,
        "errors": errors,
    }
