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
from html import unescape
from pathlib import Path
from typing import Any

from prumo_assist.core.bib import parse_bib
from prumo_assist.core.note_paths import annotations_path, meta_path

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
    """``True`` se Zotero 9 está expondo a API local em ``localhost:23119``."""
    try:
        urllib.request.urlopen(_zotero_base(), timeout=2)
        return True
    except (urllib.error.URLError, TimeoutError):
        return False


# ---------------------------------------------------------------------------
# Resolução citekey → (libraryID, itemKey) via BBT JSON-RPC
# ---------------------------------------------------------------------------


def resolve_citekey(citekey: str) -> tuple[int, str] | None:
    """Devolve ``(libraryID, itemKey)`` ou ``None`` se BBT não achar."""
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "method": "item.search",
        "params": [citekey],
        "id": 1,
    }
    try:
        resp = _http_post_json(_bbt_rpc(), payload)
    except urllib.error.URLError:
        return None
    if not isinstance(resp, dict):
        return None
    items = resp.get("result") or []
    for it in items:
        ck = it.get("citationKey") or it.get("citekey")
        if ck == citekey:
            lib = (it.get("library") or {}).get("id", 1)
            key = it.get("itemKey") or it.get("key")
            if key:
                return (int(lib), str(key))
    if items:
        first = items[0]
        lib = (first.get("library") or {}).get("id", 1)
        key = first.get("itemKey") or first.get("key")
        if key:
            return (int(lib), str(key))
    return None


# ---------------------------------------------------------------------------
# Fetch children (annotations + child notes) via API local
# ---------------------------------------------------------------------------


def fetch_children(library_id: int, item_key: str) -> list[dict[str, Any]]:
    """Lista bruta de child items (data dict por item)."""
    url = f"{_zotero_api()}/users/{library_id}/items/{item_key}/children?format=json&limit=200"
    try:
        resp = _http_get_json(url)
    except urllib.error.URLError:
        return []
    if not isinstance(resp, list):
        return []
    out: list[dict[str, Any]] = []
    for entry in resp:
        data = entry.get("data") if isinstance(entry, dict) else None
        if isinstance(data, dict):
            out.append(data)
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
    fm = (
        f"---\n"
        f"paper: {citekey}\n"
        f"source: prumo-zotero-annotations\n"
        f"---\n\n"
    )
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

    for citekey in citekeys:
        meta = meta_path(pj_path, citekey)
        if not meta.exists():
            no_meta.append(citekey)
            continue
        resolved = resolve_citekey(citekey)
        if not resolved:
            no_resolve.append(citekey)
            continue
        lib_id, item_key = resolved
        try:
            children = fetch_children(lib_id, item_key)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            errors.append((citekey, str(exc)))
            continue

        annots, notes_lst = split_children(children)
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
        resolved = resolve_citekey(citekey)
        if not resolved:
            no_resolve.append(citekey)
            continue
        lib_id, item_key = resolved
        try:
            children = fetch_children(lib_id, item_key)
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
