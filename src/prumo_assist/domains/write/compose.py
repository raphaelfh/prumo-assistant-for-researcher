"""Backend compartilhado da família ``write-*``.

Funções:

- ``read_inputs`` — carrega ``ComposeInputs`` lendo ``.claude/picot.toml``,
  ``references/_references.bib``, callouts ``_extract.md``, ``protocol.md``,
  ``project.md``, ``findings/*.md``.
- ``resolve_template`` — chain ``--template`` > ``.claude/writing_templates/`` > plugin default.
- ``compose_path`` — resolve output path por modo (drafts/into/out).
- ``write_output`` — escreve conteúdo no destino + retorna ``WriteOutput``.
- ``extract_missing_refs`` — varre texto pra ``[REF FALTANTE: ...]``.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from prumo_assist.core.bib import extract_field, parse_bib
from prumo_assist.core.note_paths import extract_path
from prumo_assist.domains.write.schemas.v1 import (
    ComposeInputs,
    FindingSummary,
    PaperSummary,
)


def read_inputs(pj_path: Path) -> ComposeInputs:
    """Carrega ``ComposeInputs`` lendo ``pj_path``. Cada parte é graceful (None/empty)."""
    return ComposeInputs(
        picot=_read_picot(pj_path),
        citekeys=_read_citekeys(pj_path),
        papers=_read_papers(pj_path),
        protocol=_read_text(pj_path / "docs" / "protocol.md"),
        project=_read_text(pj_path / "docs" / "project.md"),
        findings=_read_findings(pj_path),
    )


def _read_picot(pj_path: Path):  # type: ignore[no-untyped-def]
    """Tenta carregar PicotSpec; ``None`` se ausente ou inválido."""
    try:
        from prumo_assist.domains.protocol.picot_io import read_picot
    except ImportError:
        return None
    try:
        return read_picot(pj_path)
    except (FileNotFoundError, ValueError):
        return None


def _read_citekeys(pj_path: Path) -> list[str]:
    bib = pj_path / "references" / "_references.bib"
    if not bib.exists():
        return []
    return [e.citekey for e in parse_bib(bib.read_text(encoding="utf-8"))]


def _read_papers(pj_path: Path) -> dict[str, PaperSummary]:
    """Combina ``.bib`` (metadata) + ``_extract.md`` (callout body) por citekey."""
    bib = pj_path / "references" / "_references.bib"
    if not bib.exists():
        return {}
    out: dict[str, PaperSummary] = {}
    for entry in parse_bib(bib.read_text(encoding="utf-8")):
        title = (extract_field(entry.body, "title") or "").strip()
        year_raw = (extract_field(entry.body, "year") or "").strip()
        year = int(year_raw) if year_raw.isdigit() else None
        authors = (extract_field(entry.body, "author") or "").strip()
        extract_content = _read_text(extract_path(pj_path, entry.citekey))
        out[entry.citekey] = PaperSummary(
            citekey=entry.citekey,
            title=title,
            year=year,
            authors=authors,
            extract_content=extract_content,
        )
    return out


def _read_findings(pj_path: Path) -> list[FindingSummary]:
    """Tenta ``docs/wiki/findings/`` primeiro, fallback ``docs/findings/``."""
    candidates = [
        pj_path / "docs" / "wiki" / "findings",
        pj_path / "docs" / "findings",
    ]
    findings_dir = next((c for c in candidates if c.exists()), None)
    if findings_dir is None:
        return []
    out: list[FindingSummary] = []
    for md in sorted(findings_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        title = _extract_yaml_field(text, "title") or md.stem
        body = _strip_frontmatter(text)
        out.append(FindingSummary(path=md, title=title, body=body))
    return out


def _read_text(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def _extract_yaml_field(text: str, key: str) -> str | None:
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return None
    parsed = yaml.safe_load(m.group(1)) or {}
    if isinstance(parsed, dict):
        v = parsed.get(key)
        return str(v) if v is not None else None
    return None


def _strip_frontmatter(text: str) -> str:
    return re.sub(r"\A---\n.*?\n---\n+", "", text, count=1, flags=re.DOTALL).strip()
