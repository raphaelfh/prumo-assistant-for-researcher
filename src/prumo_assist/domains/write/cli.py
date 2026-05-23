"""Subcomandos ``prumo write *``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from prumo_assist.core.cli_op import cli_run
from prumo_assist.domains.write import comments, export

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
    template: Annotated[
        Path | None,
        typer.Option("--template", help="Template para typst/pdf (ignorado em docx)."),
    ] = None,
    reference_doc: Annotated[
        Path | None,
        typer.Option(
            "--reference-doc",
            help="Template .docx (estilos/cabeçalho/rodapé) — somente formato docx.",
        ),
    ] = None,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Exporta uma página Markdown via Pandoc + CSL → DOCX/Typst/PDF/HTML."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError, ValueError)) as console:
        page_resolved = page.resolve()
        project_root = export.detect_project_root(page_resolved)

        out: Path | None = None
        if out_dir is not None:
            out = (
                out_dir.resolve()
                / f"{export._slugify(page_resolved, project_root)}.{export.EXT_BY_FORMAT[to]}"
            )

        result = export.export(
            page=page_resolved,
            style=style,
            to=to,
            out=out,
            bib=bib.resolve() if bib else None,
            template=template.resolve() if template else None,
            reference_doc=reference_doc.resolve() if reference_doc else None,
            project_root=project_root,
        )
        console.success(f"exportado: {result}")
        console.emit({"page": str(page_resolved), "output": str(result), "format": to})


@write_app.command("compose")
def compose_command(
    index: Annotated[Path, typer.Option("--index", help="Index file com pages: [...]")],
    to: Annotated[str, typer.Option("--to")] = "docx",
    style: Annotated[str | None, typer.Option("--style")] = None,
    bib: Annotated[Path | None, typer.Option("--bib")] = None,
    out_dir: Annotated[Path | None, typer.Option("--out-dir")] = None,
    template: Annotated[
        Path | None,
        typer.Option("--template", help="Template para typst/pdf (ignorado em docx)."),
    ] = None,
    reference_doc: Annotated[
        Path | None,
        typer.Option(
            "--reference-doc",
            help="Template .docx (estilos/cabeçalho/rodapé) — somente formato docx.",
        ),
    ] = None,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Compõe múltiplas páginas (frontmatter ``pages: [...]``) em um documento único."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError, ValueError)) as console:
        index_resolved = index.resolve()
        project_root = export.detect_project_root(index_resolved)

        out: Path | None = None
        if out_dir is not None:
            slug = index_resolved.stem.removesuffix(".idx")
            out = out_dir.resolve() / f"{slug}.{export.EXT_BY_FORMAT[to]}"

        result = export.compose(
            index=index_resolved,
            to=to,
            style=style,
            out=out,
            bib=bib.resolve() if bib else None,
            template=template.resolve() if template else None,
            reference_doc=reference_doc.resolve() if reference_doc else None,
            project_root=project_root,
        )
        console.success(f"composto: {result}")
        console.emit({"index": str(index_resolved), "output": str(result), "format": to})


@write_app.command("list-styles")
def list_styles_command(
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Lista CSLs disponíveis em ``~/Zotero/styles/``."""
    with cli_run(json_mode=json_mode) as console:
        styles = export.list_styles()
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
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError,)) as console:
        out = comments.extract_to_file(docx.resolve(), out_dir.resolve())
        console.success(f"checklist: {out}")
        console.emit({"docx": str(docx.resolve()), "output": str(out)})


@write_app.command("list-templates")
def list_templates_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Lista templates resolvíveis (project overrides + plugin defaults)."""
    from prumo_assist.core.paths import find_resource

    with cli_run(json_mode=json_mode) as console:
        kinds = ("paper", "projeto-cep", "statistics", "scientific")
        result: dict[str, dict[str, str | None]] = {}
        plugin_root = find_resource("templates")
        for kind in kinds:
            project_path = path.resolve() / ".claude" / "writing_templates" / f"{kind}.md"
            plugin_path = (
                plugin_root / "writing" / f"{kind}.md" if plugin_root else None
            )
            result[kind] = {
                "project_override": str(project_path) if project_path.exists() else None,
                "plugin_default": (
                    str(plugin_path) if plugin_path and plugin_path.exists() else None
                ),
            }
        console.emit(result)
