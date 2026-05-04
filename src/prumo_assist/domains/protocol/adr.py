"""Geração e parsing de ADRs ``adr-NNNN-picot-v<N>-<slug>.md``.

ADRs são append-only event logs. Cada um inclui:

- diff humano-legível dos campos que mudaram
- motivação (perguntada na skill)
- snapshot completo do TOML em bloco delimitado, pra `diff` futuro
"""

from __future__ import annotations

import re
from pathlib import Path

import tomli_w

from prumo_assist.domains.protocol.diff import PicotDiff
from prumo_assist.domains.protocol.picot_io import spec_to_toml_payload
from prumo_assist.domains.protocol.schemas.v1 import PicotSpec

SNAPSHOT_BEGIN = "<!-- picot-snapshot:begin -->"
SNAPSHOT_END = "<!-- picot-snapshot:end -->"

_ADR_FILE_RE = re.compile(r"^adr-(\d{4})-")
_PICOT_ADR_RE = re.compile(r"^adr-\d{4}-picot-v\d+")


def next_adr_number(pj_path: Path) -> int:
    """Próximo número livre em ``docs/decisions/``."""
    decisions = pj_path / "docs" / "decisions"
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


def find_last_picot_adr(pj_path: Path) -> Path | None:
    """Acha o ADR picot-v<N> mais recente (maior número), ou ``None``."""
    decisions = pj_path / "docs" / "decisions"
    if not decisions.exists():
        return None
    candidates = [c for c in decisions.iterdir() if c.is_file() and _PICOT_ADR_RE.match(c.name)]
    if not candidates:
        return None
    candidates.sort(key=lambda p: int(_ADR_FILE_RE.match(p.name).group(1)))  # type: ignore[union-attr]
    return candidates[-1]


def compose_adr(
    *,
    adr_number: int,
    spec: PicotSpec,
    diff: PicotDiff,
    motivation: str,
    supersedes_path: Path | None,
    date: str,
) -> str:
    """Renderiza o conteúdo Markdown completo de um ADR ``picot-v<N>``."""
    supersedes_field = supersedes_path.stem if supersedes_path else "—"
    slug = _slugify_motivation(motivation)
    title = f"ADR-{adr_number:04d}: PICOT v{spec.version} — {slug}"

    lines: list[str] = []
    lines.append("---")
    lines.append(f"adr: {adr_number:04d}")
    lines.append(f"title: PICOT v{spec.version} — {slug}")
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
    lines.append(f"## Snapshot do PicotSpec/v1 (versão {spec.version})")
    lines.append("")
    lines.append(SNAPSHOT_BEGIN)
    lines.append("```toml")
    lines.append(tomli_w.dumps(spec_to_toml_payload(spec)).rstrip())
    lines.append("```")
    lines.append(SNAPSHOT_END)
    lines.append("")
    return "\n".join(lines)


def extract_picot_snapshot(adr_text: str) -> str | None:
    """Extrai o conteúdo TOML do bloco ``picot-snapshot``. ``None`` se ausente."""
    pattern = re.compile(
        re.escape(SNAPSHOT_BEGIN)
        + r"\s*```toml\s*(?P<toml>.+?)```\s*"
        + re.escape(SNAPSHOT_END),
        flags=re.DOTALL,
    )
    m = pattern.search(adr_text)
    if not m:
        return None
    return m.group("toml").strip()


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
