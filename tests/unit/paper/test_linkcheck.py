"""Testes da conferência do vínculo pelo pull export do Better BibTeX (emenda da ADR-0044).

O seam HTTP é 100% mockado; bibliotecas, coleções e citekeys são sintéticas.
"""

from __future__ import annotations

import urllib.error
from pathlib import Path

import pytest

from par.domains.paper import link, linkcheck
from par.domains.paper.schemas.v1 import ZoteroLink

_BIB_AB = "@article{a,\n  title = {A}\n}\n@article{b,\n  title = {B}\n}\n"


def _pj(tmp_path: Path, bib: str, *, key: str | None = "BBB", library_id: int | None = 1) -> Path:
    refs = tmp_path / "docs" / "references"
    refs.mkdir(parents=True)
    (refs / "_references.bib").write_text(bib, encoding="utf-8")
    link.write_link(
        tmp_path,
        ZoteroLink(
            library="My Library",
            library_id=library_id,
            collection="Pesquisa/Item A",
            collection_key=key,
            linked_at="2026-01-01",
            source="connect",
        ),
    )
    return tmp_path


def _serve(monkeypatch: pytest.MonkeyPatch, answer: tuple[int, str] | Exception) -> list[str]:
    urls: list[str] = []

    def fake(url: str, timeout: float = 5.0) -> tuple[int, str]:
        urls.append(url)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr("par.domains.paper.linkcheck._http_get", fake)
    return urls


def test_sem_vinculo_nao_confere_nada(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    urls = _serve(monkeypatch, (200, ""))
    assert linkcheck.check_link(tmp_path) is None
    assert urls == []


def test_mesmas_citekeys_e_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pj = _pj(tmp_path, _BIB_AB)
    urls = _serve(monkeypatch, (200, "@article{b,\n title={B2}\n}\n@article{a,\n title={A}\n}\n"))
    check = linkcheck.check_link(pj)
    assert check is not None and check.state == "ok"
    assert urls == ["http://127.0.0.1:23119/better-bibtex/export/collection?/1/BBB.biblatex"]


def test_divergencia_conta_dos_dois_lados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pj = _pj(tmp_path, _BIB_AB)
    _serve(monkeypatch, (200, "@article{a,\n}\n@article{c,\n}\n@article{d,\n}\n"))
    check = linkcheck.check_link(pj)
    assert check is not None
    assert (check.state, check.only_zotero, check.only_bib) == ("drift", 2, 1)
    assert "Pesquisa/Item A" in check.detail and "--selected --record" in check.detail


def test_colecao_que_o_bbt_nao_acha(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pj = _pj(tmp_path, _BIB_AB)
    _serve(monkeypatch, (404, "Could not export bibliography: path 'BBB' not found"))
    check = linkcheck.check_link(pj)
    assert check is not None and check.state == "missing"
    assert "apagada" in check.detail


def test_404_sem_better_bibtex_e_inalcancavel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pj = _pj(tmp_path, _BIB_AB)
    _serve(monkeypatch, (404, "No endpoint found"))
    check = linkcheck.check_link(pj)
    assert check is not None and check.state == "unreachable"


def test_zotero_fechado_e_inalcancavel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pj = _pj(tmp_path, _BIB_AB)
    _serve(monkeypatch, urllib.error.URLError("refused"))
    check = linkcheck.check_link(pj)
    assert check is not None and check.state == "unreachable"


@pytest.mark.parametrize(("key", "library_id"), [(None, 1), ("BBB", None)])
def test_vinculo_sem_chave_nao_da_para_conferir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key: str | None, library_id: int | None
) -> None:
    pj = _pj(tmp_path, _BIB_AB, key=key, library_id=library_id)
    urls = _serve(monkeypatch, (200, ""))
    check = linkcheck.check_link(pj)
    assert check is not None and check.state == "unverifiable"
    assert "--record" in check.detail
    assert urls == []
