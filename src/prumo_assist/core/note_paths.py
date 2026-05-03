"""Path helpers para layout α de notas de paper.

Layout α: cada paper tem uma pasta `references/notes/<citekey>/` contendo:

- `_meta.md` — gerado por `prumo paper sync` (YAML CSL-JSON + body humano)
- `_extract.md` — gerado por `/prumo-assist:paper-extract` (callout estruturado)
- `_annotations.md` — gerado por `prumo paper sync-annotations` (highlights+notes)
- `note__<itemKey>__<slug>.md` — gerado por `prumo paper sync-notes` (NOVO em PR-N2)

Centralizar a montagem de path aqui evita drift entre módulos. Spec:
docs/superpowers/specs/2026-05-03-zotero-notes-integration-design.md
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

_SLUG_MAX_LEN = 30


def note_dir(pj_path: Path, citekey: str) -> Path:
    """Retorna `<pj>/references/notes/<citekey>/`."""
    return pj_path / "references" / "notes" / citekey


def meta_path(pj_path: Path, citekey: str) -> Path:
    """Retorna `<pj>/references/notes/<citekey>/_meta.md`."""
    return note_dir(pj_path, citekey) / "_meta.md"


def extract_path(pj_path: Path, citekey: str) -> Path:
    """Retorna `<pj>/references/notes/<citekey>/_extract.md`."""
    return note_dir(pj_path, citekey) / "_extract.md"


def annotations_path(pj_path: Path, citekey: str) -> Path:
    """Retorna `<pj>/references/notes/<citekey>/_annotations.md`."""
    return note_dir(pj_path, citekey) / "_annotations.md"


def child_note_path(pj_path: Path, citekey: str, item_key: str, slug: str) -> Path:
    """Retorna `<pj>/references/notes/<citekey>/note__<itemKey>__<slug>.md`."""
    return note_dir(pj_path, citekey) / f"note__{item_key}__{slug}.md"


def slugify(text: str) -> str:
    """kebab-case ASCII, ≤30 chars, sem hífens pendurados.

    Vazio ou só whitespace vira `"untitled"`.
    """
    text = text.strip()
    if not text:
        return "untitled"
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()
    kebab = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    if not kebab:
        return "untitled"
    if len(kebab) > _SLUG_MAX_LEN:
        kebab = kebab[:_SLUG_MAX_LEN].rstrip("-")
    return kebab or "untitled"
