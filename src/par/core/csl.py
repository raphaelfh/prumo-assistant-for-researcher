"""Resolução de estilos CSL (Citation Style Language) a partir de ``~/Zotero/styles/``.

Transformado de ``monorepo-anterior/.claude/scripts/_csl.py``. A única mudança
substantiva é que ``CslNotFoundError`` agora herda de ``ConfigError`` (faz parte
da hierarquia ``PrumoError``) em vez de ``FileNotFoundError`` puro.
"""

from __future__ import annotations

from pathlib import Path

from par import ConfigError

ZOTERO_STYLES_DIR = Path.home() / "Zotero" / "styles"


class CslNotFoundError(ConfigError):
    """Estilo CSL não encontrado em ``~/Zotero/styles/``."""


def list_zotero_styles(styles_dir: Path | None = None) -> list[str]:
    """Retorna lista ordenada de basenames (sem ``.csl``) em ``styles_dir``.

    Args:
        styles_dir: override pra testes; default ``~/Zotero/styles/``.
    """
    base = styles_dir or ZOTERO_STYLES_DIR
    if not base.is_dir():
        return []
    return sorted(p.stem for p in base.glob("*.csl"))


def resolve_csl(style: str, styles_dir: Path | None = None) -> Path:
    """Resolve nome de estilo (com ou sem ``.csl``) para caminho absoluto.

    Raises:
        CslNotFoundError: estilo não existe; mensagem inclui listagem.
    """
    base = styles_dir or ZOTERO_STYLES_DIR
    name = style.removesuffix(".csl")
    candidate = base / f"{name}.csl"
    if candidate.is_file():
        return candidate
    available = list_zotero_styles(base)
    listing = ", ".join(available) if available else "(nenhum)"
    raise CslNotFoundError(
        f"Estilo CSL '{style}' não encontrado em {base}.\n"
        f"Disponíveis: {listing}\n"
        f"Para instalar: Zotero → Settings → Cite → Styles → Get additional styles."
    )
