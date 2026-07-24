# Ponte Fase 4 — Verificação de Referências Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `prumo paper verify-refs` — verificação determinística de referências do `.bib` (existência via Crossref, retração via Crossref/PubMed, identidade de título) com cache local, camada profunda opcional via `academic-refchecker` pinado, e skill LLM `citation-support` que só sinaliza — fechando a Fase 4 do spec da ponte (`docs/superpowers/specs/2026-07-05-review-docx-criticmarkup-design.md`, §"Camada de verificação de referências").

**Architecture:** Motor em `domains/paper/verify.py` (bibliografia é acervo → domínio paper), em camadas: (1) nativa determinística — stdlib `urllib` contra Crossref/NCBI, cache JSON local com TTL 7 dias, é o único gate (`error` → exit 1); (2) profunda opcional `--deep` — `uvx academic-refchecker==3.0.151` sobre um `.bib` de escopo reduzido, achados viram `warning` (enriquecimento, nunca gate); (3) LLM — skill `citation-support`, classificação Fully/Partially/Unsubstantiated, sinaliza e nunca bloqueia. CLI é fachada fina no padrão `lint_command`. Fase inclui 2 itens herdados da fila F2+F3 (guarda de re-ingest com worklist pendente; timeout no seam adeu).

**Tech Stack:** Python 3.11, stdlib `urllib.request`/`json`/`difflib` (SEM dependência de runtime nova), `uvx` para o backend pinado, Typer/`cli_run`/`Console`, pytest com seams mockados.

## Grounding empírico (spike 2026-07-24 — fatos, não suposições)

- `academic-refchecker==3.0.151` (PyPI, `requires_python >=3.11`) roda **sem chave nenhuma** sobre um `.bib`: `uvx academic-refchecker==3.0.151 --paper mini.bib --report-file report.json`. Num bib de 2 entradas detectou author-count mismatch real (3 citados vs 37 no Semantic Scholar) e reprovou DOI fabricado ("Non-existent web page").
- **Exit code 0 MESMO com erros** — o gate é o `report.json`, nunca o returncode.
- Formato do report: `{"generated_at", "summary": {"total_references_processed", "total_errors_found", "total_warnings_found", "total_unverified_refs", ...}, "papers": [...], "records": [...]}`. Cada record: `{"error_type": "author"|"multiple"|..., "error_details": str, "original_reference": {"bibtex_key": str, "doi": str, ...}, ...}`.
- Sem chave = pool compartilhado do Semantic Scholar (504 + retries observados; ~2 min para 2 entradas no pior caso) → **escopo por página é essencial**.
- Crossref: `GET https://api.crossref.org/works/{doi}` → 200 com `message.title[0]` (existência + título) ou HTTP 404. Retração: o trabalho retratado **não** carrega `update-to`; quem carrega é a notice — `GET https://api.crossref.org/works?filter=updates:{doi}&rows=5&select=DOI,update-to` → `message.items[].update-to[]` com `"type": "retraction"` (confirmado ao vivo com Wakefield `10.1016/S0140-6736(97)11096-0`).
- PubMed: `GET https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json` → `result[pmid].pubtype` contém `"Retracted Publication"`.
- Dump completo do Retraction Watch (labs.crossref.org): 31 MB — **fora do MVP** (backlog); a checagem por-DOI acima cobre o caso.
- Item 2 do spec ("Retraction Watch via Zotero — nativo") é do cliente Zotero, já disponível ao usuário; a camada prumo acima é a checagem **independente** no bib (item 3 do spec: resolução por API + cache local de retratações).

## Global Constraints

- Layering: `core/` NUNCA importa de `domains/`; motor em `domains/paper/verify.py`; `domains/paper/api.py` é re-export puro.
- `from __future__ import annotations` em todo módulo; `mypy --strict` limpo; dataclasses `frozen=True` para value objects.
- Mensagens de usuário em pt-BR com o comando de correção embutido; identificadores em inglês. Nada de `print()` — `core/output.Console`; todo subcomando Typer envolto em `core/cli_op.cli_run(...)`.
- Dependências externas SEMPRE mockadas nos seams em teste: HTTP via monkeypatch de `prumo_assist.domains.paper.verify._http_get_json` (string-target), refchecker via monkeypatch de `subprocess.run` (string-target, house style — atributo direto quebra mypy strict).
- **Nenhuma dependência de runtime nova** no pyproject: rede via `urllib.request` (stdlib); refchecker roda FORA do processo via `uvx` pinado `academic-refchecker==3.0.151` (nunca flutuante — mesmo racional do pin `adeu==1.29.0`).
- Só achado `level == "error"` deriva exit 1; `--deep` produz só `warning`; a skill LLM nunca bloqueia (spec: "Sinaliza; nunca bloqueia sozinho").
- Privacidade: só DOIs/PMIDs saem da máquina na camada nativa; `--deep` envia o subconjunto do bib em escopo (nunca o bib inteiro). User-Agent identifica o projeto sem PII.
- Bateria completa ao fim de cada task: `uv run pytest` (suite toda) && `uv run ruff check .` && `uv run ruff format --check .` && `uv run mypy` — SEM PULAR NENHUM (lição da F2: pular `ruff format` quebrou o CI).
- Testes espelham layout: `tests/unit/paper/test_verify.py` (novo), appends em `tests/unit/paper/test_cli.py` e `tests/unit/write/test_review_ingest.py`.
- Commits pt-BR no padrão do repo (`feat(paper): ...`, `fix(write): ...`, `docs(...)`). NÃO bumpa versão (release é ciclo separado; ADR-0015).
- Fora de escopo (fica na fila backlog registrada no ledger, NÃO implementar aqui): page_sha256 no apply; rejeitar-drop/`--resolve-events` de 1ª classe; pareamento difflib de moves; multi-região Guarda A; round-trip guard no emit do transplante; envelope/versão da superfície MCP; dump RW local.

---

### Task 1: Fundação do `verify.py` — identificadores, cache com TTL, seam HTTP

**Files:**
- Create: `src/prumo_assist/domains/paper/verify.py`
- Test: `tests/unit/paper/test_verify.py` (novo)

**Interfaces:**
- Consumes: `prumo_assist.core.bib.BibEntry` (frozen dataclass: `entry_type: str`, `citekey: str`, `body: str`), `prumo_assist.core.bib.extract_field(body: str, field: str) -> str | None` (devolve o valor SEM o delimitador externo, tolerando `{}`/`""`/literal), `prumo_assist._version.__version__`.
- Produces (Tasks 2–3 consomem): `RefIdentifiers` (frozen: `doi: str | None`, `pmid: str | None`, `arxiv_id: str | None`), `_identifiers_for(entry: BibEntry) -> RefIdentifiers`, `RefCache` (frozen: `path: Path`, `ttl: timedelta`; métodos `get(key) -> dict | None` e `put(key, payload) -> None`), `default_cache_path() -> Path`, `_http_get_json(url: str, *, timeout: float = 10.0) -> dict[str, Any]`, `_USER_AGENT`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `tests/unit/paper/test_verify.py`:

