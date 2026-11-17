"""Vínculo do projeto com a coleção do Zotero: ``.claude/zotero.toml`` (``ZoteroLink/v1``).

O Better BibTeX não expõe os autoexports por RPC (não há ``autoexport.list``) e o
``.bib`` exportado não diz de qual coleção veio. A única hora em que o PAR sabe a
coleção é no ``prumo paper connect``; este módulo guarda essa resposta para o
``prumo status`` e o painel "Projeto" mostrarem (ADR-0044).

Só I/O de arquivo: quem fala com o Zotero é ``connect.py``, que grava aqui.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import tomli_w
from pydantic import ValidationError

from par.domains.paper.schemas.v1 import ZoteroLink

#: ``id`` da biblioteca pessoal ("My Library") no Zotero — grupos têm ids
#: próprios (2, 5, 6, ...). É o alvo default de ``--create`` sem ``--library``:
#: criar no acervo pessoal é sempre menos invasivo que criar num grupo
#: compartilhado com outras pessoas.
PERSONAL_LIBRARY_ID = 1

__all__ = ["PERSONAL_LIBRARY_ID", "link_path", "read_link", "select_uri", "write_link"]


def link_path(pj_path: Path) -> Path:
    """Retorna ``<pj>/.claude/zotero.toml``."""
    return pj_path / ".claude" / "zotero.toml"


def read_link(pj_path: Path) -> ZoteroLink | None:
    """O vínculo gravado, ou ``None`` se o arquivo não existe ou não valida.

    Arquivo ilegível conta como "sem vínculo": o registro é informativo, e
    regravar é um comando (``prumo paper connect "<coleção>" --record``).
    """
    try:
        raw = tomllib.loads(link_path(pj_path).read_text(encoding="utf-8"))
        return ZoteroLink.model_validate(raw.get("zotero", {}))
    except (OSError, tomllib.TOMLDecodeError, ValidationError):
        return None


def write_link(pj_path: Path, link: ZoteroLink) -> Path:
    """Grava ``.claude/zotero.toml`` (substitui o anterior)."""
    path = link_path(pj_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"zotero": link.model_dump(exclude_none=True)}
    path.write_text(tomli_w.dumps(payload), encoding="utf-8")
    return path


def select_uri(link: ZoteroLink) -> str | None:
    """``zotero://select/...`` que abre a coleção no Zotero, quando dá para montar.

    Só na biblioteca pessoal: o link de grupo pede o ``groupID``, e o
    ``user.groups`` do Better BibTeX devolve só o ``libraryID`` local.
    """
    if link.collection_key is None or link.library_id != PERSONAL_LIBRARY_ID:
        return None
    return f"zotero://select/library/collections/{link.collection_key}"
