"""Subcomandos ``prumo write *``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, cast

import typer

from prumo_assist import PrumoError
from prumo_assist.core.cli_io import parse_json_list, read_stdin_text
from prumo_assist.core.cli_op import cli_run
from prumo_assist.domains.write import comments, compose, export
from prumo_assist.domains.write.schemas.v1 import WriteKind, WriteMode

write_app = typer.Typer(
    name="write",
    help="Escrita: export Pandoc/Typst, composição multi-página, extração de comentários.",
    no_args_is_help=True,
)

_WRITE_KINDS = ("paper", "projeto-cep", "statistics", "scientific")
_WRITE_MODES = ("drafts", "into", "out")


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


@write_app.command("zettlr-profile")
def zettlr_profile_command(
    path: Annotated[Path, typer.Option("--path", help="Raiz do pj_*.")] = Path("."),
    style: Annotated[str, typer.Option("--style", help="Estilo CSL (default: apa).")] = "apa",
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """(Re)gera o perfil de export docx do Zettlr (defaults file) do projeto."""
    with cli_run(json_mode=json_mode, catches=(OSError,)) as console:
        from prumo_assist.domains.write.zettlr import generate_profile

        out = generate_profile(path.resolve(), style=style)
        console.success(
            f"Perfil Zettlr gerado: {out}. Importe uma vez no Zettlr "
            "(Assets Manager → defaults files); re-rode este comando se o prumo for reinstalado."
        )
        console.emit({"profile": str(out)})


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


@write_app.command("disclosure")
def disclosure_command(
    path: Annotated[Path, typer.Argument(help="Raiz do pj_* a escanear.")] = Path("."),
    lang: Annotated[str, typer.Option("--lang", help="Idioma da declaração: en | pt.")] = "en",
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Gera a declaração de uso de IA a partir da proveniência dos artefatos."""
    with cli_run(json_mode=json_mode) as console:
        from prumo_assist.domains.write.disclosure import generate_disclosure

        disc = generate_disclosure(root=path.resolve())
        if json_mode:
            console.emit(disc.model_dump())
        else:
            console.emit(disc.statement_pt if lang == "pt" else disc.statement_en)


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
            plugin_path = plugin_root / "writing" / f"{kind}.md" if plugin_root else None
            result[kind] = {
                "project_override": str(project_path) if project_path.exists() else None,
                "plugin_default": (
                    str(plugin_path) if plugin_path and plugin_path.exists() else None
                ),
            }
        console.emit(result)


@write_app.command("prep")
def prep_command(
    kind: Annotated[
        str, typer.Option("--kind", help="paper|projeto-cep|statistics|scientific.")
    ] = "paper",
    path: Annotated[Path, typer.Option("--path", help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Lê inputs do projeto + resolve o template (contexto pra escrita) num só passo."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError,)) as console:
        if kind not in _WRITE_KINDS:
            raise PrumoError(f"--kind deve ser um de {list(_WRITE_KINDS)}.")
        result = compose.prep(path.resolve(), kind=cast(WriteKind, kind))
        console.success(f"Contexto pronto (template {result.template_path.name}).")
        console.emit(
            {
                "inputs": result.inputs.model_dump(mode="json"),
                "template_path": str(result.template_path),
            }
        )


@write_app.command("draft")
def draft_command(
    kind: Annotated[str, typer.Option("--kind", help="paper|projeto-cep|statistics|scientific.")],
    date: Annotated[str, typer.Option("--date", help="Data ISO YYYY-MM-DD.")],
    slug: Annotated[str, typer.Option("--slug", help="Slug do output.")],
    mode: Annotated[str, typer.Option("--mode", help="drafts|into|out.")] = "drafts",
    section: Annotated[
        str, typer.Option("--section", help="Nome da seção alvo (obrigatório no modo into).")
    ] = "",
    sections: Annotated[
        str, typer.Option("--sections", help="Array JSON de seções preenchidas.")
    ] = "[]",
    into: Annotated[str, typer.Option("--into", help="Caminho destino (modo into).")] = "",
    out: Annotated[str, typer.Option("--out", help="Caminho destino (modo out).")] = "",
    force: Annotated[bool, typer.Option("--force", help="Sobrescreve no modo out.")] = False,
    path: Annotated[Path, typer.Option("--path", help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Grava o draft (markdown via stdin) conforme o modo; reporta o WriteOutput."""
    with cli_run(
        json_mode=json_mode, catches=(ValueError, FileNotFoundError, FileExistsError)
    ) as console:
        if kind not in _WRITE_KINDS:
            raise PrumoError(f"--kind deve ser um de {list(_WRITE_KINDS)}.")
        if mode not in _WRITE_MODES:
            raise PrumoError(f"--mode deve ser um de {list(_WRITE_MODES)}.")
        content = read_stdin_text()
        sections_list = parse_json_list(sections, "--sections")
        result = compose.write_output(
            content=content,
            pj_path=path.resolve(),
            kind=cast(WriteKind, kind),
            mode=cast(WriteMode, mode),
            section=section or None,
            date=date,
            slug=slug,
            into=Path(into) if into else None,
            out=Path(out) if out else None,
            force=force,
            sections_filled=sections_list,
        )
        console.success(
            f"Draft gravado em {result.output_path} ({result.words_generated} palavras)."
        )
        console.emit(result.model_dump(mode="json"))


def zettlr_export_entry() -> None:
    """Console-script pro custom command do Zettlr: `prumo-zettlr-export <arquivo.md>`.

    O Zettlr invoca o comando com o caminho absoluto do arquivo
    selecionado como único argumento e mostra a saída ao usuário.
    Caminho canônico: mesmas guardas do ``prumo write export --to docx``.
    """
    import sys

    try:
        with cli_run(
            json_mode=False, catches=(FileNotFoundError, ValueError, RuntimeError)
        ) as console:
            if len(sys.argv) != 2:
                raise PrumoError("uso: prumo-zettlr-export <arquivo.md>")
            page = Path(sys.argv[1]).resolve()
            result = export.export(page=page, to="docx")
            console.success(f"exportado: {result}")
    except typer.Exit as e:
        # Entrypoint fora do dispatch do Click (é um `[project.scripts]` cru,
        # não um app Typer/Click): sem isso, o `typer.Exit` levantado por
        # `cli_run` em erro escaparia como traceback cru no painel do Zettlr,
        # mesmo após a mensagem pt-BR já ter sido impressa por `console.error`.
        raise SystemExit(e.exit_code) from None
