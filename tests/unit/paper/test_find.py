"""Tests pro índice de `prumo paper find` — cobre os dois dialetos de `.bib`."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.paper.find import build_index, fuzzy_search

_BIBLATEX = (
    "@article{audisio2025total,\n"
    "  title = {Total {{Neoadjuvant Therapy}}},\n"
    "  author = {Audisio, Alessandro},\n"
    "  date = {2025-09-01},\n"
    "  journaltitle = {JAMA Oncology},\n"
    "  urldate = {2026-07-23}\n"
    "}\n"
)

_BIBTEX = (
    "@article{audisio2025total,\n"
    "  title = {Total {{Neoadjuvant Therapy}}},\n"
    "  author = {Audisio, Alessandro},\n"
    "  year = 2025,\n"
    "  month = sep,\n"
    "  journal = {JAMA Oncology}\n"
    "}\n"
)


def _pj(tmp_path: Path, bib_text: str) -> Path:
    pj = tmp_path / "pj_demo"
    refs = pj / "references"
    refs.mkdir(parents=True)
    (refs / "_references.bib").write_text(bib_text)
    return pj


def test_build_index_year_from_biblatex_date(tmp_path: Path) -> None:
    """Better BibLaTeX não emite ``year``: o ano do índice vem do ``date``."""
    index = build_index(_pj(tmp_path, _BIBLATEX))
    assert index["audisio2025total"]["year"] == "2025"


def test_build_index_year_from_bibtex_year(tmp_path: Path) -> None:
    """Dialeto legado segue idêntico — nenhuma regressão nos projetos existentes."""
    index = build_index(_pj(tmp_path, _BIBTEX))
    assert index["audisio2025total"]["year"] == "2025"


def test_build_index_keeps_non_numeric_year_verbatim(tmp_path: Path) -> None:
    """Ano não-numérico não é representável como inteiro, mas o índice é TEXTO:
    o valor cru é preservado para não sumir do haystack de busca."""
    bib = "@article{silva2024,\n  title = {X},\n  author = {Silva, A.},\n  year = {n.d.}\n}\n"
    index = build_index(_pj(tmp_path, bib))
    assert index["silva2024"]["year"] == "n.d."


def test_fuzzy_search_matches_year_from_biblatex_date(tmp_path: Path) -> None:
    """O ano recuperado do ``date`` entra no haystack e é buscável."""
    hits = fuzzy_search(_pj(tmp_path, _BIBLATEX), "2025")
    assert [h["citekey"] for h in hits] == ["audisio2025total"]
