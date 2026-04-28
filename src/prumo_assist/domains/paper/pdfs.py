"""Symlinks ``references/pdfs/<citekey>.pdf`` → PDF no ``~/Zotero/storage/...``.

Migrado de ``sync_zotero_pdfs.py``. Idempotente: pula o que já está correto,
corrige apontamentos desatualizados, nunca sobrescreve arquivo real.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from prumo_assist.core.bib import extract_field, parse_bib


def _extract_pdf_path_from_bib_body(body: str) -> str | None:
    """Pega o primeiro caminho ``.pdf`` existente dentro do campo ``file = {...}``."""
    raw = extract_field(body, "file")
    if not raw:
        return None
    raw = raw.replace("\\:", "\x00")
    for item in raw.split(";"):
        for piece in item.split(":"):
            p = piece.replace("\x00", ":").strip()
            if p.lower().endswith(".pdf") and os.path.exists(p):
                return p
    return None


def sync_pdfs(pj_path: Path) -> dict[str, Any]:
    """Cria/atualiza symlinks. Retorna report com contagens + ``missing``."""
    bib = pj_path / "references" / "_references.bib"
    out = pj_path / "references" / "pdfs"

    if not bib.exists():
        raise FileNotFoundError(f"{bib} não encontrado. Rode o auto-export do Better BibTeX.")

    out.mkdir(parents=True, exist_ok=True)
    entries = parse_bib(bib.read_text())

    created, updated, ok = 0, 0, 0
    missing: list[str] = []
    blocked: list[str] = []

    for entry in entries:
        citekey = entry.citekey
        pdf = _extract_pdf_path_from_bib_body(entry.body)
        if not pdf:
            missing.append(citekey)
            continue
        link = out / f"{citekey}.pdf"
        if link.is_symlink():
            if os.readlink(link) == pdf:
                ok += 1
                continue
            link.unlink()
            link.symlink_to(pdf)
            updated += 1
        elif link.exists():
            blocked.append(citekey)  # arquivo real, não tocamos
            continue
        else:
            link.symlink_to(pdf)
            created += 1

    return {
        "created": created,
        "updated": updated,
        "ok": ok,
        "missing": missing,
        "blocked": blocked,
    }
