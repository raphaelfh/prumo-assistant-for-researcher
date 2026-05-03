"""Helper compartilhado pelos comandos Typer dos domínios.

Cada subcomando do CLI repete o mesmo esqueleto: cria ``Console``, executa a
operação do domínio, captura ``PrumoError`` (e exceções específicas que cada
operação permite vazar) e mapeia pra ``typer.Exit(1)``. Isolamos isso aqui
pra que ``domains/<X>/cli.py`` fique apenas com parsing de args + chamada do
domínio + formatação de saída.

Uso típico::

    @paper_app.command("sync")
    def sync_command(path: Path = Path("."), json_mode: bool = False) -> None:
        with cli_run(json_mode=json_mode, catches=(FileNotFoundError,)) as console:
            report = sync_mod.sync(path.resolve())
            console.success(f"{report['created']} novas.")
            console.emit(report)
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

import typer

from prumo_assist import PrumoError
from prumo_assist.core.output import Console


@contextmanager
def cli_run(
    *,
    json_mode: bool = False,
    catches: tuple[type[Exception], ...] = (),
    exit_code: int = 1,
) -> Generator[Console, None, None]:
    """Context manager: cria ``Console`` e converte exceções em ``Exit(exit_code)``.

    Captura sempre ``PrumoError`` e, adicionalmente, qualquer classe listada em
    ``catches``. Outras exceções vazam (são bugs, queremos traceback).
    """
    console = Console(json_mode=json_mode)
    handled: tuple[type[Exception], ...] = (PrumoError, *catches)
    try:
        yield console
    except handled as e:
        console.error(str(e))
        raise typer.Exit(code=exit_code) from e
