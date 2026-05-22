"""Backend compartilhado da família ``write-*``.

Funções:

- ``read_inputs`` — carrega ``ComposeInputs`` lendo ``.claude/picot.toml``,
  ``references/_references.bib``, callouts ``_extract.md``, ``protocol.md``,
  ``project.md``, ``findings/*.md``.
- ``resolve_template`` — chain ``--template`` > ``.claude/writing_templates/`` > skill bundle.
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
from prumo_assist.core.paths import find_resource
from prumo_assist.domains.write.schemas.v1 import (
    ComposeInputs,
    FindingSummary,
    PaperSummary,
    WriteKind,
    WriteMode,
    WriteOutput,
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


_VALID_KINDS = ("paper", "projeto-cep", "statistics", "scientific")


def resolve_template(
    *,
    pj_path: Path,
    kind: WriteKind,
    explicit: Path | None = None,
) -> Path:
    """Resolve template via fallback chain ``explicit > project > plugin``."""
    if kind not in _VALID_KINDS:
        raise ValueError(
            f"kind inválido '{kind}'; esperado um de {list(_VALID_KINDS)}"
        )
    if explicit is not None:
        if not explicit.exists():
            raise FileNotFoundError(f"--template {explicit} não existe.")
        return explicit
    project_override = pj_path / ".claude" / "writing_templates" / f"{kind}.md"
    if project_override.exists():
        return project_override
    skills_root = find_resource("skills")
    if skills_root is not None:
        skill_template = skills_root / f"write-{kind}" / "template.md"
        if skill_template.exists():
            return skill_template
    raise FileNotFoundError(
        f"Nenhum template '{kind}' encontrado. Crie "
        f".claude/writing_templates/{kind}.md ou passe --template."
    )


def compose_path(
    *,
    pj_path: Path,
    kind: WriteKind,
    date: str,
    slug: str,
    into: Path | None = None,
    out: Path | None = None,
) -> Path:
    """Resolve output path por modo. ``into``/``out`` mutuamente exclusivos."""
    if into is not None and out is not None:
        raise ValueError("--into e --out são mutuamente exclusivos.")
    if into is not None:
        return into
    if out is not None:
        return out
    drafts = pj_path / "docs" / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    return drafts / f"{kind}-{date}-{slug}.md"


def write_output(
    *,
    content: str,
    pj_path: Path,
    kind: WriteKind,
    mode: WriteMode,
    date: str,
    slug: str,
    into: Path | None = None,
    out: Path | None = None,
    section: str | None = None,
    force: bool = False,
    sections_filled: list[str] | None = None,
    sections_skipped: list[str] | None = None,
) -> WriteOutput:
    """Escreve ``content`` no destino conforme ``mode`` e retorna ``WriteOutput``."""
    target = compose_path(
        pj_path=pj_path, kind=kind, date=date, slug=slug, into=into, out=out,
    )

    if mode == "into":
        if not target.exists():
            raise FileNotFoundError(f"--into {target} não existe.")
        if section is None:
            raise ValueError("--into requer --section <name>.")
        new_block = (
            f"<!-- write:begin kind={kind} section={section} -->\n"
            f"{content.rstrip()}\n"
            f"<!-- write:end -->"
        )
        existing = target.read_text(encoding="utf-8")
        block_specific_re = re.compile(
            rf"<!--\s*write:begin\s+kind={re.escape(kind)}\s+section={re.escape(section)}\s*-->"
            r".*?<!--\s*write:end\s*-->",
            flags=re.DOTALL,
        )
        if block_specific_re.search(existing):
            updated = block_specific_re.sub(new_block, existing, count=1)
        else:
            updated = existing.rstrip() + "\n\n" + new_block + "\n"
        target.write_text(updated, encoding="utf-8")
    elif mode == "out":
        if target.exists() and not force:
            raise FileExistsError(
                f"{target} já existe. Use force=True pra sobrescrever."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    else:  # drafts
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    return WriteOutput(
        output_path=target,
        mode=mode,
        kind=kind,
        sections_filled=sections_filled or [],
        sections_skipped=sections_skipped or [],
        citations_used=_extract_citekeys_used(content),
        references_missing=extract_missing_refs(content),
        words_generated=len(content.split()),
    )


def extract_missing_refs(text: str) -> list[str]:
    """Captura ``[REF FALTANTE: <descrição>]`` em ``text``."""
    pattern = re.compile(r"\[REF FALTANTE:\s*(?P<desc>[^\]]+)\]")
    return [m.group("desc").strip() for m in pattern.finditer(text)]


def _extract_citekeys_used(text: str) -> list[str]:
    """Captura ``[[@<citekey>]]`` em ``text``; retorna lista única ordenada."""
    pattern = re.compile(r"\[\[@(?P<key>[a-zA-Z0-9._+-]+)(?:\|[^\]]+)?\]\]")
    return sorted({m.group("key") for m in pattern.finditer(text)})