```python
"""Testes do motor de verificação de referências (Fase 4 da ponte)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from prumo_assist.core.bib import BibEntry
from prumo_assist.domains.paper import verify


def _entry(body: str, *, citekey: str = "smith2020", entry_type: str = "article") -> BibEntry:
    return BibEntry(entry_type=entry_type, citekey=citekey, body=body)


class TestIdentifiers:
    def test_doi_campo_direto(self) -> None:
        ids = verify._identifiers_for(_entry("\n  doi = {10.1056/NEJMoa2002032},\n"))
        assert ids.doi == "10.1056/NEJMoa2002032"
        assert ids.pmid is None and ids.arxiv_id is None

    def test_doi_urlizado_e_prefixo(self) -> None:
        ids = verify._identifiers_for(_entry("doi = {https://doi.org/10.1000/xyz},"))
        assert ids.doi == "10.1000/xyz"
        ids2 = verify._identifiers_for(_entry('doi = "doi:10.1000/abc",'))
        assert ids2.doi == "10.1000/abc"

    def test_pmid_campo_dedicado(self) -> None:
        ids = verify._identifiers_for(_entry("pmid = {32109013},"))
        assert ids.pmid == "32109013"

    def test_pmid_no_note_estilo_bbt(self) -> None:
        ids = verify._identifiers_for(_entry("note = {PMID: 9500320},"))
        assert ids.pmid == "9500320"

    def test_arxiv_por_eprinttype(self) -> None:
        ids = verify._identifiers_for(
            _entry("eprint = {2301.00001},\n  eprinttype = {arXiv},")
        )
        assert ids.arxiv_id == "2301.00001"

    def test_arxiv_por_archiveprefix(self) -> None:
        ids = verify._identifiers_for(
            _entry("eprint = {2301.00002},\n  archiveprefix = {arxiv},")
        )
        assert ids.arxiv_id == "2301.00002"

    def test_sem_identificador(self) -> None:
        ids = verify._identifiers_for(_entry("title = {Sem nada},"))
        assert ids == verify.RefIdentifiers(doi=None, pmid=None, arxiv_id=None)

    def test_pmid_invalido_ignorado(self) -> None:
        # campo pmid não-numérico não vira identificador
        ids = verify._identifiers_for(_entry("pmid = {n/a},"))
        assert ids.pmid is None


class TestRefCache:
    def test_miss_em_cache_vazio(self, tmp_path: Path) -> None:
        cache = verify.RefCache(path=tmp_path / "c.json")
        assert cache.get("crossref:works:10.1/x") is None

    def test_put_get_roundtrip(self, tmp_path: Path) -> None:
        cache = verify.RefCache(path=tmp_path / "sub" / "c.json")  # cria diretórios
        cache.put("k1", {"a": 1})
        assert cache.get("k1") == {"a": 1}

    def test_ttl_expira(self, tmp_path: Path) -> None:
        cache = verify.RefCache(path=tmp_path / "c.json", ttl=timedelta(days=7))
        old = datetime.now(timezone.utc) - timedelta(days=8)
        cache.put("k1", {"a": 1}, now=old)
        assert cache.get("k1") is None
        # dentro do TTL segue vivo
        cache.put("k2", {"b": 2}, now=datetime.now(timezone.utc) - timedelta(days=6))
        assert cache.get("k2") == {"b": 2}

    def test_arquivo_corrompido_vira_cache_vazio(self, tmp_path: Path) -> None:
        p = tmp_path / "c.json"
        p.write_text("{nao é json", encoding="utf-8")
        cache = verify.RefCache(path=p)
        assert cache.get("k") is None
        cache.put("k", {"ok": True})  # não explode; regrava do zero
        assert cache.get("k") == {"ok": True}

    def test_default_cache_path_respeita_xdg(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
        assert verify.default_cache_path() == tmp_path / "prumo-assist" / "refcheck.json"

    def test_default_cache_path_fallback_home(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        p = verify.default_cache_path()
        assert p.name == "refcheck.json" and ".cache" in p.parts


class TestHttpSeam:
    def test_user_agent_identifica_projeto_sem_pii(self) -> None:
        assert "prumo-assist/" in verify._USER_AGENT
        assert "@" not in verify._USER_AGENT  # sem e-mail/PII
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `uv run pytest tests/unit/paper/test_verify.py -x -q`
Expected: FAIL — `ModuleNotFoundError` / `ImportError` (verify não existe).

- [ ] **Step 3: Implementação mínima**

Criar `src/prumo_assist/domains/paper/verify.py`:

```python
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
from datetime import datetime, timedelta, timezone
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
_PMID_IN_BODY_RE = re.compile(r"\bPMID:?\s*(\d{1,9})\b", re.IGNORECASE)


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
    return doi or None


def _identifiers_for(entry: BibEntry) -> RefIdentifiers:
    """Extrai DOI/PMID/arXiv tolerando as convenções do BBT.

    PMID: campo dedicado ``pmid`` OU padrão ``PMID: NNNN`` em qualquer campo
    (BBT costuma despejar no ``note``). arXiv: ``eprint`` quando
    ``eprinttype``/``archiveprefix`` é ``arxiv`` (case-insensitive).
    """
    raw_doi = extract_field(entry.body, "doi")
    doi = _normalize_doi(raw_doi) if raw_doi else None

    pmid: str | None = None
    raw_pmid = extract_field(entry.body, "pmid")
    if raw_pmid and raw_pmid.strip().isdigit():
        pmid = raw_pmid.strip()
    else:
        m = _PMID_IN_BODY_RE.search(entry.body)
        if m:
            pmid = m.group(1)

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
        moment = now or datetime.now(timezone.utc)
        if moment - fetched_at > self.ttl:
            return None
        return cast(dict[str, Any], payload) if isinstance(payload, dict) else None

    def put(self, key: str, payload: dict[str, Any], *, now: datetime | None = None) -> None:
        data = self._load()
        moment = now or datetime.now(timezone.utc)
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
```

- [ ] **Step 4: Rodar para ver passar + bateria**

Run: `uv run pytest tests/unit/paper/test_verify.py -q && uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy`
Expected: tudo PASS/limpo. Nenhum teste toca a rede (não há chamada real a `_http_get_json` nos testes).

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/paper/verify.py tests/unit/paper/test_verify.py
git commit -m "feat(paper): fundação do verify-refs — identificadores BBT, cache TTL, seam HTTP (Fase 4)"
```

---

### Task 2: Checks nativos — `check_entry` + `verify_refs` (Crossref/PubMed, retração, título)

**Files:**
- Modify: `src/prumo_assist/domains/paper/verify.py` (append)
- Test: `tests/unit/paper/test_verify.py` (append)

**Interfaces:**
- Consumes (Task 1): `RefIdentifiers`, `_identifiers_for`, `RefCache`, `default_cache_path`, `_http_get_json`.
- Consumes (repo): `prumo_assist.core.bib.parse_bib(text: str) -> list[BibEntry]`; `prumo_assist.core.citations.scan_marked_citekeys(markdown_text: str) -> list[str]` (citekeys em formas MARCADAS `[[@key]]`/`[@key]`, ordenadas).
- Produces (Tasks 3–4 consomem): `Finding` (frozen: `citekey: str`, `level: str` em {"error","warning","info"}, `kind: str`, `message: str`, `source: str`), `check_entry(entry: BibEntry, *, cache: RefCache, refresh: bool = False) -> list[Finding]`, `verify_refs(pj_path: Path, *, page: Path | None = None, refresh: bool = False, cache_path: Path | None = None) -> dict[str, Any]` (Task 3 ADICIONA o kwarg `deep`). Report dict: `{"pj": str, "page": str | None, "scope": list[str], "checked": int, "findings": [asdict(Finding), ...], "summary": {"errors": int, "warnings": int, "infos": int}}`.

Kinds e níveis (exatos — os testes cobram):

| kind | level | fonte | gatilho |
|---|---|---|---|
| `doi-not-found` | error | crossref | HTTP 404 em `works/{doi}` |
| `retracted` | error | crossref | `update-to[].type == "retraction"` no filtro `updates:` |
| `retracted` | error | pubmed | `pubtype` contém `"Retracted Publication"` (só se o Crossref ainda não acusou) |
| `title-mismatch` | warning | crossref | similaridade título bib × Crossref < 0.6 |
| `pmid-not-found` | warning | pubmed | esummary devolve erro para o id |
| `no-identifier` | info | local | entrada sem DOI e sem PMID |
| `network-error` | error | crossref/pubmed | URLError/timeout/JSON inválido/HTTP != 404 |
| `missing-citekey` | info | local | citekey na página sem entrada no bib (só com `--page`) |

- [ ] **Step 1: Escrever os testes que falham**

Append em `tests/unit/paper/test_verify.py`:

