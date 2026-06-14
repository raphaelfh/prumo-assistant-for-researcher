"""Subcomandos ``prumo protocol *`` — Typer fachada."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from prumo_assist import PrumoError
from prumo_assist.core.cli_io import read_stdin_json
from prumo_assist.core.cli_op import cli_run
from prumo_assist.domains.protocol import ops
from prumo_assist.domains.protocol.schemas.v1 import Hypothesis, PicotSpec

protocol_app = typer.Typer(
    name="protocol",
    help="PICOT: propagate (regenerar blocos) + diff (comparar contra último ADR).",
    no_args_is_help=True,
)


@protocol_app.command("propagate")
def propagate_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Regenera blocos ``<!-- picot:begin -->`` em ``protocol.md`` e ``project_guide.md``."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError,)) as console:
        report = ops.propagate(path.resolve())
        console.success(
            f"protocol.md: {report.protocol_status} · project_guide.md: {report.project_status} "
            f"(hash {report.hash8})"
        )
        console.emit(asdict(report))


@protocol_app.command("diff")
def diff_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Compara ``picot.toml`` atual contra snapshot do último ADR ``picot-v<N>``."""
    with cli_run(json_mode=json_mode, catches=(FileNotFoundError,)) as console:
        diff = ops.diff_against_last_adr(path.resolve())
        if diff is None:
            console.warn("`.claude/picot.toml` não encontrado.")
            console.emit({"changes": [], "has_structural": False, "missing": True})
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
        console.emit(
            {
                "changes": [_change_to_dict(c) for c in diff.changes],
                "has_structural": diff.has_structural,
            }
        )


@protocol_app.command("detect-mode")
def detect_mode_command(
    path: Annotated[Path, typer.Argument(help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Imprime o modo da skill (init|formalize|propagate|diff) pelo estado do projeto."""
    with cli_run(json_mode=json_mode) as console:
        console.emit(ops.detect_mode(path.resolve()))


@protocol_app.command("init")
def init_command(
    date: Annotated[str, typer.Option("--date", help="Data ISO YYYY-MM-DD.")],
    motivation: Annotated[
        str, typer.Option("--motivation", help="Motivação do ADR-0001.")
    ] = "versão inicial — primeira formalização",
    path: Annotated[Path, typer.Option("--path", help="Diretório do pj_*.")] = Path("."),
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Cria o PicotSpec inicial (JSON via stdin), propaga blocos e grava o ADR-0001."""
    with cli_run(
        json_mode=json_mode, catches=(ValueError, FileNotFoundError, ValidationError)
    ) as console:
        payload = read_stdin_json()
        hypothesis_data = payload.pop("hypothesis", None)
        if not isinstance(hypothesis_data, dict):
            raise PrumoError("payload PicotSpec exige a chave 'hypothesis' (objeto).")
        spec = PicotSpec(**payload, hypothesis=Hypothesis(**hypothesis_data))
        result = ops.init_picot_spec(path.resolve(), spec=spec, motivation=motivation, date=date)
        console.success(f"PicotSpec v{spec.version} inicializado; ADR em {result.adr_path}")
        console.emit({"adr_path": str(result.adr_path), "propagate": asdict(result.report)})


def _change_to_dict(change: object) -> dict[str, object]:
    if is_dataclass(change):
        return asdict(change)  # type: ignore[arg-type]
    return {"field": "?", "before": None, "after": None, "structural": False}
