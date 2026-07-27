"""Sincroniza ``references/_references.bib`` → ``references/notes/<key>/_meta.md`` (layout α).

Migrado de ``monorepo-anterior/.claude/scripts/paper_sync.py``. Comportamento
preservado; mudanças exclusivamente de packaging:

- Imports relativos (``from prumo_assist.core.bib import ...``).
- ``FRONTMATTER_RE``, ``read_nota_yaml``, ``write_nota`` reexportados aqui pois
  ``graph``, ``find`` e ``callout`` dependem deles.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path
from typing import Any

import yaml

from prumo_assist.core.bib import BibEntry, extract_field, extract_year, parse_bib

METADATA_FIELDS = {
    "id",
    "type",
    "title",
    "author",
    "issued",
    "DOI",
    "container-title",
    "URL",
    "pdf",
}
EXTRACTED_FIELDS = {"extracted_at", "extracted_model", "extracted_template_hash"}

# Mapeamento BBT entry type → CSL-JSON type
TYPE_MAP = {
    "article": "article-journal",
    "inproceedings": "paper-conference",
    "incollection": "chapter",
    "book": "book",
    "misc": "manuscript",
    "unpublished": "manuscript",
    "techreport": "report",
}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def bib_entry_to_metadata(entry: BibEntry) -> dict[str, Any]:
    """Converte ``BibEntry`` → dict com campos metadata-only para YAML da nota."""
    body = entry.body
    title = (extract_field(body, "title") or "").strip()
    year_raw = extract_year(body)
    year: int | None = int(year_raw) if year_raw else None
    doi = (extract_field(body, "doi") or "").strip()
    url = (extract_field(body, "url") or "").strip()
    # `journal` é o dialeto Better BibTeX; `journaltitle`, o Better BibLaTeX (que
    # nunca emite `journal`). Nunca coexistem. `shortjournal` fica de fora de
    # propósito: é abreviação ("JAMA Oncol."), não o título do container.
    container = (
        extract_field(body, "journal")
        or extract_field(body, "journaltitle")
        or extract_field(body, "booktitle")
        or extract_field(body, "publisher")
        or ""
    ).strip()
    author_raw = extract_field(body, "author") or ""
    authors = _parse_authors(author_raw)

    return {
        "id": entry.citekey,
        "type": TYPE_MAP.get(entry.entry_type, "article-journal"),
        "title": title,
        "author": authors,
        "issued": {"date-parts": [[year]]} if year else {"date-parts": [[None]]},
        "DOI": doi,
        "container-title": container,
        "URL": url,
        "pdf": f"../../pdfs/{entry.citekey}.pdf",
    }


def _parse_authors(raw: str) -> list[dict[str, str]]:
    """BBT author field: ``'Smith, Jane and Doe, John'`` → ``[{family, given}, ...]``."""
    out: list[dict[str, str]] = []
    for chunk_raw in re.split(r"\s+and\s+", raw):
        chunk = chunk_raw.strip()
        if not chunk:
            continue
        if "," in chunk:
            family, given = chunk.split(",", 1)
            out.append({"family": family.strip(), "given": given.strip()})
        else:
            parts = chunk.split()
            if len(parts) >= 2:
                out.append({"family": parts[-1], "given": " ".join(parts[:-1])})
            else:
                out.append({"family": chunk, "given": ""})
    return out


def merge_nota_yaml(
    existing: dict[str, Any],
    new_metadata: dict[str, Any],
    today: str | None = None,
) -> dict[str, Any]:
    """Merge rules:

    - ``METADATA_FIELDS``: sobrescreve com ``new_metadata``.
    - ``EXTRACTED_FIELDS``: nunca toca.
    - ``added``: preserva se existe; senão seta ``today`` (default = hoje).
    - Outros campos (curadoria): preserva ``existing``.
    """
    merged: dict[str, Any] = dict(existing)
    for k, v in new_metadata.items():
        if k in METADATA_FIELDS:
            merged[k] = v
    if not merged.get("added"):
        merged["added"] = today or _dt.date.today().isoformat()
    for f in EXTRACTED_FIELDS:
        merged.setdefault(f, None)
    return merged


def read_nota_yaml(path: Path) -> dict[str, Any]:
    """Lê frontmatter YAML da nota. Retorna ``{}`` se não houver."""
    text = path.read_text()
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    parsed = yaml.safe_load(m.group(1)) or {}
    return parsed if isinstance(parsed, dict) else {}


class _NotaDumper(yaml.SafeDumper):
    """Dumper customizado: representa string vazia como ``""`` literal.

    Necessário pra round-trip de templates onde o autor mantém ``tldr: ""``
    como placeholder editável."""


def _str_representer(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    style = '"' if data == "" else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_NotaDumper.add_representer(str, _str_representer)


def write_nota(path: Path, yaml_dict: dict[str, Any], body: str) -> None:
    """Escreve nota: ``frontmatter(yaml_dict) + body``."""
    fm = yaml.dump(yaml_dict, Dumper=_NotaDumper, sort_keys=False, allow_unicode=True)
    path.write_text(f"---\n{fm}---\n{body}")


def _dump_minimal_yaml(d: dict[str, Any]) -> str:
    """Dump YAML mínimo (fallback didático; PyYAML é o caminho normal)."""
    lines: list[str] = []
    for k, v in d.items():
        if v is None:
            lines.append(f"{k}: null")
        elif isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            elif all(isinstance(x, str) for x in v):
                lines.append(f"{k}:")
                lines.extend(f'  - "{x}"' for x in v)
            else:
                lines.append(f"{k}:")
                for item in v:
                    if isinstance(item, dict):
                        parts = [f'{ik}: "{iv}"' for ik, iv in item.items()]
                        lines.append(f"  - {{ {', '.join(parts)} }}")
                    else:
                        lines.append(f"  - {item}")
        elif isinstance(v, dict):
            lines.append(f"{k}: {json.dumps(v)}")
        elif isinstance(v, str):
            lines.append(f'{k}: "{v}"')
        else:
            lines.append(f"{k}: {v}")
    return "\n".join(lines) + "\n"


def _template_body(pj_path: Path) -> str:
    """Retorna o body (pós-frontmatter) do ``literature_note.md`` template."""
    tpl = pj_path / "references" / "templates" / "literature_note.md"
    if not tpl.exists():
        return ""
    text = tpl.read_text()
    m = FRONTMATTER_RE.match(text)
    return text[m.end() :] if m else text


def _template_yaml_defaults(pj_path: Path) -> dict[str, Any]:
    """Lê YAML frontmatter do template como defaults de curadoria.

    Retorna apenas campos que NÃO são ``METADATA_FIELDS``, ``EXTRACTED_FIELDS``
    nem ``added`` — esses ficam pra ser preenchidos pelo merge."""
    tpl = pj_path / "references" / "templates" / "literature_note.md"
    if not tpl.exists():
        return {}
    text = tpl.read_text()
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    parsed = yaml.safe_load(m.group(1)) or {}
    if not isinstance(parsed, dict):
        return {}
    return {
        k: v
        for k, v in parsed.items()
        if k not in METADATA_FIELDS and k not in EXTRACTED_FIELDS and k != "added"
    }


def sync(pj_path: Path) -> dict[str, Any]:
    """Sync ``.bib`` → ``<key>/_meta.md``. Retorna report com ``created``, ``updated``, ``orphans``."""
    from prumo_assist.core.note_paths import meta_path

    bib = pj_path / "references" / "_references.bib"
    notes_dir = pj_path / "references" / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    if not bib.exists():
        raise FileNotFoundError(f"{bib} não encontrado. Rode o auto-export do Better BibTeX.")

    entries = parse_bib(bib.read_text())
    bib_keys = {e.citekey for e in entries}

    created, updated = 0, 0
    template_body = _template_body(pj_path)
    tpl_defaults = _template_yaml_defaults(pj_path)

    for entry in entries:
        meta = bib_entry_to_metadata(entry)
        nota = meta_path(pj_path, entry.citekey)
        nota.parent.mkdir(parents=True, exist_ok=True)
        if nota.exists():
            existing = read_nota_yaml(nota)
            merged = merge_nota_yaml(existing, meta)
            current_text = nota.read_text()
            m = FRONTMATTER_RE.match(current_text)
            body = current_text[m.end() :] if m else current_text
            if merged != existing:
                write_nota(nota, merged, body)
                updated += 1
        else:
            merged = merge_nota_yaml(tpl_defaults, meta)
            write_nota(nota, merged, template_body)
            created += 1

    orphan_keys: list[str] = []
    for child in notes_dir.iterdir():
        # Subdir layout α: pasta com _meta.md
        if child.is_dir() and (child / "_meta.md").is_file():
            if child.name not in bib_keys:
                orphan_keys.append(child.name)
        # Legado: arquivo único <key>.md (suportado em transição)
        elif child.is_file() and child.suffix == ".md" and child.stem not in bib_keys:
            orphan_keys.append(child.stem)
    return {"created": created, "updated": updated, "orphans": sorted(orphan_keys)}
