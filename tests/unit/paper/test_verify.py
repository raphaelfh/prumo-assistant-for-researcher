"""Testes do motor de verificação de referências (Fase 4 da ponte)."""

from __future__ import annotations

import json
import subprocess
import urllib.error
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from email.message import Message
from pathlib import Path
from typing import Any, cast

import pytest

from prumo_assist.core.bib import BibEntry, parse_bib
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


_WORKS_OK = {
    "message": {"title": ["Clinical Characteristics of Coronavirus Disease 2019 in China"]}
}
_UPDATES_EMPTY: dict[str, Any] = {"message": {"items": []}}
_UPDATES_RETRACTED = {
    "message": {
        "items": [
            {
                "DOI": "10.x/notice",
                "update-to": [{"type": "retraction", "DOI": "10.1056/nejmoa2002032"}],
            }
        ]
    }
}
_ESUMMARY_RETRACTED = {
    "result": {"9500320": {"title": "...", "pubtype": ["Journal Article", "Retracted Publication"]}}
}
_ESUMMARY_OK = {"result": {"32109013": {"title": "...", "pubtype": ["Journal Article"]}}}
_ESUMMARY_BAD_ID = {"result": {"999999999": {"error": "cannot get document summary"}}}


def _bib_entry_doi(
    title: str = "Clinical Characteristics of Coronavirus Disease 2019 in China",
) -> BibEntry:
    return _entry(f"title = {{{title}}},\n  doi = {{10.1056/NEJMoa2002032}},")


