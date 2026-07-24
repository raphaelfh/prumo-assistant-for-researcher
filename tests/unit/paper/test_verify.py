"""Testes do motor de verificação de referências (Fase 4 da ponte)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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

    def test_pmid_prioriza_note_sobre_abstract(self) -> None:
        # emenda pós-review T1: abstract citando PMID de OUTRO trabalho não
        # pode vencer o note verdadeiro (gate validaria o registro errado)
        ids = verify._identifiers_for(
            _entry("abstract = {Como no trial X (PMID: 111111).},\n  note = {PMID: 222222},")
        )
        assert ids.pmid == "222222"

    def test_pmid_em_abstract_nao_conta(self) -> None:
        ids = verify._identifiers_for(_entry("abstract = {(PMID: 111111)},"))
        assert ids.pmid is None

    def test_doi_multilinha_colapsa_whitespace(self) -> None:
        # emenda pós-review T1: campo brace-delimited pode quebrar linha
        ids = verify._identifiers_for(_entry("doi = {10.1056/\n    NEJMoa2002032},"))
        assert ids.doi == "10.1056/NEJMoa2002032"

    def test_arxiv_por_eprinttype(self) -> None:
        ids = verify._identifiers_for(_entry("eprint = {2301.00001},\n  eprinttype = {arXiv},"))
        assert ids.arxiv_id == "2301.00001"

    def test_arxiv_por_archiveprefix(self) -> None:
        ids = verify._identifiers_for(_entry("eprint = {2301.00002},\n  archiveprefix = {arxiv},"))
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
        old = datetime.now(UTC) - timedelta(days=8)
        cache.put("k1", {"a": 1}, now=old)
        assert cache.get("k1") is None
        # dentro do TTL segue vivo
        cache.put("k2", {"b": 2}, now=datetime.now(UTC) - timedelta(days=6))
        assert cache.get("k2") == {"b": 2}

    def test_arquivo_corrompido_vira_cache_vazio(self, tmp_path: Path) -> None:
        p = tmp_path / "c.json"
        p.write_text("{nao é json", encoding="utf-8")
        cache = verify.RefCache(path=p)
        assert cache.get("k") is None
        cache.put("k", {"ok": True})  # não explode; regrava do zero
        assert cache.get("k") == {"ok": True}

    def test_default_cache_path_respeita_xdg(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
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