```python
import urllib.error
from collections.abc import Callable
from email.message import Message
from typing import Any, cast

from prumo_assist.core.bib import parse_bib


def _http_404(url: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, 404, "Not Found", Message(), None)


def _fake_http(responses: dict[str, Any]) -> Callable[..., dict[str, Any]]:
    """Fábrica de fake do seam: mapeia substring da URL → payload ou exceção."""

    def fake(url: str, *, timeout: float = 10.0) -> dict[str, Any]:
        for fragment, value in responses.items():
            if fragment in url:
                if isinstance(value, Exception):
                    raise value
                return cast(dict[str, Any], value)
        raise AssertionError(f"URL inesperada no teste: {url}")

    return fake


_WORKS_OK = {"message": {"title": ["Clinical Characteristics of Coronavirus Disease 2019 in China"]}}
_UPDATES_EMPTY = {"message": {"items": []}}
_UPDATES_RETRACTED = {
    "message": {"items": [{"DOI": "10.x/notice", "update-to": [{"type": "retraction", "DOI": "10.1056/nejmoa2002032"}]}]}
}
_ESUMMARY_RETRACTED = {
    "result": {"9500320": {"title": "...", "pubtype": ["Journal Article", "Retracted Publication"]}}
}
_ESUMMARY_OK = {"result": {"32109013": {"title": "...", "pubtype": ["Journal Article"]}}}
_ESUMMARY_BAD_ID = {"result": {"999999999": {"error": "cannot get document summary"}}}


def _bib_entry_doi(title: str = "Clinical Characteristics of Coronavirus Disease 2019 in China") -> BibEntry:
    return _entry(f"title = {{{title}}},\n  doi = {{10.1056/NEJMoa2002032}},")


class TestCheckEntry:
    def _cache(self, tmp_path: Path) -> verify.RefCache:
        return verify.RefCache(path=tmp_path / "cache.json")

    def test_ok_sem_achados(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify._http_get_json",
            _fake_http({"api.crossref.org/works?filter=updates": _UPDATES_EMPTY, "api.crossref.org/works/": _WORKS_OK}),
        )
        assert verify.check_entry(_bib_entry_doi(), cache=self._cache(tmp_path)) == []

    def test_doi_404_vira_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify._http_get_json",
            _fake_http({"api.crossref.org/works/": _http_404("u")}),
        )
        findings = verify.check_entry(_bib_entry_doi(), cache=self._cache(tmp_path))
        assert [(f.kind, f.level) for f in findings] == [("doi-not-found", "error")]
        assert "Zotero" in findings[0].message  # comando de correção pt-BR

    def test_retracao_crossref(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify._http_get_json",
            _fake_http({"api.crossref.org/works?filter=updates": _UPDATES_RETRACTED, "api.crossref.org/works/": _WORKS_OK}),
        )
        findings = verify.check_entry(_bib_entry_doi(), cache=self._cache(tmp_path))
        assert [(f.kind, f.level, f.source) for f in findings] == [("retracted", "error", "crossref")]
        assert "RETRATADO" in findings[0].message

    def test_retracao_pubmed_sem_duplicar_crossref(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        entry = _entry(
            "title = {X},\n  doi = {10.1056/NEJMoa2002032},\n  note = {PMID: 9500320},"
        )
        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify._http_get_json",
            _fake_http(
                {
                    "api.crossref.org/works?filter=updates": _UPDATES_RETRACTED,
                    "api.crossref.org/works/": {"message": {"title": ["X"]}},
                    "eutils.ncbi.nlm.nih.gov": _ESUMMARY_RETRACTED,
                }
            ),
        )
        findings = verify.check_entry(entry, cache=self._cache(tmp_path))
        retracted = [f for f in findings if f.kind == "retracted"]
        assert len(retracted) == 1 and retracted[0].source == "crossref"

    def test_retracao_so_pubmed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        entry = _entry("title = {X},\n  note = {PMID: 9500320},")
        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify._http_get_json",
            _fake_http({"eutils.ncbi.nlm.nih.gov": _ESUMMARY_RETRACTED}),
        )
        findings = verify.check_entry(entry, cache=self._cache(tmp_path))
        assert [(f.kind, f.level, f.source) for f in findings] == [("retracted", "error", "pubmed")]

    def test_title_mismatch_warning(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify._http_get_json",
            _fake_http(
                {
                    "api.crossref.org/works?filter=updates": _UPDATES_EMPTY,
                    "api.crossref.org/works/": {"message": {"title": ["Um Trabalho Completamente Diferente Sobre Outra Coisa"]}},
                }
            ),
        )
        findings = verify.check_entry(_bib_entry_doi("Efeitos da Metformina em Idosos"), cache=self._cache(tmp_path))
        assert [(f.kind, f.level) for f in findings] == [("title-mismatch", "warning")]

    def test_pmid_invalido_warning(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        entry = _entry("title = {X},\n  pmid = {999999999},")
        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify._http_get_json",
            _fake_http({"eutils.ncbi.nlm.nih.gov": _ESUMMARY_BAD_ID}),
        )
        findings = verify.check_entry(entry, cache=self._cache(tmp_path))
        assert [(f.kind, f.level) for f in findings] == [("pmid-not-found", "warning")]

    def test_sem_identificador_info(self, tmp_path: Path) -> None:
        findings = verify.check_entry(_entry("title = {Só título},"), cache=self._cache(tmp_path))
        assert [(f.kind, f.level) for f in findings] == [("no-identifier", "info")]
        assert "--deep" in findings[0].message

    def test_rede_fora_vira_network_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify._http_get_json",
            _fake_http({"api.crossref.org/works/": urllib.error.URLError("dns down")}),
        )
        findings = verify.check_entry(_bib_entry_doi(), cache=self._cache(tmp_path))
        assert [(f.kind, f.level) for f in findings] == [("network-error", "error")]

    def test_cache_evita_segunda_chamada(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []

        def fake(url: str, *, timeout: float = 10.0) -> dict[str, Any]:
            calls.append(url)
            if "filter=updates" in url:
                return cast(dict[str, Any], _UPDATES_EMPTY)
            return cast(dict[str, Any], _WORKS_OK)

        monkeypatch.setattr("prumo_assist.domains.paper.verify._http_get_json", fake)
        cache = self._cache(tmp_path)
        verify.check_entry(_bib_entry_doi(), cache=cache)
        first = len(calls)
        verify.check_entry(_bib_entry_doi(), cache=cache)
        assert len(calls) == first  # segunda rodada 100% cache

    def test_refresh_ignora_cache(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []

        def fake(url: str, *, timeout: float = 10.0) -> dict[str, Any]:
            calls.append(url)
            if "filter=updates" in url:
                return cast(dict[str, Any], _UPDATES_EMPTY)
            return cast(dict[str, Any], _WORKS_OK)

        monkeypatch.setattr("prumo_assist.domains.paper.verify._http_get_json", fake)
        cache = self._cache(tmp_path)
        verify.check_entry(_bib_entry_doi(), cache=cache)
        first = len(calls)
        verify.check_entry(_bib_entry_doi(), cache=cache, refresh=True)
        assert len(calls) == first * 2


_BIB_TEXT = """@article{guan2020clinical,
  title = {Clinical Characteristics of Coronavirus Disease 2019 in China},
  doi = {10.1056/NEJMoa2002032},
}
@article{semid2024,
  title = {Trabalho sem identificador},
}
"""


class TestVerifyRefs:
    def _pj(self, tmp_path: Path) -> Path:
        (tmp_path / "references").mkdir(parents=True)
        (tmp_path / "references" / "_references.bib").write_text(_BIB_TEXT, encoding="utf-8")
        return tmp_path

    def test_bib_ausente_hard_fail(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Better BibTeX"):
            verify.verify_refs(tmp_path)

    def test_escopo_todo_bib(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify._http_get_json",
            _fake_http({"api.crossref.org/works?filter=updates": _UPDATES_EMPTY, "api.crossref.org/works/": _WORKS_OK}),
        )
        report = verify.verify_refs(self._pj(tmp_path), cache_path=tmp_path / "c.json")
        assert report["scope"] == ["guan2020clinical", "semid2024"]
        assert report["checked"] == 2
        assert report["summary"] == {"errors": 0, "warnings": 0, "infos": 1}
        kinds = {f["kind"] for f in report["findings"]}
        assert kinds == {"no-identifier"}

    def test_escopo_por_pagina_e_missing_citekey(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pj = self._pj(tmp_path)
        pagina = tmp_path / "draft.md"
        pagina.write_text(
            "Como mostrado em [[@guan2020clinical]] e também [@naoexiste2020].\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify._http_get_json",
            _fake_http({"api.crossref.org/works?filter=updates": _UPDATES_EMPTY, "api.crossref.org/works/": _WORKS_OK}),
        )
        report = verify.verify_refs(pj, page=pagina, cache_path=tmp_path / "c.json")
        assert report["scope"] == ["guan2020clinical"]  # semid2024 fora: página não cita
        missing = [f for f in report["findings"] if f["kind"] == "missing-citekey"]
        assert [m["citekey"] for m in missing] == ["naoexiste2020"]
        assert "prumo paper lint" in missing[0]["message"]
        assert report["page"] == str(pagina)
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `uv run pytest tests/unit/paper/test_verify.py -x -q`
Expected: FAIL — `AttributeError: ... no attribute 'check_entry'`.

- [ ] **Step 3: Implementar**

Append em `src/prumo_assist/domains/paper/verify.py` (novos imports no topo: `import difflib`, `import urllib.error`, `from dataclasses import asdict`, `from urllib.parse import quote`; e `parse_bib`/`scan_marked_citekeys`):

```python
import difflib
import urllib.error
from dataclasses import asdict
from urllib.parse import quote

