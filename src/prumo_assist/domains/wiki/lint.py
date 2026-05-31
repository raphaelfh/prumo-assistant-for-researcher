"""Auditoria determinística do wiki em ``docs/``.

Detecta problemas estruturais que LLM não precisa ver:

- Citekeys ``[[@key]]`` referenciados mas ausentes do `.bib`.
- Páginas órfãs (sem links de entrada).
- Frontmatter ausente em páginas tipadas (``concepts/``, ``entities/``, etc.).
- ``_index.md`` ou ``_log.md`` ausentes.

Não detecta "conceitos sem página" — esse é trabalho semântico que vai pra
skill ``wiki-lint`` (modo agêntico via host).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from prumo_assist.core.bib import parse_bib

EXPECTED_DIRS = ("concepts", "entities", "findings", "sources", "decisions")
WIKILINK_RE = re.compile(r"\[\[@([A-Za-z0-9_-]+)\]\]")
PAGE_LINK_RE = re.compile(r"\[\[([^\]@\|]+)(?:\|[^\]]+)?\]\]")
LOG_PREFIX_RE = re.compile(
    r"^## \[\d{4}-\d{2}-\d{2}\] (ingest|query|lint|decision|milestone|note) \| .+$"
)


@dataclass(frozen=True)
class WikiIssue:
    severity: str  # "error" | "warning"
    code: str
    message: str
    page: str | None = None


def lint(pj_path: Path) -> dict[str, Any]:
    """Roda checks do wiki. Retorna ``{"ok": bool, "issues": [...], "summary": ...}``."""
    issues: list[WikiIssue] = []
    docs = pj_path / "docs"

    if not docs.is_dir():
        issues.append(WikiIssue("error", "docs_missing", f"{docs} não existe"))
        return _report(issues)

    if not (docs / "_index.md").is_file():
        issues.append(WikiIssue("warning", "no_index", "docs/_index.md ausente"))
    if not (docs / "_log.md").is_file():
        issues.append(WikiIssue("warning", "no_log", "docs/_log.md ausente"))

    bib_path = pj_path / "references" / "_references.bib"
    bib_keys: set[str] = set()
    if bib_path.is_file():
        bib_keys = {e.citekey for e in parse_bib(bib_path.read_text())}

    pages: list[Path] = sorted(docs.rglob("*.md"))
    page_stems = {p.stem for p in pages}

    for page in pages:
        text = page.read_text()
        rel = page.relative_to(pj_path).as_posix()

        # Frontmatter check em páginas tipadas
        parts = page.relative_to(docs).parts
        if parts and parts[0] in EXPECTED_DIRS and not text.startswith("---"):
            issues.append(WikiIssue("warning", "no_frontmatter", "sem frontmatter", page=rel))

        # Citekeys quebrados
        for ck in WIKILINK_RE.findall(text):
            if bib_keys and ck not in bib_keys:
                issues.append(
                    WikiIssue(
                        "warning",
                        "broken_citekey",
                        f"[[@{ck}]] não existe no .bib",
                        page=rel,
                    )
                )

    # Páginas órfãs (não linkadas de nada)
    incoming: dict[str, int] = dict.fromkeys(page_stems, 0)
    for page in pages:
        text = page.read_text()
        for m in PAGE_LINK_RE.findall(text):
            target = m if isinstance(m, str) else m[0]
            target = target.strip().split("#")[0]
            if target in incoming:
                incoming[target] += 1

    for stem, count in sorted(incoming.items()):
        if count == 0 and not stem.startswith("_") and stem not in {"README", "protocol"}:
            issues.append(
                WikiIssue("warning", "orphan_page", "página sem links de entrada", page=stem)
            )

    issues.extend(_check_log_prefixes(docs))
    issues.extend(_check_single_primary(pj_path))
    issues.extend(_check_dead_frontmatter_links(pages, pj_path, page_stems, bib_keys))
    issues.extend(_check_concept_candidates(pages, page_stems))

    return _report(issues)


def _report(issues: list[WikiIssue]) -> dict[str, Any]:
    errors = sum(1 for i in issues if i.severity == "error")
    warnings = sum(1 for i in issues if i.severity == "warning")
    return {
        "ok": errors == 0,
        "summary": {"errors": errors, "warnings": warnings, "total": len(issues)},
        "issues": [asdict(i) for i in issues],
    }


_ROLE_PRIMARY_RE = re.compile(r"^role:\s*primary\s*$", re.MULTILINE)


def _check_single_primary(pj_path: Path) -> list[WikiIssue]:
    """``role: primary`` deve aparecer em no máximo 1 nota de ``references/notes/``."""
    notes_dir = pj_path / "references" / "notes"
    if not notes_dir.is_dir():
        return []
    primaries = [
        meta.parent.name
        for meta in sorted(notes_dir.rglob("_meta.md"))
        if _ROLE_PRIMARY_RE.search(meta.read_text(encoding="utf-8"))
    ]
    if len(primaries) >= 2:
        return [
            WikiIssue(
                "warning",
                "multiple_primary",
                f"{len(primaries)} notas com role: primary ({', '.join(primaries)}); esperado ≤ 1",
            )
        ]
    return []


def _check_log_prefixes(docs: Path) -> list[WikiIssue]:
    """Cada ``## `` em ``_log.md`` deve casar ``[YYYY-MM-DD] <verbo> | <texto>``."""
    log = docs / "_log.md"
    if not log.is_file():
        return []
    issues: list[WikiIssue] = []
    for line in log.read_text(encoding="utf-8").splitlines():
        if line.startswith("## ") and not LOG_PREFIX_RE.match(line):
            issues.append(
                WikiIssue("warning", "broken_log_prefix", f"entrada de log fora do padrão: {line!r}")
            )
    return issues


