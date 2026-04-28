"""Python API pra ``write``."""

from __future__ import annotations

from pathlib import Path

from prumo_assist.domains.write import comments as _comments
from prumo_assist.domains.write import export as _export


def export(
    page: Path,
    *,
    to: str = "docx",
    style: str = "apa",
    out: Path | None = None,
    bib: Path | None = None,
) -> Path:
    """Exporta uma página Markdown."""
    return _export.export(page=page, to=to, style=style, out=out, bib=bib)


def compose(
    index: Path,
    *,
    to: str = "docx",
    style: str | None = None,
    out: Path | None = None,
    bib: Path | None = None,
) -> Path:
    """Compõe múltiplas páginas via index."""
    return _export.compose(index=index, to=to, style=style, out=out, bib=bib)


def list_styles() -> list[str]:
    """Lista CSLs disponíveis."""
    return _export.list_styles()


def extract_comments(docx_path: Path, out_dir: Path) -> Path:
    """Extrai comentários + revisões de `.docx` revisado."""
    return _comments.extract_to_file(docx_path, out_dir)
