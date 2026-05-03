"""Migração one-shot do layout legado pro layout α.

Layout legado (antes de 0.4.0):
    references/notes/<key>.md  — arquivo único com YAML + body humano +
                                   callout paper-extract + bloco zotero annotations

Layout α (após):
    references/notes/<key>/
    ├── _meta.md         — YAML CSL-JSON + body humano
    ├── _extract.md      — callout paper-extract isolado (se existia)
    └── _annotations.md  — bloco zotero annotations isolado (se existia)

Idempotente: rodar duas vezes não faz mal — pasta já existe e arquivo legado some.
Preserva histórico via `git mv` quando o pj_* é repo git.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from prumo_assist.core.note_paths import annotations_path, extract_path, meta_path
from prumo_assist.domains.paper.sync import FRONTMATTER_RE

CALLOUT_RE = re.compile(
    r"<!--\s*paper-extract:begin\s*-->.*?<!--\s*paper-extract:end\s*-->",
    flags=re.DOTALL,
)
ZOTERO_BLOCK_RE = re.compile(
    r"(?:^##\s+Anotações do Zotero\s*\n+)?<!--\s*BEGIN ZOTERO ANNOTATIONS\s*-->.*?"
    r"<!--\s*END ZOTERO ANNOTATIONS\s*-->",
    flags=re.DOTALL | re.MULTILINE,
)


def _extract_callout_block(body: str) -> tuple[str, str | None]:
    """Remove o callout paper-extract do body. Retorna (body_sem_callout, callout_or_None)."""
    m = CALLOUT_RE.search(body)
    if not m:
        return body, None
    callout = m.group(0)
    cleaned = (body[: m.start()] + body[m.end() :]).strip()
    return cleaned, callout


def _extract_zotero_block(body: str) -> tuple[str, str | None]:
    """Remove o bloco ZOTERO ANNOTATIONS (e o heading ## Anotações do Zotero, se presente)."""
    m = ZOTERO_BLOCK_RE.search(body)
    if not m:
        return body, None
    block = m.group(0)
    # Remove o "## Anotações do Zotero" prefix do block guardado
    inner = re.sub(r"^##\s+Anotações do Zotero\s*\n+", "", block).strip()
    cleaned = (body[: m.start()] + body[m.end() :]).strip()
    return cleaned, inner


def _git_mv(src: Path, dst: Path, cwd: Path) -> bool:
    """Tenta git mv. Retorna True se sucedeu (preservou histórico)."""
    try:
        subprocess.run(
            ["git", "mv", str(src), str(dst)],
            check=True,
            capture_output=True,
            cwd=cwd,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def migrate_pj(pj_path: Path) -> dict[str, Any]:
    """Migra todas as notas legadas em ``pj_path/references/notes/`` pro layout α.

    Retorna report com chaves:
        migrated: list[str]            — citekeys migrados nesta execução
        already_migrated: list[str]    — citekeys já em layout α (puladas)
        warnings: list[str]            — situações inesperadas
    """
    notes_dir = pj_path / "references" / "notes"
    if not notes_dir.exists():
        return {"migrated": [], "already_migrated": [], "warnings": []}

    migrated: list[str] = []
    already_migrated: list[str] = []
    warnings: list[str] = []

    for child in sorted(notes_dir.iterdir()):
        # Layout α — pasta existe e tem _meta.md
        if child.is_dir() and (child / "_meta.md").is_file():
            already_migrated.append(child.name)
            continue
        # Layout legado — arquivo .md
        if not (child.is_file() and child.suffix == ".md"):
            continue

        citekey = child.stem
        text = child.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            warnings.append(f"{child.name}: sem frontmatter; pulado")
            continue

        frontmatter = text[: m.end()]
        body = text[m.end() :]

        body, zotero_block = _extract_zotero_block(body)
        body, callout = _extract_callout_block(body)

        # Cria pasta destino
        target_dir = notes_dir / citekey
        target_dir.mkdir(parents=True, exist_ok=True)

        # Tenta preservar histórico do arquivo principal via git mv pro _meta.md
        target_meta = meta_path(pj_path, citekey)
        if _git_mv(child, target_meta, cwd=pj_path):
            # Após mv, sobrescreve com conteúdo limpo (sem callout/zotero)
            target_meta.write_text(frontmatter + body.strip() + "\n", encoding="utf-8")
        else:
            # Fallback: write + delete
            target_meta.write_text(frontmatter + body.strip() + "\n", encoding="utf-8")
            child.unlink()

        if callout:
            extract_text = (
                f"---\n"
                f"paper: {citekey}\n"
                f"source: prumo-paper-extract\n"
                f"---\n\n"
                f"{callout}\n"
            )
            extract_path(pj_path, citekey).write_text(extract_text, encoding="utf-8")

        if zotero_block:
            annot_text = (
                f"---\n"
                f"paper: {citekey}\n"
                f"source: prumo-zotero-annotations\n"
                f"---\n\n"
                f"{zotero_block}\n"
            )
            annotations_path(pj_path, citekey).write_text(annot_text, encoding="utf-8")

        migrated.append(citekey)

    return {
        "migrated": sorted(migrated),
        "already_migrated": sorted(already_migrated),
        "warnings": warnings,
    }
