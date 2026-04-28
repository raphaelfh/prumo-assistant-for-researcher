"""Subcomandos ``prumo write *``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from prumo_assist.core.output import Console
from prumo_assist.domains.write import comments as comments_mod
from prumo_assist.domains.write import export as export_mod

write_app = typer.Typer(
    name="write",
    help="Escrita: export Pandoc/Typst, composição multi-página, extração de comentários.",
    no_args_is_help=True,
)


@write_app.command("export")
def export_command(
    page: Annotated[Path, typer.Argument(help="Página .md a exportar.")],
    to: Annotated[str, typer.Option("--to", help="docx | typst | pdf | html")] = "docx",
    style: Annotated[str, typer.Option("--style", help="Estilo CSL (default: apa).")] = "apa",
    bib: Annotated[Path | None, typer.Option("--bib")] = None,
    out_dir: Annotated[Path | None, typer.Option("--out-dir")] = None,
    template: Annotated[Path | None, typer.Option("--template")] = None,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Exporta uma página Markdown via Pandoc + CSL → DOCX/Typst/PDF/HTML."""
    console = Console(json_mode=json_mode)
    page_resolved = page.resolve()
    try:
        project_root = export_mod.detect_project_root(page_resolved)
    except FileNotFoundError as e:
        console.error(str(e))
        raise typer.Exit(code=1) from e

    out: Path | None = None
    if out_dir is not None:
        out = (
            out_dir.resolve()
            / f"{export_mod._slugify(page_resolved, project_root)}.{export_mod.EXT_BY_FORMAT[to]}"
        )

    try:
        result = export_mod.export(
            page=page_resolved,
            style=style,
            to=to,
            out=out,
            bib=bib.resolve() if bib else None,
            template=template.resolve() if template else None,
            project_root=project_root,
        )
    except (FileNotFoundError, ValueError) as e:
        console.error(str(e))
        raise typer.Exit(code=1) from e
    console.success(f"exportado: {result}")
    console.emit({"page": str(page_resolved), "output": str(result), "format": to})


@write_app.command("compose")
def compose_command(
    index: Annotated[Path, typer.Option("--index", help="Index file com pages: [...]")],
    to: Annotated[str, typer.Option("--to")] = "docx",
    style: Annotated[str | None, typer.Option("--style")] = None,
    bib: Annotated[Path | None, typer.Option("--bib")] = None,
    out_dir: Annotated[Path | None, typer.Option("--out-dir")] = None,
    template: Annotated[Path | None, typer.Option("--template")] = None,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Compõe múltiplas páginas (frontmatter ``pages: [...]``) em um documento único."""
    console = Console(json_mode=json_mode)
    index_resolved = index.resolve()
    try:
        project_root = export_mod.detect_project_root(index_resolved)
    except FileNotFoundError as e:
        console.error(str(e))
        raise typer.Exit(code=1) from e

    out: Path | None = None
    if out_dir is not None:
        slug = index_resolved.stem.removesuffix(".idx")
        out = out_dir.resolve() / f"{slug}.{export_mod.EXT_BY_FORMAT[to]}"

    try:
        result = export_mod.compose(
            index=index_resolved,
            to=to,
            style=style,
            out=out,
            bib=bib.resolve() if bib else None,
            template=template.resolve() if template else None,
            project_root=project_root,
        )
    except (FileNotFoundError, ValueError) as e:
        console.error(str(e))
        raise typer.Exit(code=1) from e
    console.success(f"composto: {result}")
    console.emit({"index": str(index_resolved), "output": str(result), "format": to})


@write_app.command("list-styles")
def list_styles_command(
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Lista CSLs disponíveis em ``~/Zotero/styles/``."""
    console = Console(json_mode=json_mode)
    styles = export_mod.list_styles()
    if not styles:
        console.warn("Nenhum estilo CSL em ~/Zotero/styles/.")
    console.emit({"styles": styles})


@write_app.command("extract-comments")
def extract_comments_command(
    docx: Annotated[Path, typer.Argument(help="Caminho do .docx revisado.")],
    out_dir: Annotated[
        Path, typer.Option("--out-dir", help="Diretório do checklist (default: docs/comments).")
    ] = Path("docs/comments"),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Extrai comentários + track changes do ``.docx`` em checklist Markdown."""
    console = Console(json_mode=json_mode)
    try:
        out = comments_mod.extract_to_file(docx.resolve(), out_dir.resolve())
    except FileNotFoundError as e:
        console.error(str(e))
        raise typer.Exit(code=1) from e
    console.success(f"checklist: {out}")
    console.emit({"docx": str(docx.resolve()), "output": str(out)})
