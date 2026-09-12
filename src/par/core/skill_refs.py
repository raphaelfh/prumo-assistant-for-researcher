"""Reescrita de invocações de skills antigas (spec 2026-09-12, D6).

Só o TOKEN de invocação muda — ``par:<antigo>`` vira
``par:<skill> <modo>``. Valor sem o prefixo (``generator: wiki-query``)
é dado de proveniência e fica como está (Princípio IV). O acervo gerado em
``docs/references/papers/`` também fica: é saída de máquina, não instrução.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from par.core.skills import SkillRef

__all__ = [
    "RefChange",
    "legacy_installed_dirs",
    "migrate_skill_names",
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
    return re.compile(rf"(?<![\w-])par:({alternation})(?![\w-])")


def rewrite_invocations(text: str, legacy: Mapping[str, SkillRef]) -> tuple[str, int]:
    """Troca cada ``par:<antigo>`` pela invocação nova. Devolve (texto, trocas)."""
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


def legacy_installed_dirs(pj_root: Path, legacy: Mapping[str, SkillRef]) -> list[str]:
    """``.claude/skills/<antigo>/`` que sobraram de um ``prumo init`` anterior.

    Não são apagados: podem ter sido customizados (a skill de estilo sugeria
    copiar-se para lá). O ``doctor`` aponta; a pessoa decide.
    """
    root = pj_root / ".claude" / "skills"
    if not root.is_dir():
        return []
    return [
        f".claude/skills/{d.name}"
        for d in sorted(root.iterdir())
        if d.is_dir() and d.name in legacy
    ]
