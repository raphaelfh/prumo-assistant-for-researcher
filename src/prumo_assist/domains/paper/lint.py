"""Auditoria de consistência da bibliografia.

Detecta problemas que quebram o pipeline de pesquisa:

- Citekeys no `.bib` sem nota correspondente em ``references/notes/``.
- Notas em ``references/notes/`` sem entrada no `.bib` (órfãs).
- Symlinks PDF quebrados (apontam pra arquivo inexistente).
- Notas sem ``id:`` no frontmatter (citekey desalinhado).
- Mais de uma nota com ``role: primary`` (deveria ter no máximo 1).

Tudo determinístico — sem LLM. ``prumo paper lint`` é seguro de rodar em CI.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from prumo_assist.core.bib import parse_bib
from prumo_assist.domains.paper.sync import read_nota_yaml


@dataclass(frozen=True)
class LintIssue:
    severity: str  # "error" | "warning"
    code: str
    message: str
    citekey: str | None = None


def lint(pj_path: Path) -> dict[str, Any]:
    """Roda todos os checks. Retorna ``{"issues": [...], "ok": bool, "summary": {...}}``."""
    issues: list[LintIssue] = []

    bib_path = pj_path / "references" / "_references.bib"
    notes_dir = pj_path / "references" / "notes"
    pdfs_dir = pj_path / "references" / "pdfs"

    if not bib_path.exists():
        issues.append(
            LintIssue("error", "bib_missing", f"{bib_path} não existe — Better BibTeX export?")
        )
        return _report(issues)

    bib_keys = {e.citekey for e in parse_bib(bib_path.read_text())}
    note_files = sorted(notes_dir.glob("*.md")) if notes_dir.exists() else []
    note_keys = {p.stem for p in note_files}

    # 1. Bib sem nota
    for ck in sorted(bib_keys - note_keys):
        issues.append(
            LintIssue(
                "warning",
                "bib_without_note",
                "citekey no .bib sem nota correspondente",
                citekey=ck,
            )
        )

    # 2. Nota sem bib (órfã)
    for ck in sorted(note_keys - bib_keys):
        issues.append(
            LintIssue(
                "warning",
                "orphan_note",
                "nota existe mas citekey não está no .bib",
                citekey=ck,
            )
        )

    # 3. id desalinhado
    for note in note_files:
        yaml_dict = read_nota_yaml(note)
        declared = yaml_dict.get("id")
        if declared and declared != note.stem:
            issues.append(
                LintIssue(
                    "error",
                    "id_mismatch",
                    f"id no YAML ('{declared}') ≠ filename ('{note.stem}')",
                    citekey=note.stem,
                )
            )

    # 4. Symlinks quebrados em pdfs/
    if pdfs_dir.exists():
        for link in sorted(pdfs_dir.glob("*.pdf")):
            if link.is_symlink():
                target = os.readlink(link)
                if not os.path.exists(target):
                    issues.append(
                        LintIssue(
                            "warning",
                            "broken_pdf_link",
                            f"symlink aponta pra arquivo inexistente: {target}",
                            citekey=link.stem,
                        )
                    )

    # 5. Mais de 1 primary
    primaries = [
        note.stem
        for note in note_files
        if (read_nota_yaml(note).get("role") or "").lower() == "primary"
    ]
    if len(primaries) > 1:
        for ck in primaries:
            issues.append(
                LintIssue(
                    "error",
                    "multiple_primaries",
                    f"role: primary aparece em {len(primaries)} notas (deveria ser ≤1)",
                    citekey=ck,
                )
            )

    return _report(issues)


def _report(issues: list[LintIssue]) -> dict[str, Any]:
    errors = sum(1 for i in issues if i.severity == "error")
    warnings = sum(1 for i in issues if i.severity == "warning")
    return {
        "ok": errors == 0,
        "summary": {"errors": errors, "warnings": warnings, "total": len(issues)},
        "issues": [asdict(i) for i in issues],
    }


def set_primary(pj_path: Path, citekey: str) -> dict[str, Any]:
    """Marca um paper como primary. Retorna report dos antes/depois.

    - Limpa ``role: primary`` de todos os outros papers (≤1 primary).
    - Seta ``role: primary`` no ``citekey`` alvo.
    - Cria a nota se não existir? **Não.** Falha com mensagem clara —
      o paper deve existir no `.bib` e ter passado por ``prumo paper sync``.
    """
    notes_dir = pj_path / "references" / "notes"
    target = notes_dir / f"{citekey}.md"
    if not target.exists():
        raise FileNotFoundError(
            f"{target} não existe — rode `prumo paper sync` antes de set-primary."
        )

    from prumo_assist.domains.paper.sync import FRONTMATTER_RE, write_nota

    cleared: list[str] = []
    for note in notes_dir.glob("*.md"):
        yaml_dict = read_nota_yaml(note)
        if (yaml_dict.get("role") or "").lower() != "primary":
            continue
        if note.stem == citekey:
            continue
        yaml_dict["role"] = ""
        text = note.read_text()
        m = FRONTMATTER_RE.match(text)
        body = text[m.end() :] if m else text
        write_nota(note, yaml_dict, body)
        cleared.append(note.stem)

    yaml_dict = read_nota_yaml(target)
    yaml_dict["role"] = "primary"
    text = target.read_text()
    m = FRONTMATTER_RE.match(text)
    body = text[m.end() :] if m else text
    write_nota(target, yaml_dict, body)

    return {"primary": citekey, "cleared_from": cleared}
