"""Subcomandos ``prumo paper *`` — Typer fachada.

Lógica fica nos módulos de domínio (``sync``, ``graph``, ``find``, ``lint``,
``pdfs``, ``annotations``, ``callout``). Aqui só parsing de args + saída.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from prumo_assist import PrumoError
from prumo_assist.core.output import Console
from prumo_assist.domains.paper import find as find_mod
from prumo_assist.domains.paper import graph as graph_mod
from prumo_assist.domains.paper import lint as lint_mod
from prumo_assist.domains.paper import pdfs as pdfs_mod
from prumo_assist.domains.paper import sync as sync_mod
from prumo_assist.domains.paper import zotero as zotero_mod

paper_app = typer.Typer(
    name="paper",
    help="Bibliografia: sync com Zotero/BBT, grafo, find, lint.",
    no_args_is_help=True,
)


def _project_path(path: Path) -> Path:
    """Normaliza path do projeto (cwd default)."""
    return path.resolve()


@paper_app.command("sync")
def sync_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """``.bib`` → ``references/notes/<citekey>.md`` (Better BibTeX → Obsidian)."""
    console = Console(json_mode=json_mode)
    pj = _project_path(path)
    try:
        report = sync_mod.sync(pj)
    except (FileNotFoundError, PrumoError) as e:
        console.error(str(e))
        raise typer.Exit(code=1) from e
    console.success(
        f"{report['created']} novas, {report['updated']} atualizadas, "
        f"{len(report['orphans'])} órfãs."
    )
    console.emit(report)


@paper_app.command("graph")
def graph_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Grafo passivo de citação: lê ``[[@key]]`` no body, popula ``cites:`` no YAML."""
    console = Console(json_mode=json_mode)
    pj = _project_path(path)
    report = graph_mod.update_graph(pj)
    console.success(
        f"+{report['edges_added']} arestas adicionadas, -{report['edges_removed']} removidas."
    )
    console.emit(report)


@paper_app.command("find")
def find_command(
    query: Annotated[str, typer.Argument(help="Texto livre.")],
    path: Annotated[Path, typer.Option("--path", help="pj_* (default cwd).")] = Path("."),
    top_k: Annotated[int, typer.Option("--top-k")] = 5,
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Fuzzy search sobre ``.bib`` + notas (autor, título, ano, tldr)."""
    console = Console(json_mode=json_mode)
    pj = _project_path(path)
    results = find_mod.fuzzy_search(pj, query, top_k=top_k)
    if not results:
        console.warn("(nenhum match)")
    console.emit({"query": query, "results": results})


@paper_app.command("lint")
def lint_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Auditoria: bib↔notas↔pdfs, citekeys quebradas, primary duplicado, etc."""
    console = Console(json_mode=json_mode)
    pj = _project_path(path)
    report = lint_mod.lint(pj)
    if report["ok"]:
        console.success(f"OK ({report['summary']['warnings']} warnings).")
    else:
        console.error(f"{report['summary']['errors']} erro(s) crítico(s).")
    console.emit(report)
    if not report["ok"]:
        raise typer.Exit(code=1)


@paper_app.command("set-primary")
def set_primary_command(
    citekey: Annotated[str, typer.Argument(help="Citekey alvo.")],
    path: Annotated[Path, typer.Option("--path")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Marca um paper como ``role: primary`` (limpa de outros)."""
    console = Console(json_mode=json_mode)
    pj = _project_path(path)
    try:
        report = lint_mod.set_primary(pj, citekey)
    except FileNotFoundError as e:
        console.error(str(e))
        raise typer.Exit(code=1) from e
    console.success(f"{citekey} é o primary agora.")
    if report["cleared_from"]:
        console.info(f"  removido de: {', '.join(report['cleared_from'])}")
    console.emit(report)


@paper_app.command("sync-pdfs")
def sync_pdfs_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Cria/atualiza symlinks ``references/pdfs/<key>.pdf`` → ``~/Zotero/storage/...``."""
    console = Console(json_mode=json_mode)
    pj = _project_path(path)
    try:
        report = pdfs_mod.sync_pdfs(pj)
    except FileNotFoundError as e:
        console.error(str(e))
        raise typer.Exit(code=1) from e
    console.success(
        f"{report['created']} novos, {report['updated']} atualizados, "
        f"{report['ok']} já ok, {len(report['missing'])} sem PDF no Zotero."
    )
    console.emit(report)


@paper_app.command("sync-annotations")
def sync_annotations_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Sincroniza annotations + child notes do Zotero pra cada nota local.

    Requer Zotero 9 aberto + Better BibTeX instalado (API local em
    ``http://localhost:23119``)."""
    console = Console(json_mode=json_mode)
    pj = _project_path(path)
    try:
        report = zotero_mod.sync_annotations(pj)
    except (FileNotFoundError, ConnectionError) as e:
        console.error(str(e))
        raise typer.Exit(code=2) from e
    console.success(
        f"{report['inserted']} inseridos, {report['updated']} atualizados, "
        f"{report['unchanged']} já em dia."
    )
    console.emit(report)
