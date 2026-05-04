"""Sincroniza annotations + child notes do Zotero → ``references/notes/<citekey>/_annotations.md``.

Migrado de ``sync_zotero_annotations.py``. Layout α: cada paper tem uma pasta
``references/notes/<citekey>/`` e as annotations vão pro arquivo dedicado
``_annotations.md`` com YAML frontmatter próprio.

Usa **stdlib apenas** pra não acrescentar dependência (``urllib`` cobre HTTP).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from html import unescape
from pathlib import Path
from typing import Any

from prumo_assist.core.bib import parse_bib
from prumo_assist.core.note_paths import annotations_path, meta_path

ZOTERO_BASE = "http://localhost:23119"
BBT_RPC = f"{ZOTERO_BASE}/better-bibtex/json-rpc"
ZOTERO_API = f"{ZOTERO_BASE}/api"

BEGIN = "<!-- BEGIN ZOTERO ANNOTATIONS -->"
END = "<!-- END ZOTERO ANNOTATIONS -->"

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
        urllib.request.urlopen(ZOTERO_BASE, timeout=2)
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
        resp = _http_post_json(BBT_RPC, payload)
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
    url = f"{ZOTERO_API}/users/{library_id}/items/{item_key}/children?format=json&limit=200"
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
            f"Zotero não está rodando em {ZOTERO_BASE}. Abra o Zotero 9 e tente de novo."
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
