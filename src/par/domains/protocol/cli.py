"""Subcomandos ``prumo protocol *`` — Typer fachada."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from par import PrumoError
from par.core import pj_layout
from par.core.cli_io import read_stdin_json
from par.core.cli_op import cli_run
from par.domains.protocol import ops
from par.domains.protocol.schemas.v1 import Hypothesis, PicotSpec

protocol_app = typer.Typer(
    name="protocol",
    help="PICOT: propagate (regenerar blocos) + diff (comparar contra último ADR).",
    no_args_is_help=True,
)


_PATH_HELP = "Escopo de escrita (docs/studies/<slug>/) ou um caminho dentro dele."


@protocol_app.command("propagate")
def propagate_command(
    path: Annotated[Path, typer.Argument(help=_PATH_HELP)] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Regenera blocos ``<!-- picot:begin -->`` em ``protocol.md`` (do escopo) e
    ``project_guide.md`` (do projeto)."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError,)) as console:
        scope = pj_layout.find_scope_root(path.resolve())
        report = ops.propagate(scope)
        console.success(
            f"protocol.md: {report.protocol_status} · project_guide.md: {report.project_status} "
            f"(hash {report.hash8})"
        )
        console.emit(asdict(report))


@protocol_app.command("diff")
def diff_command(
    path: Annotated[Path, typer.Argument(help=_PATH_HELP)] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Compara ``picot.toml`` atual contra snapshot do último ADR ``picot-v<N>`` e
    reporta drift dos drafts de ``writing/`` contra protocolo/PICOT (um ``.md`` em
    ``path`` restringe a esse draft)."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError,)) as console:
        scope = pj_layout.find_scope_root(path.resolve())
        draft = path.resolve() if path.suffix == ".md" and path.is_file() else None
        drift = [asdict(d) for d in ops.manuscript_drift(scope, draft=draft)]
        for d in drift:
            console.warn(
                f"drift {d['kind']}: protocolo {d['protocol_value']} ({d['protocol_loc']}) "
                f"≠ draft {d['draft_value']} ({', '.join(d['draft_locs'])}). {d['hint']}"
            )
        diff = ops.diff_against_last_adr(scope)
        if diff is None:
            console.warn("`.claude/picot.toml` não encontrado.")
            if json_mode:
                console.emit(
                    {"changes": [], "has_structural": False, "missing": True, "drift": drift}
                )
            return
        if not diff.changes:
            console.success("Sem mudanças desde o último ADR (ou sem baseline).")
        else:
            console.info(
                f"{len(diff.changes)} campo(s) mudaram (estrutural: {diff.has_structural})."
            )
            for c in diff.changes:
                console.info(
                    f"  • {c.field}: {c.before!r} → {c.after!r} "
                    f"({'estrutural' if c.structural else 'cosmético'})"
                )
        if json_mode:  # modo texto já disse tudo nas linhas acima (Princípio VIII)
            console.emit(
                {
                    "changes": [_change_to_dict(c) for c in diff.changes],
                    "has_structural": diff.has_structural,
                    "drift": drift,
                }
            )


@protocol_app.command("detect-mode")
def detect_mode_command(
    path: Annotated[Path, typer.Argument(help=_PATH_HELP)] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Imprime o modo da skill (init|formalize|propagate|diff) pelo estado do projeto."""
    with cli_run(json_mode=json_mode) as console:
        scope = pj_layout.find_scope_root(path.resolve())
        console.emit(ops.detect_mode(scope))


@protocol_app.command("init")
def init_command(
    date: Annotated[str, typer.Option("--date", help="Data ISO YYYY-MM-DD.")],
    motivation: Annotated[
        str, typer.Option("--motivation", help="Motivação do ADR-0001.")
    ] = "versão inicial — primeira formalização",
    path: Annotated[Path, typer.Option("--path", help=_PATH_HELP)] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Cria o PicotSpec inicial (JSON via stdin), propaga blocos e grava o ADR-0001."""
    with cli_run(
        json_mode=json_mode, catches=(ValueError, FileNotFoundError, ValidationError)
    ) as console:
        payload = read_stdin_json()
        hypothesis_data = payload.pop("hypothesis", None)
        if not isinstance(hypothesis_data, dict):
            raise PrumoError(
                "payload PicotSpec exige a chave 'hypothesis' (objeto JSON); ex.: "
                '{"hypothesis": {"statement": "...", "rationale": "...", "metrics": ["AUROC"]}, ...}'
            )
        spec = PicotSpec(**payload, hypothesis=Hypothesis(**hypothesis_data))
        scope = pj_layout.find_scope_root(path.resolve())
        result = ops.init_picot_spec(scope, spec=spec, motivation=motivation, date=date)
        console.success(f"PicotSpec v{spec.version} inicializado; ADR em {result.adr_path}")
        console.emit({"adr_path": str(result.adr_path), "propagate": asdict(result.report)})


@protocol_app.command("adr")
def adr_command(
    motivation: Annotated[str, typer.Option("--motivation", help="Motivação do ADR.")],
    slug: Annotated[str, typer.Option("--slug", help="Slug kebab-case curto.")],
    date: Annotated[str, typer.Option("--date", help="Data ISO YYYY-MM-DD.")],
    path: Annotated[Path, typer.Option("--path", help=_PATH_HELP)] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Registra o ADR-N para a versão atual do picot.toml (após bump) e propaga blocos."""
    with cli_run(json_mode=json_mode, catches=(ValueError, FileNotFoundError)) as console:
        scope = pj_layout.find_scope_root(path.resolve())
        result = ops.create_picot_adr(scope, motivation=motivation, slug=slug, date=date)
        console.success(f"ADR criado: {result.adr_path}")
        console.emit({"adr_path": str(result.adr_path), "propagate": asdict(result.report)})


def _change_to_dict(change: object) -> dict[str, object]:
    if is_dataclass(change):
        return asdict(change)  # type: ignore[arg-type]
    return {"field": "?", "before": None, "after": None, "structural": False}