_FM_LINK_FIELDS = ("links_to", "sources", "related")
_WIKILINK_TARGET_RE = re.compile(r"\[\[(@?[^\]|#]+)")


def _check_dead_frontmatter_links(
    pages: list[Path],
    pj_path: Path,
    page_stems: set[str],
    bib_keys: set[str],
) -> list[WikiIssue]:
    """Wikilinks em ``links_to``/``sources``/``related`` cujo alvo não existe."""
    issues: list[WikiIssue] = []
    for page in pages:
        text = page.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            fm = yaml.safe_load(parts[1])
        except yaml.YAMLError:
            continue
        if not isinstance(fm, dict):
            continue
        rel = page.relative_to(pj_path).as_posix()
        for field in _FM_LINK_FIELDS:
            value = fm.get(field)
            if not isinstance(value, list):
                continue
            for raw in value:
                m = _WIKILINK_TARGET_RE.search(str(raw))
                if not m:
                    continue
                target = m.group(1).strip()
                if target.startswith("@"):
                    key = target[1:]
                    if bib_keys and key not in bib_keys:
                        issues.append(
                            WikiIssue("warning", "dead_link", f"{field}: [[@{key}]] ausente do .bib", page=rel)
                        )
                elif target not in page_stems:
                    issues.append(
                        WikiIssue("warning", "dead_link", f"{field}: [[{target}]] não existe no vault", page=rel)
                    )
    return issues


_CONCEPT_CANDIDATE_MIN = 3


def _check_concept_candidates(pages: list[Path], page_stems: set[str]) -> list[WikiIssue]:
    """Wikilink ``[[termo]]`` citado ≥3× sem página correspondente → candidato a concept."""
    counts: dict[str, int] = {}
    for page in pages:
        text = page.read_text(encoding="utf-8")
        for target in PAGE_LINK_RE.findall(text):
            name = (target if isinstance(target, str) else target[0]).strip().split("#")[0]
            if name and name not in page_stems:
                counts[name] = counts.get(name, 0) + 1
    issues: list[WikiIssue] = []
    for name, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if count >= _CONCEPT_CANDIDATE_MIN:
            issues.append(
                WikiIssue("info", "concept_candidate", f"'{name}' citado {count}× sem página (candidato a /wiki-ingest)")
            )
    return issues
