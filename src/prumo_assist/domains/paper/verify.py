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

import difflib
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote

from prumo_assist._version import __version__
from prumo_assist.core.bib import BibEntry, extract_field, parse_bib
from prumo_assist.core.citations import scan_marked_citekeys

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

    def _read_disk(self) -> dict[str, Any]:
        """Leitura crua do arquivo — sempre vai ao disco (usada pelo ``put``)."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "entries": {}}
        if not isinstance(data, dict) or not isinstance(data.get("entries"), dict):
            return {"version": 1, "entries": {}}
        return cast(dict[str, Any], data)

    def _load(self) -> dict[str, Any]:
        """Estado do cache para leitura, memoizado por instância.

        Sem o memo, cada ``get`` relia e re-parseava o arquivo inteiro —
        O(N) full-loads por ``verify_refs`` com payloads Crossref de dezenas
        de KB. O ``put`` NÃO usa o memo para escrever: relê o disco
        (read-modify-write, mesma janela de corrida do código antigo — um
        memo stale nunca sobrescreve entradas gravadas por outro processo)
        e atualiza o memo com o estado gravado.
        """
        memo = getattr(self, "_data_memo", None)
        if memo is not None:
            return cast(dict[str, Any], memo)
        data = self._read_disk()
        object.__setattr__(self, "_data_memo", data)
        return data

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
        data = self._read_disk()
        moment = now or datetime.now(UTC)
        data["entries"][key] = {"fetched_at": moment.isoformat(), "payload": payload}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        object.__setattr__(self, "_data_memo", data)


def _http_get_json(url: str, *, timeout: float = 10.0) -> dict[str, Any]:
    """Seam HTTP isolado de propósito — mock nos testes (regra do repo:
    dependência externa SEMPRE mockada no seam). Levanta ``urllib.error.HTTPError``
    (status != 2xx), ``urllib.error.URLError``/``TimeoutError`` (rede) ou
    ``json.JSONDecodeError`` (corpo não-JSON) — o chamador traduz."""
    request = urllib.request.Request(
        url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    # Contrato do seam: SEMPRE objeto no topo (emenda pós-review T2 — corpo
    # JSON válido mas não-objeto viraria AttributeError vazando do
    # check_entry, violando o "nunca levanta").
    if not isinstance(payload, dict):
        raise json.JSONDecodeError("resposta JSON não é objeto no topo", "", 0)
    return cast(dict[str, Any], payload)


_CROSSREF_WORKS_URL = "https://api.crossref.org/works/{doi}"
_CROSSREF_UPDATES_URL = (
    "https://api.crossref.org/works?filter=updates:{doi}&rows=5&select=DOI,update-to"
)
_PUBMED_ESUMMARY_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json"
)

_TITLE_SIMILARITY_FLOOR = 0.6

# `URLError` e `TimeoutError` são subclasses de `OSError` — a tupla mínima
# equivale à enumeração antiga (URLError, TimeoutError, OSError, JSONDecodeError).
_NETWORK_ERRORS = (OSError, json.JSONDecodeError)


@dataclass(frozen=True)
class Finding:
    """Um achado de verificação sobre UMA entrada do bib."""

    citekey: str
    level: str  # "error" | "warning" | "info" — só "error" deriva exit 1
    kind: str
    message: str
    source: str  # "crossref" | "pubmed" | "local" | "refchecker"


def _cached_get_json(cache: RefCache, key: str, url: str, *, refresh: bool) -> dict[str, Any]:
    if not refresh:
        hit = cache.get(key)
        if hit is not None:
            return hit
    payload = _http_get_json(url)
    cache.put(key, payload)
    return payload


def _normalized_title(raw: str) -> str:
    cleaned = raw.replace("{", "").replace("}", "").casefold()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", cleaned).split())


def _title_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _normalized_title(a), _normalized_title(b)).ratio()


def _network_finding(citekey: str, source: str, api: str, exc: Exception) -> Finding:
    return Finding(
        citekey=citekey,
        level="error",
        kind="network-error",
        message=(
            f"falha de rede ao consultar {api}: {exc} — verifique a conexão e rode "
            "de novo (respostas boas ficam em cache local por 7 dias)."
        ),
        source=source,
    )


def _check_crossref(
    citekey: str, doi: str, bib_title: str | None, *, cache: RefCache, refresh: bool
) -> list[Finding]:
    findings: list[Finding] = []
    quoted = quote(doi, safe="/")
    try:
        works = _cached_get_json(
            cache,
            f"crossref:works:{doi.lower()}",
            _CROSSREF_WORKS_URL.format(doi=quoted),
            refresh=refresh,
        )
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            findings.append(
                Finding(
                    citekey=citekey,
                    level="error",
                    kind="doi-not-found",
                    message=(
                        f"DOI {doi} não resolve no Crossref (HTTP 404) — confira o campo "
                        "doi da entrada no Zotero e re-exporte o BBT."
                    ),
                    source="crossref",
                )
            )
        else:
            findings.append(_network_finding(citekey, "crossref", "Crossref works", exc))
        return findings
    except _NETWORK_ERRORS as exc:
        findings.append(_network_finding(citekey, "crossref", "Crossref works", exc))
        return findings

    message = works.get("message") if isinstance(works.get("message"), dict) else {}
    titles = message.get("title") if isinstance(message, dict) else None
    crossref_title = titles[0] if isinstance(titles, list) and titles else None
    if bib_title and isinstance(crossref_title, str):
        ratio = _title_similarity(bib_title, crossref_title)
        if ratio < _TITLE_SIMILARITY_FLOOR:
            findings.append(
                Finding(
                    citekey=citekey,
                    level="warning",
                    kind="title-mismatch",
                    message=(
                        f"título no bib difere do registro Crossref do DOI {doi} "
                        f"(similaridade {ratio:.0%}) — confira se o DOI aponta para o "
                        "trabalho certo no Zotero e re-exporte o BBT."
                    ),
                    source="crossref",
                )
            )

    try:
        updates = _cached_get_json(
            cache,
            f"crossref:updates:{doi.lower()}",
            _CROSSREF_UPDATES_URL.format(doi=quoted),
            refresh=refresh,
        )
    except _NETWORK_ERRORS as exc:
        # HTTPError (⊂ OSError) cai aqui de propósito — sem 404 especial
        # como no works acima: updates ausentes não são erro de DOI.
        findings.append(_network_finding(citekey, "crossref", "Crossref updates (retração)", exc))
        return findings

    upd_message = updates.get("message") if isinstance(updates.get("message"), dict) else {}
    items = upd_message.get("items") if isinstance(upd_message, dict) else None
    for item in items if isinstance(items, list) else []:
        for update in item.get("update-to", []) if isinstance(item, dict) else []:
            if isinstance(update, dict) and str(update.get("type", "")).lower() == "retraction":
                findings.append(
                    Finding(
                        citekey=citekey,
                        level="error",
                        kind="retracted",
                        message=(
                            f"RETRATADO: o Crossref registra retração para o DOI {doi} — "
                            "reavalie a citação (o Zotero também sinaliza via Retraction Watch)."
                        ),
                        source="crossref",
                    )
                )
                return findings
    return findings


def _check_pubmed(citekey: str, pmid: str, *, cache: RefCache, refresh: bool) -> list[Finding]:
    try:
        summary = _cached_get_json(
            cache,
            f"pubmed:esummary:{pmid}",
            _PUBMED_ESUMMARY_URL.format(pmid=pmid),
            refresh=refresh,
        )
    except _NETWORK_ERRORS as exc:
        # HTTPError (⊂ OSError) cai aqui de propósito — PMID sem registro é
        # tratado adiante pelo shape da resposta, não pelo status HTTP.
        return [_network_finding(citekey, "pubmed", "PubMed esummary", exc)]

    result = summary.get("result") if isinstance(summary.get("result"), dict) else {}
    record = result.get(pmid) if isinstance(result, dict) else None
    if not isinstance(record, dict) or "error" in record:
        return [
            Finding(
                citekey=citekey,
                level="warning",
                kind="pmid-not-found",
                message=(
                    f"PMID {pmid} não encontrado no PubMed — confira o campo na entrada "
                    "do Zotero e re-exporte o BBT."
                ),
                source="pubmed",
            )
        ]
    pubtypes = record.get("pubtype")
    if isinstance(pubtypes, list) and "Retracted Publication" in pubtypes:
        return [
            Finding(
                citekey=citekey,
                level="error",
                kind="retracted",
                message=(
                    f"RETRATADO: o PubMed marca o PMID {pmid} como 'Retracted Publication' "
                    "— reavalie a citação (o Zotero também sinaliza via Retraction Watch)."
                ),
                source="pubmed",
            )
        ]
    return []


def check_entry(entry: BibEntry, *, cache: RefCache, refresh: bool = False) -> list[Finding]:
    """Checks nativos determinísticos de UMA entrada. Nunca levanta por falha
    de rede — traduz em achado ``network-error`` (fail-soft por entrada, para
    o restante do bib seguir verificável offline parcial)."""
    ids = _identifiers_for(entry)
    if ids.doi is None and ids.pmid is None:
        extra = f" (arXiv {ids.arxiv_id})" if ids.arxiv_id else ""
        return [
            Finding(
                citekey=entry.citekey,
                level="info",
                kind="no-identifier",
                message=(
                    f"entrada sem DOI/PMID{extra} — verificação nativa impossível; rode "
                    "com --deep para busca por título/autores (refchecker)."
                ),
                source="local",
            )
        ]

    findings: list[Finding] = []
    raw_title = extract_field(entry.body, "title")
    if ids.doi:
        findings.extend(
            _check_crossref(entry.citekey, ids.doi, raw_title, cache=cache, refresh=refresh)
        )
    if ids.pmid:
        already_retracted = any(f.kind == "retracted" for f in findings)
        pubmed = _check_pubmed(entry.citekey, ids.pmid, cache=cache, refresh=refresh)
        if already_retracted:
            pubmed = [f for f in pubmed if f.kind != "retracted"]
        findings.extend(pubmed)
    return findings


REFCHECKER_PIN = "academic-refchecker==3.0.151"
_REFCHECKER_HINT = (
    "Instale o uv (https://docs.astral.sh/uv/) e confirme: "
    f"`uvx {REFCHECKER_PIN} --help`. Sem uv, rode sem --deep — a verificação "
    "nativa (Crossref/PubMed) continua funcionando."
)


class RefcheckerUnavailableError(RuntimeError):
    """Backend profundo (`uvx academic-refchecker==3.0.151`) ausente ou hostil."""


def _bib_subset_text(entries: Sequence[BibEntry]) -> str:
    """Reconstrói um .bib só com as entradas em escopo (privacidade: o bib
    inteiro nunca sai da máquina; ver Global Constraints)."""
    return "\n".join(f"@{e.entry_type}{{{e.citekey},{e.body}}}" for e in entries) + "\n"


def _run_refchecker(bib_text: str, *, timeout: float = 600.0) -> dict[str, Any]:
    """Roda o refchecker PINADO sobre um .bib temporário e devolve o report.

    Fatos do spike 2026-07-24 que este seam honra: o refchecker termina com
    **exit 0 mesmo com erros** — o gate é o ``--report-file``; sem chave de
    API o pool público é lento (default 600s de timeout). Seam isolado para
    mock nos testes (regra do repo).
    """
    with tempfile.TemporaryDirectory(prefix="prumo-refcheck-") as tmp:
        bib_path = Path(tmp) / "scope.bib"
        report_path = Path(tmp) / "report.json"
        bib_path.write_text(bib_text, encoding="utf-8")
        try:
            proc = subprocess.run(
                [
                    "uvx",
                    REFCHECKER_PIN,
                    "--paper",
                    str(bib_path),
                    "--report-file",
                    str(report_path),
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise RefcheckerUnavailableError(
                "uv/uvx não encontrado no PATH — o backend profundo "
                f"(`uvx {REFCHECKER_PIN}`) não pode ser invocado. {_REFCHECKER_HINT}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RefcheckerUnavailableError(
                f"refchecker excedeu {timeout:.0f}s — sem chave de API o pool público "
                "é lento; reduza o escopo (--page) ou rode de novo mais tarde. "
                f"{_REFCHECKER_HINT}"
            ) from exc
        if proc.returncode != 0:
            raise RefcheckerUnavailableError(
                f"refchecker (`uvx {REFCHECKER_PIN}`) terminou com exit "
                f"{proc.returncode}. stderr:\n{proc.stderr.strip()[-2000:]}\n{_REFCHECKER_HINT}"
            )
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RefcheckerUnavailableError(
                "refchecker terminou com exit 0 mas o report JSON está ausente/ilegível "
                "— o exit code dele NÃO sinaliza falha (spike 2026-07-24); sem report "
                f"não há verificação. {_REFCHECKER_HINT}"
            ) from exc
        if not isinstance(payload, dict):
            raise RefcheckerUnavailableError(
                f"report do refchecker não é o JSON esperado (objeto no topo). {_REFCHECKER_HINT}"
            )
        return cast(dict[str, Any], payload)


def _findings_from_report(report: dict[str, Any], scope: set[str]) -> list[Finding]:
    """Records → Findings ``warning`` (deep é enriquecimento, nunca gate —
    Global Constraints). Mapeamento pelo ``original_reference.bibtex_key``."""
    findings: list[Finding] = []
    records = report.get("records")
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, dict):
            continue
        error_type = record.get("error_type")
        if not error_type:
            continue
        original = record.get("original_reference")
        citekey = original.get("bibtex_key") if isinstance(original, dict) else None
        if not isinstance(citekey, str) or citekey not in scope:
            continue
        details = str(record.get("error_details") or "").strip()
        first_line = details.splitlines()[0] if details else "achado sem detalhes"
        # Cap defensivo: o refchecker embute referências cruas no
        # error_details — uma linha de milhares de chars não pode fluir
        # inteira pro Finding.message/CLI.
        if len(first_line) > 200:
            first_line = first_line[:200] + "…"
        findings.append(
            Finding(
                citekey=citekey,
                level="warning",
                kind=f"refchecker:{error_type}",
                message=(f"[deep] {first_line} — confira a entrada no Zotero e re-exporte o BBT."),
                source="refchecker",
            )
        )
    return findings


def verify_refs(
    pj_path: Path,
    *,
    page: Path | None = None,
    deep: bool = False,
    refresh: bool = False,
    cache_path: Path | None = None,
) -> dict[str, Any]:
    """Verifica as referências do ``references/_references.bib`` do pj.

    Com ``page``, restringe às citekeys MARCADAS na página (``[[@key]]`` /
    ``[@key]``) — recomendado: sem chave de API o pool público é lento.
    """
    bib_path = pj_path / "references" / "_references.bib"
    if not bib_path.exists():
        raise FileNotFoundError(
            f"{bib_path} não existe — Better BibTeX export? Rode `prumo paper lint` "
            "para o diagnóstico completo do pj."
        )
    entries = parse_bib(bib_path.read_text(encoding="utf-8"))
    findings: list[Finding] = []
    if not entries:
        # Fase-0 (R3): bib presente mas vazio reportava "0 verificadas —
        # nenhum problema", falso conforto pro clínico — sem isto parece que
        # tudo foi checado quando na verdade não há nada pra checar.
        findings.append(
            Finding(
                citekey="_references.bib",
                level="info",
                kind="empty-bib",
                message=(
                    "acervo vazio — adicione referências no Zotero (coleção do projeto) "
                    "e rode `prumo paper sync` (ou /prumo-assist:paper-manager sync) "
                    "para popular o bib antes de verificar."
                ),
                source="local",
            )
        )
    # Colisão de citekey NUNCA é silenciosa (emenda pós-review T2): o dict
    # ficaria só com a última entrada e uma duplicata retratada sumiria da
    # verificação sem rastro — a classe exata de erro que este comando existe
    # para impedir.
    by_key: dict[str, BibEntry] = {}
    duplicate_counts: dict[str, int] = {}
    for e in entries:
        if e.citekey in by_key:
            duplicate_counts[e.citekey] = duplicate_counts.get(e.citekey, 1) + 1
        else:
            by_key[e.citekey] = e

    if page is not None:
        # Emenda pós-review T4: sem esta guarda, --page inexistente vazava
        # FileNotFoundError cru do SO (inglês) — regra do repo é pt-BR com
        # comando de correção.
        if not page.exists():
            raise FileNotFoundError(
                f"{page} não existe — confira o caminho passado em --page "
                "(a página .md que cita as referências)."
            )
        page_keys = scan_marked_citekeys(page.read_text(encoding="utf-8"))
        scope = [k for k in page_keys if k in by_key]
        findings.extend(
            Finding(
                citekey=key,
                level="info",
                kind="missing-citekey",
                message=(
                    "citekey citada na página mas ausente do bib — rode `prumo paper lint` "
                    "para o diagnóstico completo."
                ),
                source="local",
            )
            for key in page_keys
            if key not in by_key
        )
    else:
        # dedup por citekey (emenda pós-review T2): uma citekey duplicada não
        # pode contar 2x no escopo — o achado duplicate-citekey já cobre o
        # problema uma única vez por citekey, não uma vez por ocorrência no bib.
        scope = list(dict.fromkeys(e.citekey for e in entries))

    cache = RefCache(path=cache_path or default_cache_path())
    for key in scope:
        if key in duplicate_counts:
            findings.append(
                Finding(
                    citekey=key,
                    level="error",
                    kind="duplicate-citekey",
                    message=(
                        f"citekey aparece {duplicate_counts[key]}x no bib — a verificação "
                        "seria ambígua (qual entrada é a verdadeira?); corrija a duplicata "
                        "no Zotero e re-exporte o BBT."
                    ),
                    source="local",
                )
            )
            continue
        findings.extend(check_entry(by_key[key], cache=cache, refresh=refresh))

    # Citekeys duplicadas ficam fora do deep (mesma razão do skip nativo) e o
    # guard usa o subconjunto filtrado: escopo só-de-duplicatas não dispara
    # subprocess nenhum (emenda pós-review T3).
    deep_keys = [k for k in scope if k not in duplicate_counts]
    if deep and deep_keys:
        deep_report = _run_refchecker(_bib_subset_text([by_key[k] for k in deep_keys]))
        findings.extend(_findings_from_report(deep_report, set(deep_keys)))

    summary = {
        "errors": sum(1 for f in findings if f.level == "error"),
        "warnings": sum(1 for f in findings if f.level == "warning"),
        "infos": sum(1 for f in findings if f.level == "info"),
    }
    return {
        "pj": str(pj_path),
        "page": str(page) if page is not None else None,
        "scope": scope,
        "checked": len(scope),
        "deep": deep,
        "findings": [asdict(f) for f in findings],
        "summary": summary,
    }
