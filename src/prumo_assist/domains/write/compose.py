"""Backend compartilhado da família ``write-*``.

Funções:

- ``read_inputs`` — carrega ``ComposeInputs`` lendo ``.claude/picot.toml``,
  ``references/_references.bib``, callouts ``_extract.md``, ``protocol.md``,
  ``project_guide.md``, ``findings/*.md``.
- ``resolve_template`` — chain ``--template`` > ``.claude/writing_templates/`` > skill bundle.
- ``resolve_language`` — cascata de idioma (ADR-0021): trava de gênero > flag >
  ``[writing].language`` > default.
- ``compose_path`` — resolve output path por modo (drafts/into/out).
- ``write_output`` — escreve conteúdo no destino + retorna ``WriteOutput``.
- ``extract_missing_refs`` — varre texto pra ``[REF FALTANTE: ...]``.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

import yaml

from prumo_assist.core.bib import extract_field, extract_year, parse_bib
from prumo_assist.core.citations import scan_citekeys
from prumo_assist.core.note_paths import extract_path
from prumo_assist.core.paths import find_resource
from prumo_assist.domains.write.errors import WriteError
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
        project=_read_text(pj_path / "docs" / "project_guide.md"),
        findings=_read_findings(pj_path),
    )


@dataclass(frozen=True)
class WritePrep:
    """Contexto de escrita: inputs compostos + template e idioma resolvidos."""

    inputs: ComposeInputs
    template_path: Path
    language: str
    language_source: str


def locale_lock(kind: WriteKind) -> str | None:
    """Trava de idioma declarada por ``skills/write-<kind>/SKILL.md``, se houver.

    Fonte única é o manifesto — o mesmo diretório de onde sai o template. Um mapa
    ``kind -> locale`` aqui seria a segunda fonte, que é exatamente como o
    ponteiro de template divergiu antes (ver ``template_candidates``).
    ``None`` quando o bundle de skills não está resolvível (é opcional) ou quando
    a skill não declara trava.
    """
    from prumo_assist.core.skills import parse_skill_file

    skills_root = find_resource("skills")
    if skills_root is None:
        return None
    manifest_path = skills_root / f"write-{kind}" / "SKILL.md"
    if not manifest_path.is_file():
        return None
    return parse_skill_file(manifest_path).locale_lock


def resolve_language(pj_path: Path, *, kind: WriteKind, lang: str | None = None) -> tuple[str, str]:
    """Resolve o idioma de escrita (ADR-0021) e a regra que o resolveu.

    Cascata determinística: trava de gênero > pedido explícito > ``[writing].language``
    do ``pj_config.toml`` > default. Os dois últimos degraus saem de
    ``load_project_config``, que valida o vocabulário — é por isto que um
    ``[writing] language`` inválido passa a estourar no caminho de escrita, e não
    só no de extração. A detecção do idioma do texto alvo continua com a skill:
    depende de ler prosa, não de consultar índice.

    Raises:
        WriteError: se ``lang`` explícito estiver fora de ``WRITING_LANGUAGES``.
        ConfigError: se ``[writing].language`` do projeto for inválido.
    """
    from prumo_assist.core.config import WRITING_LANGUAGES, load_project_config

    locked = locale_lock(kind)
    if locked is not None:
        return locked, "locale_lock"
    if lang is not None:
        if lang not in WRITING_LANGUAGES:
            raise WriteError(f"--lang '{lang}' inválido; use um de {sorted(WRITING_LANGUAGES)}.")
        return lang, "flag"
    language = str(load_project_config(pj_path)["writing"]["language"])
    return language, ("pj_config" if _declares_writing_language(pj_path) else "default")


def _declares_writing_language(pj_path: Path) -> bool:
    """``True`` se o projeto declara ``[writing].language`` explicitamente.

    Separa "veio do projeto" de "veio do default" no ``language_source`` — a
    distinção que a skill precisa para avisar o usuário quando o idioma foi
    escolhido por omissão. ``load_project_config`` já mesclou os defaults e não
    sabe mais responder isso.
    """
    cfg_path = pj_path / ".claude" / "pj_config.toml"
    if not cfg_path.exists():
        return False
    with cfg_path.open("rb") as f:
        raw = tomllib.load(f)
    writing = raw.get("writing")
    return isinstance(writing, dict) and "language" in writing


def prep(pj_path: Path, *, kind: WriteKind, lang: str | None = None) -> WritePrep:
    """Compõe ``read_inputs`` + ``resolve_template`` + idioma num só passo de contexto."""
    language, language_source = resolve_language(pj_path, kind=kind, lang=lang)
    return WritePrep(
        inputs=read_inputs(pj_path),
        template_path=resolve_template(pj_path=pj_path, kind=kind),
        language=language,
        language_source=language_source,
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
        year_raw = extract_year(entry.body)
        year = int(year_raw) if year_raw else None
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


def template_candidates(*, pj_path: Path, kind: WriteKind) -> dict[str, Path | None]:
    """Candidatos a template de ``kind``, na ordem da chain (override > plugin).

    Fonte única dos caminhos: ``resolve_template`` escolhe o primeiro que existe e
    ``write list-templates`` reporta os dois. Sem isto, o relatório do CLI diverge
    da resolução real — foi o que aconteceu quando os templates migraram para
    ``skills/write-<kind>/template.md``.
    """
    skills_root = find_resource("skills")
    return {
        "project_override": pj_path / ".claude" / "writing_templates" / f"{kind}.md",
        "plugin_default": (skills_root / f"write-{kind}" / "template.md" if skills_root else None),
    }


def resolve_template(
    *,
    pj_path: Path,
    kind: WriteKind,
    explicit: Path | None = None,
) -> Path:
    """Resolve template via fallback chain ``explicit > project > plugin``."""
    if kind not in _VALID_KINDS:
        raise ValueError(f"kind inválido '{kind}'; esperado um de {list(_VALID_KINDS)}")
    if explicit is not None:
        if not explicit.exists():
            raise FileNotFoundError(f"--template {explicit} não existe.")
        return explicit
    for candidate in template_candidates(pj_path=pj_path, kind=kind).values():
        if candidate is not None and candidate.exists():
            return candidate
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
        pj_path=pj_path,
        kind=kind,
        date=date,
        slug=slug,
        into=into,
        out=out,
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
            raise FileExistsError(f"{target} já existe. Use force=True pra sobrescrever.")
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
        citations_used=scan_citekeys(content),
        references_missing=extract_missing_refs(content),
        words_generated=len(content.split()),
    )


def extract_missing_refs(text: str) -> list[str]:
    """Captura ``[REF FALTANTE: <descrição>]`` em ``text``."""
    pattern = re.compile(r"\[REF FALTANTE:\s*(?P<desc>[^\]]+)\]")
    return [m.group("desc").strip() for m in pattern.finditer(text)]
