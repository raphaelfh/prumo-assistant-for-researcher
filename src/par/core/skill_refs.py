"""Reescrita de invocações de skills antigas (spec 2026-09-12, D6).

Só o TOKEN de invocação muda — ``par:<antigo>`` ou ``prumo-assist:<antigo>``
(projeto anterior à ADR-0034) vira ``par:<skill> <modo>``. Valor sem o prefixo (``generator: wiki-query``)
é dado de proveniência e fica como está (Princípio IV). O acervo gerado em
``docs/references/papers/`` também fica: é saída de máquina, não instrução.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from par.core.skills import SkillRef

__all__ = [
    "RefChange",
    "backup_plugin_copies",
    "exclude_paths",
    "migrate_skill_names",
    "move_plugin_copies",
    "plugin_copies",
    "rewrite_invocations",
    "scan_skill_refs",
]

_SUFFIXES = frozenset({".md", ".toml"})
_SKIP_DIRS = frozenset({".git", ".venv", ".prumo", "node_modules", "graphify-out", "_build"})
_SKIP_PREFIX = "docs/references/papers/"


@dataclass(frozen=True)
class RefChange:
    """Um arquivo do ``pj_*`` com ``count`` invocações antigas."""

    path: str
    count: int


def _pattern(legacy: Mapping[str, SkillRef]) -> re.Pattern[str] | None:
    if not legacy:
        return None
    # Mais longo primeiro: ``paper-extract-all`` não pode casar como ``paper-extract``.
    names = sorted(legacy, key=len, reverse=True)
    alternation = "|".join(re.escape(n) for n in names)
    return re.compile(rf"(?<![\w-])(?:prumo-assist|par):({alternation})(?![\w-])")


def rewrite_invocations(text: str, legacy: Mapping[str, SkillRef]) -> tuple[str, int]:
    """Troca cada ``par:<antigo>``/``prumo-assist:<antigo>`` pela invocação nova. Devolve (texto, trocas)."""
    pattern = _pattern(legacy)
    if pattern is None:
        return text, 0
    return pattern.subn(lambda m: legacy[m.group(1)].invocation, text)


def _candidates(pj_root: Path) -> list[Path]:
    out: list[Path] = []
    for path in sorted(pj_root.rglob("*")):
        if path.suffix not in _SUFFIXES or not path.is_file():
            continue
        rel = path.relative_to(pj_root)
        if _SKIP_DIRS & set(rel.parts) or rel.as_posix().startswith(_SKIP_PREFIX):
            continue
        out.append(path)
    return out


def _walk(pj_root: Path, legacy: Mapping[str, SkillRef], *, write: bool) -> list[RefChange]:
    changes: list[RefChange] = []
    if not legacy:
        return changes
    for path in _candidates(pj_root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        new, count = rewrite_invocations(text, legacy)
        if not count:
            continue
        if write:
            path.write_text(new, encoding="utf-8")
        changes.append(RefChange(path.relative_to(pj_root).as_posix(), count))
    return changes


def scan_skill_refs(pj_root: Path, legacy: Mapping[str, SkillRef]) -> list[RefChange]:
    """Arquivos com invocação antiga, sem escrever nada (``--dry-run`` e ``doctor``)."""
    return _walk(pj_root, legacy, write=False)


def migrate_skill_names(pj_root: Path, legacy: Mapping[str, SkillRef]) -> list[RefChange]:
    """Reescreve as invocações antigas do projeto. Idempotente."""
    return _walk(pj_root, legacy, write=True)


def _owned_dir(pj_root: Path, d: Path) -> bool:
    """``d`` é diretório real do pj: nem ele nem ``.claude`` são link, e resolve dentro do pj."""
    claude = pj_root / ".claude"
    if claude.is_symlink() or d.is_symlink() or not d.is_dir():
        return False
    return d.resolve().is_relative_to(pj_root.resolve())


def plugin_copies(
    pj_root: Path, skill_names: Iterable[str], agent_files: Iterable[str]
) -> list[str]:
    """Cópias de skills/agents do PAR deixadas no ``pj_*`` por um ``prumo init`` antigo (A11).

    Devolve caminhos POSIX relativos ao pj: primeiro ``.claude/skills/<n>`` (diretório,
    inclusive link para diretório, com ``n`` em ``skill_names``), depois
    ``.claude/agents/<f>`` (arquivo com ``f`` em ``agent_files``); cada grupo em ordem
    alfabética. Nomes fora dessas listas nunca entram. Só lista: nada é movido nem apagado.

    ``.claude``, ``.claude/skills`` ou ``.claude/agents`` que seja link (ou resolva fora
    do pj) não é do pj: o conteúdo pertence a outra árvore e nunca é listado — senão o
    ``prumo update`` arrancaria diretórios de fora do projeto.
    """
    skills = frozenset(skill_names)
    agents = frozenset(agent_files)
    out: list[str] = []
    skills_dir = pj_root / ".claude" / "skills"
    if _owned_dir(pj_root, skills_dir):
        out.extend(
            f".claude/skills/{d.name}"
            for d in sorted(skills_dir.iterdir(), key=lambda p: p.name)
            if d.name in skills and d.is_dir()
        )
    agents_dir = pj_root / ".claude" / "agents"
    if _owned_dir(pj_root, agents_dir):
        out.extend(
            f".claude/agents/{f.name}"
            for f in sorted(agents_dir.iterdir(), key=lambda p: p.name)
            if f.name in agents and f.is_file()
        )
    return out


def move_plugin_copies(pj_root: Path, rels: Sequence[str], dest: Path) -> list[str]:
    """Move as cópias listadas por :func:`plugin_copies` para ``dest/{skills,agents}/``.

    Nada é apagado: cada cópia vai inteira para o backup (``.prumo/legacy-copies/...``),
    e nomes fora de ``rels`` nunca são tocados. Depois do move, ``.claude/skills`` e
    ``.claude/agents`` saem só se ficarem vazios. Com ``rels`` vazio, ``dest`` não é criado.
    """
    for rel in rels:
        target = dest / Path(rel).relative_to(".claude")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pj_root / rel), str(target))
    if rels:
        for sub in ("skills", "agents"):
            d = pj_root / ".claude" / sub
            if d.is_dir() and not d.is_symlink() and not any(d.iterdir()):
                d.rmdir()
    return list(rels)


def exclude_paths(changes: Sequence[RefChange], rels: Sequence[str]) -> list[RefChange]:
    """Tira as ``RefChange`` dentro de ``rels`` (cópias do PAR): a cópia é movida, não reescrita."""
    return [
        c for c in changes if not any(c.path == rel or c.path.startswith(rel + "/") for rel in rels)
    ]


def backup_plugin_copies(pj_root: Path, rels: Sequence[str], stamp: str) -> str | None:
    """Move as cópias para ``.prumo/legacy-copies/<stamp>/`` e devolve esse caminho relativo.

    Sem cópias, nada é criado e devolve ``None``.
    """
    if not rels:
        return None
    dest = pj_root / ".prumo" / "legacy-copies" / stamp
    move_plugin_copies(pj_root, rels, dest)
    return dest.relative_to(pj_root).as_posix()
