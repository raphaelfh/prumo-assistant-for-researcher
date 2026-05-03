"""Subcomandos ``prumo wiki *`` — Typer fachada."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from prumo_assist.core.cli_op import cli_run
from prumo_assist.domains.wiki import index, lint, stats

wiki_app = typer.Typer(
    name="wiki",
    help="Conhecimento: lint, index, stats. Skills agênticas (ingest/query) vivem no host.",
    no_args_is_help=True,
)


@wiki_app.command("lint")
def lint_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Auditoria do wiki (citekeys quebradas, páginas órfãs, frontmatter)."""
    with cli_run(json_mode=json_mode) as console:
        report = lint.lint(path.resolve())
        if report["ok"]:
            console.success(f"OK ({report['summary']['warnings']} warnings).")
        else:
            console.error(f"{report['summary']['errors']} erro(s) crítico(s).")
        console.emit(report)
        if not report["ok"]:
            raise typer.Exit(code=1)


@wiki_app.command("index")
def index_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    name: Annotated[str | None, typer.Option("--name")] = None,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Reindexa o wiki via ``qmd`` (BM25 + vector + rerank)."""
    with cli_run(json_mode=json_mode, catches=(index.QmdNotFoundError,)) as console:
        report = index.reindex(path.resolve(), name=name)
        if report["ok"]:
            console.success(f"Wiki '{report['name']}' indexado.")
        else:
            console.error(f"Falha ao indexar: {report.get('stderr', 'erro desconhecido')}")
        console.emit(report)
        if not report["ok"]:
            raise typer.Exit(code=1)


@wiki_app.command("stats")
def stats_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Contagem de páginas por tipo + total."""
    with cli_run(json_mode=json_mode) as console:
        console.emit(stats.stats(path.resolve()))
