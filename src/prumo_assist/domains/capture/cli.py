"""``prumo capture <input>`` — router fino.

Exposto como **função** (não Typer sub-app) porque é um único comando sem
subcomandos. Registrado direto no app raiz via ``app.command("capture")``."""

from __future__ import annotations

from typing import Annotated

import typer

from prumo_assist.core.cli_op import cli_run
from prumo_assist.domains.capture.route import classify


def capture_command(
    input_value: Annotated[str, typer.Argument(help="URL, DOI, arXiv, PDF path ou citekey.")],
    json_mode: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Classifica o input e imprime sugestão de próximo passo."""
    with cli_run(json_mode=json_mode) as console:
        route = classify(input_value)
        # Sem marcação Rich embutida na string (Fix pós-review, Crítico #2 do
        # Console): `route.canonical` ecoa o input do usuário quase cru — um
        # citekey/URL com colchetes literais não pode ser reinterpretado.
        console.info(f"{route.kind.upper()}: {route.canonical}")
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
