"""Tests pro sync de PDFs (symlinks ``pdfs/<citekey>.pdf`` → Zotero).

Cobre duas coisas distintas:

1. **Caracterização** do comportamento que a auditoria de 2026-08-23 decidiu
   preservar (spec ``2026-08-23-ponte-zotero-auditoria-design``): resolução
   offline pelo campo ``file`` do ``.bib``, idempotência, auto-reparo de
   symlink desatualizado e recusa de sobrescrever arquivo real.
2. **Regressão** dos dois defeitos de parser encontrados na mesma auditoria
   (``\\;`` não desescapado, caminho relativo) e da distinção entre "não há
   anexo" e "anexo existe mas não está em disco".
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from par.domains.paper.pdfs import sync_pdfs


def _setup_project(tmp_path: Path, bib_text: str) -> Path:
    refs = tmp_path / "docs" / "references"
    refs.mkdir(parents=True)
    (refs / "_references.bib").write_text(bib_text, encoding="utf-8")
    return tmp_path


def _make_pdf(tmp_path: Path, name: str, subdir: str = "storage/AAA") -> Path:
    """Cria um PDF de mentira e devolve o caminho absoluto."""
    d = tmp_path / subdir
    d.mkdir(parents=True, exist_ok=True)
    pdf = d / name
    pdf.write_bytes(b"%PDF-1.4\n")
    return pdf


def _bib_entry(citekey: str, file_field: str) -> str:
    return "@article{" + citekey + ",\n  title = {x},\n  file = {" + file_field + "}\n}\n"


def _bbt_escape(path: str) -> str:
    """Escapa um caminho como o Better BibTeX escapa no campo ``file``.

    O BBT escapa três caracteres — ``\\``, ``;`` e ``:`` — via
    ``/[\\\\;:]/g``; o parser precisa desfazer os três.
    """
    return path.replace("\\", "\\\\").replace(";", "\\;").replace(":", "\\:")


# ---------------------------------------------------------------------------
# Caracterização — comportamento preservado
# ---------------------------------------------------------------------------


def test_creates_symlink_pointing_at_the_zotero_pdf(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path, "artigo.pdf")
    pj = _setup_project(tmp_path, _bib_entry("silva2024", _bbt_escape(str(pdf))))

    report = sync_pdfs(pj)

    link = pj / "docs" / "references" / "pdfs" / "silva2024.pdf"
    assert report["created"] == 1
    assert link.is_symlink()
    assert os.readlink(link) == str(pdf)


def test_second_run_is_idempotent(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path, "artigo.pdf")
    pj = _setup_project(tmp_path, _bib_entry("silva2024", _bbt_escape(str(pdf))))
    sync_pdfs(pj)

    report = sync_pdfs(pj)

    assert report["created"] == 0
    assert report["updated"] == 0
    assert report["ok"] == 1


def test_repoints_symlink_when_zotero_renamed_the_file(tmp_path: Path) -> None:
    """Zotero ≥ 8 renomeia o anexo quando a metadata do pai muda."""
    old = _make_pdf(tmp_path, "antigo.pdf")
    pj = _setup_project(tmp_path, _bib_entry("silva2024", _bbt_escape(str(old))))
    sync_pdfs(pj)
    new = _make_pdf(tmp_path, "Silva - 2024 - Titulo novo.pdf")
    (pj / "docs" / "references" / "_references.bib").write_text(
        _bib_entry("silva2024", _bbt_escape(str(new))), encoding="utf-8"
    )

    report = sync_pdfs(pj)

    link = pj / "docs" / "references" / "pdfs" / "silva2024.pdf"
    assert report["updated"] == 1
    assert os.readlink(link) == str(new)


def test_never_overwrites_a_real_file(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path, "artigo.pdf")
    pj = _setup_project(tmp_path, _bib_entry("silva2024", _bbt_escape(str(pdf))))
    pdfs_dir = pj / "docs" / "references" / "pdfs"
    pdfs_dir.mkdir(parents=True)
    real = pdfs_dir / "silva2024.pdf"
    real.write_bytes(b"%PDF-manual\n")

    report = sync_pdfs(pj)

    assert report["blocked"] == ["silva2024"]
    assert real.read_bytes() == b"%PDF-manual\n"
    assert not real.is_symlink()


def test_raises_when_bib_is_absent(tmp_path: Path) -> None:
    (tmp_path / "docs" / "references").mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="Better BibTeX"):
        sync_pdfs(tmp_path)


# ---------------------------------------------------------------------------
# Regressão — defeitos de parser (auditoria 2026-08-23, achado A1)
# ---------------------------------------------------------------------------


def test_resolves_path_whose_filename_contains_a_semicolon(tmp_path: Path) -> None:
    """``Smith; Jones - 2024.pdf`` sai do BBT como ``Smith\\; Jones…``.

    O parser desescapava só ``\\:``, então o ``\\;`` sobrevivia ao replace e o
    split em ``;`` partia o caminho ao meio — o paper caía em ``missing``.
    """
    pdf = _make_pdf(tmp_path, "Smith; Jones - 2024.pdf")
    pj = _setup_project(tmp_path, _bib_entry("smith2024", _bbt_escape(str(pdf))))

    report = sync_pdfs(pj)

    link = pj / "docs" / "references" / "pdfs" / "smith2024.pdf"
    assert report["created"] == 1
    assert os.readlink(link) == str(pdf)


def test_resolves_relative_path_against_the_zotero_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com "export file paths: relative" ligado, o BBT emite caminho relativo
    ao data dir do Zotero — antes isso zerava TODOS os PDFs do projeto."""
    data_dir = tmp_path / "Zotero"
    pdf = _make_pdf(tmp_path, "artigo.pdf", subdir="Zotero/storage/AAA")
    monkeypatch.setenv("PRUMO_ZOTERO_DATA_DIR", str(data_dir))
    pj = _setup_project(tmp_path, _bib_entry("silva2024", "storage/AAA/artigo.pdf"))

    report = sync_pdfs(pj)

    link = pj / "docs" / "references" / "pdfs" / "silva2024.pdf"
    assert report["created"] == 1
    assert os.readlink(link) == str(pdf)


