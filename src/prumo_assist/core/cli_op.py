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

from collections.abc import Generator, Mapping
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
    exit_codes: Mapping[type[Exception], int] | None = None,
) -> Generator[Console, None, None]:
    """Context manager: cria ``Console`` e converte exceções em ``Exit``.

    Captura sempre ``PrumoError`` (base de todo erro de domínio) e,
    adicionalmente, qualquer classe listada em ``catches`` ou em
    ``exit_codes``. Outras exceções vazam (são bugs, queremos traceback).

    ``exit_codes`` mapeia classe → exit code (primeiro match por
    ``isinstance`` na ordem de inserção); sem match, vale ``exit_code``
    (default 1).
    """
    console = Console(json_mode=json_mode)
    handled: tuple[type[Exception], ...] = (PrumoError, *catches, *(exit_codes or ()))
    try:
        yield console
    except handled as e:
        console.error(str(e))
        code = next(
            (mapped for cls, mapped in (exit_codes or {}).items() if isinstance(e, cls)),
            exit_code,
        )
        raise typer.Exit(code=code) from e
