"""``archive_as_finding`` — cria docs/wiki/findings/<slug>.md (ou fallback).

Extraído da prose inline do ``wiki-query`` SKILL.md pra reuso pela skill
``active-learning``. Pattern: YAML frontmatter (id, type, title, added,
status, tags, sources) + body com seções fixas. Atualiza ``_index.md`` e
``_log.md``.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _resolve_findings_dir(pj_path: Path) -> Path:
    """Prefere ``docs/wiki/findings/`` se ``docs/wiki/`` existe; senão ``docs/findings/``."""
    extended = pj_path / "docs" / "wiki" / "findings"
    if extended.parent.exists():
        extended.mkdir(parents=True, exist_ok=True)
        return extended
    fallback = pj_path / "docs" / "findings"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def archive_as_finding(
    *,
    pj_path: Path,
    slug: str,
    title: str,
    body: str,
    sources: list[str],
    date: str,
    tags: list[str] | None = None,
    generator: str = "wiki-query",
) -> Path:
    """Cria/sobrescreve docs/.../findings/<slug>.md, atualiza _index.md e _log.md.

    ``body`` é texto markdown livre que vai abaixo do frontmatter.
    ``sources`` é lista de wikilinks (strings como ``"[[@key]]"`` ou ``"[[page]]"``).
    ``generator`` identifica quem chamou (``"wiki-query"`` ou ``"active-learning"``).
    """
    if not (pj_path / "docs").exists():
        raise FileNotFoundError(
            f"{pj_path}/docs/ não existe. Rode `prumo init` ou crie manualmente."
        )

    findings_dir = _resolve_findings_dir(pj_path)
    finding_path = findings_dir / f"{slug}.md"

    fm = {
        "id": slug,
        "type": "finding",
        "title": title,
        "added": date,
        "status": "active",
        "tags": tags or [],
        "sources": sources,
    }
    yaml_block = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
    text = f"---\n{yaml_block}\n---\n\n# {title}\n\n{body.strip()}\n"
    finding_path.write_text(text, encoding="utf-8")

    _append_to_index(pj_path, slug, title)
    _append_to_log(pj_path, slug, generator, date)

    return finding_path


def _append_to_index(pj_path: Path, slug: str, title: str) -> None:
    """Adiciona linha ``- [[<slug>]] — <title>`` em § Findings do _index.md."""
    index = pj_path / "docs" / "_index.md"
    if not index.exists():
        index.write_text("# Wiki\n\n## Findings\n\n", encoding="utf-8")

    text = index.read_text(encoding="utf-8")
    line = f"- [[{slug}]] — {title}"
    if line in text:
        return
    if "## Findings" not in text:
        text = text.rstrip() + "\n\n## Findings\n\n"
    text = text.replace("## Findings\n\n", f"## Findings\n\n{line}\n", 1)
    index.write_text(text, encoding="utf-8")


def _append_to_log(pj_path: Path, slug: str, generator: str, date: str) -> None:
    """Anexa entrada ao topo de _log.md."""
    log = pj_path / "docs" / "_log.md"
    if not log.exists():
        log.write_text("# Log\n", encoding="utf-8")

    head = log.read_text(encoding="utf-8")
    entry = (
        f"\n## [{date}] {generator} | finding arquivado\n\n"
        f"- [[{slug}]]\n"
    )
    log.write_text(head.rstrip() + "\n" + entry, encoding="utf-8")
