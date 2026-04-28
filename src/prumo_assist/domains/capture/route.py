"""Detecção de tipo + roteamento de input → ação sugerida."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

InputKind = Literal["doi", "arxiv", "pdf", "url", "citekey", "unknown"]

DOI_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)$", re.IGNORECASE)
ARXIV_RE = re.compile(
    r"^(?:https?://arxiv\.org/abs/|arxiv:)?([\w.-]+/\d{4,8}|\d{4}\.\d{4,5})(v\d+)?$",
    re.IGNORECASE,
)
URL_RE = re.compile(r"^https?://", re.IGNORECASE)
CITEKEY_RE = re.compile(r"^@?([a-z][\w-]*\d{4}[\w-]*)$")


@dataclass(frozen=True)
class CaptureRoute:
    kind: InputKind
    canonical: str  # forma canônica (e.g., DOI normalizado)
    suggestion: str  # próximo passo human-readable
    next_command: str  # comando concreto (informativo, não executado aqui)


def classify(raw: str) -> CaptureRoute:
    """Detecta o tipo de ``raw`` e devolve sugestão de próximo passo."""
    s = raw.strip()

    if not s:
        return CaptureRoute(
            kind="unknown",
            canonical=s,
            suggestion="Input vazio.",
            next_command="",
        )

    # PDF local (path existente)
    if s.lower().endswith(".pdf"):
        path = Path(s)
        if path.exists():
            return CaptureRoute(
                kind="pdf",
                canonical=str(path.resolve()),
                suggestion=(
                    "PDF local. Adicione no Zotero (Better BibTeX gera o citekey), "
                    "depois rode `prumo paper sync` + `prumo paper sync-pdfs`."
                ),
                next_command="prumo paper sync && prumo paper sync-pdfs",
            )

    # arXiv (testar antes de URL genérica)
    arxiv_m = ARXIV_RE.match(s)
    if arxiv_m and ("arxiv" in s.lower() or "/" in arxiv_m.group(1) or "." in arxiv_m.group(1)):
        return CaptureRoute(
            kind="arxiv",
            canonical=f"arXiv:{arxiv_m.group(1)}",
            suggestion=(
                "arXiv ID. Adicione no Zotero via 'Add Item by Identifier', depois "
                "rode `prumo paper sync`."
            ),
            next_command="prumo paper sync",
        )

    # DOI
    doi_m = DOI_RE.match(s)
    if doi_m:
        return CaptureRoute(
            kind="doi",
            canonical=f"https://doi.org/{doi_m.group(1)}",
            suggestion=(
                "DOI. Adicione no Zotero via 'Add Item by Identifier', depois "
                "rode `prumo paper sync`."
            ),
            next_command="prumo paper sync",
        )

    # URL genérica
    if URL_RE.match(s):
        return CaptureRoute(
            kind="url",
            canonical=s,
            suggestion=(
                "URL não-acadêmica. Use a skill `wiki-ingest` no seu agent-host "
                "pra adicionar como source no wiki (`docs/sources/`)."
            ),
            next_command="(no agent-host: /prumo:wiki-ingest <url>)",
        )

    # Citekey BBT-style
    if CITEKEY_RE.match(s.lstrip("@")):
        return CaptureRoute(
            kind="citekey",
            canonical=f"@{s.lstrip('@')}",
            suggestion=(
                "Parece citekey. Use `prumo paper find` pra buscar ou "
                "`prumo paper extract <citekey>` (skill) pra extrair o PDF."
            ),
            next_command=f"prumo paper find {s.lstrip('@')}",
        )

    return CaptureRoute(
        kind="unknown",
        canonical=s,
        suggestion=(
            "Não consegui detectar o tipo. Tente: caminho .pdf, DOI completo, "
            "arXiv ID (ex: arXiv:2401.01234), URL com http(s)://, ou citekey."
        ),
        next_command="",
    )
