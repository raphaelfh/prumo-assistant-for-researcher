"""``prumo capture <input>`` — router fino.

Exposto como **função** (não Typer sub-app) porque é um único comando sem
subcomandos. Registrado direto no app raiz via ``app.command("capture")``."""

from __future__ import annotations

from typing import Annotated

import typer

from prumo_assist.core.output import Console
from prumo_assist.domains.capture.route import classify


def capture_command(
    input_value: Annotated[str, typer.Argument(help="URL, DOI, arXiv, PDF path ou citekey.")],
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Classifica o input e imprime sugestão de próximo passo."""
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
