"""Console output — Rich quando interativo, JSON quando ``--json``, plain quando piped.

Princípio: comando único deve servir 3 audiências sem código duplicado:

1. Pesquisador no terminal interativo → tabelas/cores/ícones via Rich.
2. Notebook ou script → ``--json`` pra parse downstream.
3. Pipe Unix (``prumo paper find ... | jq ...``) → plain quando não-TTY.

Resto do código nunca chama ``print()`` diretamente — sempre via ``Console``
desta camada — pra que o modo de saída seja decisão central.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from rich.console import Console as RichConsole


class Console:
    """Fachada fina sobre ``rich.Console`` com modo JSON e detecção de TTY."""

    def __init__(self, *, json_mode: bool = False, force_terminal: bool | None = None) -> None:
        self._json = json_mode
        self._rich = RichConsole(
            force_terminal=force_terminal,
            no_color=not sys.stdout.isatty() and force_terminal is None,
            highlight=False,
        )

    @property
    def json_mode(self) -> bool:
        return self._json

    def info(self, message: str) -> None:
        if self._json:
            return  # mensagens informativas não poluem stream JSON
        self._rich.print(message)

    def success(self, message: str) -> None:
        if self._json:
            return
        self._rich.print(f"[green]✓[/green] {message}")

    def warn(self, message: str) -> None:
        if self._json:
            print(json.dumps({"level": "warn", "message": message}), file=sys.stderr)
            return
        self._rich.print(f"[yellow]⚠[/yellow] {message}", style="yellow")

    def error(self, message: str) -> None:
        if self._json:
            print(json.dumps({"level": "error", "message": message}), file=sys.stderr)
            return
        self._rich.print(f"[red]✗[/red] {message}", style="red")

    def emit(self, payload: Any) -> None:
        """Emite o payload primário do comando.

        Em modo JSON: ``json.dumps(payload)`` pra stdout.
        Em modo Rich: tenta inferir formato (dict → tabela; list → enum; str → print).
        """
        if self._json:
            print(json.dumps(payload, ensure_ascii=False, default=str))
            return
        if isinstance(payload, str):
            self._rich.print(payload)
        elif isinstance(payload, dict):
            self._render_dict(payload)
        elif isinstance(payload, list):
            for item in payload:
                self.emit(item)
        else:
            self._rich.print(repr(payload))

    def _render_dict(self, d: dict[str, Any]) -> None:
        for k, v in d.items():
            self._rich.print(f"[cyan]{k}[/cyan]: {v}")
