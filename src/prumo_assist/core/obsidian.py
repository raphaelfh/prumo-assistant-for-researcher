"""Normalizador Obsidian Markdown → Pandoc Markdown.

Transformado de ``monorepo-anterior/.claude/scripts/_obsidian_md.py`` sem mudança
de comportamento. Regras (ver spec sec. 4.2 do export pipeline):

- ``[[@key]]`` → ``[@key]``
- ``[[@key|alias]]`` → ``[@key]`` (alias descartado; CSL renderiza)
- ``[[file]]`` → ``file`` (texto plano)
- ``[[file|alias]]`` → ``alias``
- ``![[img.png]]`` → ``![](caminho_resolvido)`` (busca relativa)
- ``![[paper.pdf#page=N]]`` → ``""`` + warning (Pandoc não suporta)
- ``> [!tipo] [titulo]`` / ``> corpo`` → ``> **titulo**`` / ``> corpo``
- ``^anchor`` (block ID) → removido
- Code blocks, footnotes, tags: passthrough.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?\n?", re.DOTALL)
_CODE_FENCE_RE = re.compile(r"(```.*?\n.*?\n```)", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"(`[^`\n]+`)")

_CITATION_RE = re.compile(r"\[\[@([^\]\|]+)(?:\|[^\]]+)?\]\]")
_WIKILINK_RE = re.compile(r"\[\[([^\]\|@]+)(?:\|([^\]]+))?\]\]")
_IMAGE_EMBED_RE = re.compile(r"!\[\[([^\]]+)\]\]")
_BLOCK_ID_RE = re.compile(r"\s\^[A-Za-z0-9-]+\b")
_CALLOUT_HEADER_RE = re.compile(r"^>\s*\[!(\w+)\](?:\s+(.+))?\s*$")


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Separa YAML frontmatter do corpo. Retorna ``({}, body)`` se ausente."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta = yaml.safe_load(match.group(1)) or {}
    return meta, text[match.end() :]


def _protect_code(text: str) -> tuple[str, list[str]]:
    """Substitui blocos de código por placeholders e retorna mapa pra restaurar."""
    placeholders: list[str] = []

    def stash(m: re.Match[str]) -> str:
        placeholders.append(m.group(1))
        return f"\x00CODEBLOCK{len(placeholders) - 1}\x00"

    text = _CODE_FENCE_RE.sub(stash, text)
    text = _INLINE_CODE_RE.sub(stash, text)
    return text, placeholders


def _restore_code(text: str, placeholders: list[str]) -> str:
    for i, original in enumerate(placeholders):
        text = text.replace(f"\x00CODEBLOCK{i}\x00", original)
    return text


def _normalize_citations(text: str) -> str:
    return _CITATION_RE.sub(lambda m: f"[@{m.group(1)}]", text)


def _normalize_wikilinks(text: str) -> str:
    def replace(m: re.Match[str]) -> str:
        target, alias = m.group(1), m.group(2)
        return alias if alias else target

    return _WIKILINK_RE.sub(replace, text)


def _resolve_image(name: str, page_dir: Path | None) -> Path | None:
    if page_dir is None:
        return None
    direct = page_dir / name
    if direct.is_file():
        return direct
    parent = page_dir.parent
    for candidate in (
        parent / "references" / "pdfs" / name,
        parent.parent / "references" / "pdfs" / name,
    ):
        if candidate.is_file():
            return candidate
    return None


def _normalize_image_embeds(text: str, page_dir: Path | None) -> str:
    def replace(m: re.Match[str]) -> str:
        ref = m.group(1)
        if "#page=" in ref:
            logger.warning("Embed PDF com page âncora não suportado em export: %s", ref)
            return ""
        path = _resolve_image(ref, page_dir)
        if path is None:
            logger.warning("Imagem não encontrada: %s", ref)
            return f"![]({ref})"
        return f"![]({path})"

    return _IMAGE_EMBED_RE.sub(replace, text)


def _normalize_callouts(text: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        m = _CALLOUT_HEADER_RE.match(lines[i])
        if m:
            title = m.group(2)
            if title:
                out.append(f"> **{title.strip()}**")
            i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def normalize_markdown(text: str, page_dir: Path | None = None) -> str:
    """Aplica todas as regras de normalização Obsidian → Pandoc.

    Args:
        text: markdown Obsidian (sem frontmatter; chame ``split_frontmatter`` antes).
        page_dir: diretório da página-fonte para resolver embeds de imagem.
    """
    protected, placeholders = _protect_code(text)
    protected = _normalize_image_embeds(protected, page_dir)
    protected = _normalize_citations(protected)
    protected = _normalize_wikilinks(protected)
    protected = _normalize_callouts(protected)
    protected = _BLOCK_ID_RE.sub("", protected)
    return _restore_code(protected, placeholders)