from prumo_assist.core.bib import parse_bib
from prumo_assist.core.citations import scan_marked_citekeys

_CROSSREF_WORKS_URL = "https://api.crossref.org/works/{doi}"
_CROSSREF_UPDATES_URL = "https://api.crossref.org/works?filter=updates:{doi}&rows=5&select=DOI,update-to"
_PUBMED_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json"

_TITLE_SIMILARITY_FLOOR = 0.6

_NETWORK_ERRORS = (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError)


@dataclass(frozen=True)
class Finding:
    """Um achado de verificação sobre UMA entrada do bib."""

    citekey: str
    level: str  # "error" | "warning" | "info" — só "error" deriva exit 1
    kind: str
    message: str
    source: str  # "crossref" | "pubmed" | "local" | "refchecker"


def _cached_get_json(
    cache: RefCache, key: str, url: str, *, refresh: bool
) -> dict[str, Any]:
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
            cache, f"crossref:works:{doi.lower()}", _CROSSREF_WORKS_URL.format(doi=quoted), refresh=refresh
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
    except (urllib.error.HTTPError, *_NETWORK_ERRORS) as exc:
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


def _check_pubmed(
    citekey: str, pmid: str, *, cache: RefCache, refresh: bool
) -> list[Finding]:
    try:
        summary = _cached_get_json(
            cache, f"pubmed:esummary:{pmid}", _PUBMED_ESUMMARY_URL.format(pmid=pmid), refresh=refresh
        )
    except (urllib.error.HTTPError, *_NETWORK_ERRORS) as exc:
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


def check_entry(
    entry: BibEntry, *, cache: RefCache, refresh: bool = False
) -> list[Finding]:
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


def verify_refs(
    pj_path: Path,
    *,
    page: Path | None = None,
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
    by_key = {e.citekey: e for e in entries}

    findings: list[Finding] = []
    if page is not None:
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
        scope = [e.citekey for e in entries]

    cache = RefCache(path=cache_path or default_cache_path())
    for key in scope:
        findings.extend(check_entry(by_key[key], cache=cache, refresh=refresh))

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
        "findings": [asdict(f) for f in findings],
        "summary": summary,
    }
```

- [ ] **Step 4: Rodar para ver passar + bateria**

Run: `uv run pytest tests/unit/paper/test_verify.py -q && uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy`
Expected: tudo PASS/limpo.

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/paper/verify.py tests/unit/paper/test_verify.py
git commit -m "feat(paper): checks nativos do verify-refs — existência, retração e título via Crossref/PubMed"
```

---

### Task 3: Camada profunda `--deep` — refchecker pinado via uvx

**Files:**
- Modify: `src/prumo_assist/domains/paper/verify.py` (append + assinatura de `verify_refs`)
- Test: `tests/unit/paper/test_verify.py` (append)

**Interfaces:**
- Consumes (Tasks 1–2): `Finding`, `verify_refs`, `BibEntry`.
- Produces (Task 4 consome): `RefcheckerUnavailableError(RuntimeError)`; constante PÚBLICA `REFCHECKER_PIN = "academic-refchecker==3.0.151"` (o CLI usa no texto de help); `verify_refs` ganha kwarg `deep: bool = False` (assinatura final: `verify_refs(pj_path, *, page=None, deep=False, refresh=False, cache_path=None) -> dict[str, Any]`) e o report ganha a chave `"deep": bool`. Internos: `_bib_subset_text(entries: Sequence[BibEntry]) -> str`, `_run_refchecker(bib_text: str, *, timeout: float = 600.0) -> dict[str, Any]`, `_findings_from_report(report: dict[str, Any], scope: set[str]) -> list[Finding]`.
- Fatos do spike que o código DEVE honrar: exit 0 mesmo com erros (gate = report.json); records mapeiam ao citekey por `original_reference.bibtex_key`; achados deep = `warning` com kind `refchecker:{error_type}`.

- [ ] **Step 1: Escrever os testes que falham**

Append em `tests/unit/paper/test_verify.py`:

