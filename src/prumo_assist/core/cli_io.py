"""Leitura de stdin para subcomandos que recebem corpo markdown ou payload-schema.

O repo não tinha precedente de payload via stdin; o spec do pipeline (Seção 0.5)
define: corpo markdown vai cru por stdin (heredoc), payload estruturado vai como
JSON por stdin quando já é schema, metadados via flags. O ``stream`` é injetável
para teste (seam) — em produção, ``None`` resolve para ``sys.stdin``.
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from prumo_assist import PrumoError


def read_stdin_text(stream: TextIO | None = None) -> str:
    """Lê o corpo (markdown) de stdin. Vazio é permitido (retorna ``''``)."""
    src = stream if stream is not None else sys.stdin
    return src.read()


def read_stdin_json(stream: TextIO | None = None) -> dict[str, Any]:
    """Lê e parseia um objeto JSON de stdin. ``PrumoError`` acionável se vazio/inválido."""
    raw = read_stdin_text(stream).strip()
    if not raw:
        raise PrumoError(
            "payload JSON ausente no stdin; passe o objeto via pipe "
            "(ex.: echo '{...}' | prumo ...)."
        )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise PrumoError(f"JSON inválido no stdin: {e}") from e
    if not isinstance(data, dict):
        raise PrumoError(
            "payload JSON deve ser um objeto (mapping), não lista ou escalar "
            '(ex.: echo \'{"chave": "valor"}\' | prumo ...).'
        )
    return data


def parse_json_list(raw: str, flag: str) -> list[str]:
    """Parseia uma opção ``--flag`` que carrega um array JSON de strings."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise PrumoError(f"{flag} deve ser um array JSON: {e}") from e
    if not isinstance(data, list):
        raise PrumoError(f"{flag} deve ser um array JSON.")
    return [str(x) for x in data]
