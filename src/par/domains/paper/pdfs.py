"""Symlinks ``references/pdfs/<citekey>.pdf`` → PDF no ``~/Zotero/storage/...``.

Migrado de ``sync_zotero_pdfs.py``. Idempotente: pula o que já está correto,
corrige apontamentos desatualizados, nunca sobrescreve arquivo real.

Resolve o caminho **offline**, pelo campo ``file`` do ``.bib`` que o Better
BibTeX exporta — nunca pela API local. É deliberado: este é o único comando de
``paper`` que funciona com o Zotero fechado, e a spec
``2026-08-23-ponte-zotero-auditoria-design`` registra por que a alternativa
online foi recusada (escolha de anexo pior e dois gates opt-in).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from par.core import pj_layout
from par.core.bib import extract_field, parse_bib

_DEFAULT_ZOTERO_DATA_DIR = "~/Zotero"


def _zotero_data_dir() -> Path:
    """Data dir do Zotero. Override via ``PRUMO_ZOTERO_DATA_DIR``.

    Só importa quando o BBT está exportando caminho relativo ("export file
    paths: relative"): o BBT emite relativo **ao data dir**, não ao ``.bib``
    nem ao CWD.
    """
    return Path(os.environ.get("PRUMO_ZOTERO_DATA_DIR", _DEFAULT_ZOTERO_DATA_DIR)).expanduser()


def _split_unescaped(value: str, separators: str) -> list[str]:
    """Divide ``value`` nos ``separators`` **não escapados**, desfazendo o escape.

    O Better BibTeX escapa três caracteres no campo ``file`` (``\\``, ``;`` e
    ``:``) e usa ``;`` entre anexos e ``:`` entre os campos de um anexo
    (``título:caminho:mimetype``). Separar e desescapar tem de ser a MESMA
    passada: desescapar antes de separar transforma um ``\\:`` do nome do
    arquivo num separador e parte o caminho ao meio.
    """
    out: list[str] = []
    buf: list[str] = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            buf.append(value[i + 1])
            i += 2
        elif ch in separators:
            out.append("".join(buf))
            buf = []
            i += 1
        else:
            buf.append(ch)
            i += 1
    out.append("".join(buf))
    return out


def _pdf_candidates(body: str) -> list[str]:
    """Caminhos ``.pdf`` absolutos declarados no campo ``file``, na ordem do BBT.

    Devolve os candidatos **sem** checar existência em disco — quem chama
    distingue "não há anexo" (lista vazia) de "anexo declarado, arquivo
    ausente" (lista não-vazia, nada existe).
    """
    raw = extract_field(body, "file")
    if not raw:
        return []
    out: list[str] = []
    for piece in _split_unescaped(raw, ";:"):
        candidate = piece.strip()
        if not candidate.lower().endswith(".pdf"):
            continue
        out.append(candidate if os.path.isabs(candidate) else str(_zotero_data_dir() / candidate))
    return out


def sync_pdfs(pj_path: Path) -> dict[str, Any]:
    """Cria/atualiza symlinks. Retorna report com contagens + listas por motivo.

    ``missing`` é mantido como a UNIÃO de ``no_attachment`` e ``not_downloaded``
    — consumidores do ``--json`` dependem dele.
    """
    bib = pj_layout.bib_path(pj_path)
    out = pj_layout.pdfs_dir(pj_path)

    if not bib.exists():
        raise FileNotFoundError(f"{bib} não encontrado. Rode o auto-export do Better BibTeX.")

    out.mkdir(parents=True, exist_ok=True)
    entries = parse_bib(bib.read_text())

    created, updated, ok = 0, 0, 0
    no_attachment: list[str] = []
    not_downloaded: list[str] = []
    blocked: list[str] = []

    for entry in entries:
        citekey = entry.citekey
        candidates = _pdf_candidates(entry.body)
        pdf = next((c for c in candidates if os.path.exists(c)), None)
        if pdf is None:
            (not_downloaded if candidates else no_attachment).append(citekey)
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
        "missing": no_attachment + not_downloaded,
        "no_attachment": no_attachment,
        "not_downloaded": not_downloaded,
        "blocked": blocked,
    }