```python
import subprocess


_REPORT_FIXTURE: dict[str, Any] = {
    "generated_at": "2026-07-24",
    "summary": {"total_references_processed": 2, "total_errors_found": 2},
    "papers": [],
    "records": [
        {
            "error_type": "author",
            "error_details": "Author count mismatch: 3 cited vs 37 correct:\n  cited: ...",
            "original_reference": {"bibtex_key": "guan2020clinical", "doi": "10.1056/nejmoa2002032"},
        },
        {
            "error_type": "multiple",
            "error_details": "Non-existent web page: https://doi.org/10.9999/fake",
            "original_reference": {"bibtex_key": "fora_do_escopo2024", "doi": "10.9999/fake"},
        },
        {"sem_error_type": True},
    ],
}


class TestDeepLayer:
    def test_bib_subset_reconstroi_entradas(self) -> None:
        entries = [
            BibEntry(entry_type="article", citekey="a1", body="\n  title = {T1},\n"),
            BibEntry(entry_type="book", citekey="b2", body="\n  title = {T2},\n"),
        ]
        text = verify._bib_subset_text(entries)
        assert "@article{a1," in text and "@book{b2," in text
        assert len(parse_bib(text)) == 2  # roundtrip pelo parser do repo

    def test_findings_do_report_filtra_escopo_e_vira_warning(self) -> None:
        findings = verify._findings_from_report(_REPORT_FIXTURE, {"guan2020clinical"})
        assert len(findings) == 1
        f = findings[0]
        assert f.citekey == "guan2020clinical"
        assert f.level == "warning" and f.source == "refchecker"
        assert f.kind == "refchecker:author"
        assert "Author count mismatch" in f.message

    def test_run_refchecker_uvx_ausente(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            raise FileNotFoundError("uvx")

        monkeypatch.setattr("prumo_assist.domains.paper.verify.subprocess.run", fake_run)
        with pytest.raises(verify.RefcheckerUnavailableError, match="uvx"):
            verify._run_refchecker("@article{a,}")

    def test_run_refchecker_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            raise subprocess.TimeoutExpired(cmd="uvx", timeout=1)

        monkeypatch.setattr("prumo_assist.domains.paper.verify.subprocess.run", fake_run)
        with pytest.raises(verify.RefcheckerUnavailableError, match="excedeu"):
            verify._run_refchecker("@article{a,}", timeout=1)

    def test_run_refchecker_exit_zero_com_report(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            report_path = Path(cmd[cmd.index("--report-file") + 1])
            report_path.write_text(json.dumps(_REPORT_FIXTURE), encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr("prumo_assist.domains.paper.verify.subprocess.run", fake_run)
        report = verify._run_refchecker("@article{a,}")
        assert report["summary"]["total_errors_found"] == 2

    def test_run_refchecker_sem_report_e_hostil(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")  # exit 0, sem report!

        monkeypatch.setattr("prumo_assist.domains.paper.verify.subprocess.run", fake_run)
        with pytest.raises(verify.RefcheckerUnavailableError, match="report"):
            verify._run_refchecker("@article{a,}")

        def fake_run_list(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            report_path = Path(cmd[cmd.index("--report-file") + 1])
            report_path.write_text("[1, 2]", encoding="utf-8")  # JSON válido mas não-dict
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr("prumo_assist.domains.paper.verify.subprocess.run", fake_run_list)
        with pytest.raises(verify.RefcheckerUnavailableError):
            verify._run_refchecker("@article{a,}")

    def test_verify_refs_deep_mescla_warnings(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / "references").mkdir()
        (tmp_path / "references" / "_references.bib").write_text(_BIB_TEXT, encoding="utf-8")
        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify._http_get_json",
            _fake_http({"api.crossref.org/works?filter=updates": _UPDATES_EMPTY, "api.crossref.org/works/": _WORKS_OK}),
        )

        def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            bib_path = Path(cmd[cmd.index("--paper") + 1])
            assert "guan2020clinical" in bib_path.read_text(encoding="utf-8")  # subset em escopo
            report_path = Path(cmd[cmd.index("--report-file") + 1])
            report_path.write_text(json.dumps(_REPORT_FIXTURE), encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr("prumo_assist.domains.paper.verify.subprocess.run", fake_run)
        report = verify.verify_refs(tmp_path, deep=True, cache_path=tmp_path / "c.json")
        assert report["deep"] is True
        deep_findings = [f for f in report["findings"] if f["source"] == "refchecker"]
        assert [f["kind"] for f in deep_findings] == ["refchecker:author"]
        assert report["summary"]["warnings"] == 1  # deep nunca vira error

    def test_verify_refs_sem_deep_nao_roda_subprocess(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        (tmp_path / "references").mkdir()
        (tmp_path / "references" / "_references.bib").write_text(_BIB_TEXT, encoding="utf-8")
        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify._http_get_json",
            _fake_http({"api.crossref.org/works?filter=updates": _UPDATES_EMPTY, "api.crossref.org/works/": _WORKS_OK}),
        )

        def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            raise AssertionError("subprocess não deveria rodar sem --deep")

        monkeypatch.setattr("prumo_assist.domains.paper.verify.subprocess.run", fake_run)
        report = verify.verify_refs(tmp_path, cache_path=tmp_path / "c.json")
        assert report["deep"] is False
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `uv run pytest tests/unit/paper/test_verify.py -x -q`
Expected: FAIL — `AttributeError: ... no attribute '_bib_subset_text'`.

- [ ] **Step 3: Implementar**

Append em `verify.py` (novos imports: `import subprocess`, `import tempfile`, `from collections.abc import Sequence`):

```python
import subprocess
import tempfile
from collections.abc import Sequence

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
                "report do refchecker não é o JSON esperado (objeto no topo). "
                f"{_REFCHECKER_HINT}"
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
        findings.append(
            Finding(
                citekey=citekey,
                level="warning",
                kind=f"refchecker:{error_type}",
                message=(
                    f"[deep] {first_line} — confira a entrada no Zotero e re-exporte o BBT."
                ),
                source="refchecker",
            )
        )
    return findings
```

E em `verify_refs`: adicionar o kwarg `deep: bool = False` (entre `page` e `refresh`), e antes do bloco `summary = {...}`:

```python
    if deep and scope:
        deep_report = _run_refchecker(_bib_subset_text([by_key[k] for k in scope]))
        findings.extend(_findings_from_report(deep_report, set(scope)))
```

E no dict de retorno, adicionar a chave `"deep": deep`.

- [ ] **Step 4: Rodar para ver passar + bateria**

Run: `uv run pytest tests/unit/paper/test_verify.py -q && uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy`
Expected: tudo PASS/limpo.

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/paper/verify.py tests/unit/paper/test_verify.py
git commit -m "feat(paper): camada profunda --deep via refchecker pinado (exit 0 != ok; report é o gate)"
```

---

### Task 4: CLI `prumo paper verify-refs` + re-export em `api.py`

**Files:**
- Modify: `src/prumo_assist/domains/paper/cli.py` (novo comando)
- Modify: `src/prumo_assist/domains/paper/api.py` (re-export puro)
- Test: `tests/unit/paper/test_cli.py` (append)

**Interfaces:**
- Consumes (Task 3): `verify.verify_refs(pj_path, *, page=None, deep=False, refresh=False, cache_path=None) -> dict[str, Any]` (report com `summary.errors/warnings/infos`, `checked`, `findings`), `verify.RefcheckerUnavailableError`.
- Padrão da casa: fachada fina no molde do `lint_command` (mesmo arquivo, linhas 73–88) — `cli_run(json_mode=...)`, saída via `console`, `typer.Exit(code=1)` quando há erro. `cli_run` aceita `catches=` (tupla de exceções → erro pt-BR limpo; ver `_EXPORT_CATCHES`/`_REVIEW_CATCHES` em `domains/write/cli.py` como molde).

- [ ] **Step 1: Escrever os testes que falham**

Append em `tests/unit/paper/test_cli.py` — o arquivo já tem `runner = CliRunner()`, `from prumo_assist.cli import app` e helpers (`_bootstrap_project`, `_last_json`); mypy strict COBRE `tests/` (pyproject `files = ["src/prumo_assist", "tests"]`), então tudo anotado. Novo import no topo do arquivo: `import pytest` (se ainda não houver) e `from typing import Any`:

```python
def _fake_report(pj: Path, **overrides: Any) -> dict[str, Any]:
    report: dict[str, Any] = {
        "pj": str(pj), "page": None, "scope": ["a1"], "checked": 1,
        "findings": [], "summary": {"errors": 0, "warnings": 0, "infos": 0},
        "deep": False,
    }
    report.update(overrides)
    return report


def test_verify_refs_ok_exit_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = _fake_report(tmp_path)

    def fake(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return report

    monkeypatch.setattr("prumo_assist.domains.paper.verify.verify_refs", fake)
    result = runner.invoke(app, ["paper", "verify-refs", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "verificada" in result.output


def test_verify_refs_erro_exit_um(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = _fake_report(
        tmp_path,
        findings=[
            {"citekey": "a1", "level": "error", "kind": "retracted",
             "message": "RETRATADO: reavalie a citação.", "source": "crossref"},
        ],
        summary={"errors": 1, "warnings": 0, "infos": 0},
    )

    def fake(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return report

    monkeypatch.setattr("prumo_assist.domains.paper.verify.verify_refs", fake)
    result = runner.invoke(app, ["paper", "verify-refs", str(tmp_path)])
    assert result.exit_code == 1
    assert "a1" in result.output and "retracted" in result.output


def test_verify_refs_repassa_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake(
        pj_path: Path,
        *,
        page: Path | None = None,
        deep: bool = False,
        refresh: bool = False,
        cache_path: Path | None = None,
    ) -> dict[str, Any]:
        captured.update(pj=pj_path, page=page, deep=deep, refresh=refresh)
        return _fake_report(pj_path, scope=[], checked=0, deep=deep)

    monkeypatch.setattr("prumo_assist.domains.paper.verify.verify_refs", fake)
    pagina = tmp_path / "p.md"
    pagina.write_text("x", encoding="utf-8")
    result = runner.invoke(
        app,
        ["paper", "verify-refs", str(tmp_path), "--page", str(pagina), "--deep", "--refresh"],
    )
    assert result.exit_code == 0, result.output
    assert captured["deep"] is True and captured["refresh"] is True
    assert captured["page"] == pagina.resolve()


def test_verify_refs_bib_ausente_mensagem_limpa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise FileNotFoundError("_references.bib não existe — Better BibTeX export?")

    monkeypatch.setattr("prumo_assist.domains.paper.verify.verify_refs", fake)
    result = runner.invoke(app, ["paper", "verify-refs", str(tmp_path)])
    assert result.exit_code == 1
    assert "Better BibTeX" in result.output
```

