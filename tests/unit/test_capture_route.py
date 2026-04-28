"""Tests pro router de capture."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.capture.route import classify


def test_classify_doi() -> None:
    out = classify("https://doi.org/10.1234/foo.bar")
    assert out.kind == "doi"
    assert out.canonical == "https://doi.org/10.1234/foo.bar"


def test_classify_doi_bare() -> None:
    out = classify("10.1234/foo")
    assert out.kind == "doi"


def test_classify_arxiv_id() -> None:
    out = classify("arXiv:2401.01234")
    assert out.kind == "arxiv"
    assert "2401.01234" in out.canonical


def test_classify_arxiv_url() -> None:
    out = classify("https://arxiv.org/abs/2401.01234")
    assert out.kind == "arxiv"


def test_classify_pdf_existing(tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    out = classify(str(pdf))
    assert out.kind == "pdf"


def test_classify_url() -> None:
    out = classify("https://blog.example.com/post")
    assert out.kind == "url"
    assert "wiki-ingest" in out.suggestion


def test_classify_citekey() -> None:
    out = classify("@smith2024combinado")
    assert out.kind == "citekey"


def test_classify_unknown() -> None:
    out = classify("randomgarbage")
    assert out.kind == "unknown"
