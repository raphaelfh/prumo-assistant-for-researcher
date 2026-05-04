"""Subcomandos ``prumo paper *`` — Typer fachada.

Lógica fica nos módulos de domínio (``sync``, ``graph``, ``find``, ``lint``,
``pdfs``, ``zotero``, ``callout``). Aqui só parsing de args + saída.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from prumo_assist.core.cli_op import cli_run
from prumo_assist.domains.paper import find, graph, lint, migrate, pdfs, sync, zotero

paper_app = typer.Typer(
    name="paper",
    help="Bibliografia: sync com Zotero/BBT, grafo, find, lint.",
    no_args_is_help=True,
)


@paper_app.command("sync")
def sync_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """``.bib`` → ``references/notes/<citekey>/_meta.md`` (Better BibTeX → Obsidian, layout α)."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError,)) as console:
        report = sync.sync(path.resolve())
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
    with cli_run(json_mode=json_mode) as console:
        report = graph.update_graph(path.resolve())
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
    with cli_run(json_mode=json_mode) as console:
        results = find.fuzzy_search(path.resolve(), query, top_k=top_k)
        if not results:
            console.warn("(nenhum match)")
        console.emit({"query": query, "results": results})


@paper_app.command("lint")
def lint_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Auditoria: bib↔notas↔pdfs, citekeys quebradas, primary duplicado, etc."""
    with cli_run(json_mode=json_mode) as console:
        report = lint.lint(path.resolve())
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
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError,)) as console:
        report = lint.set_primary(path.resolve(), citekey)
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
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError,)) as console:
        report = pdfs.sync_pdfs(path.resolve())
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
    with cli_run(
        json_mode=json_mode,
        catches=(FileNotFoundError, ConnectionError),
        exit_code=2,
    ) as console:
        report = zotero.sync_annotations(path.resolve())
        console.success(
            f"{report['inserted']} inseridos, {report['updated']} atualizados, "
            f"{report['unchanged']} já em dia."
        )
        console.emit(report)


@paper_app.command("migrate-layout")
def migrate_layout_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """One-shot: migra ``<key>.md`` legado pra ``<key>/_meta.md`` (+ _extract, _annotations).

    Idempotente. Preserva histórico via ``git mv`` quando o pj_* é repo git.
    """
    with cli_run(json_mode=json_mode) as console:
        report = migrate.migrate_pj(path.resolve())
        console.success(
            f"{len(report['migrated'])} migradas, "
            f"{len(report['already_migrated'])} já estavam em layout α."
        )
        if report["warnings"]:
            for w in report["warnings"]:
                console.warn(w)
        console.emit(report)
