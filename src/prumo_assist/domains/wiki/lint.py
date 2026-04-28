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

from prumo_assist.core.bib import parse_bib

EXPECTED_DIRS = ("concepts", "entities", "findings", "sources", "decisions")
WIKILINK_RE = re.compile(r"\[\[@([A-Za-z0-9_-]+)\]\]")
PAGE_LINK_RE = re.compile(r"\[\[([^\]@\|]+)(?:\|[^\]]+)?\]\]")


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

    return _report(issues)


def _report(issues: list[WikiIssue]) -> dict[str, Any]:
    errors = sum(1 for i in issues if i.severity == "error")
    warnings = sum(1 for i in issues if i.severity == "warning")
    return {
        "ok": errors == 0,
        "summary": {"errors": errors, "warnings": warnings, "total": len(issues)},
        "issues": [asdict(i) for i in issues],
    }