(Padrão dos fakes: sempre `def` com `*args: Any, **kwargs: Any` anotados — mypy strict cobre `tests/`.)

- [ ] **Step 2: Rodar para ver falhar**

Run: `uv run pytest tests/unit/paper/test_cli.py -x -q`
Expected: FAIL — exit code 2 do Typer ("No such command 'verify-refs'").

- [ ] **Step 3: Implementar**

Em `src/prumo_assist/domains/paper/cli.py` — import no topo (junto dos outros imports de domínio): `from prumo_assist.domains.paper import verify` e a tupla de catches ao lado do `paper_app`:

```python
_VERIFY_CATCHES = (FileNotFoundError, verify.RefcheckerUnavailableError)
```

Novo comando (depois do `lint_command`, seguindo o mesmo estilo):

```python
@paper_app.command("verify-refs")
def verify_refs_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    page: Annotated[
        Path | None,
        typer.Option("--page", help="Escopo: só citekeys marcadas nesta página .md (recomendado)."),
    ] = None,
    deep: Annotated[
        bool,
        typer.Option("--deep", help=f"Verificação profunda via `uvx {verify.REFCHECKER_PIN}` (lento sem chave)."),
    ] = False,
    refresh: Annotated[bool, typer.Option("--refresh", help="Ignora o cache local (TTL 7 dias).")] = False,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Verifica referências do bib: existência (Crossref), retração (Crossref/PubMed), título."""
    with cli_run(json_mode=json_mode, catches=_VERIFY_CATCHES) as console:
        report = verify.verify_refs(
            path.resolve(),
            page=page.resolve() if page is not None else None,
            deep=deep,
            refresh=refresh,
        )
        for finding in report["findings"]:
            line = f"[{finding['level']}] {finding['citekey']}: {finding['kind']} — {finding['message']}"
            if finding["level"] == "error":
                console.error(line)
            elif finding["level"] == "warning":
                console.warn(line)
            else:
                console.info(line)
        summary = report["summary"]
        if summary["errors"]:
            console.error(
                f"{report['checked']} referência(s) verificada(s): {summary['errors']} erro(s), "
                f"{summary['warnings']} warning(s)."
            )
        else:
            console.success(
                f"{report['checked']} referência(s) verificada(s) — "
                f"{summary['warnings']} warning(s), {summary['infos']} info(s)."
            )
        console.emit(report)
        if summary["errors"]:
            raise typer.Exit(code=1)
```

ATENÇÃO: `cli_run`/`typer`/`Annotated`/`Path` já estão importados no topo de `paper/cli.py` — NÃO duplicar. `cli_run(json_mode=..., catches=...)` é o padrão já usado em `domains/write/cli.py` (`_REVIEW_CATCHES`) — mesma mecânica aqui.

Em `src/prumo_assist/domains/paper/api.py`: adicionar `from prumo_assist.domains.paper.verify import verify_refs` (ordem alfabética dos imports) e `"verify_refs"` no `__all__`.

- [ ] **Step 4: Rodar para ver passar + bateria**

Run: `uv run pytest tests/unit/paper/ -q && uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy`
Expected: tudo PASS/limpo.

- [ ] **Step 5: Smoke manual (rede real, fora da suite)**

Run (no diretório do repo; `SMOKE` é um dir descartável):

```bash
SMOKE=$(mktemp -d) && mkdir -p "$SMOKE/references" && printf '@article{wakefield1998retracted,\n  title = {Ileal-lymphoid-nodular hyperplasia, non-specific colitis, and pervasive developmental disorder in children},\n  doi = {10.1016/S0140-6736(97)11096-0},\n}\n' > "$SMOKE/references/_references.bib" && uv run prumo paper verify-refs "$SMOKE"; echo "exit: $?"; rm -rf "$SMOKE"
```
Expected: achado `retracted` (error) para `wakefield1998retracted`, exit 1. (Se offline: `network-error`, também exit 1 — registrar qual dos dois ocorreu no summary do subagente.)

- [ ] **Step 6: Commit**

```bash
git add src/prumo_assist/domains/paper/cli.py src/prumo_assist/domains/paper/api.py tests/unit/paper/test_cli.py
git commit -m "feat(paper): CLI verify-refs — fachada fina com escopo por página e exit gate em errors"
```

---

### Task 5: Hardening herdado da fila F2+F3 — guarda de re-ingest + timeout no seam adeu

**Files:**
- Modify: `src/prumo_assist/domains/write/review.py` (função `ingest`, linha ~2187; função `_run_adeu_extract`, linha ~715)
- Modify: `src/prumo_assist/domains/write/cli.py` (comando `review ingest` — flag `--force`)
- Test: `tests/unit/write/test_review_ingest.py` (append), `tests/unit/write/test_review_adeu.py` (append), `tests/unit/write/test_cli.py` (append — repasse da flag)

**Interfaces:**
- `ingest(reviewed_docx: Path, page: Path, project_root: Path | None = None)` ganha kwarg keyword-only `force: bool = False` → assinatura final `ingest(reviewed_docx, page, project_root=None, *, force=False) -> IngestResult`.
- Contexto (fila registrada no archive da F3, commit 711c0c0): "aviso re-ingest com worklist pendente (prioridade subiu — protege propostas do agente)". Hoje o `ingest` SOBRESCREVE `reviews/<slug>/review.md` silenciosamente — se houver marcas pendentes (inclusive propostas do agente via `propose_prose_edit`), elas são destruídas. O fix é código, não só doc: hard-fail com `--force` para optar pelo descarte.
- Já coberto (NÃO refazer): payload não-dict no adeu já cai no catch `TypeError` existente do `_run_adeu_extract`; o item restante da fila é só o **timeout**.

- [ ] **Step 1: Escrever os testes que falham**

Append em `tests/unit/write/test_review_ingest.py` — o arquivo já define os helpers `_init_project(tmp_path, *, body) -> tuple[Path, Path]` (linha ~135), `_write_docx(path, *, paragraphs, with_comment)` (~121), `_write_sidecars(project_root, page, *, source_text, docx_sha256, occurrences=None)` (~148), `_comment_paragraph()` (~100) e a constante `_UNRELATED_DOCX_SHA256`; `review`, `ingest` e `pytest` já estão importados (ver o happy path na linha ~185, que é exatamente esta receita):

```python
def _ingest_ok_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, Path]:
    """Receita mínima de ingest válido (mesma do happy path, linha ~185):
    devolve (project_root, page, docx) com adeu mockado no seam."""
    prefix = "O paciente recebeu o tratamento"
    suffix = " conforme protocolo estabelecido pela equipe."
    body = prefix + suffix
    project_root, page = _init_project(tmp_path, body=body)
    docx = _write_docx(
        tmp_path / "revisado.docx", paragraphs=[_comment_paragraph()], with_comment=True
    )
    _write_sidecars(project_root, page, source_text=body, docx_sha256=_UNRELATED_DOCX_SHA256)
    adeu_markdown = prefix + "{++ novo++}{>>[Chg:1 insert] Coautor<<}" + suffix
    monkeypatch.setattr(review, "_run_adeu_extract", lambda _docx: adeu_markdown)
    return project_root, page, docx


def test_reingest_com_worklist_pendente_hard_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root, page, docx = _ingest_ok_setup(tmp_path, monkeypatch)
    first = ingest(reviewed_docx=docx, page=page, project_root=project_root)
    assert first.marks_applied == 1  # worklist ficou com marca pendente

    with pytest.raises(ValueError, match=r"marca\(s\) pendente"):
        ingest(reviewed_docx=docx, page=page, project_root=project_root)
    # a mensagem embute os DOIS caminhos de saída (decidir ou --force):
    with pytest.raises(ValueError, match="prumo write review apply"):
        ingest(reviewed_docx=docx, page=page, project_root=project_root)
    with pytest.raises(ValueError, match="--force"):
        ingest(reviewed_docx=docx, page=page, project_root=project_root)


def test_reingest_com_force_sobrescreve_propostas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root, page, docx = _ingest_ok_setup(tmp_path, monkeypatch)
    first = ingest(reviewed_docx=docx, page=page, project_root=project_root)
    first.review_md.write_text(
        first.review_md.read_text()
        + "{++proposta do agente++}{>>prumo-autor: agente<<}"
    )
    result = ingest(reviewed_docx=docx, page=page, project_root=project_root, force=True)
    assert "proposta do agente" not in result.review_md.read_text()
    assert "{++ novo++}" in result.review_md.read_text()  # worklist regenerado


def test_reingest_com_worklist_consumido_nao_exige_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root, page, docx = _ingest_ok_setup(tmp_path, monkeypatch)
    first = ingest(reviewed_docx=docx, page=page, project_root=project_root)
    # simula worklist 100% consumido pelo apply: corpo sem nenhuma marca
    first.review_md.write_text("corpo decidido, sem marcas")
    result = ingest(reviewed_docx=docx, page=page, project_root=project_root)
    assert "{++ novo++}" in result.review_md.read_text()
```

