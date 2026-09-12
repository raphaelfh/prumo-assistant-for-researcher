"""Tests para sync .bib → notas YAML."""

from __future__ import annotations

from pathlib import Path

import pytest

from par.core.bib import BibEntry
from par.domains.paper.sync import (
    _parse_authors,
    bib_entry_to_metadata,
    merge_nota_yaml,
    sync,
)


def test_parse_authors_handles_and_separator() -> None:
    out = _parse_authors("Smith, Jane and Doe, John")
    assert out == [
        {"family": "Smith", "given": "Jane"},
        {"family": "Doe", "given": "John"},
    ]


def test_parse_authors_handles_no_comma() -> None:
    out = _parse_authors("Jane Smith")
    assert out == [{"family": "Smith", "given": "Jane"}]


def test_parse_authors_handles_single_word() -> None:
    out = _parse_authors("Plato")
    assert out == [{"family": "Plato", "given": ""}]


def test_parse_authors_skips_empty() -> None:
    out = _parse_authors("Smith, J. and  and Doe, J.")
    assert len(out) == 2


def test_bib_entry_to_metadata_minimal() -> None:
    entry = BibEntry(
        entry_type="article",
        citekey="smith2024combinado",
        body='title = {Combinado Fusion}, author = "Smith, J.", year = 2024',
    )
    meta = bib_entry_to_metadata(entry)
    assert meta["id"] == "smith2024combinado"
    assert meta["type"] == "article-journal"
    assert meta["title"] == "Combinado Fusion"
    assert meta["author"] == [{"family": "Smith", "given": "J."}]
    assert meta["issued"] == {"date-parts": [[2024]]}
    assert meta["pdf"] == "../../pdfs/smith2024combinado.pdf"


def test_bib_entry_to_metadata_biblatex_date_yields_year() -> None:
    """Better BibLaTeX não emite ``year``; o ano tem de vir do ``date`` (EDTF)."""
    entry = BibEntry(
        entry_type="article",
        citekey="audisio2025total",
        body=(
            "\n  title = {Total {{Neoadjuvant Therapy}}},\n"
            "  author = {Audisio, Alessandro},\n"
            "  date = {2025-09-01},\n"
            "  journaltitle = {JAMA Oncology},\n"
            "  urldate = {2026-07-23}\n"
        ),
    )
    meta = bib_entry_to_metadata(entry)
    assert meta["issued"] == {"date-parts": [[2025]]}


def test_bib_entry_to_metadata_without_year_nor_date() -> None:
    """Sem ``year`` (BibTeX) E sem ``date`` (BibLaTeX): ``issued`` fica nulo."""
    entry = BibEntry(entry_type="misc", citekey="x", body='title = "Untitled"')
    meta = bib_entry_to_metadata(entry)
    assert meta["issued"] == {"date-parts": [[None]]}
    assert meta["type"] == "manuscript"


# --- container-title: dialetos Better BibTeX (journal) e Better BibLaTeX (journaltitle) ---

# Bodies mínimos derivados das fixtures reais (audisio2025total nos dois dialetos).
# O BibLaTeX traz `shortjournal` (20/23) junto do `journaltitle` (23/23).
BIBLATEX_ARTICLE_BODY = (
    "\n  title = {Total {{Neoadjuvant Therapy}}},\n"
    "  author = {Audisio, Alessandro},\n"
    "  date = {2025-09-01},\n"
    "  journaltitle = {JAMA Oncology},\n"
    "  shortjournal = {JAMA Oncol.},\n"
    "  doi = {10.1001/jamaoncol.2025.2026}\n"
)
BIBTEX_ARTICLE_BODY = (
    "\n  title = {Total {{Neoadjuvant Therapy}}},\n"
    "  author = {Audisio, Alessandro},\n"
    "  year = 2025,\n  month = sep,\n"
    "  journal = {JAMA Oncology},\n"
    "  doi = {10.1001/jamaoncol.2025.2026}\n"
)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        pytest.param(BIBLATEX_ARTICLE_BODY, "JAMA Oncology", id="biblatex-journaltitle"),
        pytest.param(BIBTEX_ARTICLE_BODY, "JAMA Oncology", id="bibtex-journal"),
    ],
)
def test_bib_entry_to_metadata_container_title_both_dialects(body: str, expected: str) -> None:
    """Better BibLaTeX escreve ``journaltitle`` e nunca ``journal``: os dois têm de valer."""
    entry = BibEntry(entry_type="article", citekey="audisio2025total", body=body)
    assert bib_entry_to_metadata(entry)["container-title"] == expected


