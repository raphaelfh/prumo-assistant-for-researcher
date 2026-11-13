"""Geração e parsing de ADRs ``adr-NNNN-question-v<N>-<slug>.md``.

ADRs ``adr-NNNN-picot-v<N>-*`` (formato anterior, ADR-0041) continuam lidos.

ADRs são append-only event logs. Cada um inclui:

- diff humano-legível dos campos que mudaram
- motivação (perguntada na skill)
- snapshot completo do TOML em bloco delimitado, pra `diff` futuro
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import tomli_w

from par.core import pj_layout
from par.domains.protocol.diff import QuestionDiff
from par.domains.protocol.question_io import spec_to_toml_payload
from par.domains.protocol.schemas.v1 import (
    PicotSpec,
    QuestionSpec,
    question_from_picot,
)

SNAPSHOT_BEGIN = "<!-- question-snapshot:begin -->"
SNAPSHOT_END = "<!-- question-snapshot:end -->"
_SNAPSHOT_RE = re.compile(
    r"<!--\s*(?:question|picot)-snapshot:begin\s*-->\s*```toml\s*(?P<toml>.+?)```\s*"
    r"<!--\s*(?:question|picot)-snapshot:end\s*-->",
    flags=re.DOTALL,
)

_ADR_FILE_RE = re.compile(r"^adr-(\d{4})-")
_QUESTION_ADR_RE = re.compile(r"^adr-\d{4}-(?:question|picot)-v\d+")


def next_number(scope: Path) -> int:
    """Próximo número livre em ``<escopo>/decisions/`` (numeração é por escopo)."""
    decisions = pj_layout.decisions_dir(scope)
    if not decisions.exists():
        return 1
    used: list[int] = []
    for child in decisions.iterdir():
        if not child.is_file():
            continue
        m = _ADR_FILE_RE.match(child.name)
        if m:
            used.append(int(m.group(1)))
    return (max(used) + 1) if used else 1


def find_last_question_adr(scope: Path) -> Path | None:
    """Acha o ADR question-v<N> (ou picot-v<N>) mais recente (maior número) no escopo, ou ``None``."""
    decisions = pj_layout.decisions_dir(scope)
    if not decisions.exists():
        return None
    candidates = [c for c in decisions.iterdir() if c.is_file() and _QUESTION_ADR_RE.match(c.name)]
    if not candidates:
        return None
    candidates.sort(key=lambda p: int(_ADR_FILE_RE.match(p.name).group(1)))  # type: ignore[union-attr]
    return candidates[-1]


def compose_adr(
    *,
    adr_number: int,
    spec: QuestionSpec,
    diff: QuestionDiff,
    motivation: str,
    supersedes_path: Path | None,
    date: str,
) -> str:
    """Renderiza o conteúdo Markdown completo de um ADR ``question-v<N>``."""
    supersedes_field = supersedes_path.stem if supersedes_path else "—"
    slug = _slugify_motivation(motivation)
    title = f"ADR-{adr_number:04d}: Pergunta do estudo v{spec.version} — {slug}"

    lines: list[str] = []
    lines.append("---")
    lines.append(f"adr: {adr_number:04d}")
    lines.append(f"title: Pergunta do estudo v{spec.version} — {slug}")
    lines.append(f"date: {date}")
    lines.append(f"supersedes: {supersedes_field}")
    lines.append("status: accepted")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    lines.append("## Mudanças")
    lines.append("")
    if diff.changes:
        for change in diff.changes:
            lines.append(f"- **`{change.field}`**:")
            lines.append(f"  - antes: {_fmt(change.before)}")
            lines.append(f"  - agora: {_fmt(change.after)}")
    else:
        lines.append("_(versão inicial — nenhuma mudança a comparar)_")
    lines.append("")
    lines.append("## Motivação")
    lines.append("")
    lines.append(motivation.strip() or "_(não informado)_")
    lines.append("")
    lines.append(f"## Snapshot do QuestionSpec/v1 (versão {spec.version})")
    lines.append("")
    lines.append(SNAPSHOT_BEGIN)
    lines.append("```toml")
    lines.append(tomli_w.dumps(spec_to_toml_payload(spec)).rstrip())
    lines.append("```")
    lines.append(SNAPSHOT_END)
    lines.append("")
    return "\n".join(lines)


def extract_snapshot(adr_text: str) -> str | None:
    """Extrai o TOML do bloco ``question-snapshot`` (ou ``picot-snapshot``). ``None`` se ausente."""
    m = _SNAPSHOT_RE.search(adr_text)
    if not m:
        return None
    return m.group("toml").strip()


def parse_snapshot(toml_text: str) -> QuestionSpec:
    """Snapshot TOML → ``QuestionSpec``; snapshot ``[picot]`` antigo é convertido."""
    parsed = tomllib.loads(toml_text)
    if "question" in parsed:
        return QuestionSpec.model_validate(parsed["question"])
    return question_from_picot(PicotSpec.model_validate(parsed["picot"]))


def _slugify_motivation(motivation: str) -> str:
    """Slug curto kebab-case (≤ 30 chars) pra title de ADR."""
    text = motivation.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if not text:
        return "atualizacao"
    return text[:30].rstrip("-") or "atualizacao"


def _fmt(value: object) -> str:
    """Formata valores diff-friendly (strings com aspas, listas inline)."""
    if value is None:
        return "_null_"
    if isinstance(value, list):
        return "[" + ", ".join(repr(x) for x in value) + "]"
    return repr(value)
