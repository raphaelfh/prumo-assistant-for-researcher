"""``archive_as_finding`` — cria ``<escopo>/notes/<slug>.md`` com ``type: finding``.

Extraído da prose inline do modo ``wiki query`` pra reuso pelo modo
``wiki study``. Pattern: YAML frontmatter (id, type, title, added,
status, tags, sources) + body com seções fixas. Atualiza ``_index.md`` e
``_log.md`` do PROJETO.

Não existe diretório ``findings/`` (nem ``docs/wiki/`` nem fallback
``docs/``): o finding é uma nota comum de ``notes/`` distinguida pelo
``type:`` do frontmatter (ADR-0023).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from prumo_assist.core import pj_layout


def archive_as_finding(
    *,
    scope: Path,
    slug: str,
    title: str,
    body: str,
    sources: list[str],
    date: str,
    tags: list[str] | None = None,
    generator: str = "wiki/query",
) -> Path:
    """Cria/sobrescreve ``<escopo>/notes/<slug>.md``, atualiza ``_index.md`` e ``_log.md``.

    ``body`` é texto markdown livre que vai abaixo do frontmatter.
    ``sources`` é lista de âncoras: citação Pandoc (``"[@key]"``) ou alvo de
    página (wikilink ``"[[page]]"`` ou link markdown ``"[texto](page.md)"``).
    ``generator`` identifica quem chamou (``"wiki/query"`` ou ``"wiki/study"``).

    Raises:
        PjRootNotFoundError: se ``scope`` não estiver dentro de um projeto
            com ``.claude/pj_config.toml`` (mensagem já traz `prumo init`).
    """
    pj_root = pj_layout.find_pj_root(scope)

    notes = pj_layout.notes_dir(scope)
    notes.mkdir(parents=True, exist_ok=True)
    finding_path = notes / f"{slug}.md"

    fm = {
        "id": slug,
        "type": "finding",
        "title": title,
        "added": date,
        "status": "active",
        "generator": generator,
        "tags": tags or [],
        "sources": sources,
    }
    yaml_block = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
    text = f"---\n{yaml_block}\n---\n\n# {title}\n\n{body.strip()}\n"
    finding_path.write_text(text, encoding="utf-8")

    _append_to_index(pj_root, slug, title)
    _append_to_log(pj_root, slug, generator, date)

    return finding_path


def _append_to_index(pj_root: Path, slug: str, title: str) -> None:
    """Adiciona linha ``- [[<slug>]] — <title>`` em § Findings do ``_index.md`` do projeto."""
    index = pj_root / "docs" / "_index.md"
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


def _append_to_log(pj_root: Path, slug: str, generator: str, date: str) -> None:
    """Anexa entrada a ``_log.md`` do projeto.

    O verbo é ``note`` — um dos aceitos pelo ``wiki lint`` (``LOG_PREFIX_RE``). O
    ``generator`` vai entre parênteses: gravá-lo no lugar do verbo fazia toda
    entrada de finding cair em ``broken_log_prefix``.
    """
    log = pj_root / "docs" / "_log.md"
    if not log.exists():
        log.write_text("# Log\n", encoding="utf-8")

    head = log.read_text(encoding="utf-8")
    entry = f"\n## [{date}] note | finding arquivado ({generator})\n\n- [[{slug}]]\n"
    log.write_text(head.rstrip() + "\n" + entry, encoding="utf-8")
