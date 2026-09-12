"""Smoke tests pro parser de _references.bib (BBT)."""

from __future__ import annotations

import pytest

from par.core.bib import extract_field, extract_year, parse_bib


def test_parses_minimal_entry() -> None:
    text = "@article{smith2024,\n  title = {A title},\n  year = 2024\n}\n"
    entries = parse_bib(text)
    assert len(entries) == 1
    e = entries[0]
    assert e.entry_type == "article"
    assert e.citekey == "smith2024"
    assert "title" in e.body


def test_skips_string_macros_and_comments() -> None:
    text = (
        '@string{j = "Journal Of Things"}\n'
        "@comment{this is a comment}\n"
        "@article{key1, title = {x}}\n"
    )
    entries = parse_bib(text)
    assert len(entries) == 1
    assert entries[0].citekey == "key1"


def test_handles_nested_braces_in_field() -> None:
    text = "@article{key, title = {{Combi-Nado} Fusion}}\n"
    entries = parse_bib(text)
    assert len(entries) == 1
    assert extract_field(entries[0].body, "title") == "{Combi-Nado} Fusion"


def test_extract_field_supports_three_delimiters() -> None:
    body = 'title = {Brace}, author = "Quoted Name", year = 2024'
    assert extract_field(body, "title") == "Brace"
    assert extract_field(body, "author") == "Quoted Name"
    assert extract_field(body, "year") == "2024"


def test_extract_field_returns_none_when_absent() -> None:
    assert extract_field("title = {x}", "doi") is None


# --- extract_year: dialetos Better BibTeX (year) e Better BibLaTeX (date) ---

# Bodies mínimos derivados das fixtures reais (audisio2025total nos dois dialetos)
BIBTEX_BODY = (
    "\n  title = {Total {{Neoadjuvant Therapy}}},\n"
    "  year = 2025,\n  month = sep,\n"
    "  journal = {JAMA Oncology},\n  urldate = {2026-07-23}\n"
)
BIBLATEX_BODY = (
    "\n  title = {Total {{Neoadjuvant Therapy}}},\n"
    "  date = {2025-09-01},\n"
    "  journaltitle = {JAMA Oncology},\n  urldate = {2026-07-23}\n"
)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        # dialeto Better BibTeX: year literal nu
        pytest.param(BIBTEX_BODY, "2025", id="bibtex-year-literal"),
        # NÃO estreitar o dialeto legado: antes deste helper o critério era
        # `str.isdigit()`, sem exigir 4 dígitos. Ano de 3 dígitos é legítimo e
        # continua valendo — exigir `^\d{4}$` seria regressão silenciosa.
        pytest.param("\n  year = {999}\n", "999", id="bibtex-year-3-digitos"),
        pytest.param("\n  year = {12345}\n", "12345", id="bibtex-year-5-digitos"),
        # Ano não-numérico não é representável: "" (quem indexa texto preserva
        # o valor cru por conta própria — ver domains/paper/find.py).
        pytest.param("\n  year = {n.d.}\n", "", id="bibtex-year-nao-numerico"),
        pytest.param("year = {2024}", "2024", id="bibtex-year-braces"),
        pytest.param('year = "2024"', "2024", id="bibtex-year-quotes"),
        # dialeto Better BibLaTeX: só date
        pytest.param(BIBLATEX_BODY, "2025", id="biblatex-date-ymd"),
        pytest.param("date = {2025-09}", "2025", id="biblatex-date-ym"),
        pytest.param("date = {2025}", "2025", id="biblatex-date-y"),
        # year vence quando os dois existem e year é limpo
        pytest.param("year = 2024, date = {2025-09-01}", "2024", id="year-wins-over-date"),
        # year sujo cai pro date
        pytest.param(
            "year = {in press}, date = {2025-09-01}", "2025", id="dirty-year-falls-to-date"
        ),
        # formas EDTF que o BBT emite (biblatexExtendedDateFormat)
        pytest.param("date = {19uu}", "", id="edtf-unknown-decade"),
        pytest.param("date = {199u}", "", id="edtf-unknown-unit"),
        pytest.param("date = {1999-uu}", "1999", id="edtf-unknown-month"),
        pytest.param("date = {1999-01-uu}", "1999", id="edtf-unknown-day"),
        pytest.param("date = {1273?\u00a0}", "1273", id="edtf-approximate-nbsp"),
        pytest.param("date = {y-51234}", "", id="edtf-long-year"),
        pytest.param("date = {2016-07-18T20:26:06}", "2016", id="edtf-datetime"),
        pytest.param("date = {1897/1913}", "1897", id="edtf-interval-years"),
        pytest.param("date = {2014-12-31/2015-01-01}", "2014", id="edtf-interval-dates"),
        pytest.param("date = {2020-21}", "2020", id="edtf-season"),
        # sem ano determinável
        pytest.param("title = {Untitled}", "", id="no-year-no-date"),
        pytest.param("", "", id="empty-body"),
        # NÃO casar com urldate/origdate
        pytest.param("urldate = {2026-07-26}", "", id="urldate-only"),
        pytest.param("origdate = {1897}", "", id="origdate-only"),
        pytest.param(
            "urldate = {2026-07-26}, date = {2025-09-01}", "2025", id="urldate-before-date"
        ),
    ],
)
def test_extract_year(body: str, expected: str) -> None:
    assert extract_year(body) == expected