# ---------------------------------------------------------------------------
# Regressão — "sem anexo" ≠ "anexo não baixado" (achado A3)
# ---------------------------------------------------------------------------


def test_entry_without_pdf_candidate_is_reported_as_no_attachment(tmp_path: Path) -> None:
    pj = _setup_project(tmp_path, "@article{silva2024,\n  title = {x}\n}\n")

    report = sync_pdfs(pj)

    assert report["no_attachment"] == ["silva2024"]
    assert report["not_downloaded"] == []


def test_candidate_absent_from_disk_is_reported_as_not_downloaded(tmp_path: Path) -> None:
    """Biblioteca em nuvem: o BBT emite o caminho mesmo sem o arquivo baixado."""
    ausente = tmp_path / "storage" / "BBB" / "nao-baixado.pdf"
    pj = _setup_project(tmp_path, _bib_entry("silva2024", _bbt_escape(str(ausente))))

    report = sync_pdfs(pj)

    assert report["not_downloaded"] == ["silva2024"]
    assert report["no_attachment"] == []


def test_missing_is_kept_as_the_union_of_both(tmp_path: Path) -> None:
    """``missing`` continua existindo pros consumidores atuais do ``--json``."""
    ausente = tmp_path / "storage" / "BBB" / "nao-baixado.pdf"
    bib = (
        _bib_entry("silva2024", _bbt_escape(str(ausente)))
        + "@article{semanexo,\n  title = {y}\n}\n"
    )
    pj = _setup_project(tmp_path, bib)

    report = sync_pdfs(pj)

    assert sorted(report["missing"]) == ["semanexo", "silva2024"]


def test_picks_the_pdf_among_multiple_attachments(tmp_path: Path) -> None:
    """Formato multi-anexo do BBT: ``título:caminho:mime;título:caminho:mime``.

    O snapshot HTML vem ANTES do PDF na ordem do Zotero — as peças que não
    terminam em ``.pdf`` têm de ser descartadas, não escolhidas.
    """
    snapshot = tmp_path / "storage" / "AAA" / "pagina.html"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text("<html></html>", encoding="utf-8")
    pdf = _make_pdf(tmp_path, "artigo.pdf")
    field = (
        f"Snapshot:{_bbt_escape(str(snapshot))}:text/html"
        f";Full Text PDF:{_bbt_escape(str(pdf))}:application/pdf"
    )
    pj = _setup_project(tmp_path, _bib_entry("silva2024", field))

    report = sync_pdfs(pj)

    link = pj / "docs" / "references" / "pdfs" / "silva2024.pdf"
    assert report["created"] == 1
    assert os.readlink(link) == str(pdf)
