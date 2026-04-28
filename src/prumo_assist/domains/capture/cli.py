"""``prumo capture <input>`` — router fino."""

from __future__ import annotations

from typing import Annotated

import typer

from prumo_assist.core.output import Console
from prumo_assist.domains.capture.route import classify

capture_app = typer.Typer(
    name="capture",
    help="Detecta tipo de input (URL, DOI, arXiv, PDF, citekey) e sugere próximo passo.",
)


@capture_app.callback(invoke_without_command=True)
def capture_command(
    input_value: Annotated[str, typer.Argument(help="URL, DOI, arXiv, PDF path ou citekey.")],
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Classifica o input e imprime sugestão."""
    console = Console(json_mode=json_mode)
    route = classify(input_value)
    console.info(f"[bold]{route.kind.upper()}[/bold]: {route.canonical}")
    console.info(f"→ {route.suggestion}")
    if route.next_command:
        console.info(f"   `{route.next_command}`")
    console.emit(
        {
            "kind": route.kind,
            "canonical": route.canonical,
            "suggestion": route.suggestion,
            "next_command": route.next_command,
        }
    )
