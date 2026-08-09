"""Autoridade única de caminho do layout de um ``pj_*``.

Dois conceitos que o código antigo fundia num resolvedor só:

- **projeto** (:func:`find_pj_root`) — marcado por ``.claude/pj_config.toml``.
  Guarda a bibliografia (``docs/references/``), ``build/exports/`` e ``reviews/``.
- **escopo** (:func:`find_scope_root`) — uma unidade de escrita, resolvida por
  POSIÇÃO: todo filho direto de ``docs/studies/`` é um escopo. Não há arquivo
  sentinela — nada a criar, nada a perder num ``git mv``.

A bibliografia é do PROJETO (uma só, um ``.bib``, um autoexport); ``notes/``,
``writing/`` e ``decisions/`` são do ESCOPO. Ver ADR-0022 e ADR-0024.
"""

from __future__ import annotations

from pathlib import Path

from prumo_assist import PrumoError

PJ_CONFIG_RELPATH = Path(".claude") / "pj_config.toml"
REFERENCES_RELPATH = Path("docs") / "references"
STUDIES_RELPATH = Path("docs") / "studies"

SCOPE_DIRS = ("notes", "writing", "decisions")


class PjRootNotFoundError(PrumoError):
    """Nem o projeto nem o escopo foram localizados a partir do caminho dado."""


class LegacyLayoutError(PrumoError):
    """Projeto ainda no layout com ``references/`` na raiz."""


def _as_dir(path: Path) -> Path:
    """Normaliza para diretório: arquivo devolve o pai."""
    resolved = path.resolve()
    return resolved.parent if resolved.is_file() else resolved


def find_pj_root(start: Path) -> Path:
    """Sobe de ``start`` até o diretório com ``.claude/pj_config.toml``."""
    cur = _as_dir(start)
    for candidate in (cur, *cur.parents):
        if (candidate / PJ_CONFIG_RELPATH).is_file():
            return candidate
    raise PjRootNotFoundError(
        f"Raiz de projeto não encontrada a partir de {start} "
        f"(esperado {PJ_CONFIG_RELPATH.as_posix()}). Rode `prumo init` ou aponte o "
        "projeto com `--path <raiz>`."
    )


def find_scope_root(start: Path) -> Path:
    """Devolve o filho direto de ``docs/studies/`` que contém ``start``."""
    pj_root = find_pj_root(start)
    studies = (pj_root / STUDIES_RELPATH).resolve()
    cur = _as_dir(start)
    for candidate in (cur, *cur.parents):
        if candidate.parent == studies:
            return candidate
    raise PjRootNotFoundError(
        f"{start} não está dentro de um escopo. Todo texto vive em "
        "`docs/studies/<slug>/`. Crie um com `prumo add study <slug>`."
    )


def iter_scopes(pj_root: Path) -> list[Path]:
    """Lista os escopos do projeto, em ordem alfabética."""
    studies = pj_root / STUDIES_RELPATH
    if not studies.is_dir():
        return []
    return sorted(p for p in studies.iterdir() if p.is_dir())


def references_dir(pj_root: Path) -> Path:
    """``<pj>/docs/references/`` — a bibliografia é do PROJETO."""
    return pj_root / REFERENCES_RELPATH


def bib_path(pj_root: Path) -> Path:
    """``<pj>/docs/references/_references.bib``."""
    return references_dir(pj_root) / "_references.bib"


def papers_dir(pj_root: Path) -> Path:
    """``<pj>/docs/references/papers/`` — uma pasta por paper (layout α, ADR-0008)."""
    return references_dir(pj_root) / "papers"


def paper_dir(pj_root: Path, citekey: str) -> Path:
    """``<pj>/docs/references/papers/<citekey>/``."""
    return papers_dir(pj_root) / citekey


def pdfs_dir(pj_root: Path) -> Path:
    """``<pj>/docs/references/pdfs/`` — symlinks pro storage do gerenciador."""
    return references_dir(pj_root) / "pdfs"


def note_template_path(pj_root: Path) -> Path:
    """``<pj>/docs/references/_note_template.md`` — modelo de nota de leitura."""
    return references_dir(pj_root) / "_note_template.md"


def notes_dir(scope: Path) -> Path:
    """``<escopo>/notes/`` — prosa humana, inclusive findings (``type: finding``)."""
    return scope / "notes"


def writing_dir(scope: Path) -> Path:
    """``<escopo>/writing/`` — o produto, com ``figures/`` e ``tables/`` ao lado."""
    return scope / "writing"


def decisions_dir(scope: Path) -> Path:
    """``<escopo>/decisions/`` — append-only."""
    return scope / "decisions"


def is_legacy_layout(pj_root: Path) -> bool:
    """True quando ``references/`` está na raiz e ``docs/references/`` não existe."""
    return (pj_root / "references").is_dir() and not references_dir(pj_root).is_dir()


def assert_current_layout(pj_root: Path) -> None:
    """Levanta em layout legado, com o convite à adequação embutido."""
    if is_legacy_layout(pj_root):
        raise LegacyLayoutError(
            f"{pj_root} ainda tem `references/` na raiz. A bibliografia agora vive em "
            "`docs/references/`. Peça a adequação ao agente: `adeque este projeto ao "
            "layout novo do prumo`."
        )
