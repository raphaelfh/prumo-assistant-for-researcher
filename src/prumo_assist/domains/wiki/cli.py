"""Subcomandos ``prumo wiki *`` — Typer fachada."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, cast

import typer
from pydantic import ValidationError

from prumo_assist import PrumoError
from prumo_assist.core.cli_io import parse_json_list, read_stdin_json, read_stdin_text
from prumo_assist.core.cli_op import cli_run
from prumo_assist.core.note_paths import slugify
from prumo_assist.domains.wiki import findings, index, lint, stats, study
from prumo_assist.domains.wiki.schemas.v1 import StepLog

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


@wiki_app.command("study-start")
def study_start_command(
    topic: Annotated[str, typer.Argument(help="Tópico da sessão (texto livre; vira slug).")],
    date: Annotated[str, typer.Option("--date", help="Data ISO YYYY-MM-DD.")],
    sources: Annotated[str, typer.Option("--sources", help="Array JSON de wikilinks.")] = "[]",
    path: Annotated[Path, typer.Option("--path", help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Cria o log de uma sessão de estudo (slugifica o tópico) e imprime o caminho."""
    with cli_run(json_mode=json_mode, catches=(ValueError,)) as console:
        sources_list = parse_json_list(sources, "--sources")
        slug = slugify(topic)
        log_path = study.create_session_log(
            pj_path=path.resolve(), topic=slug, date=date, sources_consulted=sources_list
        )
        console.success(f"Sessão criada: {log_path}")
        console.emit({"log_path": str(log_path), "slug": slug})


@wiki_app.command("study-step")
def study_step_command(
    log_path: Annotated[Path, typer.Option("--log-path", help="Caminho do log da sessão.")],
    step: Annotated[str, typer.Option("--step", help="recall|anchor|connect|apply|reflect.")],
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Anexa um step (StepLog via stdin JSON) ao log da sessão."""
    with cli_run(
        json_mode=json_mode, catches=(ValueError, FileNotFoundError, ValidationError)
    ) as console:
        payload = read_stdin_json()
        payload["step_name"] = step
        step_obj = StepLog(**payload)
        study.append_step(log_path, step_obj)
        console.success(f"Step '{step}' anexado.")
        console.emit({"ok": True, "step": step})


@wiki_app.command("study-finish")
def study_finish_command(
    log_path: Annotated[Path, typer.Option("--log-path", help="Caminho do log da sessão.")],
    duration: Annotated[int, typer.Option("--duration", help="Duração em minutos.")],
    status: Annotated[str, typer.Option("--status", help="completed|abandoned|partial.")],
    missing: Annotated[str, typer.Option("--missing", help="Array JSON de REF FALTANTE.")] = "[]",
    finding: Annotated[str, typer.Option("--finding", help="Caminho do finding (ou vazio).")] = "",
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Finaliza a sessão: grava duração/status/missing/finding no frontmatter."""
    with cli_run(json_mode=json_mode, catches=(ValueError, FileNotFoundError)) as console:
        # mantenha em sincronia com SessionStatus (Literal) em schemas/v1.py
        if status not in ("completed", "abandoned", "partial"):
            raise PrumoError("--status deve ser completed|abandoned|partial.")
        missing_list = parse_json_list(missing, "--missing")
        finding_path = Path(finding) if finding else None
        study.finalize_session(
            log_path,
            duration_minutes=duration,
            status=cast(Literal["completed", "abandoned", "partial"], status),
            references_missing=missing_list,
            finding_archived=finding_path,
        )
        console.success("Sessão finalizada.")
        console.emit({"ok": True, "status": status})


@wiki_app.command("finding")
def finding_command(
    slug: Annotated[str, typer.Option("--slug", help="Slug do finding.")],
    title: Annotated[str, typer.Option("--title", help="Título.")],
    date: Annotated[str, typer.Option("--date", help="Data ISO YYYY-MM-DD.")],
    tags: Annotated[str, typer.Option("--tags", help="Array JSON de tags.")] = "[]",
    sources: Annotated[str, typer.Option("--sources", help="Array JSON de wikilinks.")] = "[]",
    generator: Annotated[str, typer.Option("--generator", help="Skill geradora.")] = "wiki-query",
    path: Annotated[Path, typer.Option("--path", help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Arquiva um finding (corpo markdown via stdin) em docs/wiki/findings/."""
    with cli_run(json_mode=json_mode, catches=(ValueError, FileNotFoundError)) as console:
        body = read_stdin_text()
        tags_list = parse_json_list(tags, "--tags")
        sources_list = parse_json_list(sources, "--sources")
        out = findings.archive_as_finding(
            pj_path=path.resolve(),
            slug=slug,
            title=title,
            body=body,
            sources=sources_list,
            date=date,
            tags=tags_list,
            generator=generator,
        )
        console.success(f"Finding arquivado: {out}")
        console.emit({"finding_path": str(out)})