Append em `tests/unit/write/test_cli.py` (repasse da flag pela fachada; `runner`/`app` já existem no arquivo; anotar tudo — mypy strict cobre `tests/`):

```python
def test_review_ingest_cli_repassa_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def fake_ingest(reviewed_docx: Path, page: Path, **kwargs: Any) -> Any:
        captured.update(kwargs)
        raise ValueError("stop aqui — só interessa a captura do kwarg")

    monkeypatch.setattr("prumo_assist.domains.write.review.ingest", fake_ingest)
    docx = tmp_path / "r.docx"
    docx.write_text("x")
    pagina = tmp_path / "p.md"
    pagina.write_text("x")
    runner.invoke(
        app, ["write", "review", "ingest", str(docx), "--page", str(pagina), "--force"]
    )
    assert captured["force"] is True
```

(Se `Any`/`pytest` ainda não estiverem importados em `test_cli.py` do write, adicionar no topo.)

Append em `tests/unit/write/test_review_adeu.py` (confira os imports do topo do arquivo — `subprocess`, `Path`, `pytest`, `review` e `Any` devem existir; adicionar os que faltarem; tudo anotado, mypy strict cobre `tests/`):

```python
def test_run_adeu_extract_passa_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, stdout='{"markdown": "ok"}', stderr="")

    monkeypatch.setattr("prumo_assist.domains.write.review.subprocess.run", fake_run)
    assert review._run_adeu_extract(Path("x.docx")) == "ok"
    assert captured["timeout"] == 120


def test_run_adeu_extract_timeout_vira_adeu_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="uvx", timeout=120)

    monkeypatch.setattr("prumo_assist.domains.write.review.subprocess.run", fake_run)
    with pytest.raises(review.AdeuUnavailableError, match="120"):
        review._run_adeu_extract(Path("x.docx"))
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `uv run pytest tests/unit/write/test_review_ingest.py tests/unit/write/test_review_adeu.py -x -q`
Expected: FAIL — `ingest()` não aceita `force` / timeout não repassado.

- [ ] **Step 3: Implementar**

(a) Em `review.py`, assinatura: `def ingest(reviewed_docx: Path, page: Path, project_root: Path | None = None, *, force: bool = False) -> IngestResult:`. Logo APÓS a linha `review_dir = project_root / "reviews" / slug` (linha ~2234), inserir:

```python
    # Guarda herdada da fila F2+F3 (archive da F3, 711c0c0): re-ingest
    # SOBRESCREVE o worklist — se há marcas pendentes (inclusive propostas do
    # agente via propose_prose_edit), destruí-las exige opt-in explícito.
    existing_review_md = review_dir / "review.md"
    if existing_review_md.exists() and not force:
        _fm, existing_body = split_frontmatter_raw(
            existing_review_md.read_text(encoding="utf-8")
        )
        pending = len(criticmarkup.parse(existing_body))
        if pending:
            raise ValueError(
                f"{existing_review_md} já existe com {pending} marca(s) pendente(s) — "
                "re-ingerir SOBRESCREVE o worklist (inclusive propostas do agente). "
                f"Decida primeiro com `prumo write review apply --page {page}` "
                "(--accept-all/--reject-all/--by-author/--mark) ou re-rode o ingest "
                "com --force para descartar as pendências."
            )
```

(`split_frontmatter_raw` e `criticmarkup` já são importados no módulo — não duplicar imports.)

(b) Em `_run_adeu_extract`: adicionar `timeout=120,` na chamada `subprocess.run([...], capture_output=True, text=True)` existente, e um novo `except` ANTES do tratamento de returncode (junto do `except FileNotFoundError`):

```python
    except subprocess.TimeoutExpired as exc:
        raise AdeuUnavailableError(
            "adeu (backend de PROSA pinado, `uvx adeu==1.29.0`) excedeu 120s — "
            f"rede lenta no primeiro download do uvx? Re-rode. {_ADEU_INSTALL_HINT}"
        ) from exc
```

(c) Em `write/cli.py`, no `review_ingest_command`: adicionar o parâmetro

```python
    force: Annotated[
        bool,
        typer.Option("--force", help="Re-ingere mesmo com marcas pendentes no worklist (DESCARTA as pendências)."),
    ] = False,
