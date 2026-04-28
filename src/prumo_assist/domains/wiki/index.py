"""Wrapper sobre o MCP/CLI ``qmd`` pra (re)indexar o wiki.

Não embute ``qmd`` no pacote — só shell-out. Se ``qmd`` não estiver no PATH,
falha cedo com mensagem clara e link de instalação.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any


class QmdNotFoundError(FileNotFoundError):
    """``qmd`` não encontrado no PATH."""


def reindex(pj_path: Path, *, name: str | None = None) -> dict[str, Any]:
    """Roda ``qmd collection add`` + ``qmd embed`` no diretório do projeto.

    Args:
        pj_path: raiz do ``pj_*``.
        name: nome da collection (default: nome do diretório).

    Returns:
        ``{"ok": True, "name": "...", "stdout": "..."}``
    """
    qmd = shutil.which("qmd")
    if not qmd:
        raise QmdNotFoundError(
            "qmd não está no PATH. Instale conforme docs do projeto "
            "(github.com/raphaelfh/qmd ou similar)."
        )

    collection = name or pj_path.resolve().name
    cmd_add = [qmd, "collection", "add", str(pj_path), "--name", collection]
    cmd_embed = [qmd, "embed"]

    out_lines: list[str] = []
    for cmd, cwd in ((cmd_add, None), (cmd_embed, pj_path)):
        try:
            res = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
            out_lines.append(res.stdout.strip())
        except subprocess.CalledProcessError as e:
            return {
                "ok": False,
                "name": collection,
                "command": " ".join(cmd),
                "stderr": e.stderr,
            }

    return {"ok": True, "name": collection, "stdout": "\n".join(out_lines)}
