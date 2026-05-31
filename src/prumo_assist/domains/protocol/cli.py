"""Subcomandos ``prumo protocol *`` — Typer fachada."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Annotated

import typer

from prumo_assist.core.cli_op import cli_run
from prumo_assist.domains.protocol import ops

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
                f"{len(diff.changes)} campo(s) mudaram "
                f"(estrutural: {diff.has_structural})."
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


def _change_to_dict(change: object) -> dict[str, object]:
    if is_dataclass(change):
        return asdict(change)  # type: ignore[arg-type]
    return {"field": "?", "before": None, "after": None, "structural": False}