class TestCheckEntry:
    def _cache(self, tmp_path: Path) -> verify.RefCache:
        return verify.RefCache(path=tmp_path / "cache.json")

    def test_ok_sem_achados(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify._http_get_json",
            _fake_http(
                {
                    "api.crossref.org/works?filter=updates": _UPDATES_EMPTY,
                    "api.crossref.org/works/": _WORKS_OK,
                }
            ),
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
            _fake_http(
                {
                    "api.crossref.org/works?filter=updates": _UPDATES_RETRACTED,
                    "api.crossref.org/works/": _WORKS_OK,
                }
            ),
        )
        findings = verify.check_entry(_bib_entry_doi(), cache=self._cache(tmp_path))
        assert [(f.kind, f.level, f.source) for f in findings] == [
            ("retracted", "error", "crossref")
        ]
        assert "RETRATADO" in findings[0].message

    def test_retracao_pubmed_sem_duplicar_crossref(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entry = _entry("title = {X},\n  doi = {10.1056/NEJMoa2002032},\n  note = {PMID: 9500320},")
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
                    "api.crossref.org/works/": {
                        "message": {
                            "title": ["Um Trabalho Completamente Diferente Sobre Outra Coisa"]
                        }
                    },
                }
            ),
        )
        findings = verify.check_entry(
            _bib_entry_doi("Efeitos da Metformina em Idosos"), cache=self._cache(tmp_path)
        )
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

    def test_rede_fora_vira_network_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify._http_get_json",
            _fake_http({"api.crossref.org/works/": urllib.error.URLError("dns down")}),
        )
        findings = verify.check_entry(_bib_entry_doi(), cache=self._cache(tmp_path))
        assert [(f.kind, f.level) for f in findings] == [("network-error", "error")]

    def test_cache_evita_segunda_chamada(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []

        def fake(url: str, *, timeout: float = 10.0) -> dict[str, Any]:
            calls.append(url)
            if "filter=updates" in url:
                return _UPDATES_EMPTY
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
                return _UPDATES_EMPTY
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
            _fake_http(
                {
                    "api.crossref.org/works?filter=updates": _UPDATES_EMPTY,
                    "api.crossref.org/works/": _WORKS_OK,
                }
            ),
        )
        report = verify.verify_refs(self._pj(tmp_path), cache_path=tmp_path / "c.json")
        assert report["scope"] == ["guan2020clinical", "semid2024"]
        assert report["checked"] == 2
        assert report["summary"] == {"errors": 0, "warnings": 0, "infos": 1}
        kinds = {f["kind"] for f in report["findings"]}
        assert kinds == {"no-identifier"}

    def test_escopo_por_pagina_e_missing_citekey(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pj = self._pj(tmp_path)
        pagina = tmp_path / "draft.md"
        pagina.write_text(
            "Como mostrado em [[@guan2020clinical]] e também [@naoexiste2020].\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify._http_get_json",
            _fake_http(
                {
                    "api.crossref.org/works?filter=updates": _UPDATES_EMPTY,
                    "api.crossref.org/works/": _WORKS_OK,
                }
            ),
        )
        report = verify.verify_refs(pj, page=pagina, cache_path=tmp_path / "c.json")
        assert report["scope"] == ["guan2020clinical"]  # semid2024 fora: página não cita
        missing = [f for f in report["findings"] if f["kind"] == "missing-citekey"]
        assert [m["citekey"] for m in missing] == ["naoexiste2020"]
        assert "prumo paper lint" in missing[0]["message"]
        assert report["page"] == str(pagina)

    def test_page_inexistente_mensagem_pt_br(self, tmp_path: Path) -> None:
        pj = self._pj(tmp_path)
        with pytest.raises(FileNotFoundError, match="--page"):
            verify.verify_refs(pj, page=tmp_path / "nao-existe.md", cache_path=tmp_path / "c.json")


class TestDuplicateCitekey:
    _DUP_BIB = """@article{guan2020clinical,
  title = {Entrada limpa},
  doi = {10.1056/NEJMoa2002032},
}
@article{guan2020clinical,
  title = {Duplicata retratada},
  doi = {10.1016/S0140-6736(97)11096-0},
}
"""

    def _pj(self, tmp_path: Path) -> Path:
        (tmp_path / "references").mkdir(parents=True)
        (tmp_path / "references" / "_references.bib").write_text(self._DUP_BIB, encoding="utf-8")
        return tmp_path

    def test_duplicata_vira_error_e_pula_checks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []

        def fake(url: str, *, timeout: float = 10.0) -> dict[str, Any]:
            calls.append(url)
            raise AssertionError("nenhuma chamada de rede deveria ocorrer para citekey duplicada")

        monkeypatch.setattr("prumo_assist.domains.paper.verify._http_get_json", fake)
        report = verify.verify_refs(self._pj(tmp_path), cache_path=tmp_path / "c.json")
        assert calls == []
        assert report["summary"]["errors"] == 1
        [finding] = report["findings"]
        assert finding["kind"] == "duplicate-citekey" and finding["level"] == "error"
        assert "2x" in finding["message"] and "prumo paper lint" in finding["message"]

    def test_duplicata_com_page_tambem_acusa(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pj = self._pj(tmp_path)
        pagina = tmp_path / "draft.md"
        pagina.write_text("Como em [[@guan2020clinical]].\n", encoding="utf-8")

        def fake(url: str, *, timeout: float = 10.0) -> dict[str, Any]:
            raise AssertionError("nenhuma chamada de rede deveria ocorrer")

        monkeypatch.setattr("prumo_assist.domains.paper.verify._http_get_json", fake)
        report = verify.verify_refs(pj, page=pagina, cache_path=tmp_path / "c.json")
        assert [f["kind"] for f in report["findings"]] == ["duplicate-citekey"]


class TestHttpSeamContract:
    def test_json_nao_objeto_vira_jsondecodeerror(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _FakeResponse:
            def read(self) -> bytes:
                return b"[1, 2]"

            def __enter__(self) -> _FakeResponse:
                return self

            def __exit__(self, *exc: object) -> None:
                return None

        def fake_urlopen(request: Any, timeout: float = 10.0) -> _FakeResponse:
            return _FakeResponse()

        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify.urllib.request.urlopen", fake_urlopen
        )
        with pytest.raises(json.JSONDecodeError, match="não é objeto"):
            verify._http_get_json("https://api.example.test/x")


_REPORT_FIXTURE: dict[str, Any] = {
    "generated_at": "2026-07-24",
    "summary": {"total_references_processed": 2, "total_errors_found": 2},
    "papers": [],
    "records": [
        {
            "error_type": "author",
            "error_details": "Author count mismatch: 3 cited vs 37 correct:\n  cited: ...",
            "original_reference": {
                "bibtex_key": "guan2020clinical",
                "doi": "10.1056/nejmoa2002032",
            },
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

    def test_verify_refs_deep_mescla_warnings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "references").mkdir()
        (tmp_path / "references" / "_references.bib").write_text(_BIB_TEXT, encoding="utf-8")
        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify._http_get_json",
            _fake_http(
                {
                    "api.crossref.org/works?filter=updates": _UPDATES_EMPTY,
                    "api.crossref.org/works/": _WORKS_OK,
                }
            ),
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

    def test_verify_refs_sem_deep_nao_roda_subprocess(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "references").mkdir()
        (tmp_path / "references" / "_references.bib").write_text(_BIB_TEXT, encoding="utf-8")
        monkeypatch.setattr(
            "prumo_assist.domains.paper.verify._http_get_json",
            _fake_http(
                {
                    "api.crossref.org/works?filter=updates": _UPDATES_EMPTY,
                    "api.crossref.org/works/": _WORKS_OK,
                }
            ),
        )

        def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            raise AssertionError("subprocess não deveria rodar sem --deep")

        monkeypatch.setattr("prumo_assist.domains.paper.verify.subprocess.run", fake_run)
        report = verify.verify_refs(tmp_path, cache_path=tmp_path / "c.json")
        assert report["deep"] is False

    def test_deep_com_escopo_so_duplicatas_nao_roda_subprocess(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # emenda pós-review T3: escopo 100% duplicado não pode disparar
        # subprocess real contra um .bib derivado vazio
        (tmp_path / "references").mkdir()
        (tmp_path / "references" / "_references.bib").write_text(
            "@article{dup2020,\n  title = {A},\n}\n@article{dup2020,\n  title = {B},\n}\n",
            encoding="utf-8",
        )

        def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            raise AssertionError("subprocess não deveria rodar com escopo só de duplicatas")

        monkeypatch.setattr("prumo_assist.domains.paper.verify.subprocess.run", fake_run)
        report = verify.verify_refs(tmp_path, deep=True, cache_path=tmp_path / "c.json")
        assert report["deep"] is True
        assert [f["kind"] for f in report["findings"]] == ["duplicate-citekey"]