def test_bib_entry_to_metadata_container_title_falls_back_to_booktitle() -> None:
    """Capítulo de livro: a cascata pré-existente ``booktitle`` não pode regredir."""
    entry = BibEntry(
        entry_type="inbook",
        citekey="silva2020capitulo",
        body=(
            "\n  title = {Um Capítulo},\n"
            "  author = {Silva, Ana},\n"
            "  booktitle = {Manual de Oncologia},\n"
            "  publisher = {Editora X},\n"
            "  date = {2020}\n"
        ),
    )
    assert bib_entry_to_metadata(entry)["container-title"] == "Manual de Oncologia"


def test_bib_entry_to_metadata_container_title_falls_back_to_publisher() -> None:
    """Livro sem periódico nem ``booktitle``: último degrau da cascata segue valendo."""
    entry = BibEntry(
        entry_type="book",
        citekey="silva2020livro",
        body="\n  title = {Um Livro},\n  publisher = {Editora X},\n  date = {2020}\n",
    )
    assert bib_entry_to_metadata(entry)["container-title"] == "Editora X"


def test_bib_entry_to_metadata_ignores_shortjournal_abbreviation() -> None:
    """``shortjournal`` é abreviação (``JAMA Oncol.``), não ``container-title``."""
    entry = BibEntry(
        entry_type="article",
        citekey="x2025y",
        body="\n  title = {T},\n  shortjournal = {JAMA Oncol.},\n  date = {2025}\n",
    )
    assert bib_entry_to_metadata(entry)["container-title"] == ""


def test_merge_yaml_overrides_metadata_only() -> None:
    existing = {"title": "Old", "tldr": "User notes", "added": "2025-01-01"}
    new = {"title": "New", "DOI": "10.1/foo"}
    merged = merge_nota_yaml(existing, new, today="2026-04-28")
    assert merged["title"] == "New"
    assert merged["DOI"] == "10.1/foo"
    assert merged["tldr"] == "User notes"  # curadoria preservada
    assert merged["added"] == "2025-01-01"  # added preservado


def test_merge_yaml_sets_added_when_absent() -> None:
    merged = merge_nota_yaml({}, {"title": "X"}, today="2026-04-28")
    assert merged["added"] == "2026-04-28"


def test_sync_creates_meta_md_for_each_entry(tmp_path: Path) -> None:
    refs = tmp_path / "docs" / "references"
    refs.mkdir(parents=True)
    (refs / "_references.bib").write_text(
        "@article{smith2024,\n"
        "  title = {Combi-Nado Fusion},\n"
        '  author = "Smith, Jane",\n'
        "  year = 2024\n"
        "}\n"
    )
    report = sync(tmp_path)
    assert report["created"] == 1
    assert report["updated"] == 0
    assert report["orphans"] == []
    meta = refs / "papers" / "smith2024" / "_meta.md"
    assert meta.exists()
    content = meta.read_text()
    assert "Combi-Nado Fusion" in content
    assert "smith2024" in content


def test_sync_re_run_is_idempotent(tmp_path: Path) -> None:
    refs = tmp_path / "docs" / "references"
    refs.mkdir(parents=True)
    (refs / "_references.bib").write_text("@article{smith2024,\n  title = {X},\n  year = 2024\n}\n")
    sync(tmp_path)
    report = sync(tmp_path)
    assert report["created"] == 0
    assert report["updated"] == 0  # round-trip limpo: nenhum campo alterado


def test_sync_detects_orphan_subdirs(tmp_path: Path) -> None:
    refs = tmp_path / "docs" / "references"
    notes = refs / "papers"
    (notes / "orphan_one").mkdir(parents=True)
    (notes / "orphan_one" / "_meta.md").write_text("---\nid: orphan_one\n---\n\nbody\n")
    (refs / "_references.bib").write_text("@article{a, title={X}}\n")
    report = sync(tmp_path)
    assert "orphan_one" in report["orphans"]


def test_sync_raises_when_bib_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        sync(tmp_path)
