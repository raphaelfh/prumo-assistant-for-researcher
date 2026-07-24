"""Verificação de referências do ``_references.bib`` — Fase 4 da ponte.

Camada NATIVA determinística (este módulo, Tasks 1–2): existência do DOI no
Crossref, retração via Crossref ``filter=updates:`` e PubMed ``pubtype``,
identidade de título. É o único gate (achado ``error`` → exit 1 no CLI).
Camada PROFUNDA opcional (Task 3): ``uvx academic-refchecker==3.0.151`` —
achados viram ``warning`` (enriquecimento, nunca gate). Classificação
citação-suporte é da skill ``citation-support`` (LLM sinaliza, nunca bloqueia).

Privacidade (ADR-0018): só DOIs/PMIDs saem da máquina na camada nativa; o
``--deep`` envia o subconjunto do bib em escopo, nunca o bib inteiro.
Respostas ficam em cache local (TTL 7 dias) em ``default_cache_path()``.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from prumo_assist._version import __version__
from prumo_assist.core.bib import BibEntry, extract_field

_USER_AGENT = f"prumo-assist/{__version__} (+https://github.com/raphaelfh/prumo-assist)"

_DOI_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)
_PMID_RE = re.compile(r"\bPMID:?\s*(\d{1,9})\b", re.IGNORECASE)


@dataclass(frozen=True)
class RefIdentifiers:
    """Identificadores externos de uma entrada bib (todos opcionais)."""

    doi: str | None
    pmid: str | None
    arxiv_id: str | None


def _normalize_doi(raw: str) -> str | None:
    doi = raw.strip().strip("{}").strip()
    lowered = doi.lower()
    for prefix in _DOI_PREFIXES:
        if lowered.startswith(prefix):
            doi = doi[len(prefix) :].strip()
            break
    # DOI nunca contém whitespace; campo bib brace-delimited pode quebrar
    # linha (emenda pós-review T1: newline embutido virava URL malformada).
    doi = "".join(doi.split())
    return doi or None


def _identifiers_for(entry: BibEntry) -> RefIdentifiers:
    """Extrai DOI/PMID/arXiv tolerando as convenções do BBT.

    PMID: campo dedicado ``pmid`` OU padrão ``PMID: NNNN`` em ``note``/``extra``/
    ``annotation`` (nessa ordem de prioridade — BBT costuma despejar no
    ``note``), nunca varrendo o body inteiro. arXiv: ``eprint`` quando
    ``eprinttype``/``archiveprefix`` é ``arxiv`` (case-insensitive).
    """
    raw_doi = extract_field(entry.body, "doi")
    doi = _normalize_doi(raw_doi) if raw_doi else None

    pmid: str | None = None
    raw_pmid = extract_field(entry.body, "pmid")
    if raw_pmid and raw_pmid.strip().isdigit():
        pmid = raw_pmid.strip()
    else:
        # BBT despeja "PMID: NNNN" em note/extra/annotation — NUNCA varrer o
        # body inteiro: um abstract que menciona o PMID de OUTRO trabalho
        # venceria e o gate validaria o registro errado (emenda pós-review T1).
        for field_name in ("note", "extra", "annotation"):
            field_value = extract_field(entry.body, field_name)
            if field_value:
                m = _PMID_RE.search(field_value)
                if m:
                    pmid = m.group(1)
                    break

    arxiv_id: str | None = None
    eprint_type = extract_field(entry.body, "eprinttype") or extract_field(
        entry.body, "archiveprefix"
    )
    if eprint_type and eprint_type.strip().lower() == "arxiv":
        eprint = extract_field(entry.body, "eprint")
        if eprint and eprint.strip():
            arxiv_id = eprint.strip()

    return RefIdentifiers(doi=doi, pmid=pmid, arxiv_id=arxiv_id)


def default_cache_path() -> Path:
    """``$XDG_CACHE_HOME/prumo-assist/refcheck.json`` (fallback ``~/.cache``)."""
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "prumo-assist" / "refcheck.json"


@dataclass(frozen=True)
class RefCache:
    """Cache JSON local de respostas de API, com TTL (default 7 dias).

    Arquivo: ``{"version": 1, "entries": {key: {"fetched_at": iso, "payload": {...}}}}``.
    Corrompido/ausente → tratado como vazio (cache é descartável por design).
    """

    path: Path
    ttl: timedelta = timedelta(days=7)

    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "entries": {}}
        if not isinstance(data, dict) or not isinstance(data.get("entries"), dict):
            return {"version": 1, "entries": {}}
        return cast(dict[str, Any], data)

    def get(self, key: str, *, now: datetime | None = None) -> dict[str, Any] | None:
        entry = self._load()["entries"].get(key)
        if not isinstance(entry, dict):
            return None
        try:
            fetched_at = datetime.fromisoformat(str(entry["fetched_at"]))
            payload = entry["payload"]
        except (KeyError, ValueError):
            return None
        moment = now or datetime.now(UTC)
        if moment - fetched_at > self.ttl:
            return None
        return cast(dict[str, Any], payload) if isinstance(payload, dict) else None

    def put(self, key: str, payload: dict[str, Any], *, now: datetime | None = None) -> None:
        data = self._load()
        moment = now or datetime.now(UTC)
        data["entries"][key] = {"fetched_at": moment.isoformat(), "payload": payload}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _http_get_json(url: str, *, timeout: float = 10.0) -> dict[str, Any]:
    """Seam HTTP isolado de propósito — mock nos testes (regra do repo:
    dependência externa SEMPRE mockada no seam). Levanta ``urllib.error.HTTPError``
    (status != 2xx), ``urllib.error.URLError``/``TimeoutError`` (rede) ou
    ``json.JSONDecodeError`` (corpo não-JSON) — o chamador traduz."""
    request = urllib.request.Request(
        url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return cast(dict[str, Any], json.loads(response.read().decode("utf-8")))