```

e repassar `review.ingest(reviewed_docx_resolved, page_resolved, force=force)`.

- [ ] **Step 4: Rodar para ver passar + bateria**

Run: `uv run pytest tests/unit/write/ -q && uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy`
Expected: tudo PASS/limpo — atenção especial: os testes EXISTENTES de ingest não podem quebrar (o guard só dispara com review.md pré-existente + marcas + sem force).

- [ ] **Step 5: Commit**

```bash
git add src/prumo_assist/domains/write/review.py src/prumo_assist/domains/write/cli.py tests/unit/write/test_review_ingest.py tests/unit/write/test_review_adeu.py tests/unit/write/test_cli.py
git commit -m "fix(write): re-ingest exige --force com worklist pendente; timeout de 120s no seam adeu (fila F2+F3)"
```

---

### Task 6: Skill `citation-support` + ADR-0018 + docs + bateria final

**Files:**
- Create: `skills/citation-support/SKILL.md`
- Create: `docs/adr/adr-0018-verificacao-referencias-apis-publicas.md`
- Modify: `ARCHITECTURE.md` (linha do `verify.py` no domínio paper; linha da skill nova, se houver seção de skills)
- Modify: `CHANGELOG.md` (seção "Não publicado")
- Regenerar índices: `uv run python .github/scripts/gen_indexes.py` (README + `skills/start/SKILL.md` + `docs/adr/_index.md` têm blocos gerados — NUNCA editar bloco à mão)

**Interfaces:**
- Consumes: CLI da Task 4 (`prumo paper verify-refs --page <p> --json`), layout do acervo (`references/notes/<citekey>/_extraction.md` e `_meta.md`), spec §"Camada de verificação de referências" item 4 (classificação Fully/Partially/Unsubstantiated; "Sinaliza; nunca bloqueia sozinho").
- A skill DEVE passar no registry: `load_skill_registry(REPO / "skills", strict=True)` roda dentro do `gen_indexes.py` — frontmatter espelha os campos de `skills/review-reconcile/SKILL.md` (`name`, `description`, `when_to_use`, `argument-hint`, e `allowed-tools` se o molde tiver). Rodar o gerador é o teste.

- [ ] **Step 1: Escrever a skill**

Criar `skills/citation-support/SKILL.md` (frontmatter espelhando o molde `review-reconcile`; ajuste os campos ao que o molde REALMENTE tem):

```markdown
---
name: citation-support
description: "Classifica se cada citação de uma página sustenta a frase que a cita (Fully/Partially/Unsubstantiated) usando os extracts do acervo — SINALIZA apenas, nunca edita nem bloqueia. Roda `prumo paper verify-refs` antes (base determinística: existência/retração/título)."
when_to_use: |
  Quando o usuário pedir para checar se as citações de uma página/manuscrito
  sustentam as frases que as citam ("as referências batem com o que eu
  afirmo?"), ou depois de um `prumo paper verify-refs` limpo, como camada
  semântica. NÃO é para verificar existência/retração (isso é o CLI
  determinístico) nem para editar a página (proposta de prosa é o fluxo
  review-reconcile/apply).
argument-hint: "--page <page.md>"
allowed-tools: Read Glob Grep Bash(prumo paper verify-refs *)
---

# citation-support — a citação sustenta a frase?

Ataca o residual que nenhuma camada determinística alcança: **referência real
que não sustenta a afirmação** (buraco semântico da autoria original — spec da
ponte, §Camada de verificação de referências, item 4).

Regra de ouro: **este protocolo SINALIZA e para.** Nunca edita a página, nunca
propõe marca, nunca bloqueia export/apply. Se algo precisar mudar no texto, o
caminho é humano (ou o fluxo review-reconcile → `prumo write review apply`).

## Protocolo

1. **Base determinística primeiro**: rode
   `prumo paper verify-refs <pj> --page <page.md> --json`.
   - `retracted`/`doi-not-found` (errors): reporte no topo — classificação
     semântica de citação retratada/inexistente é irrelevante até o humano
     resolver o erro.
2. **Inventário**: extraia da página cada par (frase → citekeys marcadas
   `[[@key]]`/`[@key]`). Frase = sentença completa que contém a(s) marca(s).
3. **Evidência do acervo**: para cada citekey, leia
   `references/notes/<citekey>/_extraction.md` (e `_meta.md` para
   título/abstract). Sem extraction → classifique como **Sem-extract** (não
   invente conteúdo do paper; sugira `prumo paper extract <citekey>`).
4. **Classifique cada par** (3 vias do spec):
   - **Fully supported** — o extract afirma o que a frase atribui.
   - **Partially supported** — direção certa, mas a frase generaliza/omite
     condição (população, magnitude, desenho do estudo).
   - **Unsubstantiated** — o extract não contém (ou contradiz) a afirmação.
   Cada veredito vem com 1 linha de justificativa + trecho literal do extract
   (ou "extract silencioso sobre isso").
5. **Relatório final** (tabela): frase (recorte) | citekey | veredito |
   justificativa. Feche com a lista de ações sugeridas AO HUMANO
   (ex.: "reescrever a frase X", "trocar a citação Y", "rodar extract de Z")
   — sem executar nenhuma.

## Limites duros

- NUNCA edite página, bib, notas ou worklist — nem "só uma vírgula".
- NUNCA conclua veredito sem extract lido; na dúvida entre Partially e
  Unsubstantiated, escolha Unsubstantiated e diga por quê (falso-negativo é
  mais barato que falso-conforto — mesmo racional fail-closed do repo).
- Citação retratada NUNCA vira "Fully supported" — erro determinístico
  primeiro, sempre.
```

- [ ] **Step 2: Escrever o ADR-0018**

Criar `docs/adr/adr-0018-verificacao-referencias-apis-publicas.md` (MADR minimal, prosa, pt-BR — siga o formato dos ADRs existentes em `docs/adr/`, ex. ADR-0016/0017: título, status "aceito", contexto, decisão, consequências, alternativas consideradas). Conteúdo obrigatório:

- **Contexto**: Fase 4 da ponte (spec §Camada de verificação de referências); "zero erro silencioso de citação" se estende a "referência que não existe/foi retratada/não é o que diz ser"; primeira vez que um comando do CLI fala com a internet pública (até aqui: Zotero local, pandoc, uvx local).
- **Decisão**: camada nativa determinística com APIs públicas (Crossref `works/{doi}` + `works?filter=updates:{doi}` para retração; NCBI eutils `esummary` para PMID/pubtype), stdlib `urllib`, sem dependência de runtime nova; cache local `$XDG_CACHE_HOME/prumo-assist/refcheck.json` com TTL 7 dias (= o "cache local de retratações" do spec, item 3); backend profundo OPCIONAL `uvx academic-refchecker==3.0.151` (pinado; keyless; **exit 0 mesmo com erros — o gate é o report.json**, fato do spike 2026-07-24); achados nativos são o único gate (`error` → exit 1), achados deep são `warning`, LLM (skill `citation-support`) só sinaliza — três camadas, autoridade decrescente.
- **Privacidade**: só DOIs/PMIDs saem da máquina na camada nativa; `--deep` envia o subconjunto do bib em escopo (nunca o bib inteiro); User-Agent identifica o projeto sem PII; nenhum dado do manuscrito sai.
- **Consequências**: offline → `network-error` por entrada (fail-soft: o resto do bib segue verificável; comando continua determinístico); item 2 do spec (Retraction Watch via Zotero) permanece no cliente Zotero — a checagem prumo é independente e cobre o bib exportado.
- **Alternativas consideradas**: dump Retraction Watch local (31 MB — rejeitado no MVP; a consulta por-DOI cobre o caso; fica no backlog), doi.org HEAD (redundante com Crossref works), refchecker como camada única (rejeitado: keyless é lento, exit code inútil como gate, e o gate do repo precisa ser determinístico e próprio).

- [ ] **Step 3: ARCHITECTURE + CHANGELOG + índices**

- `ARCHITECTURE.md`: na seção do domínio `paper`, adicionar linha para `verify.py` ("verificação de referências: existência/retração/título via Crossref/PubMed + camada profunda refchecker pinada — ADR-0018"); se houver lista de skills, adicionar `citation-support`.
- `CHANGELOG.md`, seção "Não publicado":
  - Added: `prumo paper verify-refs` (existência/retração/título; `--page`, `--deep` via `academic-refchecker==3.0.151` pinado, `--refresh`; cache local TTL 7 dias) — ADR-0018; skill `citation-support` (classificação Fully/Partially/Unsubstantiated; sinaliza, nunca bloqueia).
  - Changed: `prumo write review ingest` agora exige `--force` para re-ingerir com marcas pendentes no worklist (protege propostas do agente — fila F2+F3).
  - Fixed: seam do adeu com timeout de 120s (fila F2+F3).
- Rodar: `uv run python .github/scripts/gen_indexes.py` (regenera blocos de README/skills/start/ADR index com a skill e o ADR novos).

- [ ] **Step 4: Bateria final completa**

Run: `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run python .github/scripts/gen_indexes.py --check && uv run python .github/scripts/validate_manifests.py`
Expected: tudo verde. (Skill nova passa no `load_skill_registry(..., strict=True)` de dentro do gerador — se falhar, o frontmatter divergiu do molde; corrija os campos, não o gerador.)

- [ ] **Step 5: Commit**

```bash
git add skills/citation-support/ docs/adr/adr-0018-verificacao-referencias-apis-publicas.md ARCHITECTURE.md CHANGELOG.md README.md skills/start/SKILL.md docs/adr/_index.md docs/_index.md
git commit -m "docs+feat(paper): skill citation-support (sinaliza, nunca bloqueia) + ADR-0018 verificação de referências"
```

---

## Self-review (do plano, contra o spec §Fase 4)

- Item 1 do spec (RefChecker): Task 3 (`--deep`, pinado, report como gate) ✓
- Item 2 (Retraction Watch via Zotero — nativo do cliente): documentado no ADR (Task 6) + checagem independente prumo nas Tasks 2 ✓
- Item 3 (resolução DOI/PMID + cache local de retratações): Tasks 1–2 (arXiv fica registrado em `RefIdentifiers` e informado no `no-identifier`; resolução ativa de arXiv fica com o `--deep` — pesquisa clínica raramente cita arXiv; decisão registrada aqui) ✓
- Item 4 (classificação citação-suporte, sinaliza-nunca-bloqueia): Task 6 (skill) ✓
- Herdados da fila F2+F3 com prioridade elevada: Task 5 ✓ (o restante da fila fica explicitamente fora de escopo — Global Constraints)
