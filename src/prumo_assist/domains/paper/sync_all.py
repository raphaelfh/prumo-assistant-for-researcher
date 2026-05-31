"""Orquestrador ``prumo paper sync-all``: sync + sync-annotations + sync-notes.

``sync`` é offline (lê o ``.bib``). ``sync-annotations`` e ``sync-notes`` exigem
Zotero rodando — se ele estiver offline, capturamos a ``ConnectionError`` e
seguimos, reportando como warning. Assim ``sync-all`` sempre atualiza o ``_meta.md``
mesmo sem o Zotero aberto.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from prumo_assist.domains.paper.sync import sync
from prumo_assist.domains.paper.zotero import sync_annotations, sync_notes


def sync_all(pj_path: Path) -> dict[str, Any]:
    """Roda as três fases em sequência. Retorna report agregado.

    Chaves: ``sync`` (sempre dict), ``annotations`` (dict ou ``None`` se Zotero
    offline), ``notes`` (idem), ``warnings`` (lista de strings).
    """
    warnings: list[str] = []

    sync_report = sync(pj_path)

    annotations_report: dict[str, Any] | None
    try:
        annotations_report = sync_annotations(pj_path)
    except (ConnectionError, FileNotFoundError) as exc:
        annotations_report = None
        warnings.append(f"sync-annotations pulado: {exc}")

    notes_report: dict[str, Any] | None
    try:
        notes_report = sync_notes(pj_path)
    except (ConnectionError, FileNotFoundError) as exc:
        notes_report = None
        warnings.append(f"sync-notes pulado: {exc}")

    return {
        "sync": sync_report,
        "annotations": annotations_report,
        "notes": notes_report,
        "warnings": warnings,
    }
